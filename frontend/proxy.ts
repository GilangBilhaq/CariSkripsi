import { type NextRequest, NextResponse } from "next/server";

// Proxy (dulu "middleware") berjalan sebelum halaman dirender.
// Pengunjung /admin/* tanpa cookie sesi langsung diarahkan ke halaman login (PRD §17).
// Keabsahan sesi tetap diperiksa backend: bila cookie kedaluwarsa, API admin membalas 401 dan
// halaman admin mengarahkan ke login (lihat lib/admin-api.ts).
export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  if (pathname === "/admin/login") return NextResponse.next();

  if (!request.cookies.has("cs_session")) {
    const url = request.nextUrl.clone();
    url.pathname = "/admin/login";
    url.search = `?next=${encodeURIComponent(pathname + search)}`;
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/admin", "/admin/:path*"],
};
