"use client";

import { useState } from "react";

type Props = {
  translated: boolean; // true bila aslinya berbahasa Inggris
  judulAsli: string;
  judulId: string | null;
  abstrakAsli: string | null;
  abstrakId: string | null;
  kataKunci: string[];
};

/** Abstrak dengan pilihan versi terjemahan (yang diindeks) atau teks asli. Toggle hanya muncul untuk dokumen Inggris. */
export function AbstractView({ translated, judulAsli, judulId, abstrakAsli, abstrakId, kataKunci }: Props) {
  const [showOriginal, setShowOriginal] = useState(false);
  const abstract = showOriginal ? abstrakAsli : (abstrakId ?? abstrakAsli);

  return (
    <section aria-labelledby="abstrak-title" className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-line pb-3">
        <div>
          <h2 id="abstrak-title" className="font-serif text-2xl">
            Abstrak
          </h2>
          <p className="text-sm text-muted">Teks yang dipakai untuk pengindeksan BM25 dan IndoSBERT</p>
        </div>
        {translated && (
          <div role="radiogroup" aria-label="Versi teks" className="flex rounded-lg border border-line bg-mist p-1 text-sm">
            {[
              { original: false, label: "Bahasa Indonesia (terjemahan)" },
              { original: true, label: "Bahasa asli (Inggris)" },
            ].map((o) => (
              <button
                key={o.label}
                type="button"
                role="radio"
                aria-checked={showOriginal === o.original}
                onClick={() => setShowOriginal(o.original)}
                className={`rounded-md px-3 py-1.5 ${showOriginal === o.original ? "bg-surface font-medium shadow-sm" : "text-muted"}`}
              >
                {o.label}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="space-y-4 rounded-lg border border-line bg-surface p-6">
        {translated && (
          <p className="border-b border-line pb-3 text-xs font-semibold uppercase tracking-wider text-sbert-dark">
            {showOriginal ? "Teks asli dari repositori" : "Terjemahan mesin (opus-mt-en-id) · dipakai untuk pengindeksan"}
          </p>
        )}
        {translated && judulId && (
          <p className="font-medium">{showOriginal ? judulAsli : judulId}</p>
        )}
        {abstract ? (
          <p className="whitespace-pre-line leading-relaxed">{abstract}</p>
        ) : (
          <p className="italic text-muted">
            Abstrak tidak tersedia di repositori. Dokumen ini diindeks dari judulnya saja.
          </p>
        )}
        {kataKunci.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 border-t border-line pt-4 text-sm">
            <span className="font-semibold">Kata kunci:</span>
            {kataKunci.map((k) => (
              <span key={k} className="rounded border border-line bg-mist px-2 py-0.5">
                {k}
              </span>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
