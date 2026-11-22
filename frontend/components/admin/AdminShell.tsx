"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ChartIcon, FileIcon, GridIcon, ListIcon, LogoutIcon, PlusIcon, SearchIcon } from "@/components/icons";
import { Logo } from "@/components/Logo";
import { adminApi } from "@/lib/admin-api";

const NAV = [
  { href: "/admin", label: "Ringkasan", icon: GridIcon, exact: true },
  { href: "/admin/data", label: "Kelola Data", icon: ListIcon },
  { href: "/admin/tambah", label: "Tambah Dokumen", icon: PlusIcon },
  { href: "/admin/import", label: "Import CSV / Excel", icon: FileIcon },
  { href: "/admin/evaluasi", label: "Evaluasi Model", icon: ChartIcon },
];

/** Kerangka halaman admin: sidebar navigasi + bar atas (nama admin, tautan publik, keluar). */
export function AdminShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [username, setUsername] = useState<string | null>(null);
  // Menu navigasi di HP/tablet (di bawah lg) dilipat; di desktop selalu tampil sebagai sidebar.
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    // Sekaligus memeriksa sesi: bila tidak valid, adminApi mengarahkan ke halaman login.
    adminApi.get<{ username: string }>("/admin/me").then((me) => setUsername(me.username), () => {});
  }, []);

  async function logout() {
    await adminApi.post("/admin/logout").catch(() => {});
    router.replace("/admin/login");
  }

  return (
    <div className="flex min-h-screen flex-col bg-mist lg:flex-row">
      <aside className="border-b border-line bg-surface lg:w-64 lg:shrink-0 lg:border-b-0 lg:border-r">
        <div className="flex items-center justify-between px-4 py-3 sm:px-5 lg:block lg:py-6">
          <Link href="/admin" aria-label="Ringkasan admin">
            <Logo size="sm" />
          </Link>
          <button
            type="button"
            onClick={() => setMenuOpen(!menuOpen)}
            aria-expanded={menuOpen}
            aria-controls="admin-nav"
            className="flex items-center gap-2 rounded-md border border-line px-3 py-1.5 text-sm hover:bg-mist lg:hidden"
          >
            <svg aria-hidden width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              {menuOpen ? <path d="M6 6l12 12M18 6L6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
            </svg>
            Menu
          </button>
        </div>
        <nav
          id="admin-nav"
          aria-label="Navigasi admin"
          className={`${menuOpen ? "flex" : "hidden"} flex-col gap-1 border-t border-line px-3 py-3 lg:flex lg:border-0 lg:pt-0 lg:pb-6`}
        >
          <p className="hidden px-3 pb-2 text-xs uppercase tracking-widest text-muted lg:block">Navigasi</p>
          {NAV.map((item) => {
            const active = item.exact ? pathname === item.href : pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                onClick={() => setMenuOpen(false)}
                className={`flex shrink-0 items-center gap-3 whitespace-nowrap rounded-md px-3 py-2.5 text-sm lg:py-2 ${
                  active ? "border-l-2 border-navy bg-mist font-medium text-navy" : "text-muted hover:bg-mist hover:text-ink"
                }`}
              >
                <Icon size={16} />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center justify-end gap-3 border-b border-line bg-surface px-4 py-3 sm:px-8">
          <Link href="/" className="inline-flex items-center gap-2 rounded-md border border-line px-3 py-1.5 text-sm hover:border-navy">
            <SearchIcon size={14} /> Pencarian Publik
          </Link>
          <span className="max-w-32 truncate text-sm font-medium">{username ?? "…"}</span>
          <button type="button" onClick={logout} aria-label="Keluar" title="Keluar" className="rounded-md p-2 text-muted hover:bg-mist hover:text-ink">
            <LogoutIcon size={18} />
          </button>
        </div>
        <main className="flex-1">{children}</main>
        <footer className="border-t border-line px-4 py-4 text-xs text-muted sm:px-8">
          CariSkripsi · Sistem Temu Kembali Skripsi Universitas Jember
        </footer>
      </div>
    </div>
  );
}
