"use client";

import Link from "next/link";
import { useState } from "react";
import { DocumentForm, EMPTY_DOCUMENT } from "@/components/admin/DocumentForm";
import { Card, Notice, PageHeader } from "@/components/admin/ui";
import type { AdminDocument } from "@/lib/types";

export default function AddDocumentPage() {
  const [saved, setSaved] = useState<AdminDocument | null>(null);
  const [formKey, setFormKey] = useState(0);

  return (
    <>
      <PageHeader title="Tambah Dokumen" description="Input satu skripsi secara manual. Untuk banyak data sekaligus, gunakan Import CSV / Excel." />
      <div className="mx-auto max-w-3xl space-y-4 p-4 sm:p-8">
        {saved && (
          <Notice kind="success">
            Dokumen #{saved.id} “{saved.judul_asli}” tersimpan dan masuk antrean indeks.{" "}
            <Link href={`/admin/data/${saved.id}`} className="underline">
              Lihat / ubah
            </Link>
          </Notice>
        )}
        <Card>
          <DocumentForm
            key={formKey}
            initial={EMPTY_DOCUMENT}
            onSaved={(doc) => {
              setSaved(doc);
              setFormKey((k) => k + 1); // kosongkan form untuk input berikutnya
              window.scrollTo({ top: 0, behavior: "smooth" });
            }}
          />
        </Card>
      </div>
    </>
  );
}
