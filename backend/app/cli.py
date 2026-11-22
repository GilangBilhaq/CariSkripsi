"""Perintah baris: python -m app.cli <perintah> ..."""

import argparse
import sys
import time
from pathlib import Path

from app.db import SessionLocal, init_db


def cmd_ingest(args: argparse.Namespace) -> int:
    from app.data.ingest import ingest_csv

    path = Path(args.csv)
    if not path.exists():
        print(f"File tidak ditemukan: {path}", file=sys.stderr)
        return 1
    init_db()
    t0 = time.monotonic()
    with SessionLocal() as session:
        report = ingest_csv(session, path)
    print("\n".join(report.lines()))
    print(f"Selesai dalam {time.monotonic() - t0:.1f} detik")
    return 0


def cmd_translate(args: argparse.Namespace) -> int:
    from app.data.translate import MarianTranslator, count_pending, translate_pending

    init_db()
    with SessionLocal() as session:
        pending = count_pending(session)
        print(f"Dokumen menunggu terjemahan: {pending}")
        if not pending:
            return 0
        print(f"Memuat model (beams={args.beams}) ...")
        translator = MarianTranslator(beams=args.beams, batch_size=args.batch, threads=args.threads)

        def progress(stats, total):
            eta = stats.sec_per_doc * (total - stats.documents) / 60
            print(f"  {stats.documents}/{total} dok | {stats.sentences} kalimat | "
                  f"{stats.sec_per_doc:.2f} s/dok | sisa ~{eta:.0f} menit", flush=True)

        limit = args.benchmark or args.limit
        stats = translate_pending(session, translator, limit=limit, commit=not args.benchmark, progress=progress)

    print(f"Selesai: {stats.documents} dokumen ({stats.titles} judul, {stats.abstracts} abstrak, "
          f"{stats.sentences} kalimat) dalam {stats.seconds / 60:.1f} menit")
    if args.benchmark:
        print(f"[BENCHMARK, tidak disimpan] {stats.sec_per_doc:.2f} s/dokumen -> "
              f"perkiraan total {stats.sec_per_doc * pending / 3600:.1f} jam untuk {pending} dokumen")
    return 0


def cmd_translate_sample(args: argparse.Namespace) -> int:
    import csv
    import random

    from sqlalchemy import or_, select

    from app import config
    from app.models import Document

    with SessionLocal() as session:
        docs = session.scalars(select(Document).where(
            or_(Document.bahasa_asli == "en", Document.bahasa_judul == "en"),
            Document.judul_id.is_not(None),
        ).order_by(Document.id)).all()
    docs = [d for d in docs if d.abstrak_id or not d.abstrak_tersedia]
    random.Random(42).shuffle(docs)
    out = config.DATA_DIR / "sampel_terjemahan.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "link", "judul_asli", "judul_id", "abstrak_asli", "abstrak_id", "penilaian (baik/cukup/buruk)"])
        for d in docs[:args.n]:
            w.writerow([d.id, d.link, d.judul_asli, d.judul_id, d.abstrak_asli or "", d.abstrak_id or "", ""])
    print(f"{min(args.n, len(docs))} sampel ditulis ke {out}")
    return 0


def cmd_build_index(args: argparse.Namespace) -> int:
    from app.search.index_manager import IndexManager

    init_db()
    manager = IndexManager(SessionLocal)
    t0 = time.monotonic()
    versi = manager.rebuild_now(translate=not args.no_translate)
    print(f"Indeks {versi} aktif: {manager.active.size} dokumen, {(time.monotonic() - t0) / 60:.1f} menit")
    print("Restart server backend (atau klik 'Bangun Ulang Indeks' di admin) agar server memakai indeks ini.")
    return 0


def cmd_create_admin(args: argparse.Namespace) -> int:
    import getpass

    from sqlalchemy import select

    from app.models import Admin
    from app.security import hash_password

    init_db()
    password = args.password or getpass.getpass("Kata sandi baru: ")
    if len(password) < 8:
        print("Kata sandi minimal 8 karakter.", file=sys.stderr)
        return 1
    with SessionLocal() as session:
        admin = session.scalar(select(Admin).where(Admin.username == args.username))
        if admin is None:
            session.add(Admin(username=args.username, password_hash=hash_password(password)))
            print(f"Admin '{args.username}' dibuat.")
        else:
            admin.password_hash = hash_password(password)
            print(f"Kata sandi admin '{args.username}' diganti.")
        session.commit()
    return 0


