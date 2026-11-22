import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { FilterPanel } from "@/components/FilterPanel";
import { CompareIcon, SwapIcon } from "@/components/icons";
import { Pagination } from "@/components/Pagination";
import { ResultCard } from "@/components/ResultCard";
import { SearchBox } from "@/components/SearchBox";
import { searchHref } from "@/lib/search-href";
import { ApiError, apiGet, queryString } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import { param, parseMethod, parsePage, type SearchParams, yearOptions, yearRange } from "@/lib/params";
import type { Method, PublicStats, SearchResponse } from "@/lib/types";

export const metadata: Metadata = { title: "Hasil Pencarian" };

type Props = { searchParams: Promise<SearchParams> };

export default function SearchPage({ searchParams }: Props) {
  return (
    <Suspense fallback={<ResultsSkeleton />}>
      <SearchResults searchParams={searchParams} />
    </Suspense>
  );
}

async function SearchResults({ searchParams }: Props) {
  const sp = await searchParams;
  const q = param(sp, "q");
  const method = parseMethod(param(sp, "metode"));
  const page = parsePage(param(sp, "hal"));
  const filters = { tahun: param(sp, "tahun"), abstrak: param(sp, "abstrak"), bahasa: param(sp, "bahasa") };

  const apiQuery = queryString({
    q,
    method,
    page,
    ...yearRange(filters.tahun),
    lang: filters.bahasa === "id" || filters.bahasa === "en" ? filters.bahasa : undefined,
    has_abstract: filters.abstrak === "ada" ? true : filters.abstrak === "tidak" ? false : undefined,
  });
  const [data, stats] = await Promise.all([
    apiGet<SearchResponse>(`/search${apiQuery}`).catch((e: unknown) => e as Error),
    apiGet<PublicStats>("/stats").catch(() => null),
  ]);
  const hrefForPage = (p: number) => `/cari${queryString({ q, metode: method, ...filters, hal: p > 1 ? p : undefined })}`;

  return (
    <>
      <div className="border-b border-line bg-surface">
        <div className="mx-auto max-w-7xl px-4 py-4 sm:px-8">
          <SearchBox key={`${q}-${method}`} initialQuery={q} initialMode={method} variant="compact" />
        </div>
      </div>

      {data instanceof Error ? (
        <ErrorState error={data} query={q} method={method} />
      ) : (
        <>
          <InfoBar data={data} />
          <div className="mx-auto grid w-full max-w-7xl gap-8 px-4 py-8 sm:px-8 lg:grid-cols-[280px_1fr]">
            <div>
              <FilterPanel yearOptions={yearOptions(stats?.tahun.map((t) => t.tahun) ?? [])} />
            </div>
            <section aria-label="Hasil pencarian" className="min-w-0">
              <p className="border-b border-line pb-3 text-sm text-muted">
                Diurutkan berdasarkan{" "}
                <span className="font-medium text-ink">
                  {method === "bm25" ? "skor relevansi leksikal (BM25 tertinggi)" : "kemiripan makna (cosine tertinggi)"}
                </span>
              </p>
              {data.results.length === 0 ? (
                <EmptyState query={q} method={method} />
              ) : (
                <>
                  {data.results.map((r) => (
                    <ResultCard key={r.id} result={r} method={method} />
                  ))}
                  <div className="flex flex-wrap items-center justify-between gap-4 pt-6">
                    <p className="text-sm text-muted">
                      Menampilkan {(page - 1) * data.page_size + 1}–{(page - 1) * data.page_size + data.results.length} dari{" "}
                      {data.total} hasil teratas (halaman {page} dari {data.pages})
                    </p>
                    <Pagination page={page} pages={data.pages} hrefFor={hrefForPage} />
                  </div>
                </>
              )}
            </section>
          </div>
        </>
      )}
    </>
  );
}

function InfoBar({ data }: { data: SearchResponse }) {
  const other: Method = data.method === "bm25" ? "sbert" : "bm25";
  const found =
    data.method === "bm25"
      ? `${formatNumber(data.total_cocok)} dokumen memuat kata kueri`
      : `${data.total} dokumen paling mirip maknanya`;
  return (
    <div className="border-b border-line bg-mist">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 text-sm sm:px-8">
        <p>
          <span className="font-semibold">{found}</span>
          <span className="text-muted"> · Metode: </span>
          <span className={data.method === "bm25" ? "text-bm25" : "text-sbert"}>
            {data.method === "bm25" ? "Kata / BM25" : "Makna / IndoSBERT"}
          </span>
          <span className="text-muted"> · {data.took_ms.toLocaleString("id-ID")} ms</span>
        </p>
        <div className="ml-auto flex flex-wrap gap-2">
          <Link
            href={searchHref(data.query, other)}
            className="inline-flex items-center gap-1.5 rounded-md border border-line bg-surface px-3 py-1.5 hover:border-navy"
          >
            <SwapIcon size={14} /> Alihkan ke {other === "bm25" ? "Kata" : "Makna"}
          </Link>
          <Link
            href={searchHref(data.query, "compare")}
            className="inline-flex items-center gap-1.5 rounded-md border border-line bg-surface px-3 py-1.5 hover:border-navy"
          >
            <CompareIcon size={14} /> Bandingkan Kedua Metode
          </Link>
        </div>
      </div>
    </div>
  );
}

function EmptyState({ query, method }: { query: string; method: Method }) {
  return (
    <div className="py-12 text-center">
      <p className="font-serif text-xl">Tidak ada dokumen yang cocok untuk “{query}”.</p>
      <p className="mt-2 text-sm text-muted">
        {method === "bm25"
          ? "BM25 hanya menemukan dokumen yang memuat kata kueri. Coba kata lain, kurangi filter, atau gunakan pencarian Makna."
          : "Coba kurangi filter atau ubah kueri."}
      </p>
      {method === "bm25" && (
        <Link href={searchHref(query, "sbert")} className="mt-4 inline-block rounded-md bg-navy px-4 py-2 text-sm text-white">
          Cari dengan Makna (IndoSBERT)
        </Link>
      )}
    </div>
  );
}

function ErrorState({ error, query, method }: { error: Error; query: string; method: Method }) {
  const status = error instanceof ApiError ? error.status : 0;
  // 503 untuk IndoSBERT = embedding masih dihitung; BM25 biasanya sudah bisa dipakai.
  const offerBm25 = status === 503 && method === "sbert" && query.length >= 2;
  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-16 text-center">
      <p className="font-serif text-xl">{status === 422 ? "Kueri belum bisa diproses" : "Pencarian sedang tidak tersedia"}</p>
      <p className="mt-2 text-muted">
        {status ? error.message : "Server pencarian tidak dapat dihubungi. Pastikan backend sedang berjalan."}
      </p>
      {offerBm25 && (
        <Link href={searchHref(query, "bm25")} className="mt-4 inline-block rounded-md bg-navy px-4 py-2 text-sm text-white">
          Cari dengan Kata (BM25)
        </Link>
      )}
    </div>
  );
}

function ResultsSkeleton() {
  return (
    <div className="mx-auto w-full max-w-7xl space-y-6 px-4 py-8 sm:px-8" aria-busy="true" aria-label="Memuat hasil">
      <div className="h-14 animate-pulse rounded-lg bg-mist" />
      {[0, 1, 2].map((i) => (
        <div key={i} className="space-y-3">
          <div className="h-6 w-3/4 animate-pulse rounded bg-mist" />
          <div className="h-4 w-1/2 animate-pulse rounded bg-mist" />
          <div className="h-16 animate-pulse rounded bg-mist" />
        </div>
      ))}
    </div>
  );
}
