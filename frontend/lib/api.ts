// Klien API untuk halaman publik.
// Di server (Server Components) memanggil FastAPI langsung; di browser memakai path relatif /api
// yang diteruskan Next.js ke FastAPI (lihat rewrites di next.config.ts).
import type { ValidationError } from "./types";

const SERVER_BASE = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

function baseUrl(): string {
  return typeof window === "undefined" ? SERVER_BASE : "";
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public errors: ValidationError[] = [],
  ) {
    super(message);
  }
}

/** Ubah respons gagal FastAPI menjadi ApiError dengan pesan berbahasa Indonesia. */
export async function toApiError(res: Response): Promise<ApiError> {
  let message = `Terjadi kesalahan (${res.status})`;
  let errors: ValidationError[] = [];
  try {
    const body = await res.json();
    const detail = body.detail;
    if (typeof detail === "string") message = detail;
    else if (detail && typeof detail === "object" && "pesan" in detail) {
      message = detail.pesan;
      errors = detail.errors ?? [];
    } else if (Array.isArray(detail)) message = "Data yang dikirim tidak valid.";
  } catch {
    /* respons bukan JSON */
  }
  return new ApiError(res.status, message, errors);
}

export async function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${baseUrl()}/api${path}`, {
    ...init,
    headers: { Accept: "application/json", ...init?.headers },
  });
  if (!res.ok) throw await toApiError(res);
  return res.json() as Promise<T>;
}

/** {q: "x", page: 2, kosong: undefined} -> "?q=x&page=2" (nilai kosong dilewati). */
export function queryString(params: Record<string, string | number | boolean | null | undefined>): string {
  const sp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") sp.set(key, String(value));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export type Health = { status: string; app: string; version: string };
