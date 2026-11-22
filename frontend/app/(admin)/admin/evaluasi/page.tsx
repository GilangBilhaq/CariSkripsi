"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { btn, Notice, PageHeader, Spinner } from "@/components/admin/ui";
import { EvaluationReport } from "@/components/EvaluationReport";
import { ChartIcon, DownloadIcon, ListIcon } from "@/components/icons";
import { adminApi, downloadUrl } from "@/lib/admin-api";
import { ApiError } from "@/lib/api";
import { formatDateTime, formatDecimal } from "@/lib/format";
import type { EvaluationRun } from "@/lib/types";

type RunSummary = { id: number; created_at: string; jumlah_kueri: number; index_versi: string; ndcg: { bm25: number; sbert: number } };

export default function AdminEvaluationPage() {
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [run, setRun] = useState<EvaluationRun | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    adminApi.get<RunSummary[]>("/admin/eval/runs").then((list) => {
      setRuns(list);
      if (list.length) setSelected(list[0].id);
    }, () => setRuns([]));
  }, []);

  useEffect(() => {
    if (selected === null) return;
    adminApi.get<EvaluationRun>(`/admin/eval/runs/${selected}`).then(setRun, () => {});
  }, [selected]);

  async function runNew() {
    setBusy(true);
    setError("");
    try {
      const result = await adminApi.post<EvaluationRun>("/admin/eval/run");
      setRuns((list) => [
        { id: result.id, created_at: result.created_at, jumlah_kueri: result.jumlah_kueri, index_versi: result.index_versi, ndcg: { bm25: result.ringkasan.bm25.ndcg_at_k, sbert: result.ringkasan.sbert.ndcg_at_k } },
        ...(list ?? []),
      ]);
      setSelected(result.id);
      setRun(result);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Gagal menjalankan evaluasi.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Evaluasi Model: BM25 vs IndoSBERT"
        description="Metrik dihitung dari kueri uji dan penilaian relevansi manual yang sama untuk kedua metode (PRD §15)."
        actions={
          <>
            <Link href="/admin/evaluasi/kueri" className={btn.secondary}>
              <ListIcon size={16} /> Kueri Uji &amp; Penilaian
            </Link>
            {run && (
              <a href={downloadUrl(`/admin/eval/runs/${run.id}/export.csv`)} className={btn.secondary}>
                <DownloadIcon size={16} /> Ekspor CSV
              </a>
            )}
            <button type="button" onClick={runNew} disabled={busy} className={btn.primary}>
              <ChartIcon size={16} /> {busy ? "Menjalankan…" : "Jalankan Evaluasi Baru"}
            </button>
          </>
        }
      />
      <div className="space-y-6 p-4 sm:p-8">
        {error && <Notice kind="error">{error}</Notice>}
        {runs === null && <Spinner />}
        {runs?.length === 0 && (
          <Notice>
            Belum ada hasil evaluasi. Langkahnya: (1) buat kueri uji, (2) kedua penilai menilai kandidat dokumen, (3) selesaikan
            penilaian yang berbeda, lalu (4) klik “Jalankan Evaluasi Baru”.{" "}
            <Link href="/admin/evaluasi/kueri" className="underline">
              Mulai dari kueri uji
            </Link>
          </Notice>
        )}
        {runs && runs.length > 1 && (
          <label className="flex flex-wrap items-center gap-2 text-sm">
            Hasil evaluasi:
            <select value={selected ?? ""} onChange={(e) => setSelected(Number(e.target.value))} className="rounded-md border border-line bg-surface px-3 py-2">
              {runs.map((r) => (
                <option key={r.id} value={r.id}>
                  #{r.id} · {formatDateTime(r.created_at)} · {r.jumlah_kueri} kueri · nDCG BM25 {formatDecimal(r.ndcg.bm25)} / SBERT {formatDecimal(r.ndcg.sbert)}
                </option>
              ))}
            </select>
          </label>
        )}
        {run && <EvaluationReport run={run} />}
      </div>
    </>
  );
}
