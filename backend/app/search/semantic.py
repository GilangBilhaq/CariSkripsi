"""Pencarian semantik dengan IndoSBERT (sentence-transformers) di CPU.

- Teks dokumen = judul_id + abstrak_id, hanya dibersihkan ringan (tanpa stemming/stopword).
- Teks yang lebih panjang dari batas model dipecah per `CHUNK_WORDS` kata. Embedding potongan-potongannya
  dirata-rata menjadi satu vektor dokumen (PRD §12.2).
- Semua vektor dinormalisasi L2, sehingga cosine similarity = dot product.
"""

import hashlib
from collections.abc import Callable
from pathlib import Path

import numpy as np

MAX_SEQ_LENGTH = 256  # token per potongan; 512 (batas model) jauh lebih lambat di CPU
CHUNK_WORDS = 150  # kira-kira 200-230 token IndoBERT, masih di bawah MAX_SEQ_LENGTH
ENCODE_BATCH = 32


def split_into_chunks(text: str, chunk_words: int = CHUNK_WORDS) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    return [" ".join(words[i:i + chunk_words]) for i in range(0, len(words), chunk_words)]


def normalize_rows(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return (matrix / np.clip(norms, 1e-12, None)).astype(np.float32)


class SemanticEncoder:
    """Pembungkus model sentence-transformers. Model baru dimuat saat pertama kali dipakai."""

    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name, device="cpu")
            self._model.max_seq_length = MAX_SEQ_LENGTH
        return self._model

    def encode_query(self, query: str) -> np.ndarray:
        vec = self.model.encode([query], convert_to_numpy=True, show_progress_bar=False)
        return normalize_rows(vec)[0]

    def encode_documents(self, texts: list[str]) -> np.ndarray:
        """Satu vektor ternormalisasi per teks (rata-rata embedding potongan)."""
        chunks: list[str] = []
        owner: list[int] = []  # owner[i] = indeks teks asal untuk potongan ke-i
        for i, text in enumerate(texts):
            for chunk in split_into_chunks(text):
                chunks.append(chunk)
                owner.append(i)
        chunk_vecs = self.model.encode(chunks, batch_size=ENCODE_BATCH, convert_to_numpy=True,
                                       show_progress_bar=False)
        doc_vecs = np.zeros((len(texts), chunk_vecs.shape[1]), dtype=np.float32)
        counts = np.zeros(len(texts), dtype=np.float32)
        np.add.at(doc_vecs, owner, chunk_vecs)
        np.add.at(counts, owner, 1)
        return normalize_rows(doc_vecs / counts[:, None])


def text_fingerprint(model_name: str, text: str) -> str:
    """Penanda isi teks. Bila teks dokumen tidak berubah, embedding lamanya dipakai ulang."""
    return hashlib.sha1(f"{model_name}\n{text}".encode("utf-8")).hexdigest()


class EmbeddingCache:
    """Simpanan embedding per dokumen di satu file .npz (id, fingerprint, vektor).

    Dipakai untuk dua hal:
    1. Pembaruan inkremental: hanya dokumen baru/berubah yang dihitung ulang (PRD §12.3).
    2. Checkpoint: pembangunan panjang yang terhenti bisa dilanjutkan tanpa mengulang dari awal.
    """

    def __init__(self, path: Path):
        self.path = path
        self.entries: dict[int, tuple[str, np.ndarray]] = {}
        if path.exists():
            data = np.load(path, allow_pickle=False)
            for doc_id, fp, vec in zip(data["ids"], data["fingerprints"], data["vectors"]):
                self.entries[int(doc_id)] = (str(fp), vec)

    def get(self, doc_id: int, fingerprint: str) -> np.ndarray | None:
        entry = self.entries.get(doc_id)
        return entry[1] if entry and entry[0] == fingerprint else None

    def put(self, doc_id: int, fingerprint: str, vector: np.ndarray) -> None:
        self.entries[doc_id] = (fingerprint, vector)

    def save(self) -> None:
        if not self.entries:
            return
        ids = np.fromiter(self.entries.keys(), dtype=np.int64)
        fps = np.array([fp for fp, _ in self.entries.values()])
        vecs = np.stack([v for _, v in self.entries.values()]).astype(np.float32)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.stem + ".tmp.npz")
        np.savez(tmp, ids=ids, fingerprints=fps, vectors=vecs)
        tmp.replace(self.path)  # ganti file secara atomik: checkpoint tidak pernah setengah tertulis


def embed_with_cache(
    encoder: SemanticEncoder,
    doc_ids: list[int],
    texts: list[str],
    cache: EmbeddingCache,
    batch_docs: int = 64,
    checkpoint_every: int = 1024,
    progress: Callable[[int, int], None] | None = None,
) -> np.ndarray:
    """Matriks embedding (urut sesuai doc_ids). Dokumen yang ada di cache tidak dihitung ulang."""
    fingerprints = [text_fingerprint(encoder.model_name, t) for t in texts]
    missing = [i for i, (d, fp) in enumerate(zip(doc_ids, fingerprints)) if cache.get(d, fp) is None]

    done_since_checkpoint = 0
    for start in range(0, len(missing), batch_docs):
        batch = missing[start:start + batch_docs]
        vectors = encoder.encode_documents([texts[i] for i in batch])
        for i, vec in zip(batch, vectors):
            cache.put(doc_ids[i], fingerprints[i], vec)
        done_since_checkpoint += len(batch)
        if done_since_checkpoint >= checkpoint_every:
            cache.save()
            done_since_checkpoint = 0
        if progress:
            progress(min(start + batch_docs, len(missing)), len(missing))
    if missing:
        cache.save()

    return np.stack([cache.get(d, fp) for d, fp in zip(doc_ids, fingerprints)]).astype(np.float32)
