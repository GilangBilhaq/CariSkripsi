"use client";

import { useState } from "react";
import { CATEGORY_LABEL, formatDateTime, formatDecimal, formatPercent, METHOD_SHORT } from "@/lib/format";
import type { EvaluationRun, Method, MethodMetrics, MethodSummary } from "@/lib/types";

// Warna mark grafik: lolos validasi buta warna (lihat --color-chart-* di globals.css).
const BAR: Record<Method | "seri", string> = { bm25: "bg-chart-bm25", sbert: "bg-chart-sbert", seri: "bg-chart-neutral" };

type MetricKey = "p_at_k" | "r_at_k" | "map" | "ndcg_at_k";

/** Laporan hasil evaluasi BM25 vs IndoSBERT: kartu metrik, distribusi pemenang, dan tabel per kueri. */
export function EvaluationReport({ run }: { run: EvaluationRun }) {
  const k = run.k;
  const s = run.ringkasan;
  const metrics: { key: MetricKey; title: string; hint: string }[] = [
    { key: "p_at_k", title: `Precision@${k}`, hint: `Proporsi dokumen relevan di ${k} hasil teratas` },
    { key: "r_at_k", title: `Recall@${k}`, hint: "Cakupan dokumen relevan yang ditemukan" },
    { key: "map", title: "MAP", hint: "Mean Average Precision: kualitas urutan secara keseluruhan" },
    { key: "ndcg_at_k", title: `nDCG@${k}`, hint: "Kualitas urutan dengan relevansi bertingkat (0/1/2)" },
  ];

  return (
    <div className="space-y-8">
      <p className="text-sm text-muted">
        {run.jumlah_kueri} kueri uji · dijalankan {formatDateTime(run.created_at)} · indeks {run.index_versi} · model{" "}
        <span className="font-mono">{run.model_name}</span> · BM25 k1={run.bm25_params.k1}, b={run.bm25_params.b}
      </p>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        {metrics.map((m) => (
          <MetricCard key={m.key} title={m.title} hint={m.hint} bm25={s.bm25[m.key]} sbert={s.sbert[m.key]} />
        ))}
        <LatencyCard bm25={s.bm25} sbert={s.sbert} />
      </div>

      <WinnerDistribution menang={s.menang} total={run.jumlah_kueri} k={k} />

      <AgreementNote kesepakatan={s.kesepakatan} unresolved={s.belum_diselesaikan} />

      <QueryTable run={run} />
    </div>
  );
}

function MetricCard({ title, hint, bm25, sbert }: { title: string; hint: string; bm25: number; sbert: number }) {
  const delta = bm25 > 0 ? (sbert - bm25) / bm25 : null;
  return (
    <section className="flex flex-col gap-3 rounded-lg border border-line bg-surface p-4">
      <div>
        <h3 className="font-serif text-lg">{title}</h3>
        <p className="text-xs text-muted">{hint}</p>
      </div>
      <div className="mt-auto space-y-2">
        <MetricBar method="bm25" value={bm25} />
        <MetricBar method="sbert" value={sbert} />
      </div>
      <p className="rounded bg-mist px-2 py-1 text-xs">
        Selisih IndoSBERT vs BM25:{" "}
        <span className="font-mono font-medium">
          {sbert - bm25 >= 0 ? "+" : ""}
          {formatDecimal(sbert - bm25)}
          {delta !== null && ` (${delta >= 0 ? "+" : ""}${formatPercent(delta, 1)})`}
        </span>
      </p>
    </section>
  );
}

/** Batang tipis 0..1 dengan label metode dan nilai di sampingnya (identitas tidak hanya lewat warna). */
function MetricBar({ method, value }: { method: Method; value: number }) {
  return (
    <div title={`${METHOD_SHORT[method]}: ${formatDecimal(value)}`}>
      <div className="flex items-baseline justify-between text-xs">
        <span className="text-muted">{METHOD_SHORT[method]}</span>
        <span className="font-mono text-base font-medium text-ink">{formatDecimal(value)}</span>
      </div>
      <div className="mt-1 h-1.5 w-full rounded-full bg-mist">
        <div className={`h-1.5 rounded-full ${BAR[method]}`} style={{ width: `${Math.min(100, value * 100)}%` }} />
      </div>
    </div>
  );
}

