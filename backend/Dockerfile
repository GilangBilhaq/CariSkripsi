# Server pencarian CariSkripsi (dijalankan di VPS lewat deploy/docker-compose.yml).
# Panduan lengkap: DEPLOY.md di akar proyek.
FROM python:3.11-slim

# Jalan sebagai user biasa (bukan root).
RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/home/user/.cache/huggingface \
    CARISKRIPSI_DATA_DIR=/home/user/data \
    CARISKRIPSI_COOKIE_SECURE=1 \
    CARISKRIPSI_TRUST_FORWARDED_FOR=1
WORKDIR /home/user/app

# torch versi CPU (jauh lebih kecil dari versi CUDA), lalu dependensi lain.
COPY requirements.txt .
RUN pip install --no-cache-dir torch==2.9.1 --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt

USER user
# Unduh model saat build supaya server langsung siap ketika menyala (tidak mengunduh setiap restart).
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('firqaaa/indo-sentence-bert-base')" \
 && python -c "from transformers import MarianMTModel, MarianTokenizer as T; m='Helsinki-NLP/opus-mt-en-id'; T.from_pretrained(m); MarianMTModel.from_pretrained(m)"
ENV HF_HUB_OFFLINE=1

COPY --chown=user app ./app

# Cloud Run memberi nomor port lewat env PORT (biasanya 8080).
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
