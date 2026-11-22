#!/usr/bin/env bash
# Persiapan sekali jalan untuk VPS Ubuntu baru (dijalankan sebagai root oleh scripts/deploy_vps.py).
# Aman dijalankan ulang.
set -euo pipefail

# 1. Swap 2 GB: cadangan saat bangun ulang indeks / build image (RAM fisik hanya 2 GB).
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
sysctl -q vm.swappiness=10
echo 'vm.swappiness=10' > /etc/sysctl.d/99-cariskripsi.conf

# 2. Docker + Compose, sqlite3 (cadangan database), pembaruan keamanan otomatis.
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q docker.io docker-compose-v2 sqlite3 unattended-upgrades
systemctl enable --now docker
# Log container dibatasi supaya disk tidak penuh.
if [ ! -f /etc/docker/daemon.json ]; then
  echo '{"log-driver":"json-file","log-opts":{"max-size":"10m","max-file":"3"}}' > /etc/docker/daemon.json
  systemctl restart docker
fi

# 3. Firewall: hanya SSH, HTTP, HTTPS.
ufw allow 22/tcp >/dev/null
ufw allow 80/tcp >/dev/null
ufw allow 443/tcp >/dev/null
ufw --force enable >/dev/null

# 4. Folder aplikasi. Data dimiliki uid 1000 (user di dalam container backend).
mkdir -p /opt/cariskripsi/data /opt/cariskripsi/backups
chown -R 1000:1000 /opt/cariskripsi/data

# 5. Cadangan database harian pukul 02.30 WIB (19.30 UTC).
install -m 755 /opt/cariskripsi/deploy/backup.sh /usr/local/bin/cariskripsi-backup
echo '30 19 * * * root /usr/local/bin/cariskripsi-backup >> /var/log/cariskripsi-backup.log 2>&1' \
  > /etc/cron.d/cariskripsi-backup

echo "Persiapan server selesai."
