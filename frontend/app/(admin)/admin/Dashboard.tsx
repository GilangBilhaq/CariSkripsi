"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { IndexPanel } from "@/components/admin/IndexPanel";
import { btn, Card, inputClass, Notice, PageHeader, Spinner } from "@/components/admin/ui";
import { UploadIcon } from "@/components/icons";
import { Pager } from "@/components/admin/Pager";
import { adminApi } from "@/lib/admin-api";
import { ApiError, queryString } from "@/lib/api";
import { formatDateTime, formatNumber, formatPercent, LANGUAGE_LABEL } from "@/lib/format";
import type { AdminStats, Paged, SearchLogItem } from "@/lib/types";

export function Dashboard() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    adminApi.get<AdminStats>("/admin/stats").then(setStats, (e) => setError(e instanceof ApiError ? e.message : "Gagal memuat."));
  }, []);
  useEffect(load, [load]);

  return (
    <>
      <PageHeader
        title="Ringkasan Koleksi & Status Sistem"
        actions={
          <Link href="/admin/import" className={btn.secondary}>
            <UploadIcon size={16} /> Import Dokumen Baru
          </Link>
        }
      />
      <div className="space-y-6 p-4 sm:p-8">
        {error && <Notice kind="error">{error}</Notice>}
        <IndexPanel onFinished={load} />
        {!stats ? (
          <Spinner />
        ) : (
          <>
            <StatCards stats={stats} />
            <div className="grid gap-6 xl:grid-cols-[2fr_1fr]">
              <YearChart data={stats.per_tahun} />
              <LanguageChart perBahasa={stats.per_bahasa} total={stats.total} untranslated={stats.belum_diterjemahkan} />
            </div>
          </>
        )}
        <SearchLogTable />
      </div>
    </>
  );
}

function StatCards({ stats }: { stats: AdminStats }) {
  const last = stats.import_terakhir;
  return (
    <div className="grid gap-4 md:grid-cols-3">
      <Card>
        <p className="text-xs uppercase tracking-wider text-muted">Total dokumen</p>
        <p className="mt-2 font-serif text-4xl">{formatNumber(stats.total)}</p>
        <p className="mt-2 text-sm text-muted">{formatNumber(stats.pencarian_24_jam)} pencarian dalam 24 jam terakhir</p>
      </Card>
      <Card>
        <p className="text-xs uppercase tracking-wider text-muted">Abstrak tersedia</p>
        <p className="mt-2 font-serif text-4xl">{formatPercent(stats.total ? stats.dengan_abstrak / stats.total : 0, 1)}</p>
        <p className="mt-2 text-sm text-muted">
          {formatNumber(stats.dengan_abstrak)} berabstrak · {formatNumber(stats.tanpa_abstrak)} hanya judul
        </p>
      </Card>
      <Card>
        <p className="text-xs uppercase tracking-wider text-muted">Import terakhir</p>
        {last ? (
          <>
            <p className="mt-2 truncate font-mono text-sm" title={last.nama_file}>
              {last.nama_file}
            </p>
            <p className="mt-1 text-sm">
              <span className="text-bm25">+{formatNumber(last.disimpan)} disimpan</span>
              <span className="text-muted">
                , {last.duplikat} duplikat, {last.error} error
              </span>
            </p>
            <p className="mt-1 text-xs text-muted">{formatDateTime(last.confirmed_at)}</p>
          </>
        ) : (
          <p className="mt-2 text-sm text-muted">Belum ada import.</p>
        )}
      </Card>
    </div>
  );
}

