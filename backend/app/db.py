"""Koneksi database dan sesi SQLAlchemy."""

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app import config


class Base(DeclarativeBase):
    pass


def make_engine(url: str = config.DATABASE_URL):
    if not url.startswith("sqlite"):
        # PostgreSQL (Supabase): pre_ping + recycle karena pooler menutup koneksi yang lama menganggur.
        engine = create_engine(url, pool_pre_ping=True, pool_recycle=300, pool_size=5, max_overflow=5)

        @event.listens_for(engine, "connect")
        def _postgres_utc(dbapi_conn, _record):
            # Semua waktu di database disimpan UTC (lihat models.utcnow), termasuk default now() dari server.
            cur = dbapi_conn.cursor()
            cur.execute("SET TIME ZONE INTERVAL '+00:00' HOUR TO MINUTE")  # = UTC, tanpa perlu data zona waktu
            cur.close()
            dbapi_conn.commit()

        return engine

    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        # WAL: pencarian (baca) tetap jalan saat admin menulis data atau indeks sedang dibangun.
        cur.execute("PRAGMA journal_mode=WAL")
        cur.close()

    return engine


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db(bind=None) -> None:
    from app import models  # noqa: F401  (registrasi tabel)

    if (bind or engine).url.get_backend_name() == "sqlite" and (bind or engine).url.database:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind or engine)


def get_session() -> Iterator[Session]:
    """Dependency FastAPI: satu sesi database per request."""
    with SessionLocal() as session:
        yield session
