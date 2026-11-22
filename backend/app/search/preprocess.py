"""Pra-pemrosesan teks untuk BM25 (PRD §12.1 langkah 3).

Urutan: huruf kecil -> ambil kata (huruf/angka) -> buang stopword -> stemming Sastrawi.

IndoSBERT TIDAK memakai fungsi ini; model membaca kalimat utuh tanpa stemming.
"""

import re
from functools import lru_cache

from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
from Sastrawi.StopWordRemover.StopWordRemoverFactory import StopWordRemoverFactory

_TOKEN = re.compile(r"[a-z0-9]+")

_stemmer = StemmerFactory().create_stemmer()
STOPWORDS: frozenset[str] = frozenset(StopWordRemoverFactory().get_stop_words())


def tokenize(text: str) -> list[str]:
    """Pecah teks menjadi kata huruf kecil. Contoh: 'COVID-19 di Jember' -> ['covid', '19', 'di', 'jember']."""
    return _TOKEN.findall(text.lower())


@lru_cache(maxsize=None)
def stem(word: str) -> str:
    """Kata dasar Sastrawi, di-cache per kata unik.

    Sastrawi lambat (berbasis aturan), padahal korpus hanya punya sekitar seratus ribu kata unik.
    Dengan cache, tiap kata unik cukup di-stem sekali.
    """
    if any(ch.isdigit() for ch in word):
        return word  # angka/kode (mis. 'covid19', '2024') tidak di-stem
    return _stemmer.stem(word) or word


def analyze(text: str) -> list[str]:
    """Teks -> daftar term untuk indeks BM25 dan kueri BM25."""
    return [stem(w) for w in tokenize(text) if w not in STOPWORDS and len(w) > 1]
