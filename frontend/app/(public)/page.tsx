import Link from "next/link";
import { Suspense } from "react";
import { Logo } from "@/components/Logo";
import { SearchBox } from "@/components/SearchBox";
import { searchHref } from "@/lib/search-href";
import { apiGet } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import type { PublicStats } from "@/lib/types";

const EXAMPLE_QUERIES = [
  "energi biomassa",
  "klasifikasi sentimen ulasan aplikasi",
  "pengaruh pupuk organik terhadap tanaman padi",
  "deteksi penyakit daun tembakau",
  "kesehatan mental tenaga medis",
];

export default function HomePage() {
  return (
    <section className="flex flex-1 flex-col items-center justify-center gap-8 px-4 py-16 text-center sm:py-24">
      <div className="space-y-4">
        <h1>
          <Logo size="xl" />
        </h1>
        <p className="font-serif text-xl sm:text-2xl">Cari dengan kata, temukan dengan makna.</p>
        <p className="mx-auto max-w-2xl text-sm text-muted sm:text-base">
          Sistem Temu Kembali Skripsi Berbahasa Indonesia (BM25 vs IndoSBERT) · Universitas Jember
        </p>
      </div>

      <SearchBox variant="hero" autoFocus />

      <p className="-mt-4 max-w-2xl text-sm text-muted">
        <span className="font-medium text-bm25">Kata:</span> mencocokkan istilah persis (leksikal) ·{" "}
        <span className="font-medium text-sbert">Makna:</span> memahami arti kalimat dan konsep (semantik)
      </p>

      <div className="space-y-3">
        <p className="text-xs uppercase tracking-widest text-muted">Contoh kueri</p>
        <ul className="flex max-w-3xl flex-wrap justify-center gap-2">
          {EXAMPLE_QUERIES.map((q) => (
            <li key={q}>
              <Link
                href={searchHref(q, "bm25")}
                className="block rounded-md border border-line bg-surface px-4 py-2 text-sm hover:border-navy"
              >
                {q}
              </Link>
            </li>
          ))}
        </ul>
      </div>

      <Suspense fallback={<p className="text-sm text-muted">Memuat jumlah dokumen…</p>}>
        <IndexedCount />
      </Suspense>
    </section>
  );
}

async function IndexedCount() {
  const stats = await apiGet<PublicStats>("/stats").catch(() => null);
  if (!stats) return <p className="text-sm text-danger">Server pencarian tidak dapat dihubungi.</p>;
  if (!stats.dokumen_terindeks) return <p className="text-sm text-muted">Indeks pencarian belum dibangun.</p>;
  return (
    <p className="text-sm text-muted">
      <span className="font-mono font-medium text-ink">{formatNumber(stats.dokumen_terindeks)}</span> skripsi
      terindeks
      {!stats.semantik_siap && (
        <span className="mt-1 block text-warn">
          Pencarian Makna (IndoSBERT) sedang disiapkan; sementara gunakan pencarian Kata (BM25).
        </span>
      )}
    </p>
  );
}
