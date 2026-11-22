import type { Highlighted } from "@/lib/types";

/**
 * Menampilkan teks dengan bagian tertentu dibungkus <mark>.
 * Backend hanya mengirim teks polos + posisi sorotan, jadi tidak ada HTML dari data yang dirender (aman dari XSS).
 */
export function HighlightedText({ value }: { value: Highlighted }) {
  const parts: React.ReactNode[] = [];
  let cursor = 0;
  value.highlights.forEach(([start, end], i) => {
    if (start > cursor) parts.push(value.text.slice(cursor, start));
    parts.push(<mark key={i}>{value.text.slice(start, end)}</mark>);
    cursor = end;
  });
  if (cursor < value.text.length) parts.push(value.text.slice(cursor));
  return <>{parts}</>;
}
