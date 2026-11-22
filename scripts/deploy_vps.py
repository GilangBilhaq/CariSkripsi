"""Deploy CariSkripsi ke VPS (Docker Compose: Caddy + frontend + backend). Panduan: DEPLOY.md.

Dijalankan dari akar proyek di komputer pengembang (butuh ssh/scp dengan kunci SSH yang sudah terpasang):

    backend\\.venv\\Scripts\\python scripts\\deploy_vps.py                 kirim kode terbaru + jalankan ulang
    backend\\.venv\\Scripts\\python scripts\\deploy_vps.py --data          + GANTI database & indeks di VPS
                                                                        dengan salinan dari komputer ini
    backend\\.venv\\Scripts\\python scripts\\deploy_vps.py --siapkan       + jalankan ulang persiapan server
    backend\\.venv\\Scripts\\python scripts\\deploy_vps.py --unduh-cadangan  unduh cadangan database terbaru

Pengaturan dibaca dari deploy.env (lihat deploy.env.example).
"""

from __future__ import annotations

import argparse
import secrets
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / "deploy.env"
REMOTE = "/opt/cariskripsi"

# Yang TIDAK ikut dikirim ke server.
SKIP_DIRS = {".venv", "node_modules", ".next", "__pycache__", ".pytest_cache", "tests", ".vercel"}
SKIP_SUFFIXES = (".tsbuildinfo", ".pyc")


# --- pengaturan ----------------------------------------------------------------------------------

def read_env() -> dict[str, str]:
    if not ENV_FILE.exists():
        sys.exit("deploy.env belum ada. Salin deploy.env.example menjadi deploy.env lalu isi.")
    env = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    for key in ("VPS_HOST", "VPS_USER"):
        if not env.get(key):
            sys.exit(f"{key} belum diisi di deploy.env")
    if not env.get("CARISKRIPSI_SECRET_KEY"):
        env["CARISKRIPSI_SECRET_KEY"] = secrets.token_urlsafe(48)
        text = ENV_FILE.read_text(encoding="utf-8")
        ENV_FILE.write_text(text.replace("CARISKRIPSI_SECRET_KEY=",
                                         f"CARISKRIPSI_SECRET_KEY={env['CARISKRIPSI_SECRET_KEY']}", 1),
                            encoding="utf-8")
        print("Kunci rahasia baru dibuat dan disimpan di deploy.env")
    return env


class Server:
    def __init__(self, env: dict[str, str]):
        self.port = env.get("VPS_PORT", "22")
        self.target = f"{env['VPS_USER']}@{env['VPS_HOST']}"
        self.opts = ["-o", "BatchMode=yes", "-o", "ServerAliveInterval=30"]

    def run(self, script: str, check: bool = True) -> int:
        """Jalankan skrip bash di server (lewat stdin, jadi tidak ada masalah tanda kutip)."""
        proc = subprocess.run(["ssh", "-p", self.port, *self.opts, self.target, "bash -s"],
                              input=script.replace("\r\n", "\n").encode())
        if check and proc.returncode != 0:
            sys.exit(f"Perintah di server gagal (kode {proc.returncode}).")
        return proc.returncode

    def upload(self, local: Path, remote: str) -> None:
        subprocess.run(["scp", "-P", self.port, *self.opts, str(local), f"{self.target}:{remote}"], check=True)

    def download(self, remote: str, local: Path) -> None:
        subprocess.run(["scp", "-P", self.port, *self.opts, f"{self.target}:{remote}", str(local)], check=True)


# --- paket kode dan data -------------------------------------------------------------------------

def _add_tree(tar: tarfile.TarFile, folder: Path, arcname: str) -> None:
    for path in sorted(folder.rglob("*")):
        rel = path.relative_to(folder)
        if any(part in SKIP_DIRS for part in rel.parts) or path.name.endswith(SKIP_SUFFIXES):
            continue
        if path.is_file():
            tar.add(path, f"{arcname}/{rel.as_posix()}", recursive=False)


def pack_code(out: Path) -> None:
    with tarfile.open(out, "w:gz") as tar:
        for name in ("backend", "frontend", "deploy"):
            _add_tree(tar, ROOT / name, name)


def pack_data(out: Path) -> str:
    """Salinan database (aman walau server lokal sedang berjalan) + indeks aktif + cache embedding."""
    data = ROOT / "data"
    with tempfile.TemporaryDirectory() as tmp:
        snapshot = Path(tmp) / "cariskripsi.db"
        src = sqlite3.connect(f"file:{(data / 'cariskripsi.db').as_posix()}?mode=ro", uri=True)
        dst = sqlite3.connect(snapshot)
        src.backup(dst)
        row = dst.execute("SELECT versi FROM index_versions WHERE status = 'active'").fetchone()
        dst.execute("PRAGMA journal_mode=DELETE")
        src.close()
        dst.close()
        if row is None:
            sys.exit("Belum ada indeks aktif di database lokal. Jalankan build-index dulu.")
        versi = row[0]
        with tarfile.open(out, "w") as tar:  # embedding tidak bisa dikompres; tar biasa saja
            tar.add(snapshot, "cariskripsi.db")
            tar.add(data / "index" / versi, f"index/{versi}")
            cache = data / "index" / "embedding_cache.npz"
            if cache.exists():
                tar.add(cache, "index/embedding_cache.npz")
    return versi


