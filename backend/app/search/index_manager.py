"""Pembangunan, penyimpanan, dan penggantian indeks pencarian.

Satu "versi indeks" = satu folder di data/index/<versi>/ berisi:
    bm25.pkl        indeks BM25
    embeddings.npy  matriks embedding IndoSBERT (n_dokumen x 768), baris ke-i milik doc_ids[i]
    doc_ids.npy     id dokumen sesuai urutan baris
    filters.npz     tahun, bahasa, dan status abstrak per dokumen (untuk filter pencarian)
    meta.json       info versi: model, parameter BM25, jumlah dokumen, waktu

Alur pembangunan (dijalankan di thread latar belakang, PRD FR-26/27):
    1. terjemahkan dokumen berbahasa Inggris yang belum punya terjemahan
    2. ambil semua dokumen dari database
    3. bangun BM25 (selalu penuh, hanya beberapa detik/menit)
    4. hitung embedding, hanya untuk dokumen baru/berubah (sisanya dari cache)
    5. simpan ke folder versi baru, lalu jadikan aktif

Bila penyimpanan cadangan dipakai (Supabase Storage, lihat index_store.py), setiap versi baru diunggah sebelum
diaktifkan, dan versi aktif diunduh otomatis bila foldernya tidak ada di disk (mis. server Cloud Run baru menyala).

Selama proses berjalan, indeks lama tetap melayani pencarian. Penggantian dilakukan dengan menukar satu
referensi objek (`self.active = bundle_baru`), jadi setiap request memakai indeks lama ATAU baru secara utuh.
"""

from __future__ import annotations

import json
import logging
import shutil
import threading
import time
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

import numpy as np
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app import config
from app.models import Document, IndexVersion, utcnow
from app.search.bm25 import Bm25Index
from app.search.build_lock import BuildLock
from app.search.index_store import IndexStore, default_store, download_folder, upload_folder
from app.search.preprocess import analyze
from app.search.semantic import EmbeddingCache, SemanticEncoder, embed_with_cache

log = logging.getLogger(__name__)

KEEP_OLD_VERSIONS = 2  # folder versi lama yang disimpan untuk berjaga-jaga; sisanya dihapus
BUNDLE_FILES = ["bm25.pkl", "embeddings.npy", "doc_ids.npy", "filters.npz", "meta.json"]
CACHE_FILE = "embedding_cache.npz"


def document_text(doc: Document) -> str:
    """Teks yang diindeks oleh KEDUA metode: judul + abstrak versi bahasa Indonesia."""
    title = doc.judul_id or doc.judul_asli
    return f"{title}. {doc.abstrak_id}" if doc.abstrak_id else title


@dataclass
class IndexBundle:
    """Satu versi indeks yang sudah dimuat ke memori."""

    versi: str
    doc_ids: np.ndarray  # int64, posisi -> id dokumen
    years: np.ndarray  # int32, 0 = tahun tidak diketahui
    languages: np.ndarray  # str, bahasa asli: 'id' | 'en' | 'lain'
    has_abstract: np.ndarray  # bool
    bm25: Bm25Index
    embeddings: np.ndarray | None  # float32, baris ternormalisasi L2. None = indeks sementara (BM25 saja)
    meta: dict

    def __post_init__(self):
        self.position_of = {int(d): i for i, d in enumerate(self.doc_ids)}

    @property
    def size(self) -> int:
        return len(self.doc_ids)

    @property
    def has_semantic(self) -> bool:
        """False selama embedding IndoSBERT pembangunan pertama belum selesai."""
        return self.embeddings is not None

    @classmethod
    def load(cls, folder: Path) -> IndexBundle:
        filters = np.load(folder / "filters.npz", allow_pickle=False)
        return cls(
            versi=folder.name,
            doc_ids=np.load(folder / "doc_ids.npy"),
            years=filters["years"],
            languages=filters["languages"],
            has_abstract=filters["has_abstract"],
            bm25=Bm25Index.load(folder / "bm25.pkl"),
            embeddings=np.load(folder / "embeddings.npy"),
            meta=json.loads((folder / "meta.json").read_text(encoding="utf-8")),
        )

    def save(self, folder: Path) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        np.save(folder / "doc_ids.npy", self.doc_ids)
        np.save(folder / "embeddings.npy", self.embeddings)
        np.savez(folder / "filters.npz", years=self.years, languages=self.languages, has_abstract=self.has_abstract)
        self.bm25.save(folder / "bm25.pkl")
        (folder / "meta.json").write_text(json.dumps(self.meta, indent=2, ensure_ascii=False), encoding="utf-8")


