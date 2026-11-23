"""Tes API dari sisi HTTP, termasuk kriteria penerimaan PRD §17."""

import io

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import func, select

from app import config
from app.api import auth as auth_module
from app.main import create_app
from app.models import Admin, Document, EvalJudgment
from app.security import LoginRateLimiter, hash_password

H = "https://repository.unej.ac.id/handle/123456789/"


@pytest.fixture
def client(session_factory, index_manager):
    auth_module.login_limiter = LoginRateLimiter()  # mulai bersih untuk setiap tes
    with session_factory() as s:
        s.add(Admin(username="admin", password_hash=hash_password("rahasia123")))
        s.commit()
    with TestClient(create_app(session_factory, index_manager)) as c:
        yield c


@pytest.fixture
def admin(client):
    """Klien yang sudah login; header CSRF dipasang otomatis."""
    r = client.post("/api/admin/login", json={"username": "admin", "password": "rahasia123"})
    assert r.status_code == 200
    client.headers[config.CSRF_HEADER] = client.cookies[config.CSRF_COOKIE]
    return client


# --- Publik ---------------------------------------------------------------------------------------------

def test_search_bm25_returns_scores_and_time(client):
    r = client.get("/api/search", params={"q": "energi biomassa", "method": "bm25"})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3 and body["took_ms"] >= 0
    first = body["results"][0]
    assert first["judul"].startswith("Pemanfaatan Energi Biomassa") and first["score"] > 0
    assert first["frekuensi_kata"] >= 2
    marked = [first["judul_sorot"]["text"][a:b] for a, b in first["judul_sorot"]["highlights"]]
    assert marked == ["Energi", "Biomassa"]


def test_search_sbert_and_filters(client):
    r = client.get("/api/search", params={"q": "energi biomassa", "method": "sbert", "year_from": 2025})
    assert r.status_code == 200
    assert {x["tahun"] for x in r.json()["results"]} <= {2025, 2026}


@pytest.mark.parametrize("q", ["", "   ", "a"])
def test_search_rejects_empty_or_short_query(client, q):
    r = client.get("/api/search", params={"q": q})
    assert r.status_code == 422 and isinstance(r.json()["detail"], str)


def test_search_without_results_is_empty_list(client):
    r = client.get("/api/search", params={"q": "kriptografi kuantum"})
    assert r.status_code == 200 and r.json()["results"] == []


def test_semantic_features_report_not_ready_on_bm25_only_index(client, index_manager, sample_docs):
    from dataclasses import replace

    index_manager.active = replace(index_manager.active, embeddings=None)  # seperti saat embedding dihitung
    assert client.get("/api/search", params={"q": "energi biomassa", "method": "bm25"}).status_code == 200
    for path, params in [("/api/search", {"q": "energi biomassa", "method": "sbert"}),
                         ("/api/compare", {"q": "energi biomassa"})]:
        r = client.get(path, params=params)
        assert r.status_code == 503 and "sedang disiapkan" in r.json()["detail"]
    assert client.get("/api/stats").json()["semantik_siap"] is False
    assert client.get(f"/api/documents/{sample_docs[0].id}").json()["serupa"] == []


def test_compare_marks_overlap(client):
    body = client.get("/api/compare", params={"q": "energi biomassa"}).json()
    bm25_ids = {x["id"] for x in body["bm25"]["results"]}
    sbert_ids = {x["id"] for x in body["sbert"]["results"]}
    assert body["jumlah_irisan"] == len(bm25_ids & sbert_ids)
    for x in body["bm25"]["results"]:
        assert (x["peringkat_di_lawan"] is not None) == (x["id"] in sbert_ids)


def test_document_detail_with_similar(client, sample_docs):
    body = client.get(f"/api/documents/{sample_docs[0].id}").json()
    assert body["judul_asli"].startswith("Pemanfaatan")
    assert len(body["serupa"]) == 3 and sample_docs[0].id not in [s["id"] for s in body["serupa"]]
    assert client.get("/api/documents/9999").status_code == 404


