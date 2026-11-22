"""
Harvester metadata Repository Universitas Jember (DSpace 9 REST API).

Mengambil metadata (judul, abstrak, tahun, tautan, penulis, kata kunci) dari
repository.unej.ac.id melalui REST API DSpace, lalu menyimpannya sebagai CSV
yang formatnya sesuai template import PRD CariSkripsi.

Catatan: endpoint OAI-PMH repositori UNEJ (/server/oai/request) aktif tetapi
indeksnya kosong (noRecordsMatch), sehingga skrip ini memakai REST API.

Contoh pemakaian:
    python scripts/harvest_unej.py                  # semua skripsi (15 fakultas)
    python scripts/harvest_unej.py --scope all      # seluruh koleksi repositori
    python scripts/harvest_unej.py --limit 200      # uji coba: maks. 200 item per koleksi
    python scripts/harvest_unej.py --fresh          # abaikan checkpoint, mulai dari awal

Skrip bisa dihentikan dan dijalankan ulang: koleksi yang sudah selesai dilewati.
Hanya metadata yang diambil (tanpa file PDF).
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import requests

BASE_API = "https://repository.unej.ac.id/server/api"
SKRIPSI_COMMUNITY = "add8fd04-a225-4b74-bfc6-bb13373250f0"  # UNDERGRADUATE THESES (handle 123456789/3)
PAGE_SIZE = 100  # maksimum page size DSpace
USER_AGENT = "Mozilla/5.0 (compatible; academic-ir-harvester/1.0)"

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"

# Kolom template import PRD (Lampiran A) di depan, kolom tambahan di belakang.
CSV_COLUMNS = [
    "judul", "abstrak", "tahun", "link", "penulis", "program_studi",
    "fakultas", "koleksi", "kata_kunci", "bahasa", "abstrak_lain",
    "tanggal_terbit", "handle", "uuid",
]

ID_WORDS = {"yang", "dan", "di", "ini", "dengan", "untuk", "dari", "pada", "dalam",
            "adalah", "tersebut", "penelitian", "terhadap", "secara", "oleh", "akan"}
EN_WORDS = {"the", "of", "and", "this", "is", "to", "in", "with", "that", "was",
            "were", "are", "research", "study", "by", "from", "results"}
WORD_RE = re.compile(r"[a-zA-Z]+")


# --------------------------------------------------------------------------- HTTP

class Client:
    def __init__(self, delay: float, timeout: int = 90, retries: int = 5):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
        self.delay, self.timeout, self.retries = delay, timeout, retries
        self._last = 0.0

    def get(self, path: str, **params) -> dict:
        url = path if path.startswith("http") else f"{BASE_API}{path}"
        for attempt in range(1, self.retries + 1):
            wait = self.delay - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            try:
                r = self.s.get(url, params=params, timeout=self.timeout)
                if r.status_code == 200:
                    return r.json()
                if r.status_code in (429, 500, 502, 503, 504):
                    raise requests.HTTPError(f"HTTP {r.status_code}")
                r.raise_for_status()
            except (requests.RequestException, ValueError) as e:
                if attempt == self.retries:
                    raise
                backoff = min(60, 2 ** attempt * 2)
                log(f"  ! {e} -> coba lagi {attempt}/{self.retries} dalam {backoff}s")
                time.sleep(backoff)
        raise RuntimeError("unreachable")


# --------------------------------------------------------------------------- utils

def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def clean(text: str | None) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def detect_lang(text: str) -> str:
    words = [w.lower() for w in WORD_RE.findall(text)]
    if len(words) < 5:
        return "lain"
    id_n = sum(w in ID_WORDS for w in words)
    en_n = sum(w in EN_WORDS for w in words)
    if id_n == en_n == 0:
        return "lain"
    return "id" if id_n >= en_n else "en"


def values(md: dict, key: str) -> list[str]:
    return [clean(v.get("value")) for v in md.get(key, []) if clean(v.get("value"))]


def faculty_name(collection_name: str) -> str:
    # "UT-Faculty of Computer Science" -> "Faculty of Computer Science"
    return re.sub(r"^[A-Z]{1,4}\s*-\s*", "", collection_name).strip()


# --------------------------------------------------------------------------- harvest

def list_collections(client: Client, scope: str) -> list[dict]:
    path = (f"/core/communities/{SKRIPSI_COMMUNITY}/collections" if scope == "skripsi"
            else "/core/collections")
    out, page = [], 0
    while True:
        d = client.get(path, size=100, page=page)
        out += [{"uuid": c["uuid"], "name": c["name"], "handle": c.get("handle")}
                for c in d.get("_embedded", {}).get("collections", [])]
        info = d.get("page", {})
        if page + 1 >= info.get("totalPages", 1):
            return out
        page += 1


def harvest_collection(client: Client, coll: dict, limit: int | None) -> tuple[int, int]:
    """Simpan item satu koleksi ke data/raw/<uuid>.jsonl. Mengembalikan (jumlah, total)."""
    tmp = RAW_DIR / f"{coll['uuid']}.jsonl.part"
    n, page, total = 0, 0, None
    with tmp.open("w", encoding="utf-8") as f:
        while True:
            d = client.get("/discover/search/objects", scope=coll["uuid"], dsoType="ITEM",
                           size=PAGE_SIZE, page=page, sort="dc.date.accessioned,ASC")
            res = d["_embedded"]["searchResult"]
            total = res["page"]["totalElements"]
            objs = res.get("_embedded", {}).get("objects", [])
            for o in objs:
                it = o["_embedded"]["indexableObject"]
                f.write(json.dumps({"uuid": it["uuid"], "handle": it.get("handle"),
                                    "collection": coll["name"], "metadata": it["metadata"]},
                                   ensure_ascii=False) + "\n")
                n += 1
                if limit and n >= limit:
                    break
            if limit and n >= limit:
                break
            if not objs or page + 1 >= res["page"]["totalPages"]:
                break
            page += 1
            if page % 10 == 0:
                log(f"    {coll['name']}: {n}/{total}")
    tmp.replace(RAW_DIR / f"{coll['uuid']}.jsonl")
    return n, total or 0


def to_row(rec: dict) -> dict:
    md = rec["metadata"]
    abstracts = values(md, "dc.description.abstract")
    # Pilih abstrak berbahasa Indonesia bila ada lebih dari satu (mis. versi ID dan EN).
    langs = [detect_lang(a) for a in abstracts]
    main_i = langs.index("id") if "id" in langs else 0
    abstrak = abstracts[main_i] if abstracts else ""
    lain = [a for i, a in enumerate(abstracts) if i != main_i]

    issued = (values(md, "dc.date.issued") or [""])[0]
    m = re.match(r"(\d{4})", issued)
    uri = (values(md, "dc.identifier.uri") or [""])[0]
    if not uri and rec.get("handle"):
        uri = f"https://repository.unej.ac.id/handle/{rec['handle']}"
    judul = (values(md, "dc.title") or [""])[0]

    return {
        "judul": judul,
        "abstrak": abstrak,
        "tahun": m.group(1) if m else "",
        "link": uri,
        "penulis": "; ".join(values(md, "dc.contributor.author")),
        "program_studi": "",  # tidak tersedia sebagai field di repositori
        "fakultas": faculty_name(rec["collection"]),
        "koleksi": rec["collection"],
        "kata_kunci": "; ".join(values(md, "dc.subject")),
        "bahasa": detect_lang(abstrak or judul),
        "abstrak_lain": " ||| ".join(lain),
        "tanggal_terbit": issued,
        "handle": rec.get("handle") or "",
        "uuid": rec["uuid"],
    }


def norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


# --------------------------------------------------------------------------- output

def build_outputs(collections: list[dict], counts: dict, out_name: str) -> None:
    rows, seen = [], set()
    dup_uuid = 0
    for c in collections:
        p = RAW_DIR / f"{c['uuid']}.jsonl"
        if not p.exists():
            continue
        for line in p.open(encoding="utf-8"):
            rec = json.loads(line)
            if rec["uuid"] in seen:  # item yang dipetakan ke >1 koleksi
                dup_uuid += 1
                continue
            seen.add(rec["uuid"])
            rows.append(to_row(rec))

    out_csv = DATA_DIR / out_name
    # utf-8-sig agar terbaca benar di Excel; tetap valid UTF-8 untuk pandas.
    with out_csv.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        w.writeheader()
        w.writerows(rows)

    # ---- laporan kualitas
    n = len(rows)
    this_year = datetime.now().year
    no_abs = sum(1 for r in rows if len(r["abstrak"]) < 50)
    bad_year = sum(1 for r in rows if not r["tahun"] or not 1990 <= int(r["tahun"]) <= this_year + 1)
    no_link = sum(1 for r in rows if not r["link"])
    t_counts = Counter(norm_title(r["judul"]) for r in rows if r["judul"])
    dup_title = sum(c - 1 for c in t_counts.values() if c > 1)
    l_counts = Counter(r["link"] for r in rows if r["link"])
    dup_link = sum(c - 1 for c in l_counts.values() if c > 1)
    lens = sorted(len(r["abstrak"]) for r in rows) or [0]

    lines = [
        f"# Laporan Kualitas Data Harvest UNEJ",
        f"",
        f"- Waktu: {datetime.now():%Y-%m-%d %H:%M}",
        f"- Sumber: {BASE_API} (DSpace REST API)",
        f"- File: data/{out_name}",
        f"",
        f"## Ringkasan",
        f"",
        f"| Aspek | Jumlah |",
        f"| --- | --- |",
        f"| Total dokumen unik | {n} |",
        f"| Item ganda antar-koleksi (dibuang) | {dup_uuid} |",
        f"| Abstrak kosong/sangat pendek (<50 karakter) | {no_abs} |",
        f"| Tahun kosong/di luar 1990-{this_year + 1} | {bad_year} |",
        f"| Link kosong | {no_link} |",
        f"| Judul duplikat (ternormalisasi) | {dup_title} |",
        f"| Link duplikat | {dup_link} |",
        f"| Panjang abstrak median (karakter) | {lens[len(lens) // 2]} |",
        f"| Dokumen dengan >1 abstrak | {sum(1 for r in rows if r['abstrak_lain'])} |",
        f"",
        f"## Bahasa (deteksi heuristik)",
        f"",
        f"| Bahasa | Jumlah | % |",
        f"| --- | --- | --- |",
    ]
    for k, v in Counter(r["bahasa"] for r in rows).most_common():
        lines.append(f"| {k} | {v} | {v / max(n, 1) * 100:.1f} |")
    lines += ["", "## Per Koleksi/Fakultas", "", "| Koleksi | Dipanen | Total di API |", "| --- | --- | --- |"]
    for c in collections:
        got, tot = counts.get(c["uuid"], (0, 0))
        lines.append(f"| {c['name']} | {got} | {tot} |")
    lines += ["", "## Per Tahun", "", "| Tahun | Jumlah |", "| --- | --- |"]
    for k, v in sorted(Counter(r["tahun"] or "(kosong)" for r in rows).items()):
        lines.append(f"| {k} | {v} |")

    report = DATA_DIR / (Path(out_name).stem + "_laporan.md")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"CSV     : {out_csv}  ({n} baris)")
    log(f"Laporan : {report}")


# --------------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scope", choices=["skripsi", "all"], default="skripsi",
                    help="skripsi = Koleksi Skripsi Sarjana (default); all = seluruh repositori")
    ap.add_argument("--delay", type=float, default=1.0, help="jeda antar-permintaan (detik), default 1.0")
    ap.add_argument("--limit", type=int, default=None, help="maks. item per koleksi (untuk uji coba)")
    ap.add_argument("--fresh", action="store_true", help="hapus checkpoint dan mulai dari awal")
    ap.add_argument("--output", default=None, help="nama file CSV output di folder data/")
    args = ap.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    state_path = RAW_DIR / f"_state_{args.scope}.json"
    if args.fresh and state_path.exists():
        state_path.unlink()
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    # Checkpoint dari mode --limit tidak boleh dipakai untuk harvest penuh, begitu juga sebaliknya.
    if state.get("limit") != args.limit:
        state = {"limit": args.limit, "done": {}}

    client = Client(delay=args.delay)
    log(f"Mengambil daftar koleksi (scope={args.scope}) ...")
    collections = list_collections(client, args.scope)
    log(f"{len(collections)} koleksi ditemukan")

    t0 = time.monotonic()
    for i, c in enumerate(collections, 1):
        if c["uuid"] in state["done"] and (RAW_DIR / f"{c['uuid']}.jsonl").exists():
            got, tot = state["done"][c["uuid"]]
            log(f"[{i}/{len(collections)}] {c['name']}: dilewati (checkpoint, {got} item)")
            continue
        log(f"[{i}/{len(collections)}] {c['name']} ...")
        got, tot = harvest_collection(client, c, args.limit)
        state["done"][c["uuid"]] = [got, tot]
        state_path.write_text(json.dumps(state, indent=1), encoding="utf-8")
        flag = "" if args.limit or got == tot else f"  (PERHATIAN: total API {tot})"
        log(f"    selesai: {got} item{flag}")

    log(f"Harvest selesai dalam {(time.monotonic() - t0) / 60:.1f} menit. Menyusun CSV ...")
    out_name = args.output or ("skripsi_unej.csv" if args.scope == "skripsi" else "repo_unej_all.csv")
    if args.limit:
        out_name = out_name.replace(".csv", f"_sample{args.limit}.csv")
    build_outputs(collections, {k: tuple(v) for k, v in state["done"].items()}, out_name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
