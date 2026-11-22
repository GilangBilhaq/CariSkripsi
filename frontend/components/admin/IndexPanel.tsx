"use client";

import { useCallback, useEffect, useState } from "react";
import { adminApi } from "@/lib/admin-api";
import { ApiError } from "@/lib/api";
import { formatDateTime, formatNumber } from "@/lib/format";
import type { IndexVersion } from "@/lib/types";
import { RefreshIcon } from "../icons";
import { btn, Card, Notice } from "./ui";

type IndexStatus = {
  sedang_dibangun: boolean;
  terbaru: IndexVersion | null;
  aktif: string | null;
  perlu_indeks: number;
  riwayat: IndexVersion[];
};

/** Status indeks + tombol "Bangun Ulang Indeks". Saat pembangunan berjalan, progres diperbarui tiap 2 detik. */
export function IndexPanel({ onFinished }: { onFinished?: () => void }) {
  const [status, setStatus] = useState<IndexStatus | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    return adminApi.get<IndexStatus>("/admin/index/status").then(setStatus, (e) =>
      setError(e instanceof ApiError ? e.message : "Gagal memuat status indeks."),
    );
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const building = status?.sedang_dibangun ?? false;
  useEffect(() => {
    if (!building) return;
    const timer = setInterval(async () => {
      const next = await adminApi.get<IndexStatus>("/admin/index/status").catch(() => null);
      if (!next) return;
      setStatus(next);
      if (!next.sedang_dibangun) onFinished?.();
    }, 2000);
    return () => clearInterval(timer);
  }, [building, onFinished]);

  async function rebuild() {
    setError("");
    try {
      await adminApi.post("/admin/index/rebuild");
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Gagal memulai pembangunan indeks.");
    }
  }

  const latest = status?.terbaru;
  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="font-serif text-xl">Indeks pencarian</h2>
          <p className="text-sm text-muted">
            {status?.aktif ? (
              <>
                Versi aktif <span className="font-mono">{status.aktif}</span>
              </>
            ) : (
              "Belum ada indeks aktif"
            )}
            {status && status.perlu_indeks > 0 && (
              <>
                {" "}· <span className="text-warn">{formatNumber(status.perlu_indeks)} dokumen menunggu diindeks</span>
              </>
            )}
          </p>
        </div>
        <button type="button" onClick={rebuild} disabled={building || !status} className={btn.primary}>
          <RefreshIcon size={16} className={building ? "animate-spin" : ""} />
          {building ? "Sedang membangun…" : "Bangun Ulang Indeks"}
        </button>
      </div>

      {building && latest && (
        <div className="mt-4 space-y-2">
          <div className="flex justify-between text-sm">
            <span>{latest.tahap}</span>
            <span className="font-mono">{latest.persen}%</span>
          </div>
          <div className="h-2 rounded-full bg-mist" role="progressbar" aria-valuenow={latest.persen} aria-valuemin={0} aria-valuemax={100}>
            <div className="h-2 rounded-full bg-navy transition-all" style={{ width: `${latest.persen}%` }} />
          </div>
          <p className="text-xs text-muted">Pencarian tetap memakai indeks lama sampai pembangunan selesai.</p>
        </div>
      )}
      {!building && latest?.status === "failed" && (
        <div className="mt-4">
          <Notice kind="error">
            Pembangunan terakhir ({formatDateTime(latest.created_at)}) gagal: {latest.pesan_error}
          </Notice>
        </div>
      )}
      {error && (
        <div className="mt-4">
          <Notice kind="error">{error}</Notice>
        </div>
      )}
      {status && status.riwayat.length > 0 && (
        <details className="mt-4 text-sm">
          <summary className="cursor-pointer text-muted">Riwayat pembangunan</summary>
          <ul className="mt-2 space-y-1">
            {status.riwayat.map((v) => (
              <li key={v.id} className="flex flex-wrap gap-x-3 font-mono text-xs">
                <span>{v.versi}</span>
                <span className={v.status === "failed" ? "text-danger" : v.status === "active" ? "text-bm25" : "text-muted"}>{v.status}</span>
                <span className="text-muted">{formatNumber(v.jumlah_dokumen)} dok</span>
                <span className="text-muted">{v.model_name}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </Card>
  );
}
