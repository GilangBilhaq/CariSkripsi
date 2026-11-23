"""API publik (tanpa login): pencarian, mode Bandingkan, detail dokumen, dan statistik."""

import math
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import config
from app.api.deps import get_active_index, get_index_manager, get_semantic_index, get_session, require_semantic
from app.api.serializers import document_full, document_summary, highlighted
from app.models import Document, SearchLog
from app.search.highlight import highlight_full, make_snippet, query_terms
from app.search.index_manager import IndexBundle, IndexManager
from app.search.service import Hit, SearchFilters, compare, rank, similar_documents

router = APIRouter(tags=["publik"])


def clean_query(q: str) -> str:
    """Rapikan kueri dan tolak kueri kosong/terlalu pendek dengan pesan ramah (PRD FR-11)."""
    q = " ".join(q.split())
    if not q:
        raise HTTPException(422, "Ketik kata kunci atau topik penelitian terlebih dahulu.")
    if len(q) < config.MIN_QUERY_CHARS:
        raise HTTPException(422, f"Kueri terlalu pendek. Ketik minimal {config.MIN_QUERY_CHARS} karakter.")
    return q[:300]


def load_documents(session: Session, hits: list[Hit]) -> list[tuple[Hit, Document]]:
    """Ambil dokumen untuk setiap hit, urutan dipertahankan. Dokumen yang sudah dihapus dilewati."""
    docs = {d.id: d for d in session.scalars(select(Document).where(Document.id.in_([h.doc_id for h in hits])))}
    return [(h, docs[h.doc_id]) for h in hits if h.doc_id in docs]


def result_item(hit: Hit, doc: Document, terms: set[str]) -> dict:
    return document_summary(doc) | {
        "rank": hit.rank,
        "score": round(hit.score, 4),
        "judul_sorot": highlighted(highlight_full(doc.judul_id or doc.judul_asli, terms)),
        "cuplikan": highlighted(make_snippet(doc.abstrak_id or doc.abstrak_asli, terms)),
    }


def log_search(session: Session, query: str, method: str, count: int, took_ms: float) -> None:
    session.add(SearchLog(kueri=query[:500], metode=method, jumlah_hasil=count, waktu_ms=round(took_ms, 2)))
    session.commit()


@router.get("/stats")
def public_stats(session: Session = Depends(get_session), manager: IndexManager = Depends(get_index_manager)):
    """Angka untuk beranda dan footer: jumlah dokumen terindeks, tahun tersedia, model yang dipakai."""
    manager.sync_with_database()
    years = session.execute(select(Document.tahun, func.count()).where(Document.tahun.is_not(None))
                            .group_by(Document.tahun).order_by(Document.tahun.desc())).all()
    bundle = manager.active
    return {
        "dokumen_terindeks": bundle.size if bundle else 0,
        "dokumen_total": session.scalar(select(func.count(Document.id))),
        "tahun": [{"tahun": y, "jumlah": n} for y, n in years],
        "indeks_versi": bundle.versi if bundle else None,
        "semantik_siap": bool(bundle and bundle.has_semantic),  # False = baru BM25 (embedding masih dihitung)
        "model_sbert": config.SBERT_MODEL,
        "bm25_params": {"k1": config.BM25_K1, "b": config.BM25_B},
    }


@router.get("/search")
def search(
    q: str = Query("", description="Kueri pencarian"),
    method: Literal["bm25", "sbert"] = "bm25",
    page: int = Query(1, ge=1),
    year_from: int | None = None,
    year_to: int | None = None,
    lang: Literal["id", "en"] | None = None,
    has_abstract: bool | None = None,
    session: Session = Depends(get_session),
    bundle: IndexBundle = Depends(get_active_index),
    manager: IndexManager = Depends(get_index_manager),
):
    query = clean_query(q)
    if method == "sbert":
        require_semantic(bundle)
    filters = SearchFilters(year_from, year_to, lang, has_abstract)
    ranking = rank(bundle, manager.encoder, method, query, filters, limit=config.MAX_RESULTS)
    if page == 1:
        log_search(session, query, method, len(ranking.hits), ranking.took_ms)

    terms = query_terms(query)
    start = (page - 1) * config.PAGE_SIZE
    page_hits = load_documents(session, ranking.hits[start:start + config.PAGE_SIZE])
    results = []
    for hit, doc in page_hits:
        item = result_item(hit, doc, terms)
        if method == "bm25":
            item["frekuensi_kata"] = bundle.bm25.term_frequency(hit.position, ranking.query_terms)
        results.append(item)

    return {
        "query": query,
        "method": method,
        "total_cocok": ranking.total_matches,  # BM25: dokumen berskor > 0. IndoSBERT: semua dokumen.
        "total": len(ranking.hits),  # yang ditampilkan (maksimal MAX_RESULTS)
        "page": page,
        "pages": max(1, math.ceil(len(ranking.hits) / config.PAGE_SIZE)),
        "page_size": config.PAGE_SIZE,
        "took_ms": round(ranking.took_ms, 1),
        "results": results,
    }


@router.get("/compare")
def compare_methods(
    q: str = "",
    session: Session = Depends(get_session),
    bundle: IndexBundle = Depends(get_semantic_index),
    manager: IndexManager = Depends(get_index_manager),
):
    query = clean_query(q)
    result = compare(bundle, manager.encoder, query, top_k=config.COMPARE_TOP_K)
    log_search(session, query, "compare", len(result.overlap_ids),
               result.bm25.took_ms + result.sbert.took_ms)
    terms = query_terms(query)
    rank_in = {
        "bm25": {h.doc_id: h.rank for h in result.bm25.hits},
        "sbert": {h.doc_id: h.rank for h in result.sbert.hits},
    }

    def column(method: str, other: str) -> dict:
        ranking = getattr(result, method)
        items = []
        for hit, doc in load_documents(session, ranking.hits):
            item = result_item(hit, doc, terms)
            item["peringkat_di_lawan"] = rank_in[other].get(doc.id)  # None = tidak beririsan
            if method == "bm25":
                item["frekuensi_kata"] = bundle.bm25.term_frequency(hit.position, ranking.query_terms)
            items.append(item)
        return {"took_ms": round(ranking.took_ms, 1), "total_cocok": ranking.total_matches, "results": items}

    return {
        "query": query,
        "top_k": config.COMPARE_TOP_K,
        "jumlah_irisan": len(result.overlap_ids),
        "rasio_irisan": round(result.overlap_ratio, 3),
        "bm25": column("bm25", "sbert"),
        "sbert": column("sbert", "bm25"),
        "model_sbert": bundle.meta.get("model_name"),
    }


@router.get("/documents/{doc_id}")
def document_detail(
    doc_id: int,
    session: Session = Depends(get_session),
    manager: IndexManager = Depends(get_index_manager),
):
    doc = session.get(Document, doc_id)
    if doc is None:
        raise HTTPException(404, "Dokumen tidak ditemukan.")
    similar = []
    if manager.active is not None:
        for hit, other in load_documents(session, similar_documents(manager.active, doc_id, limit=3)):
            similar.append(document_summary(other) | {
                "skor": round(hit.score, 4),
                "cuplikan": (other.abstrak_id or other.abstrak_asli or "")[:260],
            })
    return document_full(doc) | {"serupa": similar, "terindeks": not doc.perlu_indeks}


# Hasil evaluasi sengaja TIDAK disediakan di API publik: hanya admin yang boleh melihatnya
# (lihat /api/admin/eval/runs di admin_eval.py).
