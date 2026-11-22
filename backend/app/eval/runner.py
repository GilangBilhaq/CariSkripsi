"""Pooling, penentuan nilai akhir, dan menjalankan evaluasi BM25 vs IndoSBERT (PRD §15).

Penilaian relevansi:
    1. ensure_pool()   untuk tiap kueri, gabungkan 10 hasil teratas BM25 dan IndoSBERT, acak urutannya
                       (penilai tidak tahu dokumen berasal dari metode mana), lalu bekukan.
    2. Para penilai memberi nilai 0/1/2 sendiri-sendiri (tabel eval_judgments).
    3. final_grades()  nilai akhir per dokumen:
                         - keputusan bersama (penilai FINAL_JUDGE) bila ada,
                         - bila semua penilai sepakat: nilai itu,
                         - bila berbeda dan belum diputuskan: nilai TERENDAH (konservatif) dan dihitung
                           sebagai "belum diselesaikan".
    4. run_evaluation() jalankan kedua metode untuk semua kueri yang sudah dinilai dan simpan hasilnya.
"""

import random
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import config
from app.eval.metrics import (average_precision, cohen_kappa, ndcg_at_k, percentile, precision_at_k,
                              recall_at_k, total_relevant)
from app.models import FINAL_JUDGE, EvalJudgment, EvalPoolItem, EvalQuery, EvalRun
from app.search.index_manager import IndexBundle
from app.search.semantic import SemanticEncoder
from app.search.service import rank

METHODS = ("bm25", "sbert")


# --- Pooling ---------------------------------------------------------------------------------------

def ensure_pool(session: Session, bundle: IndexBundle, encoder: SemanticEncoder, query: EvalQuery,
                depth: int = config.EVAL_POOL_DEPTH) -> list[EvalPoolItem]:
    """Pool kandidat untuk kueri. Dibuat sekali; panggilan berikutnya mengembalikan pool yang sama."""
    existing = session.scalars(select(EvalPoolItem).where(EvalPoolItem.query_id == query.id)
                               .order_by(EvalPoolItem.urutan)).all()
    if existing:
        return list(existing)

    doc_ids: list[int] = []
    for method in METHODS:
        for hit in rank(bundle, encoder, method, query.teks, limit=depth).hits:
            if hit.doc_id not in doc_ids:
                doc_ids.append(hit.doc_id)
    random.Random(query.id).shuffle(doc_ids)  # acak tetapi tetap sama bila dibuat ulang (seed = id kueri)
    items = [EvalPoolItem(query_id=query.id, document_id=d, urutan=i) for i, d in enumerate(doc_ids)]
    session.add_all(items)
    session.commit()
    return items


def reset_pool(session: Session, query_id: int) -> None:
    """Hapus pool dan semua penilaiannya (mis. setelah teks kueri diubah)."""
    session.execute(delete(EvalJudgment).where(EvalJudgment.query_id == query_id))
    session.execute(delete(EvalPoolItem).where(EvalPoolItem.query_id == query_id))
    session.commit()


# --- Nilai akhir & kesepakatan ------------------------------------------------------------------------

@dataclass
class QueryGrades:
    grades: dict[int, int] = field(default_factory=dict)  # nilai akhir per dokumen
    unresolved: list[int] = field(default_factory=list)  # dokumen yang nilainya berbeda dan belum diputuskan


def _scores_by_doc(session: Session, query_id: int) -> dict[int, dict[str, int]]:
    scores: dict[int, dict[str, int]] = defaultdict(dict)
    for j in session.scalars(select(EvalJudgment).where(EvalJudgment.query_id == query_id)):
        scores[j.document_id][j.penilai] = j.skor
    return scores


def final_grades(session: Session, query_id: int) -> QueryGrades:
    result = QueryGrades()
    for doc_id, by_judge in _scores_by_doc(session, query_id).items():
        if FINAL_JUDGE in by_judge:
            result.grades[doc_id] = by_judge[FINAL_JUDGE]
            continue
        values = set(by_judge.values())
        result.grades[doc_id] = min(values)
        if len(values) > 1:
            result.unresolved.append(doc_id)
    return result


