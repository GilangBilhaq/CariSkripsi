// Komponen tampilan kecil yang dipakai berulang di halaman admin.

/** Kelas tombol standar admin. */
export const btn = {
  primary:
    "inline-flex items-center justify-center gap-2 rounded-md bg-navy px-4 py-2 text-sm font-medium text-white hover:bg-navy-dark disabled:cursor-not-allowed disabled:opacity-50",
  secondary:
    "inline-flex items-center justify-center gap-2 rounded-md border border-line bg-surface px-4 py-2 text-sm hover:border-navy disabled:cursor-not-allowed disabled:opacity-50",
  danger:
    "inline-flex items-center justify-center gap-2 rounded-md border border-danger px-3 py-1.5 text-sm text-danger hover:bg-danger-soft disabled:opacity-50",
};

export const inputClass = "w-full rounded-md border border-line bg-surface px-3 py-2 text-sm outline-none focus:border-navy";

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: React.ReactNode }) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-4 border-b border-line bg-surface px-4 py-6 sm:px-8">
      <div className="space-y-1">
        <h1 className="font-serif text-3xl">{title}</h1>
        {description && <p className="max-w-3xl text-sm text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </header>
  );
}

export function Card({ title, description, children, className = "" }: { title?: string; description?: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={`rounded-lg border border-line bg-surface p-5 ${className}`}>
      {title && (
        <div className="mb-4">
          <h2 className="font-serif text-xl">{title}</h2>
          {description && <p className="text-sm text-muted">{description}</p>}
        </div>
      )}
      {children}
    </section>
  );
}

export function Notice({ kind = "info", children }: { kind?: "info" | "error" | "warn" | "success"; children: React.ReactNode }) {
  const style = {
    info: "bg-mist text-ink",
    error: "bg-danger-soft text-danger",
    warn: "bg-warn-soft text-warn",
    success: "bg-bm25-soft text-bm25",
  }[kind];
  return (
    <div role={kind === "error" ? "alert" : "status"} className={`rounded-md px-4 py-3 text-sm ${style}`}>
      {children}
    </div>
  );
}

export function Spinner({ label = "Memuat…" }: { label?: string }) {
  return (
    <p className="flex items-center gap-2 text-sm text-muted" aria-busy="true">
      <span aria-hidden className="size-4 animate-spin rounded-full border-2 border-line border-t-navy" />
      {label}
    </p>
  );
}

/** Label status indeks dokumen. */
export function IndexStatus({ pending }: { pending: boolean }) {
  return pending ? (
    <span className="inline-flex items-center gap-1.5 text-xs text-warn">
      <span aria-hidden className="size-1.5 rounded-full bg-warn" /> Antrean indeks
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 text-xs text-bm25">
      <span aria-hidden className="size-1.5 rounded-full bg-bm25" /> Terindeks
    </span>
  );
}