def test_deleted_document_disappears_from_results(admin, sample_docs):
    doc_id = sample_docs[0].id
    assert admin.delete(f"/api/admin/documents/{doc_id}").status_code == 200
    ids = [x["id"] for x in admin.get("/api/search", params={"q": "energi biomassa"}).json()["results"]]
    assert doc_id not in ids


# --- Autentikasi --------------------------------------------------------------------------------------

def test_admin_endpoints_require_login(client):
    assert client.get("/api/admin/stats").status_code == 401
    assert client.get("/api/admin/documents").status_code == 401


def test_login_logout_and_csrf(client):
    r = client.post("/api/admin/login", json={"username": "admin", "password": "rahasia123"})
    assert r.status_code == 200
    assert client.get("/api/admin/me").json() == {"username": "admin"}
    # Tanpa header CSRF, request yang mengubah data ditolak
    assert client.post("/api/admin/index/rebuild").status_code == 403
    client.headers[config.CSRF_HEADER] = "salah"
    assert client.post("/api/admin/index/rebuild").status_code == 403
    client.headers[config.CSRF_HEADER] = client.cookies[config.CSRF_COOKIE]
    assert client.post("/api/admin/logout").status_code == 200
    client.cookies.clear()
    assert client.get("/api/admin/me").status_code == 401


def test_tampered_or_expired_session_rejected(client, monkeypatch):
    client.cookies.set(config.SESSION_COOKIE, "token-palsu")
    assert client.get("/api/admin/me").status_code == 401
    client.post("/api/admin/login", json={"username": "admin", "password": "rahasia123"})
    from app import security
    monkeypatch.setattr(security.config, "SESSION_MAX_AGE_SECONDS", -1)
    monkeypatch.setattr(security.read_session_token, "__defaults__", (-1,))
    assert client.get("/api/admin/me").status_code == 401


def test_login_rate_limit_after_five_failures(client):
    for _ in range(5):
        assert client.post("/api/admin/login", json={"username": "admin", "password": "x"}).status_code == 401
    r = client.post("/api/admin/login", json={"username": "admin", "password": "rahasia123"})
    assert r.status_code == 429


# --- Kelola data -----------------------------------------------------------------------------------------

def test_create_update_validate_document(admin):
    bad = admin.post("/api/admin/documents", json={"judul": "ab", "tahun": "1800", "link": "bukan-link"})
    assert bad.status_code == 422
    assert {e["kolom"] for e in bad.json()["detail"]["errors"]} == {"judul", "tahun", "link"}

    body = {"judul": "Sistem Irigasi Otomatis Berbasis IoT", "abstrak": "", "tahun": 2025,
            "link": "10.1234/abc.2025"}
    r = admin.post("/api/admin/documents", json=body)
    assert r.status_code == 201
    doc = r.json()
    assert doc["link"] == "https://doi.org/10.1234/abc.2025" and doc["perlu_indeks"] is True
    assert doc["abstrak_tersedia"] is False and doc["sumber"] == "manual"
    assert admin.post("/api/admin/documents", json=body).status_code == 409  # link sama

    r = admin.put(f"/api/admin/documents/{doc['id']}", json=body | {"judul": "Sistem Irigasi Tetes Otomatis"})
    assert r.status_code == 200 and r.json()["judul"] == "Sistem Irigasi Tetes Otomatis"


def test_list_filter_and_export_csv_is_injection_safe(admin, session_factory):
    with session_factory() as s:
        doc = s.scalars(select(Document)).first()
        doc.judul_asli = "=HYPERLINK(\"http://jahat\")"
        s.commit()
    r = admin.get("/api/admin/documents", params={"tahun": 2025})
    assert r.json()["total"] == 2
    csv_text = admin.get("/api/admin/documents/export.csv").content.decode("utf-8-sig")
    assert "'=HYPERLINK" in csv_text


def test_admin_stats(admin):
    s = admin.get("/api/admin/stats").json()
    assert s["total"] == 6 and s["dengan_abstrak"] == 5
    assert s["indeks_aktif"]["status"] == "active"


# --- Import ---------------------------------------------------------------------------------------------

