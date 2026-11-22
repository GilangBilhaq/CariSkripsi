"""Metrik evaluasi temu kembali (PRD §15.3).

Semua fungsi menerima:
    ranked  : daftar id dokumen hasil sistem, urut dari peringkat 1
    grades  : {id dokumen: nilai relevansi} hasil penilaian manusia, 0 = tidak relevan, 1 = agak, 2 = relevan

Dokumen yang tidak pernah dinilai dianggap tidak relevan (nilai 0), sesuai praktik standar pooling.
Untuk P@k, R@k, dan AP, nilai >= 1 dihitung "relevan". nDCG memakai nilai bertingkat 0/1/2.
"""

import math
from collections.abc import Sequence

RELEVANT_MIN_GRADE = 1


def _is_relevant(doc_id: int, grades: dict[int, int]) -> bool:
    return grades.get(doc_id, 0) >= RELEVANT_MIN_GRADE


def total_relevant(grades: dict[int, int]) -> int:
    return sum(g >= RELEVANT_MIN_GRADE for g in grades.values())


def precision_at_k(ranked: Sequence[int], grades: dict[int, int], k: int) -> float:
    """Proporsi dokumen relevan di k hasil teratas. Pembagi selalu k (hasil kurang dari k = dianggap tidak relevan)."""
    return sum(_is_relevant(d, grades) for d in ranked[:k]) / k


def recall_at_k(ranked: Sequence[int], grades: dict[int, int], k: int) -> float:
    """Proporsi dari SEMUA dokumen relevan yang muncul di k teratas. 0 bila kueri tidak punya dokumen relevan.

    Catatan: bila dokumen relevan lebih dari k, recall@k tidak mungkin mencapai 1.
    """
    total = total_relevant(grades)
    return sum(_is_relevant(d, grades) for d in ranked[:k]) / total if total else 0.0


def average_precision(ranked: Sequence[int], grades: dict[int, int]) -> float:
    """Rata-rata precision di setiap posisi dokumen relevan, dibagi jumlah seluruh dokumen relevan.

    Contoh: relevan di posisi 1 dan 3, total relevan 2 -> (1/1 + 2/3) / 2 = 0,833.
    """
    total = total_relevant(grades)
    if not total:
        return 0.0
    hits, precision_sum = 0, 0.0
    for position, doc_id in enumerate(ranked, start=1):
        if _is_relevant(doc_id, grades):
            hits += 1
            precision_sum += hits / position
    return precision_sum / total


def _dcg(gains: Sequence[int]) -> float:
    return sum((2 ** g - 1) / math.log2(i + 1) for i, g in enumerate(gains, start=1))


def ndcg_at_k(ranked: Sequence[int], grades: dict[int, int], k: int) -> float:
    """DCG hasil sistem dibagi DCG urutan ideal. Gain = 2^nilai - 1, diskon = log2(posisi + 1)."""
    ideal = _dcg(sorted(grades.values(), reverse=True)[:k])
    if ideal == 0:
        return 0.0
    return _dcg([grades.get(d, 0) for d in ranked[:k]]) / ideal


def cohen_kappa(pairs: Sequence[tuple[int, int]], categories: Sequence[int] = (0, 1, 2)) -> float | None:
    """Kesepakatan dua penilai di luar kebetulan. 1 = sepakat sempurna, 0 = setara kebetulan.

    kappa = (po - pe) / (1 - pe)
        po = proporsi item yang nilainya sama
        pe = peluang sama secara kebetulan = sum_c P(penilai A memberi c) * P(penilai B memberi c)
    None bila tidak ada pasangan untuk dibandingkan.
    """
    n = len(pairs)
    if n == 0:
        return None
    po = sum(a == b for a, b in pairs) / n
    pe = sum((sum(a == c for a, _ in pairs) / n) * (sum(b == c for _, b in pairs) / n) for c in categories)
    if pe == 1:
        return 1.0
    return (po - pe) / (1 - pe)


def percentile(values: Sequence[float], q: float) -> float:
    """Persentil dengan interpolasi linear (sama dengan numpy.percentile default). q dalam 0..100."""
    if not values:
        return 0.0
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q / 100
    low = math.floor(pos)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)
