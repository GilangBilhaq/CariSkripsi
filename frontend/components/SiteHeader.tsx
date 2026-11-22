import Link from "next/link";
import { Suspense } from "react";
import { Logo } from "./Logo";
import { NavLinks } from "./NavLinks";

const LOCK_ICON = (
  <svg aria-hidden width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="4" y="11" width="16" height="10" rx="2" />
    <path d="M8 11V7a4 4 0 0 1 8 0v4" />
  </svg>
);

/**
 * HP: baris 1 = logo + tombol login (ikon), baris 2 = navigasi selebar layar.
 * Tablet/desktop (sm ke atas): semuanya dalam satu baris.
 */
export function SiteHeader() {
  return (
    <header className="border-b border-line bg-surface">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-4 px-4 sm:flex-nowrap sm:gap-8 sm:px-8">
        <Link href="/" className="flex shrink-0 items-center gap-4 py-3" aria-label="CariSkripsi, beranda">
          <Logo size="sm" />
          <span className="hidden border-l border-line pl-4 text-[10px] uppercase leading-tight tracking-widest text-muted lg:block">
            Sistem Temu Kembali
            <br />
            Dokumen Akademik
          </span>
        </Link>
        <div className="order-last -mx-4 w-[calc(100%+2rem)] border-t border-line sm:order-none sm:mx-0 sm:w-auto sm:min-w-0 sm:flex-1 sm:border-0">
          {/* NavLinks membaca URL (usePathname), jadi perlu Suspense; fallback = tautan tanpa penanda aktif. */}
          <Suspense fallback={<NavLinks static />}>
            <NavLinks />
          </Suspense>
        </div>
        <Link
          href="/admin/login"
          aria-label="Login Admin"
          className="ml-auto flex shrink-0 items-center gap-2 rounded-md border border-line p-2 text-sm text-ink hover:bg-mist sm:ml-0 sm:px-4 sm:py-2"
        >
          {LOCK_ICON}
          <span className="hidden sm:inline">Login Admin</span>
        </Link>
      </div>
    </header>
  );
}
