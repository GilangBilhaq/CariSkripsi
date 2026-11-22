"""Admin: kueri uji, penilaian relevansi (blind), penyelesaian perbedaan, dan menjalankan evaluasi (FR-28, FR-29)."""

from collections import defaultdict
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_index_manager, get_semantic_index, get_session, require_admin
from app.eval.public import evaluation_csv, public_evaluation
from app.eval.runner import agreement, ensure_pool, final_grades, judges, reset_pool, run_evaluation
from app.models import FINAL_JUDGE, Document, EvalJudgment, EvalPoolItem, EvalQuery, EvalRun
from app.search.index_manager import IndexBundle, IndexManager

router = APIRouter(prefix="/admin/eval", tags=["admin: evaluasi"], dependencies=[Depends(require_admin)])

Category = Literal["kata_kunci", "deskriptif", "parafrase"]


# --- Kueri uji ----------------------------------------------------------------------------------------

class QueryIn(BaseModel):
    teks: str = Field(min_length=2, max_length=300)
    kategori: Category
    catatan: str | None = Field(default=None, max_length=1000)


def query_progress(session: Session, q: EvalQuery) -> dict:
    pool_size = session.scalar(select(func.count(EvalPoolItem.id)).where(EvalPoolItem.query_id == q.id)) or 0
    per_judge = dict(session.execute(
        select(EvalJudgment.penilai, func.count()).where(EvalJudgment.query_id == q.id,
                                                          EvalJudgment.penilai != FINAL_JUDGE)
        .group_by(EvalJudgment.penilai)).all())
    return {"id": q.id, "teks": q.teks, "kategori": q.kategori, "catatan": q.catatan,
            "jumlah_pool": pool_size, "dinilai": per_judge,
            "belum_diselesaikan": len(final_grades(session, q.id).unresolved)}


@router.get("/queries")
def list_queries(session: Session = Depends(get_session)):
    queries = session.scalars(select(EvalQuery).order_by(EvalQuery.id))
    return {"items": [query_progress(session, q) for q in queries], "penilai": judges(session)}


@router.post("/queries", status_code=201)
def create_query(body: QueryIn, session: Session = Depends(get_session)):
    q = EvalQuery(teks=" ".join(body.teks.split()), kategori=body.kategori, catatan=body.catatan)
    session.add(q)
    session.commit()
    return query_progress(session, q)


@router.put("/queries/{query_id}")
def update_query(query_id: int, body: QueryIn, session: Session = Depends(get_session)):
    q = session.get(EvalQuery, query_id)
    if q is None:
        raise HTTPException(404, "Kueri tidak ditemukan.")
    new_text = " ".join(body.teks.split())
    if new_text != q.teks:
        reset_pool(session, q.id)  # teks berubah -> kandidat dan penilaian lama tidak berlaku lagi
    q.teks, q.kategori, q.catatan = new_text, body.kategori, body.catatan
    session.commit()
    return query_progress(session, q)


@router.delete("/queries/{query_id}")
def delete_query(query_id: int, session: Session = Depends(get_session)):
    q = session.get(EvalQuery, query_id)
    if q is None:
        raise HTTPException(404, "Kueri tidak ditemukan.")
    reset_pool(session, q.id)
    session.delete(q)
    session.commit()
    return {"ok": True}


# --- Penilaian (blind) -----------------------------------------------------------------------------

def check_judge_name(name: str) -> str:
    name = " ".join(name.split())
    if not name or len(name) > 100 or name == FINAL_JUDGE:
        raise HTTPException(422, "Nama penilai tidak valid.")
    return name


@router.get("/queries/{query_id}/pool")
def judging_pool(query_id: int, penilai: str, session: Session = Depends(get_session),
                 bundle: IndexBundle = Depends(get_semantic_index), manager: IndexManager = Depends(get_index_manager)):
    """Dokumen yang harus dinilai, TANPA informasi metode, peringkat, atau skor (blind)."""
    penilai = check_judge_name(penilai)
    q = session.get(EvalQuery, query_id)
    if q is None:
        raise HTTPException(404, "Kueri tidak ditemukan.")
    pool = ensure_pool(session, bundle, manager.encoder, q)
    docs = {d.id: d for d in session.scalars(select(Document).where(Document.id.in_([p.document_id for p in pool])))}
    mine = dict(session.execute(select(EvalJudgment.document_id, EvalJudgment.skor)
                                .where(EvalJudgment.query_id == q.id, EvalJudgment.penilai == penilai)).all())
    items = []
    for p in pool:
        d = docs.get(p.document_id)
        items.append({
            "document_id": p.document_id,
            "judul": (d.judul_id or d.judul_asli) if d else "(dokumen sudah dihapus)",
            "abstrak": (d.abstrak_id or d.abstrak_asli) if d else None,
            "tahun": d.tahun if d else None,
            "link": d.link if d else None,
            "skor": mine.get(p.document_id),
        })
    return {"query": {"id": q.id, "teks": q.teks, "kategori": q.kategori, "catatan": q.catatan},
            "penilai": penilai, "items": items}


