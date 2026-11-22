// Membaca parameter URL halaman publik.
import type { YearOption } from "@/components/FilterPanel";
import type { Method } from "./types";

export type SearchParams = Record<string, string | string[] | undefined>;

/** Ambil satu nilai string dari searchParams (?a=1&a=2 -> "1"). */
export function param(sp: SearchParams, key: string): string {
  const v = sp[key];
  return (Array.isArray(v) ? v[0] : v) ?? "";
}

export function parseMethod(value: string): Method {
  return value === "sbert" ? "sbert" : "bm25";
}

export function parsePage(value: string): number {
  const n = Number.parseInt(value, 10);
  return Number.isFinite(n) && n > 0 ? n : 1;
}

/**
 * Pilihan filter tahun: 3 tahun terbaru yang punya data, lalu "2023 dan sebelumnya".
 * Nilai di URL: "2025" (tepat tahun itu) atau "sd-2023" (sampai dengan 2023).
 */
export function yearOptions(years: number[]): YearOption[] {
  const recent = [...years].sort((a, b) => b - a).slice(0, 3);
  if (recent.length === 0) return [];
  const older = recent[recent.length - 1] - 1;
  const options = recent.map((y) => ({ value: String(y), label: String(y) }));
  if (years.some((y) => y <= older)) options.push({ value: `sd-${older}`, label: `${older} dan sebelumnya` });
  return options;
}

/** Nilai filter tahun di URL -> parameter API year_from/year_to. */
export function yearRange(value: string): { year_from?: number; year_to?: number } {
  const upTo = value.match(/^sd-(\d{4})$/);
  if (upTo) return { year_to: Number(upTo[1]) };
  if (/^\d{4}$/.test(value)) return { year_from: Number(value), year_to: Number(value) };
  return {};
}
