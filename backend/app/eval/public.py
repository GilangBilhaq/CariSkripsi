"""Bentuk JSON dan CSV hasil evaluasi (dipakai halaman Evaluasi publik dan admin)."""

from app.api.serializers import iso
from app.data.files import to_csv
from app.models import EvalRun

METHOD_LABEL = {"bm25": "BM25", "sbert": "IndoSBERT"}


def public_evaluation(run: EvalRun) -> dict:
    return {
        "id": run.id,
        "created_at": iso(run.created_at),
        "index_versi": run.index_versi,
        "model_name": run.model_name,
        "bm25_params": run.bm25_params,
        "k": run.k,
        "jumlah_kueri": run.jumlah_kueri,
        "ringkasan": run.ringkasan,
        "per_kueri": [
            {key: value for key, value in row.items() if key != "metode"} | {
                "metode": {m: {k: v for k, v in metrics.items() if k != "hasil"}
                           for m, metrics in row["metode"].items()}
            }
            for row in run.per_kueri
        ],
    }


def evaluation_csv(run: EvalRun) -> bytes:
    k = run.k
    header = ["no", "kueri", "kategori", "jumlah_relevan"]
    for m in ("bm25", "sbert"):
        label = METHOD_LABEL[m]
        header += [f"P@{k} {label}", f"R@{k} {label}", f"AP {label}", f"nDCG@{k} {label}", f"waktu_ms {label}"]
    header.append("pemenang (nDCG)")

    rows = []
    for i, row in enumerate(run.per_kueri, start=1):
        line = [i, row["teks"], row["kategori"], row["jumlah_relevan"]]
        for m in ("bm25", "sbert"):
            mt = row["metode"][m]
            line += [f"{mt['p_at_k']:.4f}", f"{mt['r_at_k']:.4f}", f"{mt['ap']:.4f}", f"{mt['ndcg_at_k']:.4f}",
                     f"{mt['waktu_ms']:.1f}"]
        line.append(METHOD_LABEL.get(row["pemenang"], row["pemenang"]))
        rows.append(line)

    s = run.ringkasan
    avg = ["", f"RATA-RATA ({run.jumlah_kueri} kueri)", "", ""]
    for m in ("bm25", "sbert"):
        avg += [f"{s[m]['p_at_k']:.4f}", f"{s[m]['r_at_k']:.4f}", f"{s[m]['map']:.4f}", f"{s[m]['ndcg_at_k']:.4f}",
                f"{s[m]['waktu_rata_ms']:.1f}"]
    rows.append(avg + [""])
    rows.append([])
    rows.append(["", f"Versi indeks: {run.index_versi}", f"Model: {run.model_name}",
                 f"BM25 k1={run.bm25_params.get('k1')} b={run.bm25_params.get('b')}"])
    return to_csv(header, rows)
