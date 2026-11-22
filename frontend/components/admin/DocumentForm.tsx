"use client";

import { useState } from "react";
import { adminApi } from "@/lib/admin-api";
import { ApiError } from "@/lib/api";
import type { AdminDocument, ValidationError } from "@/lib/types";
import { btn, inputClass, Notice } from "./ui";

export type DocumentValues = {
  judul: string;
  abstrak: string;
  tahun: string;
  link: string;
  penulis: string;
  program_studi: string;
  fakultas: string;
  kata_kunci: string;
};

export const EMPTY_DOCUMENT: DocumentValues = {
  judul: "",
  abstrak: "",
  tahun: String(new Date().getFullYear()),
  link: "",
  penulis: "",
  program_studi: "",
  fakultas: "",
  kata_kunci: "",
};

export function valuesFromDocument(doc: AdminDocument): DocumentValues {
  return {
    judul: doc.judul_asli,
    abstrak: doc.abstrak_asli ?? "",
    tahun: doc.tahun ? String(doc.tahun) : "",
    link: doc.link,
    penulis: doc.penulis_teks ?? "",
    program_studi: doc.program_studi ?? "",
    fakultas: doc.fakultas ?? "",
    kata_kunci: doc.kata_kunci_teks ?? "",
  };
}

type Field = { name: keyof DocumentValues; label: string; required?: boolean; hint?: string; multiline?: boolean };

const FIELDS: Field[] = [
  { name: "judul", label: "Judul", required: true, hint: "3–500 karakter, sesuai judul di repositori." },
  {
    name: "abstrak",
    label: "Abstrak",
    multiline: true,
    hint: "Boleh kosong; dokumen tetap bisa dicari dari judulnya. Abstrak berbahasa Inggris akan diterjemahkan otomatis.",
  },
  { name: "tahun", label: "Tahun", required: true, hint: "Angka 4 digit, 1990 sampai tahun depan." },
  { name: "link", label: "Link repositori / DOI", required: true, hint: "Contoh: https://repository.unej.ac.id/handle/123456789/12345" },
  { name: "penulis", label: "Penulis", hint: "Pisahkan beberapa nama dengan titik koma (;)." },
  { name: "program_studi", label: "Program studi" },
  { name: "fakultas", label: "Fakultas" },
  { name: "kata_kunci", label: "Kata kunci", hint: "Pisahkan dengan titik koma (;)." },
];

type Props = {
  initial: DocumentValues;
  documentId?: number; // ada = mode edit
  onSaved: (doc: AdminDocument) => void;
};

/** Form tambah/edit dokumen. Validasi akhir dilakukan backend (aturan yang sama dengan import). */
export function DocumentForm({ initial, documentId, onSaved }: Props) {
  const [values, setValues] = useState(initial);
  const [errors, setErrors] = useState<ValidationError[]>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  function set(name: keyof DocumentValues, value: string) {
    setValues((v) => ({ ...v, [name]: value }));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErrors([]);
    setMessage("");
    try {
      const doc = documentId
        ? await adminApi.put<AdminDocument>(`/admin/documents/${documentId}`, values)
        : await adminApi.post<AdminDocument>("/admin/documents", values);
      onSaved(doc);
    } catch (err) {
      if (err instanceof ApiError) {
        setMessage(err.message);
        setErrors(err.errors);
      } else setMessage("Server tidak dapat dihubungi.");
    } finally {
      setBusy(false);
    }
  }

  const errorFor = (name: string) => errors.find((e) => e.kolom === name)?.pesan;

  return (
    <form onSubmit={submit} className="space-y-5" noValidate>
      {message && <Notice kind="error">{message}</Notice>}
      {FIELDS.map((f) => {
        const err = errorFor(f.name);
        const id = `field-${f.name}`;
        const common = {
          id,
          value: values[f.name],
          onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => set(f.name, e.target.value),
          "aria-invalid": err ? true : undefined,
          "aria-describedby": `${id}-hint`,
          className: `${inputClass} ${err ? "border-danger" : ""}`,
        };
        return (
          <div key={f.name} className="space-y-1.5">
            <label htmlFor={id} className="text-sm font-semibold">
              {f.label} {f.required && <span className="text-danger">*</span>}
            </label>
            {f.multiline ? <textarea rows={8} {...common} /> : <input {...common} inputMode={f.name === "tahun" ? "numeric" : undefined} />}
            <p id={`${id}-hint`} className={`text-xs ${err ? "text-danger" : "text-muted"}`}>
              {err ?? f.hint}
            </p>
          </div>
        );
      })}
      <div className="flex gap-3 border-t border-line pt-5">
        <button type="submit" disabled={busy} className={btn.primary}>
          {busy ? "Menyimpan…" : documentId ? "Simpan Perubahan" : "Simpan Dokumen"}
        </button>
      </div>
      <p className="text-xs text-muted">
        Setelah disimpan, dokumen masuk antrean indeks. Klik “Bangun Ulang Indeks” di Ringkasan agar bisa dicari.
      </p>
    </form>
  );
}
