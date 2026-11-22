"""Salinan cadangan file indeks di luar server (Supabase Storage).

Kenapa perlu: server online (Google Cloud Run) memakai disk sementara yang kosong lagi setiap kali server
menyala. Membangun ulang embedding butuh berjam-jam, jadi setiap versi indeks yang selesai dibangun
diunggah ke sini, dan diunduh kembali saat server menyala.

Susunan di bucket (sama dengan folder lokal data/index/):
    <versi>/bm25.pkl, <versi>/embeddings.npy, ...   satu "folder" per versi indeks
    embedding_cache.npz                              cache embedding (agar pembaruan berikutnya inkremental)

Supabase gratis membatasi 50 MB per file. File yang lebih besar dipotong menjadi beberapa bagian
(`nama.part000`, `nama.part001`, ...) dengan daftar bagian di `nama.parts.json`.

Dua implementasi dengan antarmuka yang sama:
    SupabaseStore   dipakai server online
    LocalDirStore   menyalin ke folder lain; dipakai tes (dan bisa untuk cadangan lokal)
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Protocol

import httpx

from app import config

log = logging.getLogger(__name__)

PART_BYTES = 40 * 1024 * 1024  # di bawah batas 50 MB per file Supabase gratis


class IndexStore(Protocol):
    def put_file(self, local: Path, remote: str) -> None: ...
    def get_file(self, remote: str, local: Path) -> bool: ...  # False bila file tidak ada
    def delete_folder(self, prefix: str) -> None: ...
    def list_folders(self) -> list[str]: ...
    def ping(self) -> None: ...  # permintaan ringan; dipakai keep-alive


def upload_folder(store: IndexStore, folder: Path, prefix: str) -> None:
    """Unggah semua file di `folder` ke `<prefix>/`. meta.json diunggah TERAKHIR sebagai tanda lengkap."""
    files = sorted(p for p in folder.iterdir() if p.is_file())
    for path in sorted(files, key=lambda p: p.name == "meta.json"):
        store.put_file(path, f"{prefix}/{path.name}")
    log.info("Indeks %s diunggah ke penyimpanan cadangan", prefix)


def download_folder(store: IndexStore, prefix: str, folder: Path, names: list[str]) -> bool:
    """Unduh `<prefix>/<nama>` ke `folder`. False (dan folder tidak dibuat) bila ada file yang hilang."""
    tmp = folder.with_name(folder.name + ".download")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    for name in names:
        if not store.get_file(f"{prefix}/{name}", tmp / name):
            shutil.rmtree(tmp, ignore_errors=True)
            return False
    shutil.rmtree(folder, ignore_errors=True)
    tmp.rename(folder)
    log.info("Indeks %s diunduh dari penyimpanan cadangan", prefix)
    return True


class SupabaseStore:
    """Supabase Storage lewat REST API. Butuh service_role key (hanya disimpan di server, jangan di frontend)."""

    def __init__(self, url: str, service_key: str, bucket: str, transport: httpx.BaseTransport | None = None):
        self.bucket = bucket
        self.http = httpx.Client(
            base_url=f"{url}/storage/v1",
            headers=self._auth_headers(service_key),
            timeout=httpx.Timeout(300, connect=20),
            transport=transport,  # tes memakai tiruan Supabase
        )

    @staticmethod
    def _auth_headers(key: str) -> dict[str, str]:
        """Kunci lama `service_role` berupa JWT (eyJ...) dan dikirim juga sebagai Bearer. Kunci baru
        `sb_secret_...` bukan JWT, cukup lewat header apikey."""
        headers = {"apikey": key}
        if key.startswith("eyJ"):
            headers["Authorization"] = f"Bearer {key}"
        return headers

    # --- operasi satu objek ----------------------------------------------------------------------

    def _upload(self, remote: str, data: bytes) -> None:
        r = self.http.post(f"/object/{self.bucket}/{remote}", content=data,
                           headers={"Content-Type": "application/octet-stream", "x-upsert": "true"})
        r.raise_for_status()

    def _download(self, remote: str) -> bytes | None:
        r = self.http.get(f"/object/{self.bucket}/{remote}")
        if r.status_code in (400, 404):  # Supabase menjawab 400 "Object not found" untuk objek yang tidak ada
            return None
        r.raise_for_status()
        return r.content

    def _remove(self, names: list[str]) -> None:
        for i in range(0, len(names), 100):
            self.http.request("DELETE", f"/object/{self.bucket}", json={"prefixes": names[i:i + 100]})

    def _list(self, prefix: str) -> list[dict]:
        r = self.http.post(f"/object/list/{self.bucket}", json={"prefix": prefix, "limit": 1000, "offset": 0})
        r.raise_for_status()
        return r.json()

    # --- antarmuka IndexStore ----------------------------------------------------------------------

    def ensure_bucket(self) -> None:
        """Buat bucket privat bila belum ada (dipanggil oleh perintah CLI upload-index)."""
        if self.http.get(f"/bucket/{self.bucket}").status_code == 200:
            return
        r = self.http.post("/bucket", json={"id": self.bucket, "name": self.bucket, "public": False})
        r.raise_for_status()

    def put_file(self, local: Path, remote: str) -> None:
        size = local.stat().st_size
        old_parts = self._download(f"{remote}.parts.json")
        if size <= PART_BYTES:
            self._upload(remote, local.read_bytes())
            if old_parts:  # versi lama file ini pernah dipotong; buang bagian-bagiannya
                self._remove([f"{remote}.parts.json", *json.loads(old_parts)])
            return
        parts: list[str] = []
        with local.open("rb") as f:
            while chunk := f.read(PART_BYTES):
                name = f"{remote}.part{len(parts):03d}"
                self._upload(name, chunk)
                parts.append(name)
        # Daftar bagian ditulis terakhir: unduhan tidak pernah melihat potongan yang belum lengkap.
        self._upload(f"{remote}.parts.json", json.dumps(parts).encode())

    def get_file(self, remote: str, local: Path) -> bool:
        local.parent.mkdir(parents=True, exist_ok=True)
        manifest = self._download(f"{remote}.parts.json")
        if manifest is not None:
            with local.open("wb") as f:
                for name in json.loads(manifest):
                    chunk = self._download(name)
                    if chunk is None:
                        return False
                    f.write(chunk)
            return True
        data = self._download(remote)
        if data is None:
            return False
        local.write_bytes(data)
        return True

    def delete_folder(self, prefix: str) -> None:
        names = [f"{prefix}/{item['name']}" for item in self._list(f"{prefix}/")]
        if names:
            self._remove(names)

    def list_folders(self) -> list[str]:
        # Di Supabase, "folder" muncul sebagai entri tanpa id.
        return [item["name"] for item in self._list("") if item.get("id") is None]

    def ping(self) -> None:
        self.http.get(f"/bucket/{self.bucket}").raise_for_status()


class LocalDirStore:
    """Implementasi berbasis folder biasa (untuk tes)."""

    def __init__(self, root: Path):
        self.root = root

    def put_file(self, local: Path, remote: str) -> None:
        target = self.root / remote
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(local, target)

    def get_file(self, remote: str, local: Path) -> bool:
        source = self.root / remote
        if not source.exists():
            return False
        local.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, local)
        return True

    def delete_folder(self, prefix: str) -> None:
        shutil.rmtree(self.root / prefix, ignore_errors=True)

    def list_folders(self) -> list[str]:
        return [p.name for p in self.root.iterdir() if p.is_dir()] if self.root.exists() else []

    def ping(self) -> None:
        pass


def default_store() -> IndexStore | None:
    """SupabaseStore bila SUPABASE_URL dan SUPABASE_SERVICE_KEY diisi; None untuk pemakaian lokal."""
    if config.SUPABASE_URL and config.SUPABASE_SERVICE_KEY:
        return SupabaseStore(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY, config.SUPABASE_BUCKET)
    return None