class IndexManager:
    """Memegang indeks aktif dan menjalankan pembangunan ulang (satu pembangunan pada satu waktu)."""

    def __init__(self, session_factory: sessionmaker, index_dir: Path = config.INDEX_DIR,
                 encoder: SemanticEncoder | None = None, store: IndexStore | None | str = "default"):
        self.session_factory = session_factory
        self.index_dir = index_dir
        # Penyimpanan cadangan file indeks. "default" = Supabase bila dikonfigurasi, None = hanya disk lokal.
        self.store: IndexStore | None = default_store() if store == "default" else store
        self.encoder = encoder or SemanticEncoder(config.SBERT_MODEL)  # tes memakai encoder palsu yang ringan
        self.active: IndexBundle | None = None
        # Dua lapis kunci: _build_lock untuk thread di proses ini, _process_lock untuk proses lain
        # (mis. `python -m app.cli build-index` yang berjalan bersamaan dengan server).
        self._build_lock = threading.Lock()
        self._process_lock = BuildLock(index_dir / ".build.lock")
        self._last_sync = 0.0

    # --- memuat indeks aktif --------------------------------------------------------------------------

    def load_active(self) -> None:
        """Dipanggil saat server mulai: muat versi aktif dan bereskan pembangunan yang terputus."""
        with self.session_factory() as session:
            if not self._process_lock.held_by_other_process():
                # Tidak ada proses yang sedang membangun, jadi status 'building' berarti sisa proses yang mati.
                session.execute(update(IndexVersion).where(IndexVersion.status == "building")
                                .values(status="failed", pesan_error="Terhenti sebelum selesai"))
                session.commit()
        self._download_cache_if_missing()
        self.sync_with_database(force=True)
        if self.active is None:
            log.warning("Belum ada indeks aktif. Jalankan: python -m app.cli build-index")

    def sync_with_database(self, force: bool = False, every_seconds: float = 30) -> None:
        """Muat versi aktif terbaru bila berbeda dari yang ada di memori.

        Perlu karena indeks juga bisa dibangun oleh proses lain (CLI); server akan memakainya tanpa restart.
        Pengecekan dibatasi sekali per `every_seconds` agar tidak membebani setiap pencarian.
        """
        now = time.monotonic()
        if not force and now - self._last_sync < every_seconds:
            return
        self._last_sync = now
        with self.session_factory() as session:
            versi = session.scalar(select(IndexVersion.versi).where(IndexVersion.status == "active"))
        if versi is None or (self.active is not None and self.active.versi == versi):
            return
        folder = self.index_dir / versi
        if not (folder / "meta.json").exists():
            if self.store is None or not download_folder(self.store, versi, folder, BUNDLE_FILES):
                log.error("File indeks %s tidak ditemukan di %s maupun di penyimpanan cadangan", versi, folder)
                return
        self.active = IndexBundle.load(folder)
        log.info("Indeks %s dimuat (%d dokumen)", versi, self.active.size)

    def _download_cache_if_missing(self) -> None:
        path = self.index_dir / CACHE_FILE
        if self.store is not None and not path.exists() and self.store.get_file(CACHE_FILE, path):
            log.info("Cache embedding diunduh dari penyimpanan cadangan")

    def upload_to_store(self, versi: str) -> None:
        """Unggah satu versi indeks + cache embedding ke penyimpanan cadangan (bila dipakai)."""
        if self.store is None:
            return
        upload_folder(self.store, self.index_dir / versi, versi)
        cache = self.index_dir / CACHE_FILE
        if cache.exists():
            self.store.put_file(cache, CACHE_FILE)

    @property
    def is_building(self) -> bool:
        return self._build_lock.locked() or self._process_lock.held_by_other_process()

    # --- pembangunan ulang ------------------------------------------------------------------------

    def _acquire_locks(self) -> bool:
        if not self._build_lock.acquire(blocking=False):
            return False
        if not self._process_lock.acquire():
            self._build_lock.release()
            return False
        return True

    def _release_locks(self) -> None:
        self._process_lock.release()
        self._build_lock.release()

    def start_rebuild_in_background(self) -> bool:
        """Mulai pembangunan di thread terpisah. False bila pembangunan lain sedang berjalan."""
        if not self._acquire_locks():
            return False

        def run():
            try:
                self._build()
            except Exception:  # sudah dicatat sebagai 'failed' di _build
                log.exception("Pembangunan indeks gagal")
            finally:
                self._release_locks()

        threading.Thread(target=run, name="index-rebuild", daemon=True).start()
        return True

    def rebuild_now(self, translate: bool = True) -> str:
        """Pembangunan sinkron (dipakai CLI). Mengembalikan nama versi baru."""
        if not self._acquire_locks():
            raise RuntimeError("Pembangunan indeks lain sedang berjalan (dari server atau CLI).")
        try:
            return self._build(translate=translate)
        finally:
            self._release_locks()

    def _build(self, translate: bool = True) -> str:
        params = {"k1": config.BM25_K1, "b": config.BM25_B}
        with self.session_factory() as session:
            versi = self._new_version_name(session)
            version = IndexVersion(versi=versi, status="building", tahap="Menyiapkan", persen=0,
                                   model_name=self.encoder.model_name, bm25_params=params)
            session.add(version)
            session.commit()
            try:
                bundle, indexed_texts = self._build_bundle(session, version, translate)
                bundle.save(self.index_dir / versi)
                if self.store is not None:
                    self._progress(session, version, "Mengunggah indeks ke penyimpanan cadangan", 99)
                    self.upload_to_store(versi)  # sebelum diaktifkan: server lain harus bisa mengunduhnya
                self._activate(session, version, bundle, indexed_texts)
            except Exception as exc:
                session.rollback()
                version.status = "failed"
                version.pesan_error = f"{type(exc).__name__}: {exc}"
                version.finished_at = utcnow()
                session.commit()
                shutil.rmtree(self.index_dir / versi, ignore_errors=True)
                raise
        self._delete_old_folders()
        return versi

    @staticmethod
    def _new_version_name(session: Session) -> str:
        """Nama versi = waktu pembuatan, mis. '20261121-130512'. Diberi akhiran bila sudah terpakai."""
        base = datetime.now().strftime("%Y%m%d-%H%M%S")
        name, n = base, 1
        while session.scalar(select(IndexVersion.id).where(IndexVersion.versi == name)) is not None:
            n += 1
            name = f"{base}-{n}"
        return name

    def _progress(self, session: Session, version: IndexVersion, tahap: str, persen: int) -> None:
        version.tahap, version.persen = tahap, persen
        session.commit()
        log.info("[indeks %s] %3d%% %s", version.versi, persen, tahap)

    def _build_bundle(self, session: Session, version: IndexVersion,
                      translate: bool) -> tuple[IndexBundle, dict[int, str]]:
        """Mengembalikan indeks baru + teks tiap dokumen yang diindeks (lihat _activate)."""
        if translate:
            self._translate_pending(session, version)

        self._progress(session, version, "Membaca dokumen dari database", 10)
        docs = session.scalars(select(Document).order_by(Document.id)).all()
        if not docs:
            raise RuntimeError("Database belum berisi dokumen")
        texts = [document_text(d) for d in docs]
        doc_ids = [d.id for d in docs]
        indexed_texts = dict(zip(doc_ids, texts))

        self._progress(session, version, f"Membangun indeks BM25 ({len(docs):,} dokumen)", 15)
        bm25 = Bm25Index.build([analyze(t) for t in texts], k1=config.BM25_K1, b=config.BM25_B)
        bundle = IndexBundle(
            versi=version.versi,
            doc_ids=np.array(doc_ids, dtype=np.int64),
            years=np.array([d.tahun or 0 for d in docs], dtype=np.int32),
            languages=np.array([d.bahasa_asli for d in docs]),
            has_abstract=np.array([d.abstrak_tersedia for d in docs], dtype=bool),
            bm25=bm25,
            embeddings=None,
            meta={
                "versi": version.versi,
                "jumlah_dokumen": len(docs),
                "model_name": self.encoder.model_name,
                "bm25_params": version.bm25_params,
            },
        )
        if self.active is None:
            # Belum ada indeks sama sekali (pembangunan pertama): pakai BM25 dulu supaya pencarian Kata bisa
            # dipakai selama embedding IndoSBERT dihitung, yang di CPU bisa memakan waktu berjam-jam.
            self.active = bundle
            log.info("Indeks sementara (BM25 saja) aktif: %d dokumen", bundle.size)

        cache = EmbeddingCache(self.index_dir / "embedding_cache.npz")

        def on_embed(done: int, total: int):
            self._progress(session, version, f"Menghitung embedding IndoSBERT ({done:,}/{total:,} dokumen baru)",
                           30 + int(65 * done / max(total, 1)))

        self._progress(session, version, "Menghitung embedding IndoSBERT", 30)
        embeddings = embed_with_cache(self.encoder, doc_ids, texts, cache, progress=on_embed)

        # Objek baru (bukan mengubah `bundle`): request yang sedang memakai indeks sementara tidak terganggu.
        full = replace(bundle, embeddings=embeddings,
                       meta=bundle.meta | {"dibuat": utcnow().isoformat(timespec="seconds") + "Z"})
        return full, indexed_texts

    def _translate_pending(self, session: Session, version: IndexVersion) -> None:
        from app.data.translate import MarianTranslator, count_pending, translate_pending

        pending = count_pending(session)
        if not pending:
            return
        self._progress(session, version, f"Memuat model terjemahan ({pending} dokumen berbahasa Inggris)", 2)
        translator = MarianTranslator()

        def on_translate(stats, total):
            self._progress(session, version, f"Menerjemahkan EN→ID ({stats.documents}/{total} dokumen)",
                           2 + int(8 * stats.documents / max(total, 1)))

        translate_pending(session, translator, progress=on_translate)

    def _activate(self, session: Session, version: IndexVersion, bundle: IndexBundle,
                  indexed_texts: dict[int, str]) -> None:
        """Jadikan versi baru aktif dan hapus tanda 'perlu_indeks' pada dokumen yang sudah masuk.

        Dokumen yang diedit SELAMA pembangunan (teksnya kini berbeda dari yang diindeks) tetap
        ditandai perlu_indeks, karena isi barunya belum ada di indeks ini.
        """
        session.execute(update(IndexVersion).where(IndexVersion.status == "active").values(status="archived"))
        version.status, version.tahap, version.persen = "active", "Selesai", 100
        version.jumlah_dokumen = bundle.size
        version.finished_at = utcnow()
        session.flush()  # tulis perubahan status versi dulu; expire_all di bawah membuang perubahan yang belum ditulis
        session.expire_all()  # baca ulang dokumen dari database, bukan dari cache sesi
        for doc in session.scalars(select(Document).where(Document.perlu_indeks.is_(True))):
            if indexed_texts.get(doc.id) == document_text(doc):
                doc.perlu_indeks = False
        session.commit()
        self.active = bundle  # <- penggantian atomik: request berikutnya memakai indeks baru
        log.info("Indeks %s aktif (%d dokumen)", version.versi, bundle.size)

    def _delete_old_folders(self) -> None:
        with self.session_factory() as session:
            keep = {v.versi for v in session.scalars(
                select(IndexVersion).where(IndexVersion.status.in_(["active", "archived"]))
                .order_by(IndexVersion.id.desc()).limit(KEEP_OLD_VERSIONS + 1))}
        if self.index_dir.exists():
            for folder in self.index_dir.iterdir():
                if folder.is_dir() and folder.name not in keep:
                    shutil.rmtree(folder, ignore_errors=True)
        if self.store is not None:
            try:
                for name in self.store.list_folders():
                    if name not in keep:
                        self.store.delete_folder(name)
            except Exception:  # pembersihan boleh gagal; indeks aktif tidak terganggu
                log.exception("Gagal menghapus versi lama di penyimpanan cadangan")