def _load_manager():
    from app.search.index_manager import IndexManager

    manager = IndexManager(SessionLocal)
    manager.load_active()
    if manager.active is None or not manager.active.has_semantic:
        print("Belum ada indeks aktif. Jalankan dulu: python -m app.cli build-index", file=sys.stderr)
        sys.exit(1)
    return manager


def cmd_eval(args: argparse.Namespace) -> int:
    from app.eval.runner import run_evaluation

    init_db()
    manager = _load_manager()
    with SessionLocal() as session:
        try:
            run = run_evaluation(session, manager.active, manager.encoder)
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 1
    s, k = run.ringkasan, run.k
    print(f"Evaluasi #{run.id} | indeks {run.index_versi} | {run.jumlah_kueri} kueri | model {run.model_name}")
    print(f"{'Metode':<10} {'P@' + str(k):>7} {'R@' + str(k):>7} {'MAP':>7} {'nDCG@' + str(k):>8} "
          f"{'rata ms':>9} {'p95 ms':>8}")
    for m, label in (("bm25", "BM25"), ("sbert", "IndoSBERT")):
        x = s[m]
        print(f"{label:<10} {x['p_at_k']:>7.3f} {x['r_at_k']:>7.3f} {x['map']:>7.3f} {x['ndcg_at_k']:>8.3f} "
              f"{x['waktu_rata_ms']:>9.1f} {x['waktu_p95_ms']:>8.1f}")
    kappa = s["kesepakatan"]["kappa"]
    print(f"Menang (nDCG): {s['menang']} | Cohen's kappa: {'-' if kappa is None else f'{kappa:.3f}'} "
          f"| penilaian berbeda belum diselesaikan: {s['belum_diselesaikan']}")
    return 0


def cmd_seed_eval_queries(args: argparse.Namespace) -> int:
    from sqlalchemy import func, select

    from app.eval.draft_queries import DRAFT_QUERIES
    from app.models import EvalQuery

    init_db()
    with SessionLocal() as session:
        if session.scalar(select(func.count(EvalQuery.id))):
            print("Tabel kueri uji sudah berisi data; draf tidak dimuat agar tidak menimpa pekerjaan tim.")
            return 1
        session.add_all(EvalQuery(teks=t, kategori=k, catatan=c) for t, k, c in DRAFT_QUERIES)
        session.commit()
    print(f"{len(DRAFT_QUERIES)} draf kueri uji dimuat. Tinjau di Admin -> Evaluasi Model -> Kueri Uji & Penilaian.")
    return 0


def cmd_benchmark_search(args: argparse.Namespace) -> int:
    """Ukur latensi pencarian (rata-rata dan p95) untuk sekumpulan kueri contoh (PRD §9 Kinerja)."""
    from app.eval.metrics import percentile
    from app.search.service import rank

    manager = _load_manager()
    queries = [
        "energi biomassa", "stres kerja perawat", "klasifikasi sentimen ulasan aplikasi", "pupuk organik padi",
        "deteksi penyakit daun tembakau", "kesehatan mental tenaga medis", "literasi keuangan mahasiswa",
        "pembelajaran daring sekolah dasar", "kualitas air sungai", "sistem informasi akademik",
        "pengaruh media sosial terhadap minat beli", "hukum perlindungan konsumen", "budidaya ikan lele",
        "analisis kelayakan usaha kopi", "perilaku merokok remaja", "struktur jembatan beton",
        "kinerja keuangan bank syariah", "tradisi lisan masyarakat osing", "jaringan saraf tiruan", "diabetes melitus",
    ]
    manager.encoder.encode_query("pemanasan")  # muat model dulu agar tidak ikut terukur
    for method in ("bm25", "sbert"):
        times = [rank(manager.active, manager.encoder, method, q).took_ms for q in queries for _ in range(args.repeat)]
        print(f"{method:<6} n={len(times)} rata-rata {sum(times) / len(times):7.1f} ms | "
              f"p95 {percentile(times, 95):7.1f} ms | maks {max(times):7.1f} ms")
    return 0


