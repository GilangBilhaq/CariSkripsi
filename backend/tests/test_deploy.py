"""Fitur untuk server online: penyimpanan cadangan indeks, pemindahan database, dan cek kesehatan."""

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.data.migrate import copy_database
from app.db import make_engine
from app.main import create_app
from app.models import Admin, Document, EvalJudgment, EvalQuery
from app.search.index_manager import IndexManager
from app.search.index_store import LocalDirStore
from app.search.service import rank
from tests.conftest import FakeEncoder


def test_new_server_downloads_active_index_from_store(session_factory, sample_docs, tmp_path):
    store = LocalDirStore(tmp_path / "cadangan")
    builder = IndexManager(session_factory, index_dir=tmp_path / "disk-lama", encoder=FakeEncoder(), store=store)
    versi = builder.rebuild_now(translate=False)
    assert (tmp_path / "cadangan" / versi / "meta.json").exists()
    assert (tmp_path / "cadangan" / "embedding_cache.npz").exists()

    # Server baru dengan disk kosong (mis. Hugging Face Space setelah restart).
    server = IndexManager(session_factory, index_dir=tmp_path / "disk-baru", encoder=FakeEncoder(), store=store)
    server.load_active()
    assert server.active.versi == versi and server.active.has_semantic
    assert (tmp_path / "disk-baru" / "embedding_cache.npz").exists()
    assert rank(server.active, server.encoder, "bm25", "energi biomassa").hits


def test_old_versions_removed_from_store(session_factory, sample_docs, tmp_path):
    store = LocalDirStore(tmp_path / "cadangan")
    manager = IndexManager(session_factory, index_dir=tmp_path / "index", encoder=FakeEncoder(), store=store)
    versions = [manager.rebuild_now(translate=False) for _ in range(5)]
    assert sorted(store.list_folders()) == sorted(versions[-3:])  # aktif + 2 arsip


def test_copy_database(tmp_path, session, sample_docs):
    source_url = f"sqlite:///{(tmp_path / 'sumber.db').as_posix()}"
    target_url = f"sqlite:///{(tmp_path / 'tujuan.db').as_posix()}"
    src = make_engine(source_url)
    from app.db import init_db
    init_db(src)
    with sessionmaker(bind=src)() as s:
        s.add(Document(judul_asli="Satu", link="https://contoh/1", bahasa_asli="id", bahasa_judul="id",
                       abstrak_tersedia=False))
        q = EvalQuery(teks="kueri", kategori="parafrase")
        s.add_all([q, Admin(username="admin", password_hash="x")])
        s.flush()
        s.add(EvalJudgment(query_id=q.id, document_id=1, penilai="Abdul", skor=2))
        s.commit()

    counts = copy_database(source_url, target_url)
    assert counts["documents"] == 1 and counts["eval_judgments"] == 1
    with sessionmaker(bind=make_engine(target_url))() as t:
        assert t.scalar(select(EvalJudgment.penilai)) == "Abdul"

    try:
        copy_database(source_url, target_url)
        raise AssertionError("harus menolak database tujuan yang sudah berisi")
    except RuntimeError as exc:
        assert "--ganti" in str(exc)
    assert copy_database(source_url, target_url, replace=True)["admins"] == 1
    with sessionmaker(bind=make_engine(target_url))() as t:
        assert t.scalar(select(func.count(Admin.id))) == 1


def test_health_checks_database_and_store(session_factory, index_manager, tmp_path):
    index_manager.store = LocalDirStore(tmp_path / "cadangan")
    with TestClient(create_app(session_factory, index_manager)) as client:
        body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["database"] == "ok" and body["penyimpanan"] == "ok"
    assert body["indeks"] == index_manager.active.versi


class FakeSupabaseStorage:
    """Tiruan kecil REST API Supabase Storage (hanya yang dipakai SupabaseStore)."""

    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def handler(self, request):
        import json as _json

        import httpx

        path = request.url.path.removeprefix("/storage/v1")
        if path.startswith("/bucket"):
            return httpx.Response(200, json={"id": "b"})
        if path.startswith("/object/list/"):
            prefix = _json.loads(request.content)["prefix"]
            names = {k[len(prefix):].split("/")[0]: "/" in k[len(prefix):] for k in self.objects if k.startswith(prefix)}
            return httpx.Response(200, json=[{"name": n, "id": None if folder else "x"} for n, folder in names.items()])
        key = path.removeprefix("/object/b").lstrip("/")
        if request.method == "POST":
            self.objects[key] = request.content
            return httpx.Response(200, json={"Key": key})
        if request.method == "GET":
            if key in self.objects:
                return httpx.Response(200, content=self.objects[key])
            return httpx.Response(400, json={"statusCode": "404", "error": "not_found"})
        if request.method == "DELETE":
            for name in _json.loads(request.content)["prefixes"]:
                self.objects.pop(name, None)
            return httpx.Response(200, json=[])
        return httpx.Response(405)


def test_supabase_store_splits_large_files(tmp_path, monkeypatch):
    import httpx

    from app.search import index_store

    monkeypatch.setattr(index_store, "PART_BYTES", 10)
    fake = FakeSupabaseStorage()
    store = index_store.SupabaseStore("https://contoh.supabase.co", "kunci", "b",
                                      transport=httpx.MockTransport(fake.handler))
    big, small = tmp_path / "besar.bin", tmp_path / "kecil.bin"
    big.write_bytes(bytes(range(25)))
    small.write_bytes(b"halo")

    store.put_file(big, "v1/embeddings.npy")
    store.put_file(small, "v1/meta.json")
    assert "v1/embeddings.npy.part002" in fake.objects and "v1/embeddings.npy" not in fake.objects
    assert store.get_file("v1/embeddings.npy", tmp_path / "unduh.bin")
    assert (tmp_path / "unduh.bin").read_bytes() == big.read_bytes()
    assert store.get_file("v1/tidak-ada", tmp_path / "x") is False

    # File yang mengecil di bawah batas: potongan lama dibuang.
    store.put_file(small, "v1/embeddings.npy")
    assert not any(k.startswith("v1/embeddings.npy.part") for k in fake.objects)
    assert store.get_file("v1/embeddings.npy", tmp_path / "unduh2.bin")
    assert (tmp_path / "unduh2.bin").read_bytes() == b"halo"

    assert store.list_folders() == ["v1"]
    store.delete_folder("v1")
    assert fake.objects == {}
