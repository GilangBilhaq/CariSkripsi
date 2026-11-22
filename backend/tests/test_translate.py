import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.data.translate import clean_output, count_pending, normalize_source, split_sentences, translate_pending
from app.db import init_db
from app.models import Document


def test_normalize_source_replaces_curly_quotes_and_dashes():
    assert normalize_source("the novel “Sang Keris” – it’s") == "the novel \"Sang Keris\" - it's"


def test_clean_output_joins_reduplication_only():
    assert clean_output("Pada tahun - tahun ini negara - negara Asia") == "Pada tahun-tahun ini negara-negara Asia"
    assert clean_output("bermacam - macam") == "bermacam - macam"  # beda awalan: biarkan
    assert clean_output("Jember - Indonesia") == "Jember - Indonesia"


def test_split_sentences_basic_and_abbreviations():
    text = (
        "This study analyzes data from Jember. The results by Smith et al. show a 4.5% increase! "
        "Samples (e.g. leaves) were taken. Was it significant? Yes."
    )
    assert split_sentences(text) == [
        "This study analyzes data from Jember.",
        "The results by Smith et al. show a 4.5% increase!",
        "Samples (e.g. leaves) were taken.",
        "Was it significant?",
        "Yes.",
    ]


def test_split_sentences_keeps_initials_and_splits_very_long():
    assert split_sentences("Interviews with J. Smith were held. Next step.") == [
        "Interviews with J. Smith were held.", "Next step."]
    long = "; ".join(["clause number %d with some words" % i for i in range(40)]) + "."
    parts = split_sentences(long)
    assert len(parts) == 40 and all(len(p) < 700 for p in parts)


def fake_translate(calls):
    def tr(sentences):
        calls.append(list(sentences))
        return [f"ID[{s}]" for s in sentences]
    return tr


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    init_db(engine)
    with Session(engine) as s:
        common = dict(tahun=2025, abstrak_tersedia=True, perlu_indeks=False)
        s.add_all([
            # judul ID + abstrak EN -> hanya abstrak yang diterjemahkan
            Document(link="a", judul_asli="Judul Indonesia", judul_id="Judul Indonesia",
                     abstrak_asli="First sentence. Second sentence.", bahasa_judul="id", bahasa_asli="en", **common),
            # judul EN + abstrak EN
            Document(link="b", judul_asli="English Title", abstrak_asli="Only one.",
                     bahasa_judul="en", bahasa_asli="en", **common),
            # sudah Indonesia -> tidak tersentuh
            Document(link="c", judul_asli="Judul", judul_id="Judul", abstrak_asli="Abstrak.", abstrak_id="Abstrak.",
                     bahasa_judul="id", bahasa_asli="id", **common),
            # judul EN tanpa abstrak
            Document(link="d", judul_asli="Another Title", abstrak_asli=None, bahasa_judul="en", bahasa_asli="en",
                     tahun=2025, abstrak_tersedia=False, perlu_indeks=False),
        ])
        s.commit()
        yield s


def get(s, link):
    return s.scalar(select(Document).where(Document.link == link))


def test_translate_pending_only_english_fields(session):
    calls = []
    assert count_pending(session) == 3
    stats = translate_pending(session, fake_translate(calls), docs_per_batch=10)

    assert stats.documents == 3 and stats.titles == 2 and stats.abstracts == 2 and stats.sentences == 5
    assert len(calls) == 1  # semua kalimat dalam satu panggilan model
    a, b, c, d = (get(session, k) for k in "abcd")
    assert a.judul_id == "Judul Indonesia"
    assert a.abstrak_id == "ID[First sentence.] ID[Second sentence.]"
    assert b.judul_id == "ID[English Title]" and b.abstrak_id == "ID[Only one.]"
    assert d.judul_id == "ID[Another Title]" and d.abstrak_id is None
    assert c.abstrak_id == "Abstrak." and c.perlu_indeks is False
    assert a.perlu_indeks and b.perlu_indeks and d.perlu_indeks
    assert count_pending(session) == 0


def test_translate_pending_is_resumable_and_dry_run(session):
    calls = []
    translate_pending(session, fake_translate(calls), limit=1, commit=False)
    assert count_pending(session) == 3  # dry run tidak menyimpan

    translate_pending(session, fake_translate(calls), limit=1)
    assert count_pending(session) == 2
    stats = translate_pending(session, fake_translate(calls))
    assert stats.documents == 2 and count_pending(session) == 0
