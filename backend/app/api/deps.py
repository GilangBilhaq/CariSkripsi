"""Dependency FastAPI yang dipakai bersama oleh semua router."""

from collections.abc import Iterator

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app import config
from app.models import Admin
from app.search.index_manager import IndexBundle, IndexManager
from app.security import read_session_token

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def get_session(request: Request) -> Iterator[Session]:
    """Satu sesi database per request (pabrik sesi disimpan di app.state agar mudah diganti saat tes)."""
    with request.app.state.session_factory() as session:
        yield session


def get_index_manager(request: Request) -> IndexManager:
    return request.app.state.index_manager


def get_active_index(manager: IndexManager = Depends(get_index_manager)) -> IndexBundle:
    manager.sync_with_database()  # pakai indeks yang baru dibangun lewat CLI tanpa restart server
    if manager.active is None:
        raise HTTPException(503, "Indeks pencarian belum dibangun. Admin perlu menjalankan 'Bangun Ulang Indeks'.")
    return manager.active


SEMANTIC_NOT_READY = ("Pencarian Makna (IndoSBERT) sedang disiapkan: embedding dokumen masih dihitung. "
                      "Sementara itu gunakan pencarian Kata (BM25).")


def require_semantic(bundle: IndexBundle) -> IndexBundle:
    """Untuk fitur yang butuh embedding (IndoSBERT, Bandingkan, evaluasi): 503 bila belum siap."""
    if not bundle.has_semantic:
        raise HTTPException(503, SEMANTIC_NOT_READY)
    return bundle


def get_semantic_index(bundle: IndexBundle = Depends(get_active_index)) -> IndexBundle:
    return require_semantic(bundle)


def require_admin(request: Request, session: Session = Depends(get_session)) -> Admin:
    """Wajib login. Untuk request yang mengubah data, header CSRF juga wajib cocok."""
    data = read_session_token(request.cookies.get(config.SESSION_COOKIE))
    admin = session.get(Admin, data.admin_id) if data else None
    if admin is None:
        raise HTTPException(401, "Sesi admin tidak valid atau sudah kedaluwarsa. Silakan login kembali.")
    if request.method not in SAFE_METHODS and request.headers.get(config.CSRF_HEADER) != data.csrf:
        raise HTTPException(403, "Token CSRF tidak valid. Muat ulang halaman lalu coba lagi.")
    return admin


def client_ip(request: Request) -> str:
    """IP pengguna. Di belakang proxy (Next.js lokal, atau Vercel + Cloud Run online), IP asli ada di X-Forwarded-For."""
    forwarded = request.headers.get("x-forwarded-for")
    behind_proxy = config.TRUST_FORWARDED_FOR or (request.client and request.client.host in ("127.0.0.1", "::1"))
    if forwarded and behind_proxy:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
