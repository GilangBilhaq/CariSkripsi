"""Tabel database (SQLAlchemy). Skema mengikuti PRD §13 dengan beberapa kolom tambahan.

Semua waktu disimpan dalam UTC (tanpa zona waktu). Frontend yang mengubahnya ke WIB saat ditampilkan.
"""

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    """Waktu sekarang dalam UTC, format sama dengan CURRENT_TIMESTAMP bawaan SQLite."""
    return datetime.now(UTC).replace(tzinfo=None)


class Document(Base):
    """Satu skripsi. Kolom *_asli = teks sumber, *_id = versi bahasa Indonesia yang diindeks."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    judul_asli: Mapped[str] = mapped_column(Text)
    judul_id: Mapped[str | None] = mapped_column(Text)  # None = menunggu terjemahan
    abstrak_asli: Mapped[str | None] = mapped_column(Text)
    abstrak_id: Mapped[str | None] = mapped_column(Text)
    tahun: Mapped[int | None] = mapped_column(Integer, index=True)
    link: Mapped[str] = mapped_column(String(500), unique=True, index=True)
    link_lain: Mapped[str | None] = mapped_column(Text)  # tautan dokumen kembar yang digabung, dipisah baris baru
    penulis: Mapped[str | None] = mapped_column(Text)
    program_studi: Mapped[str | None] = mapped_column(String(200))
    fakultas: Mapped[str | None] = mapped_column(String(200), index=True)
    kata_kunci: Mapped[str | None] = mapped_column(Text)
    bahasa_asli: Mapped[str] = mapped_column(String(8), index=True)  # bahasa abstrak (atau judul bila tanpa abstrak)
    bahasa_judul: Mapped[str] = mapped_column(String(8))
    abstrak_tersedia: Mapped[bool] = mapped_column(Boolean, index=True)
    jumlah_gabungan: Mapped[int] = mapped_column(Integer, default=1)
    sumber: Mapped[str] = mapped_column(String(20), default="harvest")  # harvest | import | manual
    perlu_indeks: Mapped[bool] = mapped_column(Boolean, default=True, index=True)  # True = belum masuk indeks aktif
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SearchLog(Base):
    """Log kueri publik. Anonim: tidak menyimpan IP atau identitas pengguna (PRD §9 Privasi)."""

    __tablename__ = "search_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kueri: Mapped[str] = mapped_column(String(500))
    metode: Mapped[str] = mapped_column(String(20))  # bm25 | sbert | compare
    jumlah_hasil: Mapped[int] = mapped_column(Integer)
    waktu_ms: Mapped[float] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class IndexVersion(Base):
    """Satu kali pembangunan indeks. Hanya satu baris berstatus 'active' pada satu waktu."""

    __tablename__ = "index_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    versi: Mapped[str] = mapped_column(String(40), unique=True)  # nama folder di data/index/
    status: Mapped[str] = mapped_column(String(20), index=True)  # building | active | archived | failed
    tahap: Mapped[str | None] = mapped_column(String(200))  # teks progres untuk ditampilkan di admin
    persen: Mapped[int] = mapped_column(Integer, default=0)
    jumlah_dokumen: Mapped[int] = mapped_column(Integer, default=0)
    model_name: Mapped[str] = mapped_column(String(200))
    bm25_params: Mapped[dict] = mapped_column(JSON)
    pesan_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class ImportJob(Base):
    """Satu file yang diunggah admin. Baris-barisnya disimpan di import_rows sampai dikonfirmasi."""

    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_id: Mapped[int | None] = mapped_column(ForeignKey("admins.id"))
    nama_file: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20))  # preview | confirmed | cancelled
    total: Mapped[int] = mapped_column(Integer, default=0)
    valid: Mapped[int] = mapped_column(Integer, default=0)
    peringatan: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[int] = mapped_column(Integer, default=0)
    duplikat: Mapped[int] = mapped_column(Integer, default=0)
    mode_duplikat: Mapped[str | None] = mapped_column(String(20))  # skip | overwrite | append (diisi saat konfirmasi)
    disimpan: Mapped[int] = mapped_column(Integer, default=0)  # jumlah dokumen yang benar-benar masuk/diperbarui
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)


class ImportRow(Base):
    __tablename__ = "import_rows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("import_jobs.id", ondelete="CASCADE"), index=True)
    nomor_baris: Mapped[int] = mapped_column(Integer)  # nomor baris di file (header = baris 1)
    status: Mapped[str] = mapped_column(String(20))  # valid | peringatan | duplikat | error
    pesan: Mapped[list] = mapped_column(JSON, default=list)  # daftar temuan validasi
    data_json: Mapped[dict] = mapped_column(JSON)  # nilai yang sudah dibersihkan
    duplikat_dari: Mapped[int | None] = mapped_column(Integer)  # id dokumen yang sudah ada (bila duplikat)


class EvalQuery(Base):
    __tablename__ = "eval_queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    teks: Mapped[str] = mapped_column(String(500))
    kategori: Mapped[str] = mapped_column(String(20))  # kata_kunci | deskriptif | parafrase
    catatan: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class EvalPoolItem(Base):
    """Dokumen kandidat yang dinilai untuk satu kueri (gabungan top-10 BM25 dan IndoSBERT).

    Pool dibekukan saat pertama kali dibuat, sehingga semua penilai menilai himpunan dokumen yang sama
    walaupun indeks berubah setelahnya. Urutan tampil diacak (blind) dan disimpan di kolom `urutan`.
    """

    __tablename__ = "eval_pool_items"
    __table_args__ = (UniqueConstraint("query_id", "document_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    query_id: Mapped[int] = mapped_column(ForeignKey("eval_queries.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[int] = mapped_column(Integer)
    urutan: Mapped[int] = mapped_column(Integer)


class EvalJudgment(Base):
    """Nilai relevansi dari satu penilai: 0 = tidak relevan, 1 = agak relevan, 2 = relevan.

    Penilai bernama khusus `FINAL_JUDGE` menyimpan keputusan bersama untuk pasangan yang nilainya berbeda.
    """

    __tablename__ = "eval_judgments"
    __table_args__ = (UniqueConstraint("query_id", "document_id", "penilai"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    query_id: Mapped[int] = mapped_column(ForeignKey("eval_queries.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[int] = mapped_column(Integer)
    penilai: Mapped[str] = mapped_column(String(100))
    skor: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


FINAL_JUDGE = "__final__"


class EvalRun(Base):
    """Hasil satu kali evaluasi. Menyimpan konfigurasi lengkap supaya hasil bisa direproduksi (PRD §9)."""

    __tablename__ = "eval_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    index_versi: Mapped[str] = mapped_column(String(40))
    model_name: Mapped[str] = mapped_column(String(200))
    bm25_params: Mapped[dict] = mapped_column(JSON)
    k: Mapped[int] = mapped_column(Integer)
    jumlah_kueri: Mapped[int] = mapped_column(Integer)
    ringkasan: Mapped[dict] = mapped_column(JSON)  # rata-rata metrik + latensi per metode, kappa
    per_kueri: Mapped[list] = mapped_column(JSON)  # metrik per kueri per metode
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
