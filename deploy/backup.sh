#!/usr/bin/env bash
# Cadangan database CariSkripsi (dipasang sebagai /usr/local/bin/cariskripsi-backup, jalan tiap hari via cron).
# Menyimpan 14 cadangan terakhir di /opt/cariskripsi/backups. File indeks tidak dicadangkan di sini:
# indeks selalu bisa dibangun ulang dari database (dan salinannya ada di komputer pengembang).
set -euo pipefail
DB=/opt/cariskripsi/data/cariskripsi.db
OUT=/opt/cariskripsi/backups
mkdir -p "$OUT"
name="cariskripsi-$(date -u +%Y%m%d-%H%M).db"
sqlite3 "$DB" ".backup '$OUT/$name'"   # aman walau server sedang menulis
gzip -f "$OUT/$name"
ls -1t "$OUT"/cariskripsi-*.db.gz | tail -n +15 | xargs -r rm --
echo "$(date -u) cadangan $name.gz"
