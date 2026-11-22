import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { AbstractView } from "@/components/AbstractView";
import { CopyCitation } from "@/components/CopyCitation";
import { ArrowLeftIcon, ExternalIcon, HomeIcon } from "@/components/icons";
import { ApiError, apiGet } from "@/lib/api";
import { formatAuthors, formatDecimal } from "@/lib/format";
import type { DocumentDetail } from "@/lib/types";

export const metadata: Metadata = { title: "Detail Dokumen" };

type Props = { params: Promise<{ id: string }> };

export default function DocumentPage({ params }: Props) {
  return (
    <Suspense fallback={<p className="p-8 text-center text-muted">Memuat dokumen…</p>}>
      <DocumentContent params={params} />
    </Suspense>
  );
}

function apaCitation(doc: DocumentDetail): string {
  const authors = doc.penulis.length ? doc.penulis.join(", ") : "Anonim";
  return `${authors}. (${doc.tahun ?? "t.t."}). ${doc.judul_asli} [Skripsi, Universitas Jember]. ${doc.link}`;
}

async function DocumentContent({ params }: Props) {
  const { id } = await params;
  const doc = /^\d+$/.test(id) ? await apiGet<DocumentDetail>(`/documents/${id}`).catch((e: unknown) => e as Error) : null;

  if (!doc || doc instanceof Error) {
    const notFound = !doc || (doc instanceof ApiError && doc.status === 404);
    return (
      <div className="mx-auto max-w-2xl px-4 py-20 text-center">
        <p className="font-serif text-2xl">{notFound ? "Dokumen tidak ditemukan" : "Dokumen tidak dapat dimuat"}</p>
        <Link href="/" className="mt-4 inline-block text-navy hover:underline">
          Kembali ke pencarian
        </Link>
      </div>
    );
  }

  return (
    <>
      <nav aria-label="Breadcrumb" className="border-b border-line bg-mist">
        <div className="mx-auto flex max-w-4xl items-center gap-2 px-4 py-2 text-sm text-muted sm:px-8">
          <HomeIcon size={14} />
          <Link href="/" className="hover:underline">
            Beranda
          </Link>
          / <span className="font-medium text-ink">Detail Dokumen #{doc.id}</span>
        </div>
      </nav>

      <article className="mx-auto w-full max-w-4xl space-y-8 px-4 py-10 sm:px-8">
        <header className="space-y-3 border-b border-line pb-6">
          <h1 className="font-serif text-3xl leading-tight sm:text-4xl">{doc.judul_asli}</h1>
          {doc.diterjemahkan && doc.judul_id && doc.judul_id !== doc.judul_asli && (
            <p className="font-serif text-lg text-muted">{doc.judul_id}</p>
          )}
          <p className="text-sm">
            <span className="font-semibold">Tahun {doc.tahun ?? "tidak diketahui"}</span>
            <span className="text-muted"> · Penulis: </span>
            {formatAuthors(doc.penulis, 10)}
          </p>
          <p className="text-sm text-muted">
            {doc.program_studi && <>Program Studi: {doc.program_studi} · </>}
            {doc.fakultas ?? "Fakultas tidak tercantum"}, Universitas Jember
          </p>
          <p className="break-all text-sm">
            <span className="text-muted">Tautan: </span>
            <a href={doc.link} target="_blank" rel="noopener noreferrer" className="font-mono text-xs text-navy underline">
              {doc.link}
            </a>
          </p>
          {doc.link_lain.length > 0 && (
            <p className="text-xs text-muted">
              Skripsi kelompok: digabung dari {doc.jumlah_gabungan} unggahan dengan isi yang sama.
            </p>
          )}
          {!doc.terindeks && (
            <p className="rounded bg-warn-soft px-3 py-2 text-sm text-warn">
              Dokumen ini baru ditambahkan atau diubah dan belum masuk indeks pencarian.
            </p>
          )}
        </header>

        <div className="flex flex-wrap gap-3 rounded-lg border border-line bg-surface p-4">
          <a
            href={doc.link}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-md bg-navy px-4 py-2 text-sm font-medium text-white hover:bg-navy-dark"
          >
            Buka di Repositori <ExternalIcon size={14} />
          </a>
          <CopyCitation citation={apaCitation(doc)} />
        </div>

        <AbstractView
          translated={doc.diterjemahkan}
          judulAsli={doc.judul_asli}
          judulId={doc.judul_id}
          abstrakAsli={doc.abstrak_asli}
          abstrakId={doc.abstrak_id}
          kataKunci={doc.kata_kunci}
        />

        <section aria-labelledby="serupa-title" className="space-y-4 border-t border-line pt-8">
          <div>
            <h2 id="serupa-title" className="flex items-center gap-2 font-serif text-2xl">
              <span aria-hidden className="size-2.5 rounded-full bg-sbert-dark" /> Dokumen Serupa
            </h2>
            <p className="text-sm text-muted">Berdasarkan kemiripan vektor embedding IndoSBERT (cosine similarity).</p>
          </div>
          {doc.serupa.length === 0 ? (
            <p className="text-sm text-muted">Belum tersedia (dokumen belum masuk indeks).</p>
          ) : (
            <ul className="space-y-4">
              {doc.serupa.map((s) => (
                <li key={s.id} className="rounded-lg border border-line bg-surface p-5">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="min-w-0 flex-1 space-y-1">
                      <p className="text-xs text-muted">
                        Tahun {s.tahun ?? "-"} · Penulis: {formatAuthors(s.penulis, 2)}
                      </p>
                      <h3 className="font-serif text-lg leading-snug">
                        <Link href={`/dokumen/${s.id}`} className="hover:underline">
                          {s.judul}
                        </Link>
                      </h3>
                    </div>
                    <span className="rounded border border-sbert bg-sbert-soft px-2 py-1 font-mono text-xs text-sbert-dark">
                      Cosine {formatDecimal(s.skor, 3)}
                    </span>
                  </div>
                  {s.cuplikan && <p className="mt-2 line-clamp-2 text-sm text-muted">{s.cuplikan}</p>}
                </li>
              ))}
            </ul>
          )}
        </section>

        <Link href="/" className="inline-flex items-center gap-2 text-sm font-medium hover:underline">
          <ArrowLeftIcon size={14} /> Kembali ke pencarian
        </Link>
      </article>
    </>
  );
}
