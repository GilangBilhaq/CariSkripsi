import type { Metadata } from "next";
import { Suspense } from "react";
import { EvaluationReport } from "@/components/EvaluationReport";
import { apiGet } from "@/lib/api";
import type { EvaluationRun } from "@/lib/types";

export const metadata: Metadata = { title: "Evaluasi Model" };

export default function EvaluationPage() {
  return (
    <div className="mx-auto w-full max-w-7xl space-y-6 px-4 py-10 sm:px-8">
      <header className="space-y-2">
        <h1 className="font-serif text-3xl sm:text-4xl">Evaluasi Komparasi: Leksikal (BM25) vs Semantik (IndoSBERT)</h1>
        <p className="max-w-3xl text-muted">
          Kedua metode diuji dengan kueri dan penilaian relevansi manual yang sama. Penilaian memakai metode pooling:
          10 hasil teratas dari tiap metode digabung, diacak tanpa label metode, lalu dinilai 0 (tidak relevan), 1 (agak
          relevan), atau 2 (relevan) oleh dua penilai.
        </p>
      </header>
      <Suspense fallback={<p className="text-muted">Memuat hasil evaluasi…</p>}>
        <LatestEvaluation />
      </Suspense>
    </div>
  );
}

async function LatestEvaluation() {
  const data = await apiGet<{ run: EvaluationRun | null }>("/evaluation/latest").catch(() => null);
  if (!data) return <p className="text-danger">Server tidak dapat dihubungi.</p>;
  if (!data.run)
    return (
      <p className="rounded-lg border border-line bg-surface p-6 text-muted">
        Evaluasi belum dijalankan. Hasil akan tampil di sini setelah kueri uji dinilai dan admin menjalankan evaluasi.
      </p>
    );
  return <EvaluationReport run={data.run} />;
}
