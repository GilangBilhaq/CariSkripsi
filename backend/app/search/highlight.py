"""Cuplikan abstrak dan posisi kata yang disorot (PRD FR-07).

Backend hanya mengirim teks polos + daftar rentang [awal, akhir) yang perlu disorot. Frontend yang
membungkus rentang itu dengan <mark>, sehingga tidak ada HTML dari data yang dirender (aman dari XSS).

Kata dianggap cocok bila kata dasarnya sama dengan kata dasar salah satu kata kueri, jadi kueri
"pembangkit" juga menyorot "membangkitkan".
"""

import re
from dataclasses import dataclass

from app.search.preprocess import STOPWORDS, analyze, stem

_WORD = re.compile(r"[A-Za-z0-9]+")
SNIPPET_CHARS = 320
LEAD_CHARS = 60  # konteks sebelum kata cocok pertama


@dataclass
class Highlighted:
    text: str
    highlights: list[tuple[int, int]]


def query_terms(query: str) -> set[str]:
    return set(analyze(query))


def _matches(text: str, terms: set[str]) -> list[tuple[int, int]]:
    spans = []
    for m in _WORD.finditer(text):
        word = m.group().lower()
        if word not in STOPWORDS and len(word) > 1 and stem(word) in terms:
            spans.append((m.start(), m.end()))
    return spans


def highlight_full(text: str, terms: set[str]) -> Highlighted:
    """Seluruh teks (dipakai untuk judul)."""
    return Highlighted(text, _matches(text, terms) if terms else [])


def make_snippet(text: str | None, terms: set[str], max_chars: int = SNIPPET_CHARS) -> Highlighted:
    """Potongan teks sekitar kata cocok pertama, maksimal `max_chars` karakter."""
    if not text:
        return Highlighted("", [])
    spans = _matches(text, terms) if terms else []

    start = 0
    if spans and spans[0][0] > LEAD_CHARS:
        start = text.rfind(" ", 0, spans[0][0] - LEAD_CHARS) + 1
    end = min(len(text), start + max_chars)
    if end < len(text):
        space = text.rfind(" ", start, end)
        end = space if space > start else end

    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    shift = len(prefix) - start
    snippet = prefix + text[start:end] + suffix
    inside = [(s + shift, e + shift) for s, e in spans if s >= start and e <= end]
    return Highlighted(snippet, inside)
