"""Login, logout, dan info admin yang sedang login (PRD FR-20)."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.api.deps import client_ip, get_session, require_admin
from app.models import Admin
from app.security import LoginRateLimiter, create_session_token, verify_password

router = APIRouter(prefix="/admin", tags=["admin: autentikasi"])
login_limiter = LoginRateLimiter()


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


def set_session_cookies(response: Response, token: str, csrf: str) -> None:
    common = dict(max_age=config.SESSION_MAX_AGE_SECONDS, samesite="lax", secure=config.COOKIE_SECURE, path="/")
    response.set_cookie(config.SESSION_COOKIE, token, httponly=True, **common)
    response.set_cookie(config.CSRF_COOKIE, csrf, httponly=False, **common)  # dibaca frontend untuk header CSRF


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, session: Session = Depends(get_session)):
    ip = client_ip(request)
    if login_limiter.is_blocked(ip):
        raise HTTPException(429, "Terlalu banyak percobaan login gagal. Tunggu 1 menit lalu coba lagi.")

    admin = session.scalar(select(Admin).where(Admin.username == body.username.strip()))
    if admin is None or not verify_password(body.password, admin.password_hash):
        login_limiter.record_failure(ip)
        raise HTTPException(401, "Username atau kata sandi salah.")

    login_limiter.reset(ip)
    token, csrf = create_session_token(admin.id)
    set_session_cookies(response, token, csrf)
    return {"username": admin.username}


@router.post("/logout")
def logout(response: Response, _admin: Admin = Depends(require_admin)):
    response.delete_cookie(config.SESSION_COOKIE, path="/")
    response.delete_cookie(config.CSRF_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(admin: Admin = Depends(require_admin)):
    return {"username": admin.username}