def judges(session: Session) -> list[str]:
    """Nama penilai, diurutkan dari yang paling banyak menilai."""
    rows = session.execute(select(EvalJudgment.penilai, func.count()).where(EvalJudgment.penilai != FINAL_JUDGE)
                           .group_by(EvalJudgment.penilai).order_by(func.count().desc(), EvalJudgment.penilai))
    return [name for name, _ in rows]


def agreement(session: Session) -> dict:
    """Cohen's kappa antara dua penilai teratas, dihitung atas dokumen yang dinilai keduanya."""
    names = judges(session)
    if len(names) < 2:
        return {"penilai": names, "kappa": None, "jumlah_pasangan": 0, "sepakat": 0}
    a, b = names[:2]
    pairs = []
    for query_id in session.scalars(select(EvalQuery.id)):
        for by_judge in _scores_by_doc(session, query_id).values():
            if a in by_judge and b in by_judge:
                pairs.append((by_judge[a], by_judge[b]))
    return {"penilai": [a, b], "kappa": cohen_kappa(pairs), "jumlah_pasangan": len(pairs),
            "sepakat": sum(x == y for x, y in pairs)}


# --- Menjalankan evaluasi ---------------------------------------------------------------------------

def _method_metrics(ranked: list[int], grades: dict[int, int], k: int, took_ms: float) -> dict:
    return {
        "p_at_k": precision_at_k(ranked, grades, k),
        "r_at_k": recall_at_k(ranked, grades, k),
        "ap": average_precision(ranked, grades),
        "ndcg_at_k": ndcg_at_k(ranked, grades, k),
        "waktu_ms": took_ms,
        "hasil": ranked,
    }


def _winner(per_method: dict, key: str = "ndcg_at_k") -> str:
    diff = per_method["sbert"][key] - per_method["bm25"][key]
    if abs(diff) < 1e-9:
        return "seri"
    return "sbert" if diff > 0 else "bm25"


def run_evaluation(session: Session, bundle: IndexBundle, encoder: SemanticEncoder,
                   k: int = config.EVAL_K, depth: int = config.EVAL_POOL_DEPTH) -> EvalRun:
    """Evaluasi semua kueri yang sudah punya penilaian. Hasil metrik deterministik (latensi bisa sedikit berbeda)."""
    queries = session.scalars(select(EvalQuery).order_by(EvalQuery.id)).all()
    per_query: list[dict] = []
    latencies: dict[str, list[float]] = {m: [] for m in METHODS}

    for q in queries:
        g = final_grades(session, q.id)
        if not g.grades:
            continue  # belum dinilai
        per_method = {}
        for method in METHODS:
            r = rank(bundle, encoder, method, q.teks, limit=depth)
            per_method[method] = _method_metrics([h.doc_id for h in r.hits], g.grades, k, r.took_ms)
            latencies[method].append(r.took_ms)
        per_query.append({
            "query_id": q.id, "teks": q.teks, "kategori": q.kategori,
            "jumlah_relevan": total_relevant(g.grades), "belum_diselesaikan": len(g.unresolved),
            "metode": per_method, "pemenang": _winner(per_method),
        })

    if not per_query:
        raise ValueError("Belum ada kueri yang dinilai. Nilai relevansi dulu sebelum menjalankan evaluasi.")

    def mean(method: str, key: str) -> float:
        return sum(row["metode"][method][key] for row in per_query) / len(per_query)

    summary = {
        m: {
            "p_at_k": mean(m, "p_at_k"), "r_at_k": mean(m, "r_at_k"), "map": mean(m, "ap"),
            "ndcg_at_k": mean(m, "ndcg_at_k"),
            "waktu_rata_ms": sum(latencies[m]) / len(latencies[m]), "waktu_p95_ms": percentile(latencies[m], 95),
        }
        for m in METHODS
    }
    summary["menang"] = {w: sum(row["pemenang"] == w for row in per_query) for w in ("bm25", "sbert", "seri")}
    summary["kesepakatan"] = agreement(session)
    summary["belum_diselesaikan"] = sum(row["belum_diselesaikan"] for row in per_query)

    run = EvalRun(index_versi=bundle.versi, model_name=bundle.meta.get("model_name", encoder.model_name),
                  bm25_params=bundle.meta.get("bm25_params", {}), k=k, jumlah_kueri=len(per_query),
                  ringkasan=summary, per_kueri=per_query)
    session.add(run)
    session.commit()
    return run
