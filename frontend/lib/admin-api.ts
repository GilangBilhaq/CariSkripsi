// Klien API untuk halaman admin (hanya dipakai di browser / Client Components).
//
// - Cookie sesi (httpOnly) terkirim otomatis karena backend diakses lewat origin yang sama (/api).
// - Setiap request yang mengubah data membawa header X-CSRF-Token berisi nilai cookie cs_csrf.
// - Bila sesi habis (401), pengguna diarahkan ke halaman login.
import { toApiError } from "./api";

function csrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)cs_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

function redirectToLogin() {
  const next = encodeURIComponent(window.location.pathname + window.location.search);
  // Modul ini bukan komponen React sehingga tidak bisa memakai useRouter; muat ulang penuh ke halaman login.
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.href = `/admin/login?next=${next}`;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const isForm = body instanceof FormData;
  const headers: Record<string, string> = { Accept: "application/json" };
  if (method !== "GET") headers["X-CSRF-Token"] = csrfToken();
  if (body !== undefined && !isForm) headers["Content-Type"] = "application/json";

  const res = await fetch(`/api${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
    credentials: "same-origin",
  });
  if (res.status === 401 && !path.startsWith("/admin/login")) {
    redirectToLogin();
  }
  if (!res.ok) throw await toApiError(res);
  return res.json() as Promise<T>;
}

export const adminApi = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}),
  put: <T>(path: string, body: unknown) => request<T>("PUT", path, body),
  delete: <T>(path: string) => request<T>("DELETE", path),
};

/** URL unduhan (CSV/XLSX). Cookie sesi ikut terkirim karena same-origin. */
export function downloadUrl(path: string): string {
  return `/api${path}`;
}
