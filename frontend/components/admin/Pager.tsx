"use client";

import { pageNumbers } from "../Pagination";

/** Paginasi untuk tabel admin (state di komponen, bukan di URL). */
export function Pager({ page, pages, onChange }: { page: number; pages: number; onChange: (page: number) => void }) {
  if (pages <= 1) return null;
  const base = "min-w-8 rounded border border-line px-2.5 py-1 text-sm disabled:opacity-40";
  return (
    <nav aria-label="Halaman" className="flex flex-wrap items-center gap-1">
      <button type="button" className={base} disabled={page <= 1} onClick={() => onChange(page - 1)} aria-label="Sebelumnya">
        ‹
      </button>
      {pageNumbers(page, pages).map((p, i) =>
        p === "…" ? (
          <span key={`gap-${i}`} className="px-1">
            …
          </span>
        ) : (
          <button
            key={p}
            type="button"
            onClick={() => onChange(p)}
            aria-current={p === page ? "page" : undefined}
            className={`${base} ${p === page ? "border-navy bg-navy text-white" : "bg-surface text-ink"}`}
          >
            {p}
          </button>
        ),
      )}
      <button type="button" className={base} disabled={page >= pages} onClick={() => onChange(page + 1)} aria-label="Berikutnya">
        ›
      </button>
    </nav>
  );
}
