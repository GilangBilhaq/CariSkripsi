"""Metrik dihitung manual di komentar, lalu dicocokkan dengan kode."""

import pytest

from app.eval.metrics import (average_precision, cohen_kappa, ndcg_at_k, percentile, precision_at_k,
                              recall_at_k)

# Hasil sistem: dokumen 1..5. Relevan: 1 (nilai 2), 3 (nilai 1), dan 9 (nilai 2, tidak ditemukan sistem).
RANKED = [1, 2, 3, 4, 5]
GRADES = {1: 2, 2: 0, 3: 1, 9: 2}


def test_precision_at_k():
    assert precision_at_k(RANKED, GRADES, 5) == pytest.approx(2 / 5)
    assert precision_at_k(RANKED, GRADES, 1) == 1.0
    assert precision_at_k([1], GRADES, 5) == pytest.approx(1 / 5)  # hasil kurang dari k


def test_recall_at_k():
    assert recall_at_k(RANKED, GRADES, 5) == pytest.approx(2 / 3)
    assert recall_at_k(RANKED, GRADES, 2) == pytest.approx(1 / 3)


def test_average_precision():
    # relevan di posisi 1 dan 3 -> (1/1 + 2/3) / 3 relevan total
    assert average_precision(RANKED, GRADES) == pytest.approx((1 + 2 / 3) / 3)


def test_ndcg_at_k():
    # DCG  = (2^2-1)/log2(2) + 0 + (2^1-1)/log2(4)  = 3 + 0.5 = 3.5
    # IDCG = 3/log2(2) + 3/log2(3) + 1/log2(4)       = 3 + 1.8928 + 0.5
    assert ndcg_at_k(RANKED, GRADES, 5) == pytest.approx(3.5 / (3 + 3 / 1.5849625 + 0.5), rel=1e-6)
    assert ndcg_at_k([1, 9, 3], GRADES, 3) == pytest.approx(1.0)  # urutan ideal


def test_no_relevant_documents_gives_zero_not_error():
    grades = {1: 0, 2: 0}
    assert precision_at_k(RANKED, grades, 5) == 0
    assert recall_at_k(RANKED, grades, 5) == 0
    assert average_precision(RANKED, grades) == 0
    assert ndcg_at_k(RANKED, grades, 5) == 0
    assert precision_at_k([], {}, 5) == 0


def test_cohen_kappa():
    assert cohen_kappa([(2, 2), (1, 1), (0, 0)]) == 1.0
    # po = 0.5; A: {2: .5, 0: .5}, B: {2: .5, 0: .5} -> pe = 0.5 -> kappa 0
    assert cohen_kappa([(2, 2), (2, 0), (0, 2), (0, 0)]) == pytest.approx(0.0)
    assert cohen_kappa([(1, 1), (1, 1)]) == 1.0  # semua sama satu kategori
    assert cohen_kappa([]) is None


def test_percentile_matches_linear_interpolation():
    assert percentile([10, 20, 30, 40], 50) == 25
    assert percentile(list(range(1, 101)), 95) == pytest.approx(95.05)
    assert percentile([], 95) == 0
