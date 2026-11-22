import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { HighlightedText } from "@/components/HighlightedText";
import { ScoreBadge } from "@/components/ResultCard";
import { SearchBox } from "@/components/SearchBox";
import { ApiError, apiGet, queryString } from "@/lib/api";
import { formatAuthors, formatPercent } from "@/lib/format";
import { param, type SearchParams } from "@/lib/params";
import type { CompareResponse, Method, SearchResult } from "@/lib/types";

export const metadata: Metadata = { title: "Mode Bandingkan" };

type Props = { searchParams: Promise<SearchParams> };

export default function ComparePage({ searchParams }: Props) {
  return (
    <Suspense fallback={<p className="p-8 text-center text-muted">Memuat perbandingan…</p>}>
      <Comparison searchParams={searchParams} />
    </Suspense>
  );
}

async function Comparison({ searchParams }: Props) {
  const q = param(await searchParams, "q");
  const data = q ? await apiGet<CompareResponse>(`/compare${queryString({ q })}`).catch((e: unknown) => e as Error) : null;

  return (
    <>
      <div className="border-b border-line bg-surface">
        <div className="mx-auto max-w-7xl space-y-3 px-4 py-4 sm:px-8">
          <nav aria-label="Breadcrumb" className="text-sm text-muted">
            <Link href="/" className="hover:underline">
              Pencarian
            </Link>{" "}
            › <span className="font-medium text-ink">Mode Bandingkan</span>
          </nav>
          <SearchBox key={q} initialQuery={q} initialMode="compare" variant="compact" />
        </div>
      </div>

      {!q && (
        <p className="mx-auto max-w-2xl px-4 py-16 text-center text-muted">
          Ketik kueri untuk melihat hasil BM25 dan IndoSBERT berdampingan. Dokumen yang muncul di kedua kolom akan
          ditandai.
        </p>
      )}
      {data instanceof Error && (
        <p className="mx-auto max-w-2xl px-4 py-16 text-center text-muted">
          {data instanceof ApiError ? data.message : "Server pencarian tidak dapat dihubungi."}
        </p>
      )}
      {data && !(data instanceof Error) && <CompareView data={data} />}
    </>
  );
}

function CompareView({ data }: { data: CompareResponse }) {
  return (
    <div className="mx-auto w-full max-w-7xl space-y-6 px-4 py-6 sm:px-8">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-lg border border-line bg-surface px-5 py-4 text-sm">
        <span className="flex items-center gap-2 font-semibold uppercase tracking-wider text-bm25">
          <span aria-hidden className="size-2.5 rounded-full bg-bm25" /> BM25 (Kata)
        </span>
        <span className="flex items-center gap-2 font-semibold uppercase tracking-wider text-sbert-dark">
          <span aria-hidden className="size-2.5 rounded-full bg-sbert-dark" /> IndoSBERT (Makna)
        </span>
        <span className="rounded bg-mark px-2 py-1 font-mono text-xs">Overlap {formatPercent(data.rasio_irisan)}</span>
        <span>
          <span className="font-semibold">
            {data.jumlah_irisan} dari {data.top_k}
          </span>{" "}
          dokumen teratas beririsan di kedua metode.
        </span>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Column method="bm25" title="Kata (BM25)" subtitle="Pencocokan leksikal · Okapi BM25" data={data} />
        <Column method="sbert" title="Makna (IndoSBERT)" subtitle={`Embedding semantik · ${data.model_sbert}`} data={data} />
      </div>
    </div>
  );
}

function Column({ method, title, subtitle, data }: { method: Method; title: string; subtitle: string; data: CompareResponse }) {
  const column = data[method];
  const other = method === "bm25" ? "IndoSBERT" : "BM25";
  return (
    <section aria-label={title} className="overflow-hidden rounded-lg border border-line bg-surface">
      <header className={`border-b-2 bg-mist px-5 py-4 ${method === "bm25" ? "border-bm25" : "border-sbert-dark"}`}>
        <h2 className="flex items-center gap-2 font-serif text-2xl">
          <span aria-hidden className={`size-3 rounded-full ${method === "bm25" ? "bg-bm25" : "bg-sbert-dark"}`} />
          {title}
        </h2>
        <p className="text-sm text-muted">
          {subtitle} · {column.took_ms.toLocaleString("id-ID")} ms
        </p>
      </header>
      {column.results.length === 0 ? (
        <p className="p-6 text-sm text-muted">Tidak ada dokumen yang memuat kata kueri.</p>
      ) : (
        <ol>
          {column.results.map((r) => (
            <CompareItem key={r.id} result={r} method={method} otherLabel={other} />
          ))}
        </ol>
      )}
    </section>
  );
}

function CompareItem({ result, method, otherLabel }: { result: SearchResult; method: Method; otherLabel: string }) {
  const overlap = result.peringkat_di_lawan;
  const accent = method === "bm25" ? "text-bm25" : "text-sbert-dark";
  return (
    <li className={`space-y-2 border-b border-line px-5 py-5 last:border-0 ${overlap ? "bg-mark/30" : ""}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className={`font-mono text-lg font-medium ${accent}`}>{String(result.rank).padStart(2, "0")}.</span>
        {overlap && (
          <span className="rounded border border-line bg-mark px-2 py-0.5 font-mono text-xs">
            Beririsan (#{overlap} di {otherLabel})
          </span>
        )}
        <span className="ml-auto">
          <ScoreBadge method={method} score={result.score} />
        </span>
      </div>
      <h3 className="font-serif text-lg leading-snug">
        <Link href={`/dokumen/${result.id}`} className="hover:underline">
          <HighlightedText value={result.judul_sorot} />
        </Link>
      </h3>
      {result.cuplikan.text && (
        <p className="line-clamp-3 text-sm text-muted">
          <HighlightedText value={result.cuplikan} />
        </p>
      )}
      <p className="flex flex-wrap justify-between gap-2 text-xs text-muted">
        <span>
          {formatAuthors(result.penulis, 2)} ({result.tahun ?? "-"}){result.fakultas ? ` · ${result.fakultas}` : ""}
        </span>
        {result.frekuensi_kata !== undefined && <span className="font-mono">Frekuensi kata kunci: {result.frekuensi_kata}×</span>}
      </p>
    </li>
  );
}
