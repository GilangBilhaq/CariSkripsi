"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { btn, Notice, PageHeader, Spinner } from "@/components/admin/ui";
import { useJudgeName } from "@/components/admin/useJudgeName";
import { ArrowLeftIcon, ExternalIcon } from "@/components/icons";
import { adminApi } from "@/lib/admin-api";
import { ApiError, queryString } from "@/lib/api";
import { CATEGORY_LABEL } from "@/lib/format";
import type { QueryCategory } from "@/lib/types";

type PoolItem = { document_id: number; judul: string; abstrak: string | null; tahun: number | null; link: string | null; skor: number | null };
type Pool = { query: { id: number; teks: string; kategori: QueryCategory; catatan: string | null }; penilai: string; items: PoolItem[] };

const GRADES = [
  { value: 2, label: "Relevan", hint: "membahas persis topik kueri", cls: "border-bm25 bg-bm25 text-white" },
  { value: 1, label: "Agak relevan", hint: "topiknya bersinggungan", cls: "border-warn bg-warn text-white" },
  { value: 0, label: "Tidak relevan", hint: "tidak berhubungan", cls: "border-muted bg-muted text-white" },
];

/**
 * Penilaian blind: dokumen kandidat tampil dalam urutan acak tanpa keterangan metode, peringkat, atau skor.
 * Setiap klik langsung tersimpan.
 */
export default function JudgingPage() {
  const { id } = useParams<{ id: string }>();
  const [judge] = useJudgeName();
  const [pool, setPool] = useState<Pool | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState<number | null>(null);

  useEffect(() => {
    if (!judge.trim()) return;
    adminApi
      .get<Pool>(`/admin/eval/queries/${id}/pool${queryString({ penilai: judge })}`)
      .then(setPool, (e) => setError(e instanceof ApiError ? e.message : "Gagal memuat kandidat."));
  }, [id, judge]);

  async function grade(item: PoolItem, value: number) {
    if (!pool) return;
    setSaving(item.document_id);
    try {
      await adminApi.put("/admin/eval/judgments", { query_id: pool.query.id, document_id: item.document_id, penilai: judge, skor: value });
      setPool({ ...pool, items: pool.items.map((i) => (i.document_id === item.document_id ? { ...i, skor: value } : i)) });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Gagal menyimpan nilai.");
    } finally {
      setSaving(null);
    }
  }

  const done = pool?.items.filter((i) => i.skor !== null).length ?? 0;
  const total = pool?.items.length ?? 0;

  return (
    <>
      <PageHeader
        title={pool ? `“${pool.query.teks}”` : "Penilaian relevansi"}
        description={pool ? `${CATEGORY_LABEL[pool.query.kategori]}${pool.query.catatan ? ` · ${pool.query.catatan}` : ""}` : undefined}
        actions={
          <Link href="/admin/evaluasi/kueri" className={btn.secondary}>
            <ArrowLeftIcon size={14} /> Daftar kueri
          </Link>
        }
      />
      <div className="mx-auto max-w-5xl space-y-4 p-4 sm:p-8">
        {!judge.trim() && <Notice kind="warn">Isi nama penilai dulu di halaman daftar kueri.</Notice>}
        {error && <Notice kind="error">{error}</Notice>}
        {judge.trim() && !pool && !error && <Spinner label="Menyiapkan kandidat dokumen…" />}
        {pool && (
          <>
            <div className="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line bg-surface px-4 py-3 shadow-sm">
              <p className="text-sm">
                Penilai: <strong>{pool.penilai}</strong> · {done}/{total} dinilai
              </p>
              <div className="h-2 w-full rounded-full bg-mist sm:w-48" role="progressbar" aria-valuenow={done} aria-valuemax={total} aria-valuemin={0}>
                <div className="h-2 rounded-full bg-navy" style={{ width: `${total ? (done / total) * 100 : 0}%` }} />
              </div>
            </div>
            <ol className="space-y-4">
              {pool.items.map((item, idx) => (
                <li key={item.document_id} className={`rounded-lg border bg-surface p-5 ${item.skor === null ? "border-line" : "border-navy/40"}`}>
                  <p className="text-xs text-muted">
                    Kandidat {idx + 1} dari {total} · Tahun {item.tahun ?? "-"}
                  </p>
                  <h2 className="mt-1 font-serif text-lg leading-snug">{item.judul}</h2>
                  {item.abstrak ? (
                    <details className="mt-2 text-sm">
                      <summary className="cursor-pointer text-muted">
                        {item.abstrak.slice(0, 260)}
                        {item.abstrak.length > 260 && "… (baca lengkap)"}
                      </summary>
                      <p className="mt-2 leading-relaxed">{item.abstrak}</p>
                    </details>
                  ) : (
                    <p className="mt-2 text-sm italic text-muted">Tanpa abstrak.</p>
                  )}
                  <div className="mt-4 flex flex-wrap items-center gap-2" role="radiogroup" aria-label={`Nilai untuk kandidat ${idx + 1}`}>
                    {GRADES.map((g) => (
                      <button
                        key={g.value}
                        type="button"
                        role="radio"
                        aria-checked={item.skor === g.value}
                        disabled={saving === item.document_id}
                        onClick={() => grade(item, g.value)}
                        title={g.hint}
                        className={`rounded-md border px-3 py-1.5 text-sm ${item.skor === g.value ? g.cls : "border-line hover:border-navy"}`}
                      >
                        {g.value} · {g.label}
                      </button>
                    ))}
                    {item.link && (
                      <a href={item.link} target="_blank" rel="noopener noreferrer" className="ml-auto inline-flex items-center gap-1 text-xs text-muted hover:underline">
                        Repositori <ExternalIcon size={12} />
                      </a>
                    )}
                  </div>
                </li>
              ))}
            </ol>
            {done === total && total > 0 && <Notice kind="success">Semua kandidat untuk kueri ini sudah Anda nilai.</Notice>}
          </>
        )}
      </div>
    </>
  );
}
