"""Admin: ringkasan statistik, log kueri, dan kelola dokumen (PRD FR-21, FR-22, FR-23)."""

import math
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_index_manager, get_session, require_admin
from app.api.serializers import document_admin, index_version, iso
from app.data.documents import apply_values, new_document
from app.data.files import to_csv
from app.data.validate import validate_document
from app.models import Document, ImportJob, IndexVersion, SearchLog, utcnow
from app.search.index_manager import IndexManager

router = APIRouter(prefix="/admin", tags=["admin: data"], dependencies=[Depends(require_admin)])


# --- Ringkasan ----------------------------------------------------------------------------------------

@router.get("/stats")
def admin_stats(session: Session = Depends(get_session), manager: IndexManager = Depends(get_index_manager)):
    total = session.scalar(select(func.count(Document.id))) or 0
    with_abstract = session.scalar(select(func.count(Document.id)).where(Document.abstrak_tersedia.is_(True))) or 0
    per_year = session.execute(select(Document.tahun, func.count()).group_by(Document.tahun)
                               .order_by(Document.tahun.asc().nulls_last())).all()
    per_lang = session.execute(select(Document.bahasa_asli, func.count()).group_by(Document.bahasa_asli)).all()
    pending = session.scalar(select(func.count(Document.id)).where(Document.perlu_indeks.is_(True))) or 0
    untranslated = session.scalar(select(func.count(Document.id)).where(
        or_(Document.judul_id.is_(None), (Document.abstrak_tersedia.is_(True)) & Document.abstrak_id.is_(None)))) or 0
    last_import = session.scalar(select(ImportJob).where(ImportJob.status == "confirmed")
                                 .order_by(ImportJob.id.desc()))
    active = session.scalar(select(IndexVersion).where(IndexVersion.status == "active"))
    return {
        "total": total,
        "dengan_abstrak": with_abstract,
        "tanpa_abstrak": total - with_abstract,
        "per_tahun": [{"tahun": y, "jumlah": n} for y, n in per_year],
        "per_bahasa": {lang or "lain": n for lang, n in per_lang},
        "perlu_indeks": pending,
        "belum_diterjemahkan": untranslated,
        "indeks_aktif": index_version(active),
        "indeks_sedang_dibangun": manager.is_building,
        "import_terakhir": import_job_summary(last_import),
        "pencarian_24_jam": session.scalar(select(func.count(SearchLog.id)).where(
            SearchLog.created_at >= utcnow() - timedelta(days=1))) or 0,
    }


def import_job_summary(job: ImportJob | None) -> dict | None:
    if job is None:
        return None
    return {
        "id": job.id, "nama_file": job.nama_file, "status": job.status, "total": job.total, "valid": job.valid,
        "peringatan": job.peringatan, "error": job.error, "duplikat": job.duplikat, "disimpan": job.disimpan,
        "mode_duplikat": job.mode_duplikat,
        "created_at": iso(job.created_at),
        "confirmed_at": iso(job.confirmed_at),
    }


@router.get("/search-logs")
def search_logs(q: str = "", page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100),
                session: Session = Depends(get_session)):
    stmt = select(SearchLog)
    if q.strip():
        stmt = stmt.where(SearchLog.kueri.ilike(f"%{q.strip()}%"))
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = session.scalars(stmt.order_by(SearchLog.id.desc()).offset((page - 1) * page_size).limit(page_size))
    return {
        "total": total, "page": page, "pages": max(1, math.ceil(total / page_size)),
        "items": [{"id": r.id, "kueri": r.kueri, "metode": r.metode, "jumlah_hasil": r.jumlah_hasil,
                   "waktu_ms": r.waktu_ms, "created_at": iso(r.created_at)} for r in rows],
    }


# --- Daftar dokumen ----------------------------------------------------------------------------------

def filtered_documents(q: str, tahun: int | None, abstrak: str | None, bahasa: str | None,
                       status: str | None) -> Select:
    stmt = select(Document)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Document.judul_asli.ilike(like), Document.judul_id.ilike(like),
                              Document.penulis.ilike(like), Document.kata_kunci.ilike(like),
                              Document.link.ilike(like)))
    if tahun is not None:
        stmt = stmt.where(Document.tahun == tahun)
    if abstrak in ("ada", "tidak"):
        stmt = stmt.where(Document.abstrak_tersedia.is_(abstrak == "ada"))
    if bahasa in ("id", "en", "lain"):
        stmt = stmt.where(Document.bahasa_asli == bahasa)
    if status in ("terindeks", "antrean"):
        stmt = stmt.where(Document.perlu_indeks.is_(status == "antrean"))
    return stmt


