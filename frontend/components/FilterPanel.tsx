"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { FilterIcon } from "./icons";

export type YearOption = { value: string; label: string };

/**
 * Panel filter hasil pencarian. Semua pilihan disimpan di URL (?tahun=&abstrak=&bahasa=) sehingga hasil
 * bisa dibagikan/di-bookmark, dan halaman kembali ke halaman 1 setiap kali filter berubah.
 */
export function FilterPanel({ yearOptions }: { yearOptions: YearOption[] }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  function update(key: string, value: string | null) {
    const next = new URLSearchParams(params.toString());
    if (value) next.set(key, value);
    else next.delete(key);
    next.delete("hal");
    router.push(`${pathname}?${next.toString()}`);
  }

  function reset() {
    const next = new URLSearchParams();
    for (const key of ["q", "metode"]) {
      const v = params.get(key);
      if (v) next.set(key, v);
    }
    router.push(`${pathname}?${next.toString()}`);
  }

  const tahun = params.get("tahun") ?? "";
  const abstrak = params.get("abstrak") ?? "";
  const bahasa = params.get("bahasa") ?? "";
  const activeCount = [tahun, abstrak, bahasa].filter(Boolean).length;
  // HP/tablet: panel dilipat supaya hasil langsung terlihat. Desktop (lg): selalu terbuka.
  const [open, setOpen] = useState(false);

  return (
    <aside aria-label="Penyaring hasil" className="rounded-lg border border-line bg-surface px-5 py-3 lg:sticky lg:top-4 lg:py-5">
      <div className={`flex items-center justify-between lg:border-b lg:border-line lg:pb-3 ${open ? "border-b border-line pb-3" : ""}`}>
        <h2 className="text-xs font-semibold uppercase tracking-wider">
          <button
            type="button"
            onClick={() => setOpen(!open)}
            aria-expanded={open}
            aria-controls="filter-groups"
            className="flex items-center gap-2 py-1 uppercase lg:pointer-events-none"
          >
            <FilterIcon size={14} /> Penyaring korpus
            {activeCount > 0 && (
              <span className="rounded-full bg-navy px-1.5 text-[10px] font-medium text-white">{activeCount}</span>
            )}
            <span aria-hidden className="text-muted lg:hidden">{open ? "▴" : "▾"}</span>
          </button>
        </h2>
        <button type="button" onClick={reset} className="text-sm text-bm25 hover:underline">
          Reset
        </button>
      </div>

      <div id="filter-groups" className={open ? "block" : "hidden lg:block"}>
      <FilterGroup title="Tahun terbit">
        <Radio name="tahun" label="Semua periode" checked={!tahun} onChange={() => update("tahun", null)} />
        {yearOptions.map((o) => (
          <Radio key={o.value} name="tahun" label={o.label} checked={tahun === o.value} onChange={() => update("tahun", o.value)} />
        ))}
      </FilterGroup>

      <FilterGroup title="Ketersediaan abstrak">
        <Radio name="abstrak" label="Semua" checked={!abstrak} onChange={() => update("abstrak", null)} />
        <Radio name="abstrak" label="Hanya dengan abstrak" checked={abstrak === "ada"} onChange={() => update("abstrak", "ada")} />
        <Radio name="abstrak" label="Judul saja (tanpa abstrak)" checked={abstrak === "tidak"} onChange={() => update("abstrak", "tidak")} />
      </FilterGroup>

      <FilterGroup title="Bahasa asli dokumen">
        <Radio name="bahasa" label="Semua bahasa" checked={!bahasa} onChange={() => update("bahasa", null)} />
        <Radio name="bahasa" label="Bahasa Indonesia" checked={bahasa === "id"} onChange={() => update("bahasa", "id")} />
        <Radio name="bahasa" label="Inggris (diterjemahkan)" checked={bahasa === "en"} onChange={() => update("bahasa", "en")} />
      </FilterGroup>
      </div>
    </aside>
  );
}

function FilterGroup({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <fieldset className="space-y-2 border-b border-line py-4 last:border-0 last:pb-0">
      <legend className="mb-2 text-sm font-semibold">{title}</legend>
      {children}
    </fieldset>
  );
}

function Radio({ name, label, checked, onChange }: { name: string; label: string; checked: boolean; onChange: () => void }) {
  return (
    <label className="flex cursor-pointer items-center gap-2.5 text-sm">
      <input type="radio" name={name} checked={checked} onChange={onChange} className="size-4 accent-navy" />
      {label}
    </label>
  );
}
