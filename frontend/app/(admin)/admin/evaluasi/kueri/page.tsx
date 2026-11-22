"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { btn, Card, inputClass, Notice, PageHeader, Spinner } from "@/components/admin/ui";
import { useJudgeName } from "@/components/admin/useJudgeName";
import { ArrowLeftIcon, EditIcon, PlusIcon, TrashIcon } from "@/components/icons";
import { adminApi } from "@/lib/admin-api";
import { ApiError } from "@/lib/api";
import { CATEGORY_LABEL } from "@/lib/format";
import type { QueryCategory } from "@/lib/types";

type EvalQuery = {
  id: number;
  teks: string;
  kategori: QueryCategory;
  catatan: string | null;
  jumlah_pool: number;
  dinilai: Record<string, number>;
  belum_diselesaikan: number;
};

const EMPTY = { teks: "", kategori: "kata_kunci" as QueryCategory, catatan: "" };

export default function QueriesPage() {
  const [data, setData] = useState<{ items: EvalQuery[]; penilai: string[] } | null>(null);
  const [form, setForm] = useState(EMPTY);
  const [editing, setEditing] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [judge, setJudge] = useJudgeName();

  const load = useCallback(() => {
    adminApi.get<{ items: EvalQuery[]; penilai: string[] }>("/admin/eval/queries").then(setData, (e) => setError(e instanceof ApiError ? e.message : "Gagal memuat."));
  }, []);
  useEffect(load, [load]);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (editing) {
      const old = data?.items.find((q) => q.id === editing);
      const judged = old && Object.values(old.dinilai).some((n) => n > 0);
      if (judged && old.teks !== form.teks.trim() && !window.confirm("Mengubah teks kueri akan menghapus semua penilaian kueri ini. Lanjutkan?")) return;
    }
    try {
      const body = { ...form, catatan: form.catatan || null };
      if (editing) await adminApi.put(`/admin/eval/queries/${editing}`, body);
      else await adminApi.post("/admin/eval/queries", body);
      setForm(EMPTY);
      setEditing(null);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Gagal menyimpan kueri.");
    }
  }

  async function remove(q: EvalQuery) {
    if (!window.confirm(`Hapus kueri “${q.teks}” beserta semua penilaiannya?`)) return;
    await adminApi.delete(`/admin/eval/queries/${q.id}`).catch(() => {});
    load();
  }

  const counts = data?.items.reduce<Record<string, number>>((acc, q) => ({ ...acc, [q.kategori]: (acc[q.kategori] ?? 0) + 1 }), {});

  // Tombol aksi satu kueri (dipakai di tabel desktop dan kartu HP).
  const actions = (q: EvalQuery) => (
    <>
      <Link
        href={`/admin/evaluasi/nilai/${q.id}`}
        aria-disabled={!judge.trim()}
        onClick={(e) => {
          if (!judge.trim()) {
            e.preventDefault();
            setError("Isi nama penilai terlebih dahulu.");
          }
        }}
        className={`${btn.primary} px-3 py-1.5`}
      >
        Nilai
      </Link>
      <button
        type="button"
        onClick={() => {
          setEditing(q.id);
          setForm({ teks: q.teks, kategori: q.kategori, catatan: q.catatan ?? "" });
        }}
        aria-label={`Ubah kueri ${q.teks}`}
        className="rounded p-2 text-muted hover:bg-mist"
      >
        <EditIcon size={16} />
      </button>
      <button type="button" onClick={() => remove(q)} aria-label={`Hapus kueri ${q.teks}`} className="rounded p-2 text-muted hover:bg-danger-soft hover:text-danger">
        <TrashIcon size={16} />
      </button>
    </>
  );

  return (
    <>
      <PageHeader
        title="Kueri Uji & Penilaian Relevansi"
        description="Buat kueri uji, lalu setiap penilai menilai kandidat dokumen secara terpisah tanpa melihat metode asalnya (blind)."
        actions={
          <>
            <Link href="/admin/evaluasi" className={btn.secondary}>
              <ArrowLeftIcon size={14} /> Hasil evaluasi
            </Link>
            <Link href="/admin/evaluasi/selisih" className={btn.secondary}>
              Selesaikan perbedaan penilaian
            </Link>
          </>
        }
      />
      <div className="grid gap-6 p-4 sm:p-8 xl:grid-cols-[1fr_360px]">
        <div className="space-y-4">
          {error && <Notice kind="error">{error}</Notice>}
          <Card>
            <label className="flex flex-wrap items-center gap-3 text-sm">
              <span className="font-semibold">Nama Anda sebagai penilai:</span>
              <input value={judge} onChange={(e) => setJudge(e.target.value)} placeholder="mis. Penilai 1 / nama" className={`${inputClass} sm:w-64`} />
              <span className="text-xs text-muted">Kedua penilai memakai nama berbeda. Tersimpan di browser ini.</span>
            </label>
          </Card>

          {!data ? (
            <Spinner />
          ) : (
            <div className="overflow-hidden rounded-lg border border-line bg-surface">
              {/* Tablet/desktop: tabel. HP: daftar kartu (tabel 4 kolom tidak muat). */}
              <table className="hidden w-full text-sm md:table">
                <thead className="bg-mist text-left text-xs uppercase tracking-wider text-muted">
                  <tr>
                    <th className="px-4 py-3">No</th>
                    <th className="px-4 py-3">Kueri</th>
                    <th className="px-4 py-3">Progres penilaian</th>
                    <th className="px-4 py-3 text-right">Aksi</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((q, i) => (
                    <tr key={q.id} className="border-t border-line align-top">
                      <td className="px-4 py-3 font-mono text-muted">{queryNumber(i)}</td>
                      <td className="px-4 py-3">
                        <QueryText q={q} />
                      </td>
                      <td className="px-4 py-3 text-xs">
                        <Progress q={q} penilai={data.penilai} />
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex justify-end gap-1">{actions(q)}</div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <ul className="divide-y divide-line md:hidden">
                {data.items.map((q, i) => (
                  <li key={q.id} className="space-y-2 p-4 text-sm">
                    <div className="flex gap-3">
                      <span className="font-mono text-muted">{queryNumber(i)}</span>
                      <div className="min-w-0 flex-1">
                        <QueryText q={q} />
                      </div>
                    </div>
                    <div className="flex flex-wrap items-end justify-between gap-2 pl-10 text-xs">
                      <Progress q={q} penilai={data.penilai} />
                      <div className="ml-auto flex gap-1">{actions(q)}</div>
                    </div>
                  </li>
                ))}
              </ul>
              {data.items.length === 0 && <p className="p-6 text-center text-muted">Belum ada kueri uji.</p>}
            </div>
          )}
        </div>

        <div className="space-y-4">
          <Card title={editing ? "Ubah kueri" : "Tambah kueri uji"}>
            <form onSubmit={save} className="space-y-3">
              <label className="block space-y-1 text-sm">
                <span className="font-semibold">Teks kueri</span>
                <input required minLength={2} value={form.teks} onChange={(e) => setForm({ ...form, teks: e.target.value })} className={inputClass} />
              </label>
              <label className="block space-y-1 text-sm">
                <span className="font-semibold">Kategori</span>
                <select value={form.kategori} onChange={(e) => setForm({ ...form, kategori: e.target.value as QueryCategory })} className={inputClass}>
                  {Object.entries(CATEGORY_LABEL).map(([v, l]) => (
                    <option key={v} value={v}>
                      {l}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block space-y-1 text-sm">
                <span className="font-semibold">Catatan (opsional)</span>
                <textarea rows={3} value={form.catatan} onChange={(e) => setForm({ ...form, catatan: e.target.value })} placeholder="Apa yang dicari kueri ini? Membantu penilai menyamakan standar." className={inputClass} />
              </label>
              <div className="flex gap-2">
                <button type="submit" className={btn.primary}>
                  <PlusIcon size={14} /> {editing ? "Simpan" : "Tambah"}
                </button>
                {editing && (
                  <button type="button" onClick={() => { setEditing(null); setForm(EMPTY); }} className={btn.secondary}>
                    Batal
                  </button>
                )}
              </div>
            </form>
          </Card>
          <Card title="Komposisi">
            <ul className="space-y-1 text-sm">
              {Object.entries(CATEGORY_LABEL).map(([v, l]) => (
                <li key={v} className="flex justify-between">
                  <span>{l}</span>
                  <span className="font-mono">{counts?.[v] ?? 0}</span>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-muted">Rencana: 15 kueri (5 per kategori), 2 penilai.</p>
          </Card>
          <Card title="Panduan nilai">
            <ul className="space-y-2 text-sm">
              <li><strong>2 · Relevan</strong>: membahas persis topik kueri.</li>
              <li><strong>1 · Agak relevan</strong>: topiknya bersinggungan.</li>
              <li><strong>0 · Tidak relevan</strong>: tidak berhubungan.</li>
            </ul>
          </Card>
        </div>
      </div>
    </>
  );
}

const queryNumber = (i: number) => `Q${String(i + 1).padStart(2, "0")}`;

function QueryText({ q }: { q: EvalQuery }) {
  return (
    <>
      <p className="font-medium">{q.teks}</p>
      <p className="text-xs text-muted">
        {CATEGORY_LABEL[q.kategori]}
        {q.catatan && ` · ${q.catatan}`}
      </p>
    </>
  );
}

function Progress({ q, penilai }: { q: EvalQuery; penilai: string[] }) {
  if (q.jumlah_pool === 0) return <span className="text-muted">Belum dibuka</span>;
  return (
    <ul>
      {penilai.length === 0 && <li className="text-muted">{q.jumlah_pool} kandidat, belum dinilai</li>}
      {penilai.map((p) => (
        <li key={p} className={(q.dinilai[p] ?? 0) >= q.jumlah_pool ? "text-bm25" : ""}>
          {p}: {q.dinilai[p] ?? 0}/{q.jumlah_pool}
        </li>
      ))}
      {q.belum_diselesaikan > 0 && <li className="text-warn">{q.belum_diselesaikan} nilai berbeda</li>}
    </ul>
  );
}