@router.get("/documents")
def list_documents(
    q: str = "",
    tahun: int | None = None,
    abstrak: Literal["ada", "tidak"] | None = None,
    bahasa: Literal["id", "en", "lain"] | None = None,
    status: Literal["terindeks", "antrean"] | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    session: Session = Depends(get_session),
):
    stmt = filtered_documents(q, tahun, abstrak, bahasa, status)
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    docs = session.scalars(stmt.order_by(Document.id.desc()).offset((page - 1) * page_size).limit(page_size))
    return {
        "total": total, "page": page, "page_size": page_size, "pages": max(1, math.ceil(total / page_size)),
        "items": [document_admin(d) for d in docs],
    }


@router.get("/documents/export.csv")
def export_documents(
    q: str = "",
    tahun: int | None = None,
    abstrak: Literal["ada", "tidak"] | None = None,
    bahasa: Literal["id", "en", "lain"] | None = None,
    status: Literal["terindeks", "antrean"] | None = None,
    session: Session = Depends(get_session),
):
    header = ["id", "judul", "judul_id", "abstrak", "abstrak_id", "tahun", "link", "penulis", "program_studi",
              "fakultas", "kata_kunci", "bahasa_asli", "abstrak_tersedia", "status_indeks"]
    docs = session.scalars(filtered_documents(q, tahun, abstrak, bahasa, status).order_by(Document.id))
    rows = ([d.id, d.judul_asli, d.judul_id, d.abstrak_asli, d.abstrak_id, d.tahun, d.link, d.penulis,
             d.program_studi, d.fakultas, d.kata_kunci, d.bahasa_asli, int(d.abstrak_tersedia),
             "antrean" if d.perlu_indeks else "terindeks"] for d in docs)
    filename = f"cariskripsi-dokumen-{datetime.now():%Y%m%d-%H%M}.csv"
    return Response(to_csv(header, rows), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# --- Tambah / ubah / hapus -----------------------------------------------------------------------

class DocumentIn(BaseModel):
    judul: str = ""
    abstrak: str | None = None
    tahun: str | int | None = None
    link: str = ""
    penulis: str | None = None
    program_studi: str | None = None
    fakultas: str | None = None
    kata_kunci: str | None = None


def validated_values(body: DocumentIn) -> dict:
    result = validate_document(body.model_dump())
    if not result.ok:
        raise HTTPException(422, {"pesan": "Data belum valid", "errors": [f.as_dict() for f in result.errors]})
    return result.values


def ensure_link_unique(session: Session, link: str, own_id: int | None = None) -> None:
    other = session.scalar(select(Document.id).where(Document.link == link))
    if other is not None and other != own_id:
        raise HTTPException(409, {"pesan": "Link sudah dipakai dokumen lain",
                                  "errors": [{"kolom": "link", "nilai": link,
                                              "pesan": f"Link sudah dipakai dokumen #{other}"}]})


@router.get("/documents/{doc_id}")
def get_document(doc_id: int, session: Session = Depends(get_session)):
    doc = session.get(Document, doc_id)
    if doc is None:
        raise HTTPException(404, "Dokumen tidak ditemukan.")
    return document_admin(doc)


@router.post("/documents", status_code=201)
def create_document(body: DocumentIn, session: Session = Depends(get_session)):
    values = validated_values(body)
    ensure_link_unique(session, values["link"])
    doc = new_document(values, sumber="manual")
    session.add(doc)
    session.commit()
    return document_admin(doc)


@router.put("/documents/{doc_id}")
def update_document(doc_id: int, body: DocumentIn, session: Session = Depends(get_session)):
    doc = session.get(Document, doc_id)
    if doc is None:
        raise HTTPException(404, "Dokumen tidak ditemukan.")
    values = validated_values(body)
    ensure_link_unique(session, values["link"], own_id=doc_id)
    apply_values(doc, values)
    session.commit()
    return document_admin(doc)


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: int, session: Session = Depends(get_session)):
    doc = session.get(Document, doc_id)
    if doc is None:
        raise HTTPException(404, "Dokumen tidak ditemukan.")
    session.delete(doc)
    session.commit()
    # Dokumen yang dihapus otomatis tidak tampil di hasil pencarian (dilewati saat mengambil dari database);
    # indeks akan bersih sepenuhnya pada pembangunan ulang berikutnya.
    return {"ok": True}