class JudgmentIn(BaseModel):
    query_id: int
    document_id: int
    penilai: str
    skor: int = Field(ge=0, le=2)

    @field_validator("penilai")
    @classmethod
    def _strip(cls, v: str) -> str:
        return " ".join(v.split())


def upsert_judgment(session: Session, query_id: int, document_id: int, penilai: str, skor: int) -> None:
    in_pool = session.scalar(select(EvalPoolItem.id).where(EvalPoolItem.query_id == query_id,
                                                           EvalPoolItem.document_id == document_id))
    if in_pool is None:
        raise HTTPException(404, "Dokumen ini bukan kandidat untuk kueri tersebut.")
    j = session.scalar(select(EvalJudgment).where(EvalJudgment.query_id == query_id,
                                                  EvalJudgment.document_id == document_id,
                                                  EvalJudgment.penilai == penilai))
    if j is None:
        session.add(EvalJudgment(query_id=query_id, document_id=document_id, penilai=penilai, skor=skor))
    else:
        j.skor = skor
    session.commit()


@router.put("/judgments")
def save_judgment(body: JudgmentIn, session: Session = Depends(get_session)):
    upsert_judgment(session, body.query_id, body.document_id, check_judge_name(body.penilai), body.skor)
    return {"ok": True}


# --- Perbedaan penilaian ----------------------------------------------------------------------------

@router.get("/disagreements")
def disagreements(session: Session = Depends(get_session)):
    """Pasangan kueri-dokumen yang nilainya berbeda antarpenilai, beserta keputusan bersama (bila ada)."""
    rows = session.scalars(select(EvalJudgment)).all()
    by_pair: dict[tuple[int, int], dict[str, int]] = defaultdict(dict)
    for j in rows:
        by_pair[(j.query_id, j.document_id)][j.penilai] = j.skor

    items = []
    for (query_id, doc_id), scores in by_pair.items():
        raters = {k: v for k, v in scores.items() if k != FINAL_JUDGE}
        if len(set(raters.values())) > 1:
            items.append({"query_id": query_id, "document_id": doc_id, "nilai": raters,
                          "keputusan": scores.get(FINAL_JUDGE)})
    queries = dict(session.execute(select(EvalQuery.id, EvalQuery.teks)).all())
    docs = {d.id: d for d in session.scalars(select(Document).where(
        Document.id.in_([i["document_id"] for i in items])))}
    for i in items:
        d = docs.get(i["document_id"])
        i["kueri"] = queries.get(i["query_id"])
        i["judul"] = (d.judul_id or d.judul_asli) if d else "(dokumen sudah dihapus)"
        i["abstrak"] = (d.abstrak_id or d.abstrak_asli) if d else None
    items.sort(key=lambda i: (i["keputusan"] is not None, i["query_id"], i["document_id"]))
    return {"items": items, "kesepakatan": agreement(session)}


class ResolveIn(BaseModel):
    query_id: int
    document_id: int
    skor: int = Field(ge=0, le=2)


@router.put("/resolve")
def resolve(body: ResolveIn, session: Session = Depends(get_session)):
    upsert_judgment(session, body.query_id, body.document_id, FINAL_JUDGE, body.skor)
    return {"ok": True}


# --- Menjalankan evaluasi --------------------------------------------------------------------------

@router.post("/run", status_code=201)
def run(session: Session = Depends(get_session), bundle: IndexBundle = Depends(get_semantic_index),
        manager: IndexManager = Depends(get_index_manager)):
    try:
        result = run_evaluation(session, bundle, manager.encoder)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    return public_evaluation(result)


@router.get("/runs")
def list_runs(session: Session = Depends(get_session)):
    runs = session.scalars(select(EvalRun).order_by(EvalRun.id.desc()).limit(20))
    return [{"id": r.id, "created_at": public_evaluation(r)["created_at"], "jumlah_kueri": r.jumlah_kueri,
             "index_versi": r.index_versi,
             "ndcg": {m: r.ringkasan[m]["ndcg_at_k"] for m in ("bm25", "sbert")}} for r in runs]


@router.get("/runs/{run_id}")
def get_run(run_id: int, session: Session = Depends(get_session)):
    r = session.get(EvalRun, run_id)
    if r is None:
        raise HTTPException(404, "Hasil evaluasi tidak ditemukan.")
    return public_evaluation(r)


@router.get("/runs/{run_id}/export.csv")
def export_run(run_id: int, session: Session = Depends(get_session)):
    r = session.get(EvalRun, run_id)
    if r is None:
        raise HTTPException(404, "Hasil evaluasi tidak ditemukan.")
    return Response(evaluation_csv(r), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="evaluasi-cariskripsi-{r.id}.csv"'})
