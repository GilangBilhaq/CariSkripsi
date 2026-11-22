// Format angka, waktu, dan label untuk tampilan berbahasa Indonesia.
import type { Method, QueryCategory } from "./types";

const numberFmt = new Intl.NumberFormat("id-ID");

export function formatNumber(n: number): string {
  return numberFmt.format(n);
}

/** 0.6812 -> "0,681" */
export function formatDecimal(n: number, digits = 3): string {
  return n.toLocaleString("id-ID", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/** 0.4 -> "40%" */
export function formatPercent(ratio: number, digits = 0): string {
  return `${(ratio * 100).toLocaleString("id-ID", { maximumFractionDigits: digits })}%`;
}

/** Waktu UTC dari backend ("2026-11-21T05:30:00Z") -> "21 Nov 2026, 12.30 WIB" */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "-";
  const date = new Date(iso);
  return `${date.toLocaleString("id-ID", {
    timeZone: "Asia/Jakarta",
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })} WIB`;
}

export const METHOD_LABEL: Record<Method, string> = { bm25: "Kata (BM25)", sbert: "Makna (IndoSBERT)" };
export const METHOD_SHORT: Record<Method, string> = { bm25: "BM25", sbert: "IndoSBERT" };

export const LANGUAGE_LABEL: Record<string, string> = { id: "Indonesia", en: "Inggris", lain: "Lainnya" };

export const CATEGORY_LABEL: Record<QueryCategory, string> = {
  kata_kunci: "Kata kunci",
  deskriptif: "Deskriptif",
  parafrase: "Parafrase",
};

/** ["A", "B", "C", "D"] -> "A, B, C, dkk." */
export function formatAuthors(authors: string[], max = 3): string {
  if (authors.length === 0) return "Penulis tidak tercantum";
  return authors.length > max ? `${authors.slice(0, max).join(", ")}, dkk.` : authors.join(", ");
}

/** Tautan repositori untuk ditampilkan: tanpa skema "https://". */
export function displayLink(link: string): string {
  return link.replace(/^https?:\/\//, "");
}
