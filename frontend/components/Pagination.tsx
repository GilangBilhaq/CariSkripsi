import Link from "next/link";

/** Nomor halaman yang ditampilkan: 1 … 4 5 6 … 20 */
export function pageNumbers(current: number, total: number): (number | "…")[] {
  const pages = new Set([1, total, current - 1, current, current + 1].filter((p) => p >= 1 && p <= total));
  const sorted = [...pages].sort((a, b) => a - b);
  const out: (number | "…")[] = [];
  sorted.forEach((p, i) => {
    if (i > 0 && p - sorted[i - 1] > 1) out.push("…");
    out.push(p);
  });
  return out;
}

type Props = { page: number; pages: number; hrefFor: (page: number) => string };

export function Pagination({ page, pages, hrefFor }: Props) {
  if (pages <= 1) return null;
  const base = "rounded-md border border-line px-3 py-1.5 text-sm";
  return (
    <nav aria-label="Halaman hasil" className="flex flex-wrap items-center gap-1.5">
      {page > 1 ? (
        <Link href={hrefFor(page - 1)} className={`${base} bg-surface hover:border-navy`}>
          Sebelumnya
        </Link>
      ) : (
        <span className={`${base} text-muted opacity-60`}>Sebelumnya</span>
      )}
      {pageNumbers(page, pages).map((p, i) =>
        p === "…" ? (
          <span key={`gap-${i}`} className="px-1 text-muted">
            …
          </span>
        ) : (
          <Link
            key={p}
            href={hrefFor(p)}
            aria-current={p === page ? "page" : undefined}
            className={`${base} min-w-9 text-center ${p === page ? "border-navy bg-navy text-white" : "bg-surface hover:border-navy"}`}
          >
            {p}
          </Link>
        ),
      )}
      {page < pages ? (
        <Link href={hrefFor(page + 1)} className={`${base} bg-surface hover:border-navy`}>
          Berikutnya
        </Link>
      ) : (
        <span className={`${base} text-muted opacity-60`}>Berikutnya</span>
      )}
    </nav>
  );
}