# --- langkah deploy --------------------------------------------------------------------------------

def deploy(env: dict[str, str], with_data: bool, setup: bool) -> None:
    server = Server(env)
    with tempfile.TemporaryDirectory() as tmp:
        code = Path(tmp) / "kode.tar.gz"
        pack_code(code)
        print(f"Mengirim kode ({code.stat().st_size / 1e6:.1f} MB)...")
        server.run(f"mkdir -p {REMOTE}")
        server.upload(code, f"{REMOTE}/kode.tar.gz")

        dotenv = "\n".join([
            f"CARISKRIPSI_SECRET_KEY={env['CARISKRIPSI_SECRET_KEY']}",
            f"SITE_ADDRESS={env.get('SITE_ADDRESS') or ':80'}",
            f"COOKIE_SECURE={env.get('COOKIE_SECURE') or '0'}",
        ])
        server.run(f"""
set -e
cd {REMOTE}
rm -rf backend frontend
tar -xzf kode.tar.gz && rm kode.tar.gz
sed -i 's/\\r$//' deploy/*.sh deploy/Caddyfile deploy/docker-compose.yml
chmod +x deploy/*.sh
umask 077
cat > deploy/.env <<'EOF'
{dotenv}
EOF
""")
        print("Kode terpasang.")

        if setup or server.run("command -v docker >/dev/null", check=False) != 0:
            print("Menyiapkan server (swap, Docker, firewall, cadangan harian)...")
            server.run(f"bash {REMOTE}/deploy/setup-server.sh")

        if with_data:
            bundle = Path(tmp) / "data.tar"
            versi = pack_data(bundle)
            print(f"Mengirim database + indeks {versi} ({bundle.stat().st_size / 1e6:.0f} MB)...")
            server.upload(bundle, f"{REMOTE}/data.tar")
            server.run(f"""
set -e
cd {REMOTE}
docker compose -f deploy/docker-compose.yml stop backend 2>/dev/null || true
if [ -f data/cariskripsi.db ]; then
  cp data/cariskripsi.db backups/sebelum-ganti-$(date -u +%Y%m%d-%H%M).db
fi
rm -rf data/cariskripsi.db data/cariskripsi.db-wal data/cariskripsi.db-shm data/index
tar -xf data.tar -C data && rm data.tar
chown -R 1000:1000 data
""")
            print("Data terpasang (data lama, bila ada, disalin ke /opt/cariskripsi/backups).")

    print("Membangun dan menjalankan container (build pertama bisa 15-25 menit di VPS 1 core)...")
    server.run(f"cd {REMOTE}/deploy && docker compose up -d --build --remove-orphans && docker image prune -f")
    wait_healthy(server)


def wait_healthy(server: Server) -> None:
    print("Menunggu backend siap (memuat model + indeks)...")
    check = ("cd /opt/cariskripsi/deploy && docker compose exec -T backend python -c "
             "\"import urllib.request as u; print(u.urlopen('http://127.0.0.1:8080/api/health', timeout=10).read().decode())\"")
    for _ in range(40):
        if server.run(check + " 2>/dev/null", check=False) == 0:
            print("Backend siap.")
            return
        time.sleep(10)
    sys.exit("Backend belum siap setelah ±7 menit. Cek log: docker compose logs backend")


def download_backup(env: dict[str, str]) -> None:
    server = Server(env)
    server.run("/usr/local/bin/cariskripsi-backup")
    out = ROOT / "data" / "cadangan-vps"
    out.mkdir(parents=True, exist_ok=True)
    # Nama file terbaru dicari di server, lalu diunduh.
    proc = subprocess.run(["ssh", "-p", server.port, *server.opts, server.target,
                           "ls -1t /opt/cariskripsi/backups/cariskripsi-*.db.gz | head -1"],
                          capture_output=True, text=True, check=True)
    remote = proc.stdout.strip()
    server.download(remote, out / Path(remote).name)
    print(f"Cadangan tersimpan: {out / Path(remote).name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", action="store_true",
                        help="ganti database + indeks di VPS dengan salinan dari komputer ini")
    parser.add_argument("--siapkan", action="store_true", help="jalankan ulang persiapan server")
    parser.add_argument("--unduh-cadangan", action="store_true", help="unduh cadangan database terbaru")
    args = parser.parse_args()
    env = read_env()
    if args.unduh_cadangan:
        download_backup(env)
    else:
        deploy(env, with_data=args.data, setup=args.siapkan)


if __name__ == "__main__":
    main()
