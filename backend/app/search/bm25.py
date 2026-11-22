"""Indeks BM25 (Okapi) memakai pustaka rank_bm25.

Skor BM25 dokumen d untuk kueri q:

    sum_{t in q}  IDF(t) * f(t,d) * (k1 + 1) / ( f(t,d) + k1 * (1 - b + b * |d| / avgdl) )

f(t,d) = frekuensi term t di d, |d| = panjang dokumen (jumlah term), avgdl = rata-rata panjang dokumen.
Parameter default k1 = 1,5 dan b = 0,75 (PRD §12.2).
"""

import pickle
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi


class Bm25Index:
    def __init__(self, model: BM25Okapi):
        self._model = model

    @classmethod
    def build(cls, tokenized_docs: list[list[str]], k1: float, b: float) -> "Bm25Index":
        # rank_bm25 gagal bila ada dokumen tanpa term sama sekali; beri satu term kosong sebagai pengganti.
        safe_docs = [tokens or [""] for tokens in tokenized_docs]
        return cls(BM25Okapi(safe_docs, k1=k1, b=b))

    def scores(self, query_terms: list[str]) -> np.ndarray:
        """Skor untuk SEMUA dokumen, urut sesuai posisi dokumen di indeks."""
        if not query_terms:
            return np.zeros(self._model.corpus_size, dtype=np.float32)
        return np.asarray(self._model.get_scores(query_terms), dtype=np.float32)

    def term_frequency(self, position: int, query_terms: list[str]) -> int:
        """Berapa kali kata kueri muncul di dokumen (ditampilkan sebagai 'Frekuensi kata kunci')."""
        freqs = self._model.doc_freqs[position]
        return sum(freqs.get(t, 0) for t in set(query_terms))

    def save(self, path: Path) -> None:
        with path.open("wb") as f:
            pickle.dump(self._model, f, protocol=pickle.HIGHEST_PROTOCOL)

    @classmethod
    def load(cls, path: Path) -> "Bm25Index":
        # Hanya memuat file yang dibuat sendiri oleh aplikasi ini (folder data/index/), bukan unggahan pengguna.
        with path.open("rb") as f:
            return cls(pickle.load(f))
