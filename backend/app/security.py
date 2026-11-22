"""Keamanan admin: hash password, token sesi bertanda tangan, dan pembatas percobaan login.

Cara kerja sesi:
- Setelah login, server mengirim dua cookie:
    cs_session (httpOnly)  : token bertanda tangan berisi id admin + token CSRF. JavaScript tidak bisa membacanya.
    cs_csrf    (bisa dibaca): salinan token CSRF untuk dikirim ulang oleh frontend di header X-CSRF-Token.
- Setiap request yang mengubah data (POST/PUT/DELETE) wajib membawa header X-CSRF-Token yang sama dengan
  token CSRF di dalam cs_session. Situs lain tidak bisa membaca cookie kita, jadi tidak bisa memalsukannya.
- Token sesi kedaluwarsa setelah SESSION_MAX_AGE_SECONDS.
"""

import secrets
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass

import bcrypt
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app import config

_serializer = URLSafeTimedSerializer(config.SECRET_KEY, salt="cariskripsi-admin-session")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:  # hash rusak
        return False


@dataclass
class SessionData:
    admin_id: int
    csrf: str


def create_session_token(admin_id: int) -> tuple[str, str]:
    """Mengembalikan (token sesi, token CSRF)."""
    csrf = secrets.token_urlsafe(24)
    return _serializer.dumps({"admin_id": admin_id, "csrf": csrf}), csrf


def read_session_token(token: str | None, max_age: int = config.SESSION_MAX_AGE_SECONDS) -> SessionData | None:
    """Isi token bila tanda tangan valid dan belum kedaluwarsa, selain itu None."""
    if not token:
        return None
    try:
        data = _serializer.loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    return SessionData(admin_id=int(data["admin_id"]), csrf=str(data["csrf"]))


class LoginRateLimiter:
    """Batasi kegagalan login per alamat IP: maksimal `max_failures` dalam `window` detik (disimpan di memori)."""

    def __init__(self, max_failures: int = config.LOGIN_MAX_FAILURES, window: float = config.LOGIN_WINDOW_SECONDS):
        self.max_failures = max_failures
        self.window = window
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        times = self._failures[key]
        while times and now - times[0] > self.window:
            times.popleft()
        return times

    def is_blocked(self, key: str) -> bool:
        with self._lock:
            return len(self._prune(key, time.monotonic())) >= self.max_failures

    def record_failure(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            self._prune(key, now).append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)
