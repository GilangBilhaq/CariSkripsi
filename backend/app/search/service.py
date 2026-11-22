"""Logika pencarian: menghitung skor, menerapkan filter, dan mengambil peringkat teratas.

Fungsi di sini hanya bekerja dengan indeks di memori (posisi dokumen + skor). Mengambil isi dokumen dari
database dan membentuk respons JSON dilakukan di app/api/public.py.
"""

import time
from dataclasses import dataclass
from typing import Literal

import numpy as np

from app.search.index_manager import IndexBundle
from app.search.preprocess import analyze
from app.search.semantic import SemanticEncoder

Method = Literal["bm25", "sbert"]


@dataclass
class SearchFilters:
    year_from: int | None = None
    year_to: int | None = None
    language: str | None = None  # 'id' | 'en' (bahasa asli dokumen)
    has_abstract: bool | None = None

    def mask(self, bundle: IndexBundle) -> np.ndarray | None:
        """Array boolean dokumen yang lolos filter, atau None bila tidak ada filter."""
        mask = np.ones(bundle.size, dtype=bool)
        if self.year_from is not None:
            mask &= bundle.years >= self.year_from
        if self.year_to is not None:
            mask &= (bundle.years <= self.year_to) & (bundle.years > 0)
        if self.language:
            mask &= bundle.languages == self.language
        if self.has_abstract is not None:
            mask &= bundle.has_abstract == self.has_abstract
        return None if mask.all() else mask


@dataclass
class Hit:
    doc_id: int
    position: int  # baris di indeks
    score: float
    rank: int  # 1 = teratas


@dataclass
class Ranking:
    hits: list[Hit]
    total_matches: int  # BM25: dokumen dengan skor > 0. IndoSBERT: semua dokumen (selalu punya skor).
    took_ms: float
    query_terms: list[str]  # term BM25 kueri (setelah stopword + stemming)


def score_all(bundle: IndexBundle, encoder: SemanticEncoder, method: Method, query: str) -> np.ndarray:
    if method == "bm25":
        return bundle.bm25.scores(analyze(query))
    if not bundle.has_semantic:
        raise ValueError("Indeks ini belum punya embedding IndoSBERT")  # API memeriksa ini lebih dulu (503)
    return bundle.embeddings @ encoder.encode_query(query)  # cosine similarity (vektor sudah dinormalisasi)


def top_positions(scores: np.ndarray, candidates: np.ndarray, limit: int) -> np.ndarray:
    """Posisi `limit` skor tertinggi di antara `candidates`, terurut menurun.

    Skor sama diurutkan menurut posisi (id dokumen lebih kecil dulu) supaya hasilnya deterministik.
    """
    if candidates.size == 0:
        return candidates
    if candidates.size > limit:
        part = np.argpartition(-scores[candidates], limit - 1)[:limit]
        candidates = candidates[part]
    order = np.lexsort((candidates, -scores[candidates]))
    return candidates[order]


def rank(bundle: IndexBundle, encoder: SemanticEncoder, method: Method, query: str,
         filters: SearchFilters | None = None, limit: int = 50) -> Ranking:
    started = time.perf_counter()
    scores = score_all(bundle, encoder, method, query)

    keep = scores > 0 if method == "bm25" else np.ones(bundle.size, dtype=bool)
    mask = filters.mask(bundle) if filters else None
    if mask is not None:
        keep &= mask
    candidates = np.flatnonzero(keep)
    best = top_positions(scores, candidates, limit)
    took_ms = (time.perf_counter() - started) * 1000

    hits = [Hit(int(bundle.doc_ids[p]), int(p), float(scores[p]), i + 1) for i, p in enumerate(best)]
    return Ranking(hits, int(candidates.size), took_ms, analyze(query))


@dataclass
class Comparison:
    bm25: Ranking
    sbert: Ranking
    overlap_ids: set[int]

    @property
    def overlap_ratio(self) -> float:
        """Proporsi dokumen teratas yang muncul di kedua kolom (dasar: kolom yang lebih panjang)."""
        size = max(len(self.bm25.hits), len(self.sbert.hits))
        return len(self.overlap_ids) / size if size else 0.0


def compare(bundle: IndexBundle, encoder: SemanticEncoder, query: str, top_k: int = 10) -> Comparison:
    bm25 = rank(bundle, encoder, "bm25", query, limit=top_k)
    sbert = rank(bundle, encoder, "sbert", query, limit=top_k)
    overlap = {h.doc_id for h in bm25.hits} & {h.doc_id for h in sbert.hits}
    return Comparison(bm25, sbert, overlap)


def similar_documents(bundle: IndexBundle, doc_id: int, limit: int = 5) -> list[Hit]:
    """Dokumen dengan embedding paling mirip (PRD FR-10). Kosong bila dokumen belum masuk indeks."""
    position = bundle.position_of.get(doc_id)
    if position is None or not bundle.has_semantic:
        return []
    scores = bundle.embeddings @ bundle.embeddings[position]
    candidates = np.flatnonzero(np.arange(bundle.size) != position)
    best = top_positions(scores, candidates, limit)
    return [Hit(int(bundle.doc_ids[p]), int(p), float(scores[p]), i + 1) for i, p in enumerate(best)]