def cmd_migrate_db(args: argparse.Namespace) -> int:
    from app import config
    from app.data.migrate import copy_database

    source = config.normalize_database_url(args.dari or config.DATABASE_URL)
    target = config.normalize_database_url(args.ke)
    try:
        counts = copy_database(source, target, replace=args.ganti)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"Selesai: {sum(counts.values())} baris disalin ke database tujuan.")
    print("PENTING: ganti kata sandi admin di database tujuan, mis.:")
    print("  CARISKRIPSI_DATABASE_URL=<url> python -m app.cli create-admin admin")
    return 0


def cmd_upload_index(args: argparse.Namespace) -> int:
    from sqlalchemy import select

    from app.models import IndexVersion
    from app.search.index_manager import IndexManager
    from app.search.index_store import SupabaseStore

    manager = IndexManager(SessionLocal)
    if manager.store is None:
        print("Isi env SUPABASE_URL dan SUPABASE_SERVICE_KEY terlebih dahulu.", file=sys.stderr)
        return 1
    with SessionLocal() as session:
        versi = session.scalar(select(IndexVersion.versi).where(IndexVersion.status == "active"))
    if versi is None or not (manager.index_dir / versi / "meta.json").exists():
        print("Tidak ada indeks aktif di folder lokal. Jalankan dulu: python -m app.cli build-index", file=sys.stderr)
        return 1
    if isinstance(manager.store, SupabaseStore):
        manager.store.ensure_bucket()
    manager.upload_to_store(versi)
    print(f"Indeks {versi} dan cache embedding sudah diunggah ke penyimpanan cadangan.")
    return 0


def main(argv: list[str] | None = None) -> int:
    import logging

    # Tampilkan progres (mis. pembangunan indeks) di terminal.
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Perintah pengelolaan CariSkripsi")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("ingest", help="Masukkan CSV hasil harvest ke database (idempoten)")
    p.add_argument("csv", help="path CSV, mis. ../data/skripsi_unej.csv")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("translate", help="Terjemahkan judul/abstrak berbahasa Inggris ke Indonesia (resumable)")
    p.add_argument("--benchmark", type=int, metavar="N", help="uji kecepatan pada N dokumen tanpa menyimpan")
    p.add_argument("--limit", type=int, help="maksimum dokumen yang diproses")
    p.add_argument("--beams", type=int, default=1, help="beam search (1 = greedy, tercepat)")
    p.add_argument("--batch", type=int, default=16, help="kalimat per batch model")
    p.add_argument("--threads", type=int, default=4, help="thread CPU untuk torch")
    p.set_defaults(func=cmd_translate)

    p = sub.add_parser("translate-sample", help="Ekspor sampel terjemahan untuk dicek manual")
    p.add_argument("-n", type=int, default=30)
    p.set_defaults(func=cmd_translate_sample)

    p = sub.add_parser("build-index", help="Bangun indeks BM25 + IndoSBERT dan jadikan aktif")
    p.add_argument("--no-translate", action="store_true", help="lewati terjemahan dokumen Inggris yang tertunda")
    p.set_defaults(func=cmd_build_index)

    p = sub.add_parser("create-admin", help="Buat admin baru atau ganti kata sandinya")
    p.add_argument("username")
    p.add_argument("--password", help="kata sandi (tanpa opsi ini akan ditanyakan)")
    p.set_defaults(func=cmd_create_admin)

    p = sub.add_parser("eval", help="Jalankan evaluasi BM25 vs IndoSBERT pada kueri uji yang sudah dinilai")
    p.set_defaults(func=cmd_eval)

    p = sub.add_parser("seed-eval-queries", help="Muat draf 15 kueri uji (hanya bila belum ada kueri)")
    p.set_defaults(func=cmd_seed_eval_queries)

    p = sub.add_parser("benchmark-search", help="Ukur latensi pencarian kedua metode")
    p.add_argument("--repeat", type=int, default=3)
    p.set_defaults(func=cmd_benchmark_search)

    p = sub.add_parser("migrate-db", help="Salin seluruh database ke database lain (mis. SQLite -> Supabase)")
    p.add_argument("--ke", required=True, metavar="URL", help="URL database tujuan, mis. postgresql://...")
    p.add_argument("--dari", metavar="URL", help="URL database sumber (bawaan: database yang sedang dipakai)")
    p.add_argument("--ganti", action="store_true", help="kosongkan database tujuan lebih dulu (data di sana HILANG)")
    p.set_defaults(func=cmd_migrate_db)

    p = sub.add_parser("upload-index", help="Unggah indeks aktif + cache embedding ke Supabase Storage")
    p.set_defaults(func=cmd_upload_index)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
