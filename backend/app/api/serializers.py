"""Mengubah objek database menjadi dict JSON untuk respons API."""

from datetime import datetime

from app.models import Document, IndexVersion
from app.search.highlight import Highlighted


def iso(dt: datetime | None) -> str | None:
    """Waktu UTC dari database -> teks ISO 8601 bertanda 'Z' (UTC), mis. '2026-11-21T05:30:00Z'."""
    return dt.isoformat(timespec="seconds") + "Z" if dt else None


def highlighted(h: Highlighted) -> dict:
    return {"text": h.text, "highlights": [list(span) for span in h.highlights]}


def split_list(value: str | None) -> list[str]:
    """'a; b; c' -> ['a', 'b', 'c']"""
    return [p.strip() for p in (value or "").split(";") if p.strip()]


def is_translated(doc: Document) -> bool:
    return doc.bahasa_asli == "en" or doc.bahasa_judul == "en"


def document_summary(doc: Document) -> dict:
    """Data ringkas yang tampil di kartu hasil pencarian."""
    return {
        "id": doc.id,
        "judul": doc.judul_id or doc.judul_asli,
        "judul_asli": doc.judul_asli,
        "tahun": doc.tahun,
        "penulis": split_list(doc.penulis),
        "fakultas": doc.fakultas,
        "program_studi": doc.program_studi,
        "link": doc.link,
        "bahasa_asli": doc.bahasa_asli,
        "diterjemahkan": is_translated(doc),
        "abstrak_tersedia": doc.abstrak_tersedia,
    }


def document_full(doc: Document) -> dict:
    return document_summary(doc) | {
        "judul_id": doc.judul_id,
        "abstrak_asli": doc.abstrak_asli,
        "abstrak_id": doc.abstrak_id,
        "kata_kunci": split_list(doc.kata_kunci),
        "link_lain": [line for line in (doc.link_lain or "").splitlines() if line],
        "jumlah_gabungan": doc.jumlah_gabungan,
    }


def document_admin(doc: Document) -> dict:
    """Untuk tabel/form admin: nilai mentah yang bisa diedit + status."""
    return document_full(doc) | {
        "penulis_teks": doc.penulis,
        "kata_kunci_teks": doc.kata_kunci,
        "bahasa_judul": doc.bahasa_judul,
        "sumber": doc.sumber,
        "perlu_indeks": doc.perlu_indeks,
        "jumlah_kata_abstrak": len((doc.abstrak_asli or "").split()),
        "created_at": iso(doc.created_at),
        "updated_at": iso(doc.updated_at),
    }


def index_version(v: IndexVersion | None) -> dict | None:
    if v is None:
        return None
    return {
        "id": v.id, "versi": v.versi, "status": v.status, "tahap": v.tahap, "persen": v.persen,
        "jumlah_dokumen": v.jumlah_dokumen, "model_name": v.model_name, "bm25_params": v.bm25_params,
        "pesan_error": v.pesan_error,
        "created_at": iso(v.created_at),
        "finished_at": iso(v.finished_at),
    }