/** Grafik batang jumlah dokumen per tahun (satu seri). Nilai tiap batang muncul saat disorot/difokus. */
function YearChart({ data }: { data: AdminStats["per_tahun"] }) {
  const years = data.filter((d) => d.tahun !== null);
  const unknown = data.find((d) => d.tahun === null)?.jumlah ?? 0;
  // Tahun sebelum 2015 digabung agar batang tidak terlalu banyak.
  const cutoff = 2015;
  const older = years.filter((d) => d.tahun! < cutoff).reduce((s, d) => s + d.jumlah, 0);
  const bars = [
    ...(older ? [{ label: `< ${cutoff}`, value: older }] : []),
    ...years.filter((d) => d.tahun! >= cutoff).map((d) => ({ label: String(d.tahun), value: d.jumlah })),
  ];
  const max = Math.max(1, ...bars.map((b) => b.value));
  const peak = bars.reduce((a, b) => (b.value > a.value ? b : a), bars[0] ?? { label: "-", value: 0 });

  return (
    <Card title="Distribusi tahun terbit" description={`Jumlah skripsi per tahun. Puncak: ${peak.label} (${formatNumber(peak.value)} dokumen).`}>
      <div className="flex h-56 items-end gap-1 border-b border-line pt-6" role="img" aria-label="Grafik jumlah dokumen per tahun">
        {bars.map((b) => (
          <div key={b.label} className="group relative flex h-full flex-1 flex-col justify-end" tabIndex={0}>
            <span className="pointer-events-none absolute -top-6 left-1/2 hidden -translate-x-1/2 whitespace-nowrap rounded bg-ink px-2 py-0.5 font-mono text-xs text-white group-hover:block group-focus:block">
              {b.label}: {formatNumber(b.value)}
            </span>
            <div className="rounded-t bg-chart-navy group-hover:opacity-80" style={{ height: `${(b.value / max) * 100}%`, minHeight: 2 }} />
          </div>
        ))}
      </div>
      <div className="mt-1 flex gap-1">
        {bars.map((b, i) => (
          <span key={b.label} className="flex-1 text-center font-mono text-[10px] text-muted">
            {bars.length <= 12 || i % 2 === 0 || i === bars.length - 1 ? b.label : ""}
          </span>
        ))}
      </div>
      {unknown > 0 && <p className="mt-3 text-xs text-muted">{formatNumber(unknown)} dokumen tanpa tahun valid tidak ditampilkan.</p>}
      <details className="mt-3 text-sm">
        <summary className="cursor-pointer text-muted">Lihat sebagai tabel</summary>
        <table className="mt-2 w-full max-w-xs text-xs">
          <tbody>
            {bars.map((b) => (
              <tr key={b.label} className="border-t border-line">
                <td className="py-1">{b.label}</td>
                <td className="py-1 text-right font-mono">{formatNumber(b.value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </Card>
  );
}

function LanguageChart({ perBahasa, total, untranslated }: { perBahasa: Record<string, number>; total: number; untranslated: number }) {
  const segments = [
    { key: "id", color: "bg-chart-bm25", note: "Teks asli dipakai langsung." },
    { key: "en", color: "bg-chart-navy", note: "Diterjemahkan otomatis (opus-mt-en-id) sebelum diindeks." },
    { key: "lain", color: "bg-chart-neutral", note: "Bahasa tidak terdeteksi; teks asli dipakai." },
  ].map((s) => ({ ...s, value: perBahasa[s.key] ?? 0 }));

  return (
    <Card title="Bahasa asli dokumen" description="Bahasa abstrak (atau judul bila tanpa abstrak).">
      <div className="flex h-4 gap-0.5 overflow-hidden rounded" role="img" aria-label="Proporsi bahasa dokumen">
        {segments
          .filter((s) => s.value > 0)
          .map((s) => (
            <div key={s.key} className={s.color} style={{ width: `${(s.value / Math.max(total, 1)) * 100}%` }} title={`${LANGUAGE_LABEL[s.key]}: ${formatNumber(s.value)}`} />
          ))}
      </div>
      <ul className="mt-4 space-y-3">
        {segments.map((s) => (
          <li key={s.key} className="rounded-md bg-mist p-3 text-sm">
            <p className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-2 font-medium">
                <span aria-hidden className={`size-3 rounded-sm ${s.color}`} />
                {LANGUAGE_LABEL[s.key]}
              </span>
              <span className="font-mono">
                {formatPercent(total ? s.value / total : 0)} ({formatNumber(s.value)})
              </span>
            </p>
            <p className="mt-1 text-xs text-muted">{s.note}</p>
          </li>
        ))}
      </ul>
      {untranslated > 0 && <p className="mt-3 text-xs text-warn">{formatNumber(untranslated)} dokumen menunggu terjemahan.</p>}
    </Card>
  );
}

const METHOD_BADGE: Record<SearchLogItem["metode"], { label: string; cls: string }> = {
  bm25: { label: "Kata (BM25)", cls: "bg-bm25-soft text-bm25" },
  sbert: { label: "Makna (IndoSBERT)", cls: "bg-sbert-soft text-sbert-dark" },
  compare: { label: "Bandingkan", cls: "bg-mist text-ink" },
};

function SearchLogTable() {
  const [filter, setFilter] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Paged<SearchLogItem> | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      adminApi.get<Paged<SearchLogItem>>(`/admin/search-logs${queryString({ q: filter, page })}`).then(setData, () => {});
    }, 250); // tunggu pengguna selesai mengetik
    return () => clearTimeout(timer);
  }, [filter, page]);

  return (
    <Card>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="font-serif text-xl">Log kueri pencarian</h2>
          <p className="text-sm text-muted">Anonim: hanya kueri, metode, jumlah hasil, dan waktu.</p>
        </div>
        <div className="flex gap-2">
          <input
            value={filter}
            onChange={(e) => {
              setFilter(e.target.value);
              setPage(1);
            }}
            placeholder="Filter log kueri…"
            aria-label="Filter log kueri"
            className={`${inputClass} w-56`}
          />
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="text-left text-xs uppercase tracking-wider text-muted">
            <tr>
              <th className="py-2 pr-4">Kueri</th>
              <th className="py-2 pr-4">Metode</th>
              <th className="py-2 pr-4 text-right">Hasil</th>
              <th className="py-2 pr-4 text-right">Latensi</th>
              <th className="py-2 text-right">Waktu</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((log) => (
              <tr key={log.id} className="border-t border-line">
                <td className="py-3 pr-4">“{log.kueri}”</td>
                <td className="py-3 pr-4">
                  <span className={`rounded px-2 py-1 text-xs ${METHOD_BADGE[log.metode].cls}`}>{METHOD_BADGE[log.metode].label}</span>
                </td>
                <td className="py-3 pr-4 text-right font-mono">{log.metode === "compare" ? `${log.jumlah_hasil} irisan` : log.jumlah_hasil}</td>
                <td className="py-3 pr-4 text-right font-mono">{log.waktu_ms.toLocaleString("id-ID", { maximumFractionDigits: 0 })} ms</td>
                <td className="py-3 text-right font-mono text-xs text-muted">{formatDateTime(log.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {data?.items.length === 0 && <p className="py-6 text-center text-sm text-muted">Belum ada log kueri.</p>}
      </div>
      {data && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm text-muted">
          <span>{formatNumber(data.total)} kueri tercatat</span>
          <Pager page={data.page} pages={data.pages} onChange={setPage} />
        </div>
      )}
    </Card>
  );
}
