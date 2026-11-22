"use client";

import { useState } from "react";
import { CopyIcon } from "./icons";

/** Salin sitasi gaya APA: Penulis. (Tahun). Judul [Skripsi, Universitas Jember]. Link */
export function CopyCitation({ citation }: { citation: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(citation);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      window.prompt("Salin sitasi berikut:", citation);
    }
  }

  return (
    <button
      type="button"
      onClick={copy}
      className="inline-flex items-center gap-2 rounded-md border border-line bg-mist px-4 py-2 text-sm hover:border-navy"
    >
      <CopyIcon size={14} /> {copied ? "Sitasi disalin" : "Salin Sitasi (APA)"}
    </button>
  );
}