function LatencyCard({ bm25, sbert }: { bm25: MethodSummary; sbert: MethodSummary }) {
  const ratio = bm25.waktu_rata_ms > 0 ? sbert.waktu_rata_ms / bm25.waktu_rata_ms : null;
  return (
    <section className="flex flex-col gap-3 rounded-lg border border-line bg-surface p-4">
      <div>
        <h3 className="font-serif text-lg">Latensi</h3>
        <p className="text-xs text-muted">Waktu komputasi peringkat per kueri</p>
      </div>
      <dl className="mt-auto space-y-2 text-xs">
        {(["bm25", "sbert"] as Method[]).map((m) => {
          const x = m === "bm25" ? bm25 : sbert;
          return (
            <div key={m} className="flex items-baseline justify-between">
              <dt className="text-muted">{METHOD_SHORT[m]}</dt>
              <dd className="text-right">
                <span className="font-mono text-base font-medium">{x.waktu_rata_ms.toLocaleString("id-ID", { maximumFractionDigits: 1 })} ms</span>
                <span className="block text-muted">p95 {x.waktu_p95_ms.toLocaleString("id-ID", { maximumFractionDigits: 1 })} ms</span>
              </dd>
            </div>
          );
        })}
      </dl>
      {ratio !== null && (
        <p className="rounded bg-mist px-2 py-1 text-xs">
          BM25 {ratio >= 1 ? `${ratio.toLocaleString("id-ID", { maximumFractionDigits: 1 })}× lebih cepat` : "lebih lambat"}
        </p>
      )}
    </section>
  );
}

function WinnerDistribution({ menang, total, k }: { menang: { bm25: number; sbert: number; seri: number }; total: number; k: number }) {
  const segments: { key: Method | "seri"; label: string; value: number }[] = [
    { key: "bm25", label: "BM25 unggul", value: menang.bm25 },
    { key: "sbert", label: "IndoSBERT unggul", value: menang.sbert },
    { key: "seri", label: "Seri", value: menang.seri },
  ];
  return (
    <section className="space-y-4 rounded-lg border border-line bg-surface p-5">
      <div>
        <h3 className="font-serif text-xl">Distribusi pemenang per kueri</h3>
        <p className="text-sm text-muted">Metode dengan nDCG@{k} lebih tinggi untuk setiap kueri uji.</p>
      </div>
      <ul className="flex flex-wrap gap-x-6 gap-y-1 text-sm" aria-label="Legenda">
        {segments.map((seg) => (
          <li key={seg.key} className="flex items-center gap-2">
            <span aria-hidden className={`size-3 rounded-sm ${BAR[seg.key]}`} />
            {seg.label}: <span className="font-mono font-medium">{seg.value}</span> ({formatPercent(total ? seg.value / total : 0)})
          </li>
        ))}
      </ul>
      <div className="flex h-7 w-full gap-0.5 overflow-hidden rounded" role="img" aria-label="Proporsi kueri yang dimenangkan tiap metode">
        {segments
          .filter((seg) => seg.value > 0)
          .map((seg) => (
            <div
              key={seg.key}
              title={`${seg.label}: ${seg.value} kueri`}
              className={`flex items-center justify-center text-xs font-medium text-white ${BAR[seg.key]}`}
              style={{ width: `${(seg.value / total) * 100}%` }}
            >
              {seg.value / total >= 0.12 ? `${seg.value} kueri` : ""}
            </div>
          ))}
      </div>
    </section>
  );
}

function AgreementNote({ kesepakatan, unresolved }: { kesepakatan: EvaluationRun["ringkasan"]["kesepakatan"]; unresolved: number }) {
  const { kappa, penilai, jumlah_pasangan, sepakat } = kesepakatan;
  return (
    <section className="rounded-lg border border-line bg-mist p-4 text-sm">
      <h3 className="font-semibold">Kesepakatan antarpenilai</h3>
      {kappa === null ? (
        <p className="text-muted">Cohen&apos;s kappa memerlukan minimal dua penilai yang menilai dokumen yang sama.</p>
      ) : (
        <p>
          Cohen&apos;s kappa <span className="font-mono font-medium">{formatDecimal(kappa)}</span> ({kappaLabel(kappa)}) antara{" "}
          {penilai.join(" dan ")}: sepakat pada {sepakat} dari {jumlah_pasangan} penilaian.
        </p>
      )}
      {unresolved > 0 && (
        <p className="mt-1 text-warn">
          {unresolved} penilaian berbeda belum diputuskan bersama; sementara dipakai nilai yang lebih rendah.
        </p>
      )}
    </section>
  );
}

/** Tafsiran kappa menurut Landis & Koch (1977). */
function kappaLabel(kappa: number): string {
  if (kappa < 0.2) return "kesepakatan sangat rendah";
  if (kappa < 0.4) return "kesepakatan rendah";
  if (kappa < 0.6) return "kesepakatan sedang";
  if (kappa < 0.8) return "kesepakatan baik";
  return "kesepakatan sangat baik";
}

type Filter = "semua" | Method | "seri";

