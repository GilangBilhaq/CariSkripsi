import Link from "next/link";
import { displayLink, formatAuthors, formatDecimal } from "@/lib/format";
import type { Method, SearchResult } from "@/lib/types";
import { HighlightedText } from "./HighlightedText";
import { ExternalIcon } from "./icons";

/** Skor BM25 tidak terbatas (mis. 14,82); skor IndoSBERT adalah cosine similarity 0..1 (mis. 0,884). */
export function formatScore(method: Method, score: number): string {
  return method === "bm25" ? formatDecimal(score, 2) : formatDecimal(score, 3);
}

export function ScoreBadge({ method, score }: { method: Method; score: number }) {
  const style = method === "bm25" ? "border-bm25 bg-bm25-soft text-bm25" : "border-sbert bg-sbert-soft text-sbert-dark";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded border px-2 py-1 font-mono text-xs ${style}`}>
      <span aria-hidden className={`size-1.5 rounded-full ${method === "bm25" ? "bg-bm25" : "bg-sbert"}`} />
      {method === "bm25" ? "Skor BM25" : "Cosine"}: {formatScore(method, score)}
    </span>
  );
}

export function LanguageBadge({ result }: { result: Pick<SearchResult, "bahasa_asli" | "diterjemahkan"> }) {
  return (
    <span className="rounded bg-mist px-2 py-0.5 text-xs text-muted">
      {result.diterjemahkan ? "Bahasa asli: Inggris (diterjemahkan ke ID)" : "Bahasa asli: Indonesia"}
    </span>
  );
}

export function ResultCard({ result, method }: { result: SearchResult; method: Method }) {
  return (
    <article className="space-y-3 border-b border-line py-6 first:pt-2">
      <h2 className="font-serif text-xl leading-snug text-navy sm:text-2xl">
        <Link href={`/dokumen/${result.id}`} className="hover:underline">
          <HighlightedText value={result.judul_sorot} />
        </Link>
      </h2>

      <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted">
        <span className="max-w-full truncate font-mono text-xs text-bm25">{displayLink(result.link)}</span>
        <span aria-hidden>·</span>
        <span className="text-ink">{result.tahun ?? "Tahun tidak diketahui"}</span>
        <span aria-hidden>·</span>
        <span>Penulis: {formatAuthors(result.penulis)}</span>
        {result.fakultas && (
          <>
            <span aria-hidden>·</span>
            <span>{result.fakultas}</span>
          </>
        )}
        <LanguageBadge result={result} />
      </p>

      {result.cuplikan.text ? (
        <p className="leading-relaxed text-ink/90">
          <HighlightedText value={result.cuplikan} />
        </p>
      ) : (
        <p className="text-sm italic text-muted">Abstrak tidak tersedia. Dokumen ini ditemukan melalui judulnya.</p>
      )}

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <ScoreBadge method={method} score={result.score} />
        {result.frekuensi_kata !== undefined && (
          <span className="font-mono text-xs text-muted">Frekuensi kata kunci: {result.frekuensi_kata}×</span>
        )}
        <span className="ml-auto flex flex-wrap gap-x-5 gap-y-1 text-sm">
          <a
            href={result.link}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-bm25 hover:underline"
          >
            Buka di Repositori <ExternalIcon size={14} />
          </a>
          <Link href={`/dokumen/${result.id}`} className="text-navy hover:underline">
            Lihat Detail &amp; Dokumen Serupa ›
          </Link>
        </span>
      </div>
    </article>
  );
}
