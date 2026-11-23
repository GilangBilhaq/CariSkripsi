import { Logo } from "./Logo";

export function SiteFooter() {
  return (
    <footer className="mt-auto border-t border-line bg-surface">
      <div className="mx-auto grid max-w-7xl gap-8 px-4 py-10 sm:px-8 md:grid-cols-[2fr_1fr]">
        <div className="space-y-3">
          <Logo size="sm" />
          <p className="max-w-xl text-sm text-muted">
            Eksplorasi komparasi information retrieval leksikal (BM25) dan semantik dense vector (IndoSBERT) untuk
            korpus skripsi Universitas Jember.
          </p>
          <p className="text-xs text-muted">Sumber data: Repository Universitas Jember (repository.unej.ac.id)</p>
        </div>
        <div className="space-y-2 text-sm">
          <p className="font-semibold uppercase tracking-wider text-ink">Metode IR</p>
          <p className="text-muted">Kata · BM25 (Okapi)</p>
          <p className="text-muted">Makna · IndoSBERT (baseline)</p>
        </div>
      </div>
      <div className="mx-auto max-w-7xl border-t border-line px-4 py-4 text-xs text-muted sm:px-8">
        © 2026 CariSkripsi · Universitas Jember
      </div>
    </footer>
  );
}
