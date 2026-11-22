// Bentuk data dari API backend (lihat backend/app/api/*.py).

export type Method = "bm25" | "sbert";

/** Teks + rentang [awal, akhir) yang perlu disorot. */
export type Highlighted = { text: string; highlights: [number, number][] };

export type DocumentSummary = {
  id: number;
  judul: string; // versi bahasa Indonesia (terjemahan bila aslinya Inggris)
  judul_asli: string;
  tahun: number | null;
  penulis: string[];
  fakultas: string | null;
  program_studi: string | null;
  link: string;
  bahasa_asli: string;
  diterjemahkan: boolean;
  abstrak_tersedia: boolean;
};

export type SearchResult = DocumentSummary & {
  rank: number;
  score: number;
  judul_sorot: Highlighted;
  cuplikan: Highlighted;
  frekuensi_kata?: number;
  peringkat_di_lawan?: number | null;
};

export type SearchResponse = {
  query: string;
  method: Method;
  total_cocok: number;
  total: number;
  page: number;
  pages: number;
  page_size: number;
  took_ms: number;
  results: SearchResult[];
};

export type CompareColumn = { took_ms: number; total_cocok: number; results: SearchResult[] };

export type CompareResponse = {
  query: string;
  top_k: number;
  jumlah_irisan: number;
  rasio_irisan: number;
  bm25: CompareColumn;
  sbert: CompareColumn;
  model_sbert: string;
};

export type DocumentDetail = DocumentSummary & {
  judul_id: string | null;
  abstrak_asli: string | null;
  abstrak_id: string | null;
  kata_kunci: string[];
  link_lain: string[];
  jumlah_gabungan: number;
  terindeks: boolean;
  serupa: (DocumentSummary & { skor: number; cuplikan: string })[];
};

export type PublicStats = {
  dokumen_terindeks: number;
  dokumen_total: number;
  tahun: { tahun: number; jumlah: number }[];
  indeks_versi: string | null;
  semantik_siap: boolean; // false = baru BM25 yang aktif (embedding IndoSBERT masih dihitung)
  model_sbert: string;
  bm25_params: { k1: number; b: number };
};

// --- Evaluasi ---

export type MethodMetrics = { p_at_k: number; r_at_k: number; ap: number; ndcg_at_k: number; waktu_ms: number };

export type QueryEvaluation = {
  query_id: number;
  teks: string;
  kategori: QueryCategory;
  jumlah_relevan: number;
  belum_diselesaikan: number;
  pemenang: Method | "seri";
  metode: Record<Method, MethodMetrics>;
};

export type MethodSummary = {
  p_at_k: number;
  r_at_k: number;
  map: number;
  ndcg_at_k: number;
  waktu_rata_ms: number;
  waktu_p95_ms: number;
};

export type EvaluationRun = {
  id: number;
  created_at: string;
  index_versi: string;
  model_name: string;
  bm25_params: { k1: number; b: number };
  k: number;
  jumlah_kueri: number;
  ringkasan: Record<Method, MethodSummary> & {
    menang: { bm25: number; sbert: number; seri: number };
    kesepakatan: { penilai: string[]; kappa: number | null; jumlah_pasangan: number; sepakat: number };
    belum_diselesaikan: number;
  };
  per_kueri: QueryEvaluation[];
};

export type QueryCategory = "kata_kunci" | "deskriptif" | "parafrase";

// --- Admin ---

export type AdminDocument = DocumentDetail & {
  penulis_teks: string | null;
  kata_kunci_teks: string | null;
  bahasa_judul: string;
  sumber: string;
  perlu_indeks: boolean;
  jumlah_kata_abstrak: number;
  created_at: string | null;
  updated_at: string | null;
};

export type Paged<T> = { total: number; page: number; pages: number; items: T[] };

export type IndexVersion = {
  id: number;
  versi: string;
  status: "building" | "active" | "archived" | "failed";
  tahap: string | null;
  persen: number;
  jumlah_dokumen: number;
  model_name: string;
  bm25_params: { k1: number; b: number };
  pesan_error: string | null;
  created_at: string | null;
  finished_at: string | null;
};

export type ImportJob = {
  id: number;
  nama_file: string;
  status: "preview" | "confirmed" | "cancelled";
  total: number;
  valid: number;
  peringatan: number;
  error: number;
  duplikat: number;
  disimpan: number;
  mode_duplikat: string | null;
  created_at: string | null;
  confirmed_at: string | null;
};

export type AdminStats = {
  total: number;
  dengan_abstrak: number;
  tanpa_abstrak: number;
  per_tahun: { tahun: number | null; jumlah: number }[];
  per_bahasa: Record<string, number>;
  perlu_indeks: number;
  belum_diterjemahkan: number;
  indeks_aktif: IndexVersion | null;
  indeks_sedang_dibangun: boolean;
  import_terakhir: ImportJob | null;
  pencarian_24_jam: number;
};

export type SearchLogItem = {
  id: number;
  kueri: string;
  metode: "bm25" | "sbert" | "compare";
  jumlah_hasil: number;
  waktu_ms: number;
  created_at: string;
};

export type ValidationError = { kolom: string; nilai: string; pesan: string };
