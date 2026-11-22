"use client";

import { useEffect, useState } from "react";
import { IndexPanel } from "@/components/admin/IndexPanel";
import { Pager } from "@/components/admin/Pager";
import { btn, Card, Notice, PageHeader, Spinner } from "@/components/admin/ui";
import { AlertIcon, CheckIcon, CopyIcon, DownloadIcon, ErrorIcon, FileIcon, UploadIcon } from "@/components/icons";
import { adminApi, downloadUrl } from "@/lib/admin-api";
import { ApiError, queryString } from "@/lib/api";
import { formatDateTime, formatNumber, formatPercent } from "@/lib/format";
import type { ImportJob } from "@/lib/types";

// Alur 5 langkah (PRD §10.4): 1 Unduh Template → 2 Unggah → 3 Pratinjau → 4 Konfirmasi → 5 Selesai.
type Step = 1 | 2 | 3 | 4 | 5;
type DuplicateMode = "skip" | "overwrite" | "append";
type ConfirmResult = { ditambahkan: number; diperbarui: number; dilewati: number; indeks_dimulai: boolean; job: ImportJob };

const STEPS = ["Unduh Template", "Unggah File", "Pratinjau & Validasi", "Konfirmasi Simpan", "Selesai & Reindeks"];

export default function ImportPage() {
  const [step, setStep] = useState<Step>(1);
  const [job, setJob] = useState<(ImportJob & { ukuran_byte?: number }) | null>(null);
  const [mode, setMode] = useState<DuplicateMode>("skip");
  const [rebuild, setRebuild] = useState(true);
  const [result, setResult] = useState<ConfirmResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function upload(file: File) {
    setError("");
    setBusy(true);
    const form = new FormData();
    form.append("file", file);
    try {
      setJob(await adminApi.post<ImportJob>("/admin/import/upload", form));
      setMode("skip");
      setStep(3);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Gagal mengunggah file.");
    } finally {
      setBusy(false);
    }
  }

  async function cancel() {
    if (job?.status === "preview") await adminApi.post(`/admin/import/${job.id}/cancel`).catch(() => {});
    setJob(null);
    setStep(2);
  }

  async function confirm() {
    if (!job) return;
    setBusy(true);
    setError("");
    try {
      setResult(await adminApi.post<ConfirmResult>(`/admin/import/${job.id}/confirm`, { mode_duplikat: mode, bangun_indeks: rebuild }));
      setStep(5);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Gagal menyimpan. Tidak ada data yang tersimpan.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Import CSV / Excel"
        description="Tambah banyak skripsi sekaligus. Data divalidasi dan ditampilkan sebagai pratinjau dulu; database tidak berubah sebelum Anda mengonfirmasi."
      />
      <div className="space-y-6 p-4 sm:p-8">
        <Stepper step={step} />
        {error && <Notice kind="error">{error}</Notice>}

        {step <= 2 && (
          <div className="grid gap-6 lg:grid-cols-2">
            <TemplateCard onNext={() => setStep(2)} />
            <UploadCard busy={busy} onFile={upload} />
          </div>
        )}

        {step === 3 && job && (
          <Preview job={job} mode={mode} setMode={setMode} onBack={cancel} onNext={() => setStep(4)} />
        )}

        {step === 4 && job && (
          <Card title="Konfirmasi penyimpanan">
            <ul className="space-y-1 text-sm">
              <li>
                <strong>{formatNumber(job.valid + job.peringatan)}</strong> baris valid akan ditambahkan
                {job.peringatan > 0 && ` (${job.peringatan} di antaranya tanpa abstrak)`}.
              </li>
              {job.duplikat > 0 && (
                <li>
                  <strong>{job.duplikat}</strong> baris duplikat akan{" "}
                  {mode === "skip" ? "dilewati" : mode === "overwrite" ? "menimpa dokumen lama" : "tetap ditambahkan bila link-nya berbeda"}.
                </li>
              )}
              {job.error > 0 && (
                <li>
                  <strong>{job.error}</strong> baris error dilewati otomatis.
                </li>
              )}
            </ul>
            <label className="mt-4 flex items-center gap-2 text-sm">
              <input type="checkbox" checked={rebuild} onChange={(e) => setRebuild(e.target.checked)} className="size-4 accent-navy" />
              Bangun ulang indeks otomatis setelah disimpan (terjemahan + BM25 + IndoSBERT)
            </label>
            <p className="mt-2 text-xs text-muted">Penyimpanan berjalan dalam satu transaksi: bila gagal di tengah, tidak ada data yang masuk.</p>
            <div className="mt-5 flex gap-3">
              <button type="button" onClick={() => setStep(3)} className={btn.secondary}>
                Kembali ke pratinjau
              </button>
              <button type="button" onClick={confirm} disabled={busy} className={btn.primary}>
                {busy ? "Menyimpan…" : "Konfirmasi & Simpan"}
              </button>
            </div>
          </Card>
        )}

        {step === 5 && result && (
          <div className="space-y-6">
            <Notice kind="success">
              Import selesai: {result.ditambahkan} dokumen ditambahkan, {result.diperbarui} diperbarui, {result.dilewati} dilewati.
              {result.indeks_dimulai ? " Pembangunan indeks dimulai; dokumen baru bisa dicari setelah selesai." : ""}
            </Notice>
            <IndexPanel />
            <button
              type="button"
              onClick={() => {
                setJob(null);
                setResult(null);
                setStep(2);
              }}
              className={btn.secondary}
            >
              <UploadIcon size={16} /> Import file lain
            </button>
          </div>
        )}

        <ImportHistory refreshKey={step} />
      </div>
    </>
  );
}

function Stepper({ step }: { step: Step }) {
  return (
    <ol className="grid gap-2 rounded-lg border border-line bg-surface p-3 sm:grid-cols-5">
      {STEPS.map((label, i) => {
        const n = (i + 1) as Step;
        const state = n < step ? "done" : n === step ? "active" : "todo";
        return (
          <li key={label} aria-current={state === "active" ? "step" : undefined} className={`flex items-center gap-3 rounded-md p-2 ${state === "active" ? "bg-mist" : ""}`}>
            <span
              className={`flex size-8 shrink-0 items-center justify-center rounded border text-sm ${
                state === "done" ? "border-bm25 text-bm25" : state === "active" ? "border-navy bg-navy text-white" : "border-line text-muted"
              }`}
            >
              {state === "done" ? <CheckIcon size={14} /> : n}
            </span>
            <span className="text-sm">
              <span className="block text-xs uppercase tracking-wider text-muted">Langkah {n}</span>
              <span className={state === "todo" ? "text-muted" : "font-medium"}>{label}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}

function TemplateCard({ onNext }: { onNext: () => void }) {
  return (
    <Card title="1. Unduh template" description="Gunakan template agar nama kolom sesuai. Kolom wajib: judul, tahun, link.">
      <div className="flex flex-wrap gap-3">
        <a href={downloadUrl("/admin/import/template?format=xlsx")} onClick={onNext} className={btn.primary}>
          <DownloadIcon size={16} /> Template Excel (.xlsx)
        </a>
        <a href={downloadUrl("/admin/import/template?format=csv")} onClick={onNext} className={btn.secondary}>
          <DownloadIcon size={16} /> Template CSV
        </a>
      </div>
      <ul className="mt-4 list-disc space-y-1 pl-5 text-sm text-muted">
        <li>Template Excel berisi sheet “Petunjuk” untuk setiap kolom.</li>
        <li>Abstrak boleh kosong; dokumen tetap masuk dan dicari dari judulnya.</li>
        <li>Abstrak berbahasa Inggris diterjemahkan otomatis saat indeks dibangun.</li>
        <li>Maksimal 5.000 baris dan 10 MB per file.</li>
      </ul>
    </Card>
  );
}

function UploadCard({ busy, onFile }: { busy: boolean; onFile: (f: File) => void }) {
  const [dragging, setDragging] = useState(false);
  return (
    <Card title="2. Unggah file" description="Format .csv (UTF-8) atau .xlsx.">
      <label
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const file = e.dataTransfer.files[0];
          if (file) onFile(file);
        }}
        className={`flex cursor-pointer flex-col items-center gap-3 rounded-lg border-2 border-dashed p-8 text-center ${dragging ? "border-navy bg-mist" : "border-line"}`}
      >
        <FileIcon size={32} className="text-muted" />
        {busy ? (
          <Spinner label="Memvalidasi file…" />
        ) : (
          <>
            <span className="text-sm">
              <span className="font-medium text-navy underline">Pilih file</span> atau seret ke sini
            </span>
            <span className="text-xs text-muted">.csv atau .xlsx, maks. 10 MB</span>
          </>
        )}
        <input
          type="file"
          accept=".csv,.xlsx"
          className="sr-only"
          disabled={busy}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) onFile(file);
            e.target.value = "";
          }}
        />
      </label>
    </Card>
  );
}

type Row = {
  nomor_baris: number;
  status: "valid" | "peringatan" | "duplikat" | "error";
  pesan: { kolom: string; nilai: string; pesan: string; tingkat: string }[];
  data: Record<string, string | number | null>;
  duplikat_dari: number | null;
  judul_duplikat: string | null;
};
type PreviewData = { job: ImportJob; baris: { total: number; page: number; pages: number; items: Row[] } };
type RowFilter = "masalah" | "error" | "peringatan" | "duplikat";

function Preview({ job, mode, setMode, onBack, onNext }: { job: ImportJob; mode: DuplicateMode; setMode: (m: DuplicateMode) => void; onBack: () => void; onNext: () => void }) {
  const [filter, setFilter] = useState<RowFilter>("masalah");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<PreviewData | null>(null);

  useEffect(() => {
    adminApi.get<PreviewData>(`/admin/import/${job.id}${queryString({ status: filter, page })}`).then(setData, () => {});
  }, [job.id, filter, page]);

  const saveable = job.valid + job.peringatan;
  const cards = [
    { key: "valid", label: "Data valid", value: job.valid, icon: <CheckIcon size={18} />, cls: "border-bm25 text-bm25", note: "Semua kolom wajib lengkap dan formatnya benar." },
    { key: "peringatan", label: "Peringatan", value: job.peringatan, icon: <AlertIcon size={18} />, cls: "border-line text-warn", note: "Abstrak kosong/placeholder. Tetap disimpan, dicari dari judul." },
    { key: "duplikat", label: "Duplikat", value: job.duplikat, icon: <CopyIcon size={18} />, cls: "border-navy text-navy", note: "Link atau judul sudah ada di database atau di file ini." },
    { key: "error", label: "Error", value: job.error, icon: <ErrorIcon size={18} />, cls: "border-danger text-danger", note: "Melanggar aturan wajib. Dilewati otomatis." },
  ];

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <FileIcon size={28} className="text-muted" />
            <div>
              <p className="font-serif text-lg">{job.nama_file}</p>
              <p className="text-sm text-muted">{formatNumber(job.total)} baris terbaca</p>
            </div>
          </div>
          <button type="button" onClick={onBack} className={btn.secondary}>
            Ganti file
          </button>
        </div>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map((c) => (
          <section key={c.key} className={`rounded-lg border-2 bg-surface p-4 ${c.cls}`}>
            <p className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider">
              {c.label} {c.icon}
            </p>
            <p className="mt-2 font-mono text-3xl">
              {formatNumber(c.value)}
              <span className="text-sm text-muted"> / {formatNumber(job.total)}</span>
            </p>
            <p className="mt-1 text-sm text-muted">{c.note}</p>
          </section>
        ))}
      </div>

      {job.duplikat > 0 && (
        <Card title={`Penanganan baris duplikat (${job.duplikat} baris)`}>
          <div className="grid gap-3 md:grid-cols-3">
            {(
              [
                ["skip", "Lewati (disarankan)", "Baris duplikat diabaikan. Dokumen lama tidak berubah."],
                ["overwrite", "Timpa data lama", "Dokumen lama diperbarui dengan isi dari file, lalu diindeks ulang."],
                ["append", "Tambahkan tetap", "Disimpan sebagai dokumen baru. Hanya untuk duplikat judul; link harus tetap unik."],
              ] as [DuplicateMode, string, string][]
            ).map(([value, title, desc]) => (
              <label key={value} className={`cursor-pointer rounded-lg border-2 p-4 ${mode === value ? "border-navy bg-mist" : "border-line"}`}>
                <span className="flex items-center justify-between font-semibold">
                  {title}
                  <input type="radio" name="mode" checked={mode === value} onChange={() => setMode(value)} className="size-4 accent-navy" />
                </span>
                <span className="mt-1 block text-sm text-muted">{desc}</span>
              </label>
            ))}
          </div>
        </Card>
      )}

      <Card title="Komposisi baris">
        <div className="flex h-3 gap-0.5 overflow-hidden rounded" role="img" aria-label="Komposisi status baris">
          {[
            [job.valid, "bg-chart-bm25"],
            [job.peringatan, "bg-warn"],
            [job.duplikat, "bg-chart-navy"],
            [job.error, "bg-danger"],
          ]
            .filter(([v]) => (v as number) > 0)
            .map(([v, cls]) => (
              <div key={cls as string} className={cls as string} style={{ width: `${((v as number) / job.total) * 100}%` }} />
            ))}
        </div>
        <p className="mt-2 font-mono text-xs text-muted">
          Valid {formatPercent(job.valid / job.total, 1)} · Peringatan {formatPercent(job.peringatan / job.total, 1)} · Duplikat{" "}
          {formatPercent(job.duplikat / job.total, 1)} · Error {formatPercent(job.error / job.total, 1)}
        </p>
      </Card>

      <section className="rounded-lg border border-line bg-surface">
        <div className="flex flex-wrap items-end justify-between gap-3 p-5">
          <div>
            <h2 className="font-serif text-xl">Baris yang perlu perhatian</h2>
            <p className="text-sm text-muted">Nomor baris sesuai file (baris 1 = header).</p>
          </div>
          <div role="tablist" className="flex flex-wrap rounded-lg border border-line bg-mist p-1 text-xs">
            {(
              [
                ["masalah", `Semua (${job.peringatan + job.duplikat + job.error})`],
                ["error", `Error (${job.error})`],
                ["peringatan", `Peringatan (${job.peringatan})`],
                ["duplikat", `Duplikat (${job.duplikat})`],
              ] as [RowFilter, string][]
            ).map(([value, label]) => (
              <button
                key={value}
                role="tab"
                aria-selected={filter === value}
                onClick={() => {
                  setFilter(value);
                  setPage(1);
                }}
                className={`rounded-md px-3 py-1.5 ${filter === value ? "bg-surface font-medium shadow-sm" : "text-muted"}`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead className="bg-mist text-left text-xs uppercase tracking-wider text-muted">
              <tr>
                <th className="px-4 py-3">Baris</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Kolom &amp; nilai</th>
                <th className="px-4 py-3">Keterangan</th>
                <th className="px-4 py-3">Tindakan</th>
              </tr>
            </thead>
            <tbody>
              {data?.baris.items.map((r) => (
                <tr key={r.nomor_baris} className="border-t border-line align-top">
                  <td className="px-4 py-3 font-mono">#{r.nomor_baris}</td>
                  <td className="px-4 py-3">
                    <RowBadge status={r.status} />
                  </td>
                  <td className="px-4 py-3">
                    {r.pesan.map((p, i) => (
                      <p key={i} className="mb-1">
                        <code className="rounded bg-mist px-1.5 py-0.5 font-mono text-xs">{p.nilai ? `"${p.nilai}"` : "<kosong>"}</code>
                        <span className="ml-1 text-xs text-muted">kolom {p.kolom}</span>
                      </p>
                    ))}
                  </td>
                  <td className="px-4 py-3">
                    {r.pesan.map((p, i) => (
                      <p key={i} className={p.tingkat === "error" ? "text-danger" : ""}>
                        {p.pesan}
                      </p>
                    ))}
                    {r.judul_duplikat && <p className="text-xs text-muted">Dokumen lama: “{r.judul_duplikat}”</p>}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs">
                    {r.status === "error" ? "Dilewati" : r.status === "duplikat" ? `Sesuai opsi (${{ skip: "lewati", overwrite: "timpa", append: "tambah" }[mode]})` : "Disimpan"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {data && data.baris.items.length === 0 && <p className="p-6 text-center text-muted">Tidak ada baris pada kategori ini.</p>}
        </div>
        {data && (
          <div className="flex justify-end border-t border-line p-3">
            <Pager page={data.baris.page} pages={data.baris.pages} onChange={setPage} />
          </div>
        )}
      </section>

      <div className="flex flex-wrap items-center justify-between gap-4 border-t border-line pt-5">
        <button type="button" onClick={onBack} className={btn.secondary}>
          Kembali / ganti file
        </button>
        <div className="flex items-center gap-4">
          <p className="text-right text-sm">
            <span className="font-mono text-bm25">
              {job.valid} valid + {job.peringatan} peringatan
            </span>
            {job.error > 0 && <span className="block text-xs text-muted">{job.error} baris error dilewati otomatis</span>}
          </p>
          <button type="button" onClick={onNext} disabled={saveable === 0 && !(job.duplikat > 0 && mode !== "skip")} className={btn.primary}>
            Lanjut ke konfirmasi
          </button>
        </div>
      </div>
    </div>
  );
}

function RowBadge({ status }: { status: Row["status"] }) {
  const style = {
    valid: ["Valid", "border-bm25 text-bm25", <CheckIcon key="i" size={12} />],
    peringatan: ["Peringatan", "border-warn text-warn", <AlertIcon key="i" size={12} />],
    duplikat: ["Duplikat", "border-navy text-navy", <CopyIcon key="i" size={12} />],
    error: ["Error", "border-danger text-danger", <ErrorIcon key="i" size={12} />],
  }[status] as [string, string, React.ReactNode];
  return (
    <span className={`inline-flex items-center gap-1 rounded border px-2 py-1 text-xs font-medium ${style[1]}`}>
      {style[2]} {style[0]}
    </span>
  );
}

function ImportHistory({ refreshKey }: { refreshKey: number }) {
  const [jobs, setJobs] = useState<ImportJob[] | null>(null);
  useEffect(() => {
    adminApi.get<ImportJob[]>("/admin/import/history").then(setJobs, () => {});
  }, [refreshKey]);
  if (!jobs || jobs.length === 0) return null;
  const label = { preview: "Pratinjau (belum disimpan)", confirmed: "Disimpan", cancelled: "Dibatalkan" };
  return (
    <Card title="Riwayat import">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="text-left text-xs uppercase tracking-wider text-muted">
            <tr>
              <th className="py-2 pr-4">File</th>
              <th className="py-2 pr-4">Status</th>
              <th className="py-2 pr-4 text-right">Baris</th>
              <th className="py-2 pr-4 text-right">Disimpan</th>
              <th className="py-2 pr-4 text-right">Duplikat / error</th>
              <th className="py-2 text-right">Waktu</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((j) => (
              <tr key={j.id} className="border-t border-line">
                <td className="py-2 pr-4 font-mono text-xs">{j.nama_file}</td>
                <td className="py-2 pr-4">{label[j.status]}</td>
                <td className="py-2 pr-4 text-right font-mono">{j.total}</td>
                <td className="py-2 pr-4 text-right font-mono">{j.disimpan}</td>
                <td className="py-2 pr-4 text-right font-mono">
                  {j.duplikat} / {j.error}
                </td>
                <td className="py-2 text-right text-xs text-muted">{formatDateTime(j.confirmed_at ?? j.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
