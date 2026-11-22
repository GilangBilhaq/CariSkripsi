import numpy as np
from sqlalchemy import select

from app.models import Document, IndexVersion
from app.search.highlight import make_snippet, query_terms
from app.search.index_manager import IndexBundle, IndexManager
from app.search.preprocess import analyze
from app.search.service import SearchFilters, compare, rank, similar_documents, top_positions


def titles(session, ranking):
    return [session.get(Document, h.doc_id).judul_asli for h in ranking.hits]


def test_analyze_removes_stopwords_and_stems():
    assert analyze("Pengaruh pembangkit listrik di desa-desa") == ["pengaruh", "bangkit", "listrik", "desa", "desa"]
    assert analyze("COVID-19 pada 2024") == ["covid", "19", "2024"]


def test_bm25_ranks_matching_documents_first(index_manager, session):
    r = rank(index_manager.active, index_manager.encoder, "bm25", "energi biomassa")
    found = titles(session, r)
    assert found[0].startswith("Pemanfaatan Energi Biomassa")
    assert all(h.score > 0 for h in r.hits)
    assert r.total_matches == len(r.hits) == 3  # dua dokumen biomassa + satu dokumen 'energi' tanpa abstrak
    assert [h.rank for h in r.hits] == [1, 2, 3]
    assert r.took_ms >= 0


def test_bm25_no_match_returns_empty(index_manager):
    r = rank(index_manager.active, index_manager.encoder, "bm25", "kriptografi kuantum")
    assert r.hits == [] and r.total_matches == 0


def test_document_without_abstract_found_by_title(index_manager, session):
    r = rank(index_manager.active, index_manager.encoder, "bm25", "kebijakan daerah")
    assert titles(session, r) == ["Analisis Kebijakan Energi Daerah"]


def test_semantic_finds_paraphrase_without_shared_words(index_manager, session):
    # 'tertekan' dan 'bidan' tidak muncul di kueri, tetapi encoder palsu memetakannya sebagai sinonim.
    r = rank(index_manager.active, index_manager.encoder, "sbert", "stres perawat", limit=2)
    assert set(titles(session, r)) == {"Hubungan Beban Kerja dengan Stres Kerja Perawat",
                                       "Perasaan Tertekan pada Bidan di Puskesmas"}


def test_filters(index_manager, session):
    bundle, enc = index_manager.active, index_manager.encoder
    r = rank(bundle, enc, "sbert", "energi", SearchFilters(year_from=2025))
    assert {session.get(Document, h.doc_id).tahun for h in r.hits} == {2025, 2026}
    r = rank(bundle, enc, "sbert", "energi", SearchFilters(language="en"))
    assert titles(session, r) == ["Perasaan Tertekan pada Bidan di Puskesmas"]
    r = rank(bundle, enc, "sbert", "energi", SearchFilters(has_abstract=False))
    assert titles(session, r) == ["Analisis Kebijakan Energi Daerah"]
    r = rank(bundle, enc, "sbert", "energi", SearchFilters(year_to=2023))  # tahun kosong tidak ikut
    assert titles(session, r) == ["Briket Biomassa dari Tongkol Jagung"]


def test_compare_overlap(index_manager):
    c = compare(index_manager.active, index_manager.encoder, "energi biomassa", top_k=3)
    bm25_ids = [h.doc_id for h in c.bm25.hits]
    sbert_ids = [h.doc_id for h in c.sbert.hits]
    assert c.overlap_ids == set(bm25_ids) & set(sbert_ids)
    assert c.overlap_ratio == len(c.overlap_ids) / 3


def test_similar_documents_excludes_itself(index_manager, sample_docs):
    doc_id = sample_docs[0].id
    similar = similar_documents(index_manager.active, doc_id, limit=3)
    assert len(similar) == 3 and doc_id not in [h.doc_id for h in similar]
    assert similar[0].doc_id == sample_docs[1].id  # dokumen biomassa lain paling mirip
    assert similar_documents(index_manager.active, 99999) == []


def test_top_positions_is_deterministic_on_ties():
    scores = np.array([1.0, 2.0, 2.0, 0.5])
    assert top_positions(scores, np.arange(4), 3).tolist() == [1, 2, 0]


