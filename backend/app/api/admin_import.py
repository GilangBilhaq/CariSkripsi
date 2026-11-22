"""Admin: import CSV/Excel 5 langkah (PRD FR-24, FR-25) dan pembangunan indeks (FR-26, FR-27)."""

import math
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import config
from app.api.admin_data import import_job_summary
from app.api.deps import get_index_manager, get_session, require_admin
from app.api.serializers import index_version
from app.data.files import template_csv, template_xlsx
from app.data.importer import ImportFileError, confirm_import, create_preview, read_upload
from app.models import Admin, Document, ImportJob, ImportRow, IndexVersion
from app.search.index_manager import IndexManager

router = APIRouter(prefix="/admin", tags=["admin: import & indeks"], dependencies=[Depends(require_admin)])


# --- Langkah 1: template -----------------------------------------------------------------------------

@router.get("/import/template")
def download_template(format: Literal["csv", "xlsx"] = "xlsx"):
    if format == "csv":
        content, media = template_csv(), "text/csv; charset=utf-8"
    else:
        content, media = template_xlsx(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return Response(content, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="template-import-cariskripsi.{format}"'})


# --- Langkah 2-3: unggah + pratinjau ----------------------------------------------------------------

@router.post("/import/upload", status_code=201)
async def upload(file: UploadFile, session: Session = Depends(get_session), admin: Admin = Depends(require_admin)):
    content = await file.read(config.IMPORT_MAX_BYTES + 1)
    try:
        records = read_upload(file.filename or "tanpa-nama", content)
    except ImportFileError as exc:
        raise HTTPException(400, str(exc))
    job = create_preview(session, file.filename or "tanpa-nama", records, admin.id)
    return import_job_summary(job) | {"ukuran_byte": len(content)}


@router.get("/import/history")
def import_history(session: Session = Depends(get_session)):
    jobs = session.scalars(select(ImportJob).order_by(ImportJob.id.desc()).limit(20))
    return [import_job_summary(j) for j in jobs]


@router.get("/import/{job_id}")
def preview(job_id: int, status: Literal["masalah", "valid", "peringatan", "duplikat", "error"] = "masalah",
            page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
            session: Session = Depends(get_session)):
    """Ringkasan import + daftar baris. status='masalah' = peringatan, duplikat, dan error sekaligus."""
    job = session.get(ImportJob, job_id)
    if job is None:
        raise HTTPException(404, "Import tidak ditemukan.")
    stmt = select(ImportRow).where(ImportRow.job_id == job_id)
    if status == "masalah":
        stmt = stmt.where(ImportRow.status.in_(["peringatan", "duplikat", "error"]))
    else:
        stmt = stmt.where(ImportRow.status == status)
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = session.scalars(stmt.order_by(ImportRow.nomor_baris).offset((page - 1) * page_size).limit(page_size))

    titles = {}  # judul dokumen yang sudah ada, untuk menjelaskan duplikat
    rows = list(rows)
    dup_ids = [r.duplikat_dari for r in rows if r.duplikat_dari]
    if dup_ids:
        titles = dict(session.execute(select(Document.id, Document.judul_asli).where(Document.id.in_(dup_ids))).all())

    return {
        "job": import_job_summary(job),
        "baris": {
            "total": total, "page": page, "pages": max(1, math.ceil(total / page_size)),
            "items": [{"nomor_baris": r.nomor_baris, "status": r.status, "pesan": r.pesan, "data": r.data_json,
                       "duplikat_dari": r.duplikat_dari, "judul_duplikat": titles.get(r.duplikat_dari)}
                      for r in rows],
        },
    }


# --- Langkah 4-5: konfirmasi + reindeks ---------------------------------------------------------------

class ConfirmIn(BaseModel):
    mode_duplikat: Literal["skip", "overwrite", "append"] = "skip"
    bangun_indeks: bool = True


@router.post("/import/{job_id}/confirm")
def confirm(job_id: int, body: ConfirmIn, session: Session = Depends(get_session),
            manager: IndexManager = Depends(get_index_manager)):
    job = session.get(ImportJob, job_id)
    if job is None:
        raise HTTPException(404, "Import tidak ditemukan.")
    try:
        result = confirm_import(session, job, body.mode_duplikat)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    started = manager.start_rebuild_in_background() if body.bangun_indeks and (result.inserted or result.updated) \
        else False
    return {"ditambahkan": result.inserted, "diperbarui": result.updated, "dilewati": result.skipped,
            "indeks_dimulai": started, "job": import_job_summary(job)}


@router.post("/import/{job_id}/cancel")
def cancel(job_id: int, session: Session = Depends(get_session)):
    job = session.get(ImportJob, job_id)
    if job is None:
        raise HTTPException(404, "Import tidak ditemukan.")
    if job.status != "preview":
        raise HTTPException(409, "Import ini sudah dikonfirmasi atau dibatalkan.")
    job.status = "cancelled"
    session.commit()
    return import_job_summary(job)


# --- Indeks --------------------------------------------------------------------------------------------

@router.post("/index/rebuild", status_code=202)
def rebuild_index(manager: IndexManager = Depends(get_index_manager)):
    if not manager.start_rebuild_in_background():
        raise HTTPException(409, "Pembangunan indeks sedang berjalan.")
    return {"dimulai": True}


@router.get("/index/status")
def index_status(session: Session = Depends(get_session), manager: IndexManager = Depends(get_index_manager)):
    manager.sync_with_database(force=True)
    versions = session.scalars(select(IndexVersion).order_by(IndexVersion.id.desc()).limit(5)).all()
    return {
        "sedang_dibangun": manager.is_building,
        "terbaru": index_version(versions[0]) if versions else None,
        "aktif": manager.active.versi if manager.active else None,
        "perlu_indeks": session.scalar(select(func.count(Document.id)).where(Document.perlu_indeks.is_(True))),
        "riwayat": [index_version(v) for v in versions],
    }
