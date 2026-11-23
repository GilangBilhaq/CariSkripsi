"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { type SearchMode, searchHref } from "@/lib/search-href";
import { ArrowRightIcon, CompareIcon, SearchIcon } from "./icons";

const MODES: { value: SearchMode; label: string; dot?: string }[] = [
  { value: "bm25", label: "Kata", dot: "bg-bm25" },
  { value: "sbert", label: "Makna", dot: "bg-sbert" },
  { value: "compare", label: "Bandingkan" },
];

type Props = {
  initialQuery?: string;
  initialMode?: SearchMode;
  variant?: "hero" | "compact";
  autoFocus?: boolean;
};

export function SearchBox({ initialQuery = "", initialMode = "bm25", variant = "hero", autoFocus }: Props) {
  const router = useRouter();
  const [query, setQuery] = useState(initialQuery);
  const [mode, setMode] = useState<SearchMode>(initialMode);
  const [error, setError] = useState("");
  const hero = variant === "hero";

  function submit(nextMode: SearchMode = mode) {
    const q = query.trim();
    if (q.length < 2) {
      setError(q ? "Kueri terlalu pendek. Ketik minimal 2 karakter." : "Ketik kata kunci atau topik penelitian.");
      return;
    }
    setError("");
    router.push(searchHref(q, nextMode));
  }

  function chooseMode(next: SearchMode) {
    setMode(next);
    // Di halaman hasil, mengganti metode langsung mencari ulang dengan kueri yang sama.
    if (!hero && query.trim().length >= 2) submit(next);
  }

  return (
    <div className={hero ? "w-full max-w-3xl" : "w-full"}>
      <div className={`flex flex-col gap-3 ${hero ? "" : "lg:flex-row lg:items-center"}`}>
        <form
          role="search"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
          className={`flex flex-1 items-center gap-3 rounded-lg border border-line bg-surface pl-4 shadow-sm focus-within:border-navy ${
            hero ? "py-2 pr-2" : "py-1.5 pr-1.5"
          }`}
        >
          <SearchIcon size={20} className="shrink-0 text-muted" />
          <label htmlFor={`q-${variant}`} className="sr-only">
            Kueri pencarian
          </label>
          <input
            id={`q-${variant}`}
            type="search"
            value={query}
            autoFocus={autoFocus}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ketik topik penelitian atau pertanyaan..."
            maxLength={300}
            className={`min-w-0 flex-1 bg-transparent outline-none placeholder:text-muted ${hero ? "text-lg" : "text-base"}`}
          />
          <button
            type="submit"
            aria-label="Cari"
            className={`flex shrink-0 items-center justify-center gap-2 rounded-md bg-navy font-medium text-white hover:bg-navy-dark ${
              hero ? "size-12" : "px-5 py-2.5"
            }`}
          >
            {hero ? <ArrowRightIcon size={20} /> : "Cari"}
          </button>
        </form>

        <div
          role="radiogroup"
          aria-label="Metode pencarian"
          className={`grid grid-cols-3 rounded-lg border border-line bg-mist p-1 text-sm sm:flex ${
            hero ? "sm:self-center" : "sm:self-start lg:self-auto"
          }`}
        >
          {MODES.map((m) => {
            const active = mode === m.value;
            return (
              <button
                key={m.value}
                type="button"
                role="radio"
                aria-checked={active}
                onClick={() => chooseMode(m.value)}
                className={`flex items-center justify-center gap-2 whitespace-nowrap rounded-md px-2 py-2 sm:px-4 ${
                  active ? "bg-surface font-medium text-ink shadow-sm" : "text-muted hover:text-ink"
                }`}
              >
                {m.dot ? <span aria-hidden className={`size-2 shrink-0 rounded-full ${m.dot}`} /> : <CompareIcon size={14} />}
                {m.label}
              </button>
            );
          })}
        </div>
      </div>
      {error && (
        <p role="alert" className="mt-2 text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
