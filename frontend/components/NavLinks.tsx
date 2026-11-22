"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

// `short` dipakai di layar HP supaya ketiga tautan muat dalam satu baris.
const LINKS = [
  { href: "/", label: "Pencarian", short: "Pencarian", match: (p: string) => p === "/" || p.startsWith("/cari") || p.startsWith("/dokumen") },
  { href: "/bandingkan", label: "Mode Bandingkan", short: "Bandingkan", match: (p: string) => p.startsWith("/bandingkan") },
  { href: "/evaluasi", label: "Evaluasi Model", short: "Evaluasi", match: (p: string) => p.startsWith("/evaluasi") },
];

/** Navigasi utama. Varian `static` (tanpa penanda halaman aktif) dipakai sebagai fallback Suspense. */
export function NavLinks({ static: isStatic = false }: { static?: boolean }) {
  return isStatic ? <NavList pathname={null} /> : <ActiveNavList />;
}

function ActiveNavList() {
  return <NavList pathname={usePathname()} />;
}

function NavList({ pathname }: { pathname: string | null }) {
  return (
    <nav aria-label="Navigasi utama" className="grid grid-cols-3 text-sm sm:flex sm:gap-8 sm:text-base">
      {LINKS.map((l) => {
        const active = pathname !== null && l.match(pathname);
        return (
          <Link
            key={l.href}
            href={l.href}
            aria-current={active ? "page" : undefined}
            className={`whitespace-nowrap border-b-2 py-3 text-center transition-colors sm:py-5 ${
              active ? "border-navy text-ink" : "border-transparent text-muted hover:text-ink"
            }`}
          >
            <span className="sm:hidden">{l.short}</span>
            <span className="hidden sm:inline">{l.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
