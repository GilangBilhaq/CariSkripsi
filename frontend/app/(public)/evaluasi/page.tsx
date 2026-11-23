import { redirect } from "next/navigation";

// Hasil evaluasi hanya untuk admin. Tautan lama /evaluasi diarahkan ke halaman admin
// (pengunjung yang belum login otomatis diminta login oleh proxy.ts).
export default function EvaluationPage() {
  redirect("/admin/evaluasi");
}
