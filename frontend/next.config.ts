import type { NextConfig } from "next";

// Alamat FastAPI. Semua /api/* diteruskan ke sini sehingga browser hanya melihat satu origin
// (tanpa CORS, cookie sesi admin tetap first-party).
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // Hasil build mandiri (server.js + node_modules minimal) untuk image Docker di VPS.
  output: "standalone",
  // Sembunyikan tombol "N" Next.js di pojok layar saat pengembangan lokal (error tetap ditampilkan).
  devIndicators: false,
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` }];
  },
};

export default nextConfig;