def test_snippet_highlights_stemmed_matches():
    text = "Penelitian ini membahas pembangkit listrik tenaga biomassa di pedesaan Jember."
    s = make_snippet(text, query_terms("membangkitkan listrik"))
    marked = [s.text[a:b] for a, b in s.highlights]
    assert marked == ["pembangkit", "listrik"]


def test_snippet_starts_near_first_match():
    text = ("Kalimat pembuka yang panjang sekali. " * 10) + "Bagian penting tentang biomassa ada di sini."
    s = make_snippet(text, query_terms("biomassa"), max_chars=120)
    assert s.text.startswith("…") and "biomassa" in s.text
    a, b = s.highlights[0]
    assert s.text[a:b] == "biomassa"


def test_rebuild_marks_documents_indexed_and_saves_version(index_manager, session):
    assert session.scalar(select(Document).where(Document.perlu_indeks.is_(True))) is None
    version = session.scalar(select(IndexVersion).where(IndexVersion.status == "active"))
    assert version.jumlah_dokumen == 6 and version.persen == 100
    reloaded = IndexBundle.load(index_manager.index_dir / version.versi)
    assert reloaded.size == 6
    np.testing.assert_allclose(reloaded.embeddings, index_manager.active.embeddings)


def test_only_one_build_across_processes(index_manager, session_factory, session):
    """Manajer kedua (mewakili proses lain, mis. CLI) tidak boleh membangun selama kunci dipegang."""
    from tests.conftest import FakeEncoder

    other = IndexManager(session_factory, index_dir=index_manager.index_dir, encoder=FakeEncoder(), store=None)
    assert other._process_lock.acquire()
    try:
        assert index_manager.is_building
        assert index_manager.start_rebuild_in_background() is False
        # Saat server mulai, build milik proses lain yang masih hidup TIDAK ditandai gagal.
        session.add(IndexVersion(versi="sedang-jalan", status="building", model_name="x", bm25_params={}))
        session.commit()
        index_manager.load_active()
        assert session.scalar(select(IndexVersion.status).where(IndexVersion.versi == "sedang-jalan")) == "building"
    finally:
        other._process_lock.release()
    index_manager.load_active()  # kunci sudah lepas -> sisa build dianggap terputus
    session.expire_all()
    assert session.scalar(select(IndexVersion.status).where(IndexVersion.versi == "sedang-jalan")) == "failed"


def test_server_picks_up_index_built_elsewhere(index_manager, session_factory):
    from tests.conftest import FakeEncoder

    server = IndexManager(session_factory, index_dir=index_manager.index_dir, encoder=FakeEncoder(), store=None)
    server.load_active()
    old = server.active.versi
    index_manager.rebuild_now(translate=False)  # "CLI" membangun versi baru
    server.sync_with_database(force=True)
    assert server.active.versi != old and server.active.versi == index_manager.active.versi


def test_first_build_activates_bm25_before_embeddings(session_factory, sample_docs, tmp_path):
    """Pembangunan pertama: pencarian BM25 sudah bisa dipakai selama embedding masih dihitung."""
    from tests.conftest import FakeEncoder

    seen_during_embedding = []

    class WatchingEncoder(FakeEncoder):
        def encode_documents(self, texts):
            seen_during_embedding.append(manager.active)
            return super().encode_documents(texts)

    manager = IndexManager(session_factory, index_dir=tmp_path / "index", encoder=WatchingEncoder(), store=None)
    manager.rebuild_now(translate=False)

    provisional = seen_during_embedding[0]
    assert provisional is not None and not provisional.has_semantic
    assert rank(provisional, manager.encoder, "bm25", "energi biomassa").hits  # BM25 sudah jalan
    assert similar_documents(provisional, sample_docs[0].id) == []
    assert manager.active.has_semantic  # setelah selesai: indeks lengkap


def test_rebuild_reuses_cached_embeddings(index_manager, session):
    calls = []
    original = index_manager.encoder.encode_documents
    index_manager.encoder.encode_documents = lambda texts: calls.append(len(texts)) or original(texts)

    doc = session.scalars(select(Document)).first()
    doc.abstrak_id = "Teks abstrak yang diubah tentang irigasi sawah."
    session.commit()
    index_manager.rebuild_now(translate=False)
    assert calls == [1]  # hanya dokumen yang berubah yang di-encode ulang
    r = rank(index_manager.active, index_manager.encoder, "bm25", "irigasi sawah")
    assert r.hits[0].doc_id == doc.id
