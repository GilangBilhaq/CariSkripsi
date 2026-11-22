# Menjalankan backend (FastAPI, port 8000) dan frontend (Next.js, port 3000) sekaligus.
# Pemakaian (dari folder proyek):  powershell -ExecutionPolicy Bypass -File scripts\dev.ps1
# Hentikan dengan Ctrl+C; kedua proses ikut berhenti.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root "backend\.venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "Virtualenv backend belum ada. Lihat README.md bagian 'Persiapan'." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path (Join-Path $root "frontend\node_modules"))) {
    Write-Host "Dependensi frontend belum dipasang. Jalankan: cd frontend; npm install" -ForegroundColor Red
    exit 1
}

# Model sudah diunduh saat persiapan; jangan cek ke internet setiap kali server mulai.
$env:HF_HUB_OFFLINE = "1"

Write-Host "Menjalankan backend di http://localhost:8000 (dokumentasi API: /api/docs) ..." -ForegroundColor Cyan
$backend = Start-Process -FilePath $python -ArgumentList "-m", "uvicorn", "app.main:app", "--port", "8000" `
    -WorkingDirectory (Join-Path $root "backend") -NoNewWindow -PassThru

Write-Host "Menjalankan frontend di http://localhost:3000 ..." -ForegroundColor Cyan
$frontend = Start-Process -FilePath "npm.cmd" -ArgumentList "run", "dev" `
    -WorkingDirectory (Join-Path $root "frontend") -NoNewWindow -PassThru

try {
    Write-Host "Buka http://localhost:3000 . Tekan Ctrl+C untuk berhenti." -ForegroundColor Green
    Wait-Process -Id $backend.Id, $frontend.Id
}
finally {
    foreach ($p in @($backend, $frontend)) {
        if (-not $p.HasExited) {
            # /T menghentikan proses anak juga (npm menjalankan node sebagai proses anak).
            taskkill /PID $p.Id /T /F | Out-Null
        }
    }
    Write-Host "Server dihentikan."
}