function QueryTable({ run }: { run: EvaluationRun }) {
  const [filter, setFilter] = useState<Filter>("semua");
  const rows = run.per_kueri.filter((r) => filter === "semua" || r.pemenang === filter);
  const k = run.k;
  const tabs: { value: Filter; label: string }[] = [
    { value: "semua", label: `Semua (${run.jumlah_kueri})` },
    { value: "bm25", label: `BM25 unggul (${run.ringkasan.menang.bm25})` },
    { value: "sbert", label: `IndoSBERT unggul (${run.ringkasan.menang.sbert})` },
    { value: "seri", label: `Seri (${run.ringkasan.menang.seri})` },
  ];
  const cols: { key: keyof MethodMetrics; label: string }[] = [
    { key: "p_at_k", label: `P@${k}` },
    { key: "r_at_k", label: `R@${k}` },
    { key: "ap", label: "AP" },
    { key: "ndcg_at_k", label: `nDCG@${k}` },
  ];

  return (
    <section className="rounded-lg border border-line bg-surface">
      <div className="flex flex-wrap items-end justify-between gap-4 p-5">
        <div>
          <h3 className="font-serif text-xl">Hasil per kueri uji</h3>
          <p className="text-sm text-muted">Dokumen yang belum dinilai dianggap tidak relevan (pooling top-10 kedua metode).</p>
        </div>
        <div role="tablist" className="flex flex-wrap rounded-lg border border-line bg-mist p-1 text-xs">
          {tabs.map((t) => (
            <button
              key={t.value}
              role="tab"
              aria-selected={filter === t.value}
              onClick={() => setFilter(t.value)}
              className={`rounded-md px-3 py-1.5 ${filter === t.value ? "bg-surface font-medium shadow-sm" : "text-muted"}`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[900px] text-sm">
          <thead className="bg-mist text-left text-xs uppercase tracking-wider text-muted">
            <tr>
              <th className="px-4 py-3">No</th>
              <th className="px-4 py-3">Kueri uji</th>
              <th className="px-4 py-3">Kategori</th>
              {cols.map((c) => (
                <th key={c.key} className="px-3 py-3 text-right" colSpan={2}>
                  {c.label}
                  <span className="block font-normal normal-case">BM25 · SBERT</span>
                </th>
              ))}
              <th className="px-4 py-3">Unggul</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.query_id} className="border-t border-line">
                <td className="px-4 py-3 font-mono text-muted">Q{String(run.per_kueri.indexOf(r) + 1).padStart(2, "0")}</td>
                <td className="px-4 py-3">
                  <p className="font-medium">{r.teks}</p>
                  <p className="text-xs text-muted">{r.jumlah_relevan} dokumen relevan</p>
                </td>
                <td className="px-4 py-3">
                  <span className="rounded bg-mist px-2 py-0.5 text-xs">{CATEGORY_LABEL[r.kategori]}</span>
                </td>
                {cols.map((c) => (
                  <Pair key={c.key} bm25={r.metode.bm25[c.key]} sbert={r.metode.sbert[c.key]} />
                ))}
                <td className="px-4 py-3 text-xs">
                  {r.pemenang === "seri" ? "Seri" : <span className={r.pemenang === "bm25" ? "text-bm25" : "text-sbert-dark"}>{METHOD_SHORT[r.pemenang]}</span>}
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={12} className="px-4 py-6 text-center text-muted">
                  Tidak ada kueri pada kategori ini.
                </td>
              </tr>
            )}
          </tbody>
          <tfoot className="border-t-2 border-line bg-mist font-mono text-sm">
            <tr>
              <td className="px-4 py-3 font-sans text-xs font-semibold uppercase" colSpan={3}>
                Rata-rata ({run.jumlah_kueri} kueri)
              </td>
              <Pair bm25={run.ringkasan.bm25.p_at_k} sbert={run.ringkasan.sbert.p_at_k} />
              <Pair bm25={run.ringkasan.bm25.r_at_k} sbert={run.ringkasan.sbert.r_at_k} />
              <Pair bm25={run.ringkasan.bm25.map} sbert={run.ringkasan.sbert.map} />
              <Pair bm25={run.ringkasan.bm25.ndcg_at_k} sbert={run.ringkasan.sbert.ndcg_at_k} />
              <td />
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  );
}

/** Dua sel berdampingan; nilai yang lebih tinggi ditebalkan. */
function Pair({ bm25, sbert }: { bm25: number; sbert: number }) {
  return (
    <>
      <td className={`py-3 pl-3 text-right font-mono ${bm25 > sbert ? "font-semibold text-bm25" : "text-muted"}`}>{formatDecimal(bm25)}</td>
      <td className={`py-3 pr-3 text-right font-mono ${sbert > bm25 ? "font-semibold text-sbert-dark" : "text-muted"}`}>{formatDecimal(sbert)}</td>
    </>
  );
}
