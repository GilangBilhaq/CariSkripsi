import csv

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.data.ingest import ingest_csv
from app.db import init_db
from app.models import Document

ABS_GROUP = (
    "Pra-rancangan pabrik ini bertujuan untuk memenuhi kebutuhan asam musat dalam negeri dengan memanfaatkan "
    "limbah kulit kopi sebagai bahan baku utama melalui proses oksidasi."
)
ABS_OTHER = (
    "Penelitian ini membahas rancangan pabrik asam musat dengan kapasitas berbeda dan menggunakan proses "
    "fermentasi sebagai alternatif yang lebih ramah lingkungan bagi industri."
)
ABS_EN = (
    "This study aims to analyze the effect of financial literacy on the consumptive behavior of students "
    "in online shopping in Jember Regency using a quantitative method with a survey of respondents."
)
H = "https://repository.unej.ac.id/handle/123456789/"
FIELDS = ["judul", "abstrak", "tahun", "link", "penulis", "program_studi", "fakultas", "kata_kunci"]


def write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def base_rows():
    title = "Pra-Rancangan Pabrik Mucic Acid dari Limbah Kulit Kopi"
    return [
        # tiga anggota kelompok: judul + abstrak identik -> digabung, dokumen utama = handle terkecil (10)
        {"judul": title, "abstrak": ABS_GROUP, "tahun": "2026-01-05", "link": H + "12", "penulis": "Budi", "kata_kunci": "kopi"},
        {"judul": title, "abstrak": ABS_GROUP, "tahun": "2026-01-05", "link": H + "10", "penulis": "Ani", "kata_kunci": "kopi; pabrik"},
        # salah ketik kecil di abstrak (Jaccard >= 0,9) -> tetap dianggap kembar
        {"judul": title.upper(), "abstrak": ABS_GROUP.replace("memanfaatkan", "memanfatkan"), "tahun": "2026",
         "link": H + "11", "penulis": "Citra"},
        # judul sama, abstrak berbeda -> tetap terpisah
        {"judul": title, "abstrak": ABS_OTHER, "tahun": "2025", "link": H + "13", "penulis": "Dedi"},
        # judul ID, abstrak EN -> judul_id terisi, abstrak_id menunggu terjemahan
        {"judul": "Pengaruh Literasi Keuangan Terhadap Perilaku Konsumtif", "abstrak": ABS_EN, "tahun": "0026",
         "link": H + "20", "penulis": "Eka", "fakultas": "Faculty of Economic and Business"},
        # placeholder abstrak
        {"judul": "Analisis Produksi Biogas", "abstrak": "Dosen Pembimbing Utama : - Dosen Pembimbing Anggota: -",
         "tahun": "2024", "link": H + "30", "penulis": "Fajar"},
        # tanpa link -> dilewati
        {"judul": "Tanpa Tautan", "abstrak": ABS_OTHER, "tahun": "2024", "link": ""},
    ]


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    init_db(engine)
    with Session(engine) as s:
        yield s


def by_link(session, n):
    return session.scalar(select(Document).where(Document.link == H + str(n)))


def test_ingest_merges_twins_and_flags_quality(tmp_path, session):
    path = tmp_path / "in.csv"
    write_csv(path, base_rows())
    rep = ingest_csv(session, path)

    assert rep.rows_read == 7 and rep.rows_skipped == 1
    assert rep.merged_groups == 1 and rep.merged_rows == 2
    assert session.query(Document).count() == 4

    main = by_link(session, 10)
    assert main.jumlah_gabungan == 3
    assert main.penulis == "Ani; Citra; Budi"  # urut handle 10, 11, 12
    assert main.kata_kunci == "kopi; pabrik"
    assert main.link_lain.splitlines() == [H + "11", H + "12"]
    assert by_link(session, 13).jumlah_gabungan == 1  # abstrak berbeda tidak digabung

    en = by_link(session, 20)
    assert en.bahasa_asli == "en" and en.bahasa_judul == "id"
    assert en.judul_id == en.judul_asli and en.abstrak_id is None
    assert en.tahun is None

    ph = by_link(session, 30)
    assert ph.abstrak_asli is None and ph.abstrak_tersedia is False


def test_ingest_is_idempotent_and_keeps_translations(tmp_path, session):
    path = tmp_path / "in.csv"
    write_csv(path, base_rows())
    ingest_csv(session, path)

    en = by_link(session, 20)
    en.abstrak_id = "Terjemahan hasil T3"
    session.commit()

    rep = ingest_csv(session, path)
    assert rep.inserted == 0 and rep.updated == 0 and rep.unchanged == 4
    assert by_link(session, 20).abstrak_id == "Terjemahan hasil T3"

    rows = base_rows()
    rows[4]["abstrak"] = ABS_EN + " Updated sentence about the results of this study."
    write_csv(path, rows)
    rep = ingest_csv(session, path)
    assert rep.updated == 1
    assert by_link(session, 20).abstrak_id is None  # teks sumber berubah -> terjemahan lama dibuang


def test_reingest_removes_rows_that_became_twins(tmp_path, session):
    """DB lama berisi dokumen 13 terpisah; setelah abstraknya ternyata kembar dokumen 10, baris 13 dilebur."""
    path = tmp_path / "in.csv"
    write_csv(path, base_rows())
    ingest_csv(session, path)
    assert by_link(session, 13) is not None

    rows = base_rows()
    rows[3]["abstrak"] = ABS_GROUP
    write_csv(path, rows)
    rep = ingest_csv(session, path)
    assert rep.removed == 1
    assert by_link(session, 13) is None
    assert H + "13" in by_link(session, 10).link_lain.splitlines()
