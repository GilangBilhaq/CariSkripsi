import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { ArrowLeftIcon } from "@/components/icons";
import { Logo } from "@/components/Logo";
import { LoginForm } from "./LoginForm";

export const metadata: Metadata = { title: "Login Admin" };

export default function LoginPage() {
  return (
    <section className="flex flex-1 flex-col items-center px-4 py-12">
      <div className="w-full max-w-lg space-y-6 rounded-xl border border-line bg-surface p-8 sm:p-12">
        <div className="space-y-3 border-b border-line pb-6 text-center">
          <Logo size="md" />
          <h1 className="font-serif text-2xl">Konsol Admin</h1>
          <p className="text-sm text-muted">
            Masuk untuk mengelola koleksi skripsi, membangun indeks BM25 &amp; IndoSBERT, dan menjalankan evaluasi.
          </p>
        </div>
        <Suspense>
          <LoginForm />
        </Suspense>
      </div>
      <Link href="/" className="mt-8 inline-flex items-center gap-2 text-sm text-muted hover:text-ink">
        <ArrowLeftIcon size={14} /> Kembali ke Pencarian Publik
      </Link>
    </section>
  );
}
