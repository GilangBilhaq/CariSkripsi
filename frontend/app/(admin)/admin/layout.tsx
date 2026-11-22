import type { Metadata } from "next";
import { Suspense } from "react";
import { AdminShell } from "@/components/admin/AdminShell";
import { Spinner } from "@/components/admin/ui";

export const metadata: Metadata = { title: { default: "Admin", template: "%s · Admin CariSkripsi" } };

// Halaman admin sepenuhnya dirender di browser (data bergantung pada sesi login), jadi seluruh
// kerangka dibungkus Suspense: Next.js 16 mewajibkannya untuk hook URL seperti usePathname/useParams.
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={<div className="p-8"><Spinner /></div>}>
      <AdminShell>{children}</AdminShell>
    </Suspense>
  );
}
