"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { EyeIcon, LockIcon } from "@/components/icons";
import { adminApi } from "@/lib/admin-api";
import { ApiError } from "@/lib/api";

/** Hanya izinkan kembali ke halaman admin sendiri (mencegah open redirect ke situs lain). */
function safeNext(value: string | null): string {
  return value && value.startsWith("/admin") && !value.startsWith("//") ? value : "/admin";
}

export function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await adminApi.post("/admin/login", { username, password });
      router.replace(safeNext(params.get("next")));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Server tidak dapat dihubungi.");
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      <div className="space-y-2">
        <label htmlFor="username" className="text-sm font-semibold">
          Username
        </label>
        <input
          id="username"
          autoComplete="username"
          required
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="w-full rounded-md border border-line px-4 py-3 outline-none focus:border-navy"
        />
      </div>
      <div className="space-y-2">
        <label htmlFor="password" className="text-sm font-semibold">
          Kata sandi
        </label>
        <div className="flex items-center rounded-md border border-line focus-within:border-navy">
          <LockIcon size={16} className="ml-4 text-muted" />
          <input
            id="password"
            type={showPassword ? "text" : "password"}
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="min-w-0 flex-1 bg-transparent px-3 py-3 outline-none"
          />
          <button
            type="button"
            onClick={() => setShowPassword((v) => !v)}
            aria-label={showPassword ? "Sembunyikan kata sandi" : "Tampilkan kata sandi"}
            className="px-4 text-muted hover:text-ink"
          >
            <EyeIcon size={18} />
          </button>
        </div>
      </div>
      {error && (
        <p role="alert" className="rounded-md bg-danger-soft px-4 py-2 text-sm text-danger">
          {error}
        </p>
      )}
      <button
        type="submit"
        disabled={busy}
        className="w-full rounded-md bg-navy py-3 font-medium text-white hover:bg-navy-dark disabled:opacity-60"
      >
        {busy ? "Memeriksa…" : "Masuk ke Konsol Admin"}
      </button>
      <p className="text-center text-xs text-muted">
        Lupa kata sandi? Jalankan <code className="font-mono">python -m app.cli create-admin &lt;username&gt;</code> di server.
      </p>
    </form>
  );
}
