"""Fixture bersama untuk tes: database SQLite di memori, dokumen contoh, dan encoder palsu.

Untuk menjalankan semua tes pada PostgreSQL (mis. sebelum deploy ke Supabase), isi env
CARISKRIPSI_TEST_DATABASE_URL dengan database KOSONG khusus tes; semua tabelnya dihapus di setiap tes.

Encoder palsu menggantikan IndoSBERT supaya tes cepat dan tidak perlu mengunduh model. Vektornya adalah
'bag of words' yang di-hash, ditambah daftar sinonim kecil agar perilaku "semantik" bisa diuji.
"""

import hashlib
import os

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, init_db, make_engine
from app.models import Document
from app.search.index_manager import IndexManager
from app.search.preprocess import analyze
from app.search.semantic import normalize_rows

DIM = 64
SYNONYMS = {"tekan": "stres", "beban": "stres", "bidan": "rawat"}  # 'tertekan' ~ 'stres', 'bidan' ~ 'perawat'


class FakeEncoder:
    model_name = "fake-encoder"

    def _vector(self, text: str) -> np.ndarray:
        vec = np.zeros(DIM, dtype=np.float32)
        for term in analyze(text):
            term = SYNONYMS.get(term, term)
            vec[int(hashlib.md5(term.encode()).hexdigest(), 16) % DIM] += 1
        vec[0] += 0.01  # hindari vektor nol
        return vec

    def encode_query(self, query: str) -> np.ndarray:
        return normalize_rows(self._vector(query)[None, :])[0]

    def encode_documents(self, texts: list[str]) -> np.ndarray:
        return normalize_rows(np.stack([self._vector(t) for t in texts]))


SAMPLE_DOCS = [
    dict(judul_asli="Pemanfaatan Energi Biomassa Sekam Padi untuk Pembangkit Listrik Desa",
         abstrak_asli="Penelitian ini menganalisis potensi energi biomassa dari limbah sekam padi.",
         tahun=2024, bahasa_asli="id"),
    dict(judul_asli="Briket Biomassa dari Tongkol Jagung",
         abstrak_asli="Briket dibuat dari tongkol jagung sebagai bahan bakar alternatif.", tahun=2023, bahasa_asli="id"),
    dict(judul_asli="Hubungan Beban Kerja dengan Stres Kerja Perawat",
         abstrak_asli="Stres kerja perawat di rumah sakit dipengaruhi beban kerja yang tinggi.",
         tahun=2025, bahasa_asli="id"),
    dict(judul_asli="Perasaan Tertekan pada Bidan di Puskesmas",
         abstrak_asli="Bidan sering merasa tertekan karena jam kerja panjang.", tahun=2025, bahasa_asli="en"),
    dict(judul_asli="Klasifikasi Sentimen Ulasan Aplikasi dengan Naive Bayes",
         abstrak_asli="Sentimen ulasan pengguna diklasifikasikan menggunakan Naive Bayes.",
         tahun=2026, bahasa_asli="id"),
    dict(judul_asli="Analisis Kebijakan Energi Daerah", abstrak_asli=None, tahun=None, bahasa_asli="id"),
]


def add_sample_documents(session) -> list[Document]:
    docs = []
    for i, d in enumerate(SAMPLE_DOCS, start=1):
        doc = Document(
            judul_asli=d["judul_asli"], judul_id=d["judul_asli"],
            abstrak_asli=d["abstrak_asli"], abstrak_id=d["abstrak_asli"],
            tahun=d["tahun"], link=f"https://repository.unej.ac.id/handle/123456789/{i}",
            penulis=f"Penulis {i}", fakultas="Fakultas Teknik", bahasa_asli=d["bahasa_asli"], bahasa_judul="id",
            abstrak_tersedia=d["abstrak_asli"] is not None, perlu_indeks=True,
        )
        session.add(doc)
        docs.append(doc)
    session.commit()
    return docs


TEST_DATABASE_URL = os.getenv("CARISKRIPSI_TEST_DATABASE_URL")


@pytest.fixture
def engine():
    if TEST_DATABASE_URL:
        eng = make_engine(TEST_DATABASE_URL)
        Base.metadata.drop_all(eng)
        init_db(eng)
        yield eng
        eng.dispose()
        return
    # StaticPool: semua koneksi (termasuk dari thread lain) memakai database memori yang sama.
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    init_db(eng)
    yield eng


@pytest.fixture
def session_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def session(session_factory):
    with session_factory() as s:
        yield s


@pytest.fixture
def sample_docs(session):
    return add_sample_documents(session)


@pytest.fixture
def index_manager(session_factory, sample_docs, tmp_path):
    manager = IndexManager(session_factory, index_dir=tmp_path / "index", encoder=FakeEncoder(), store=None)
    manager.rebuild_now(translate=False)
    return manager
