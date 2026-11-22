"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { btn, Notice, PageHeader, Spinner } from "@/components/admin/ui";
import { ArrowLeftIcon } from "@/components/icons";
import { adminApi } from "@/lib/admin-api";
import { formatDecimal } from "@/lib/format";

type Disagreement = {
  query_id: number;
  document_id: number;
  kueri: string;
  judul: string;
  abstrak: string | null;
  nilai: Record<string, number>;
  keputusan: number | null;
};
type Data = { items: Disagreement[]; kesepakatan: { penilai: string[]; kappa: number | null; jumlah_pasangan: number; sepakat: number } };

const LABEL = ["Tidak relevan", "Agak relevan", "Relevan"];

/** Dokumen yang nilainya berbeda antarpenilai. Keputusan diambil bersama lewat diskusi (PRD §15.2). */
export default function DisagreementsPage() {
  const [data, setData] = useState<Data | null>(null);

  const load = useCallback(() => {
    adminApi.get<Data>("/admin/eval/disagreements").then(setData, () => {});
  }, []);
  useEffect(load, [load]);

  async function resolve(item: Disagreement, skor: number) {
    await adminApi.put("/admin/eval/resolve", { query_id: item.query_id, document_id: item.document_id, skor }).catch(() => {});
    load();
  }

  const open = data?.items.filter((i) => i.keputusan === null).length ?? 0;
  const k = data?.kesepakatan;

  return (
    <>
      <PageHeader
        title="Selesaikan Perbedaan Penilaian"
        description="Diskusikan setiap dokumen yang nilainya berbeda, lalu pilih nilai akhir. Sebelum diputuskan, evaluasi memakai nilai yang lebih rendah."
        actions={
          <Link href="/admin/evaluasi/kueri" className={btn.secondary}>
            <ArrowLeftIcon size={14} /> Daftar kueri
          </Link>
        }
      />
      <div className="mx-auto max-w-5xl space-y-4 p-4 sm:p-8">
        {!data ? (
          <Spinner />
        ) : (
          <>
            <Notice>
              {k?.kappa === null || k === undefined
                ? "Cohen's kappa muncul setelah dua penilai menilai dokumen yang sama."
                : `Cohen's kappa ${formatDecimal(k.kappa)} antara ${k.penilai.join(" dan ")} (sepakat ${k.sepakat} dari ${k.jumlah_pasangan}).`}{" "}
              {open} perbedaan belum diputuskan.
            </Notice>
            {data.items.length === 0 && <p className="text-center text-muted">Tidak ada perbedaan penilaian.</p>}
            <ul className="space-y-4">
              {data.items.map((item) => (
                <li key={`${item.query_id}-${item.document_id}`} className="rounded-lg border border-line bg-surface p-5">
                  <p className="text-xs text-muted">Kueri: “{item.kueri}”</p>
                  <h2 className="mt-1 font-serif text-lg">{item.judul}</h2>
                  {item.abstrak && (
                    <details className="mt-1 text-sm text-muted">
                      <summary className="cursor-pointer">Abstrak</summary>
                      <p className="mt-2">{item.abstrak}</p>
                    </details>
                  )}
                  <p className="mt-3 text-sm">
                    {Object.entries(item.nilai).map(([judge, score]) => (
                      <span key={judge} className="mr-4">
                        {judge}: <strong>{score}</strong> ({LABEL[score]})
                      </span>
                    ))}
                  </p>
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <span className="text-sm">Nilai akhir:</span>
                    {[2, 1, 0].map((v) => (
                      <button
                        key={v}
                        type="button"
                        onClick={() => resolve(item, v)}
                        aria-pressed={item.keputusan === v}
                        className={`rounded-md border px-3 py-1.5 text-sm ${item.keputusan === v ? "border-navy bg-navy text-white" : "border-line hover:border-navy"}`}
                      >
                        {v} · {LABEL[v]}
                      </button>
                    ))}
                  </div>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </>
  );
}