CSV_WITH_3_PROBLEMS = (
    "judul,abstrak,tahun,link,penulis\n"
    "Analisis Kualitas Air Sungai Bedadung,Penelitian ini mengukur kualitas air sungai Bedadung di Jember "
    "berdasarkan parameter fisika dan kimia.,2025," + H + "9001,Ani\n"
    ",Abstrak tanpa judul yang cukup panjang untuk lolos batas minimum karakter.,2025," + H + "9002,Budi\n"
    "Judul Dengan Tahun Salah,Abstrak dengan tahun yang salah dan cukup panjang untuk validasi.,20x5,"
    + H + "9003,Cici\n"
    "Judul Dengan Link Rusak,Abstrak dengan link rusak dan cukup panjang untuk validasi minimum.,2024,"
    "link-rusak,Dodi\n"
    "Pengaruh Media Sosial terhadap Minat Baca,,2024," + H + "9005,Eka\n"
)


def upload(admin, content: bytes, name="data.csv"):
    return admin.post("/api/admin/import/upload", files={"file": (name, content, "text/csv")})


def count_docs(session_factory):
    with session_factory() as s:
        return s.scalar(select(func.count(Document.id)))


def test_import_preview_shows_exactly_the_three_bad_rows(admin, session_factory):
    before = count_docs(session_factory)
    r = upload(admin, CSV_WITH_3_PROBLEMS.encode())
    assert r.status_code == 201
    job = r.json()
    assert (job["valid"], job["peringatan"], job["error"], job["duplikat"]) == (1, 1, 3, 0)
    assert count_docs(session_factory) == before  # belum tersimpan sebelum konfirmasi

    errors = admin.get(f"/api/admin/import/{job['id']}", params={"status": "error"}).json()["baris"]["items"]
    assert [e["nomor_baris"] for e in errors] == [3, 4, 5]
    assert [e["pesan"][0]["kolom"] for e in errors] == ["judul", "tahun", "link"]

    r = admin.post(f"/api/admin/import/{job['id']}/confirm", json={"mode_duplikat": "skip", "bangun_indeks": False})
    assert r.json()["ditambahkan"] == 2
    assert count_docs(session_factory) == before + 2
    assert admin.post(f"/api/admin/import/{job['id']}/confirm", json={}).status_code == 409  # tidak bisa dua kali


def test_import_duplicates_skip_overwrite_append(admin, sample_docs, session_factory):
    existing = sample_docs[0]
    csv = ("judul,abstrak,tahun,link\n"
           f"Judul Baru Untuk Link Lama,Abstrak pengganti yang cukup panjang untuk validasi sistem.,2024,"
           f"{existing.link}\n"
           f"{existing.judul_asli},Abstrak lain yang cukup panjang untuk validasi sistem import.,2024,{H}7777\n")
    for mode, expected_total, expected_title in [
        ("skip", 6, existing.judul_asli),
        ("overwrite", 6, "Judul Baru Untuk Link Lama"),
    ]:
        job = upload(admin, csv.encode()).json()
        assert job["duplikat"] == 2
        admin.post(f"/api/admin/import/{job['id']}/confirm", json={"mode_duplikat": mode, "bangun_indeks": False})
        assert count_docs(session_factory) == expected_total
        with session_factory() as s:
            assert s.get(Document, existing.id).judul_asli == expected_title

    job = upload(admin, csv.encode()).json()
    r = admin.post(f"/api/admin/import/{job['id']}/confirm", json={"mode_duplikat": "append", "bangun_indeks": False})
    assert r.json()["ditambahkan"] == 1  # duplikat-judul ditambah; duplikat-link tidak bisa (link unik)
    assert count_docs(session_factory) == 7


def test_import_is_atomic(admin, session_factory, monkeypatch):
    job = upload(admin, CSV_WITH_3_PROBLEMS.encode()).json()
    before = count_docs(session_factory)
    from app.data import importer
    calls = []

    def failing_new_document(values, sumber):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("disk penuh")
        return Document(**{"judul_asli": values["judul_asli"], "link": values["link"], "bahasa_asli": "id",
                           "bahasa_judul": "id", "abstrak_tersedia": False, "sumber": sumber})

    monkeypatch.setattr(importer, "new_document", failing_new_document)
    with pytest.raises(RuntimeError):
        admin.post(f"/api/admin/import/{job['id']}/confirm", json={"bangun_indeks": False})
    assert count_docs(session_factory) == before  # baris pertama ikut dibatalkan


