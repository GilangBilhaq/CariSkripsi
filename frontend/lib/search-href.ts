// Tautan halaman pencarian. Dipakai di server dan browser, jadi sengaja tidak berada di file "use client".
import { queryString } from "./api";

export type SearchMode = "bm25" | "sbert" | "compare";

/** Satu metode -> /cari?q=&metode=, dua metode berdampingan -> /bandingkan?q= */
export function searchHref(query: string, mode: SearchMode): string {
  return mode === "compare" ? `/bandingkan${queryString({ q: query })}` : `/cari${queryString({ q: query, metode: mode })}`;
}
