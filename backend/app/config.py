"""Konfigurasi aplikasi.

Semua nilai bisa diganti lewat environment variable. Nilai default di sini cocok untuk pengembangan lokal.
"""

import os
import secrets
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]

APP_NAME = "CariSkripsi"
APP_VERSION = "1.0.0"

# --- Penyimpanan ---------------------------------------------------------------------------------
DATA_DIR = Path(os.getenv("CARISKRIPSI_DATA_DIR", ROOT_DIR / "data"))


def normalize_database_url(url: str) -> str:
    """Terima URL gaya Supabase/Heroku (postgres://...) dan arahkan ke driver psycopg 3."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


# Lokal: SQLite di data/cariskripsi.db. Online: URL PostgreSQL Supabase (lihat DEPLOY.md).
DATABASE_URL = normalize_database_url(
    os.getenv("CARISKRIPSI_DATABASE_URL", f"sqlite:///{(DATA_DIR / 'cariskripsi.db').as_posix()}"))
INDEX_DIR = DATA_DIR / "index"  # satu subfolder per versi indeks, mis. data/index/20261121-1305/

# Penyimpanan cadangan file indeks di Supabase Storage. Wajib bila disk server tidak permanen
# (Google Cloud Run): file indeks diunduh ulang dari sini setiap server menyala.
# Kosongkan untuk pemakaian lokal.
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "cariskripsi-index")

# --- Pencarian -----------------------------------------------------------------------------------
BM25_K1 = 1.5
BM25_B = 0.75
SBERT_MODEL = os.getenv("CARISKRIPSI_SBERT_MODEL", "firqaaa/indo-sentence-bert-base")
MAX_RESULTS = 50  # batas hasil teratas per pencarian (PRD FR-06)
PAGE_SIZE = 10
COMPARE_TOP_K = 10  # jumlah hasil per kolom di mode Bandingkan
MIN_QUERY_CHARS = 2

# --- Admin & keamanan ----------------------------------------------------------------------------
SESSION_COOKIE = "cs_session"
CSRF_COOKIE = "cs_csrf"
CSRF_HEADER = "X-CSRF-Token"
SESSION_MAX_AGE_SECONDS = 8 * 60 * 60  # sesi admin berlaku 8 jam
LOGIN_MAX_FAILURES = 5  # kegagalan login per menit sebelum diblokir sementara
LOGIN_WINDOW_SECONDS = 60
COOKIE_SECURE = os.getenv("CARISKRIPSI_COOKIE_SECURE", "0") == "1"  # set 1 bila disajikan lewat HTTPS
# 1 = server berada di belakang proxy tepercaya (Vercel + Cloud Run): IP pengguna diambil dari
# X-Forwarded-For untuk pembatasan percobaan login. Biarkan 0 bila server bisa diakses langsung.
TRUST_FORWARDED_FOR = os.getenv("CARISKRIPSI_TRUST_FORWARDED_FOR", "0") == "1"

# --- Import --------------------------------------------------------------------------------------
IMPORT_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
IMPORT_MAX_ROWS = 5000

# --- Evaluasi ------------------------------------------------------------------------------------
EVAL_K = 5  # metrik @5 (PRD §15.3)
EVAL_POOL_DEPTH = 10  # pooling: 10 hasil teratas dari tiap metode


def _load_secret_key() -> str:
    """Kunci penanda tangan cookie sesi.

    Diambil dari env CARISKRIPSI_SECRET_KEY. Bila tidak ada, dibuat sekali lalu disimpan ke
    data/secret_key.txt supaya sesi admin tetap berlaku setelah server di-restart.
    """
    from_env = os.getenv("CARISKRIPSI_SECRET_KEY")
    if from_env:
        return from_env
    path = DATA_DIR / "secret_key.txt"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    key = secrets.token_urlsafe(48)
    path.write_text(key, encoding="utf-8")
    return key


SECRET_KEY = _load_secret_key()