def test_import_rejects_bad_files(admin):
    assert upload(admin, b"kolom_a,kolom_b\n1,2\n").status_code == 400  # kolom wajib tidak ada
    assert upload(admin, b"x", name="data.pdf").status_code == 400
    assert upload(admin, "judul,tahun,link\nÁ,2024,x\n".encode("latin-1")).status_code == 400  # bukan UTF-8


def test_template_xlsx_roundtrip(admin):
    r = admin.get("/api/admin/import/template", params={"format": "xlsx"})
    wb = load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Data", "Petunjuk"]
    job = admin.post("/api/admin/import/upload", files={"file": ("t.xlsx", r.content, "application/octet-stream")})
    assert job.status_code == 201 and job.json()["valid"] == 1


def test_import_then_rebuild_makes_document_searchable(admin, index_manager):
    csv = ("judul,abstrak,tahun,link\nSistem Hidroponik Otomatis untuk Selada,Penelitian hidroponik selada "
           f"dengan kendali nutrisi otomatis berbasis mikrokontroler.,2025,{H}8888\n")
    job = upload(admin, csv.encode()).json()
    admin.post(f"/api/admin/import/{job['id']}/confirm", json={"bangun_indeks": False})
    assert admin.get("/api/search", params={"q": "hidroponik selada"}).json()["results"] == []
    index_manager.rebuild_now(translate=False)
    for method in ("bm25", "sbert"):
        results = admin.get("/api/search", params={"q": "hidroponik selada", "method": method}).json()["results"]
        assert results[0]["judul"] == "Sistem Hidroponik Otomatis untuk Selada"


# --- Evaluasi ----------------------------------------------------------------------------------------------

def test_evaluation_flow(admin, session_factory):
    q = admin.post("/api/admin/eval/queries", json={"teks": "energi biomassa", "kategori": "kata_kunci"}).json()
    pool = admin.get(f"/api/admin/eval/queries/{q['id']}/pool", params={"penilai": "Ani"}).json()
    item = pool["items"][0]
    assert set(item) == {"document_id", "judul", "abstrak", "tahun", "link", "skor"}  # tanpa info metode/skor

    for i, it in enumerate(pool["items"]):
        for judge, score in (("Ani", 2 if i == 0 else 0), ("Budi", 1 if i == 0 else 0)):
            r = admin.put("/api/admin/eval/judgments", json={"query_id": q["id"], "document_id": it["document_id"],
                                                               "penilai": judge, "skor": score})
            assert r.status_code == 200
    dis = admin.get("/api/admin/eval/disagreements").json()
    assert len(dis["items"]) == 1 and dis["kesepakatan"]["jumlah_pasangan"] == len(pool["items"])
    admin.put("/api/admin/eval/resolve", json={"query_id": q["id"], "document_id": item["document_id"], "skor": 2})

    run = admin.post("/api/admin/eval/run").json()
    assert run["jumlah_kueri"] == 1 and run["ringkasan"]["belum_diselesaikan"] == 0
    assert admin.get("/api/admin/eval/runs").json()[0]["id"] == run["id"]
    csv_text = admin.get(f"/api/admin/eval/runs/{run['id']}/export.csv").content.decode("utf-8-sig")
    assert "energi biomassa" in csv_text and "RATA-RATA" in csv_text

    # hasil evaluasi hanya untuk admin: tanpa login tidak bisa dibaca, dan tidak ada endpoint publiknya
    cookies = dict(admin.cookies)
    admin.cookies.clear()
    assert admin.get("/api/admin/eval/runs").status_code == 401
    assert admin.get(f"/api/admin/eval/runs/{run['id']}").status_code == 401
    assert admin.get("/api/evaluation/latest").status_code == 404
    admin.cookies.update(cookies)

    # mengubah teks kueri menghapus pool dan penilaian lama
    admin.put(f"/api/admin/eval/queries/{q['id']}", json={"teks": "briket jagung", "kategori": "kata_kunci"})
    with session_factory() as s:
        assert s.scalar(select(func.count(EvalJudgment.id))) == 0
