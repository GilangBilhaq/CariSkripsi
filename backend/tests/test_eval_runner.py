from sqlalchemy import select

from app.eval.runner import agreement, ensure_pool, final_grades, run_evaluation
from app.models import FINAL_JUDGE, EvalJudgment, EvalPoolItem, EvalQuery


def add_query(session, teks="energi biomassa", kategori="kata_kunci"):
    q = EvalQuery(teks=teks, kategori=kategori)
    session.add(q)
    session.commit()
    return q


def judge(session, q, doc_id, penilai, skor):
    session.add(EvalJudgment(query_id=q.id, document_id=doc_id, penilai=penilai, skor=skor))
    session.commit()


def test_pool_is_union_of_both_methods_and_frozen(session, index_manager):
    q = add_query(session)
    pool = ensure_pool(session, index_manager.active, index_manager.encoder, q, depth=3)
    assert 3 <= len(pool) <= 6
    assert len({p.document_id for p in pool}) == len(pool)
    again = ensure_pool(session, index_manager.active, index_manager.encoder, q, depth=3)
    assert [p.document_id for p in again] == [p.document_id for p in pool]
    assert session.scalar(select(EvalPoolItem.id).where(EvalPoolItem.query_id == q.id)) is not None


def test_final_grades_consensus_conservative_and_resolution(session, sample_docs):
    q = add_query(session)
    a, b, c = (d.id for d in sample_docs[:3])
    judge(session, q, a, "Ani", 2)
    judge(session, q, a, "Budi", 2)  # sepakat
    judge(session, q, b, "Ani", 2)
    judge(session, q, b, "Budi", 0)  # berbeda, belum diputuskan -> 0
    judge(session, q, c, "Ani", 1)
    judge(session, q, c, "Budi", 0)
    judge(session, q, c, FINAL_JUDGE, 1)  # berbeda, sudah diputuskan -> 1
    g = final_grades(session, q.id)
    assert g.grades == {a: 2, b: 0, c: 1}
    assert g.unresolved == [b]


def test_agreement_uses_two_most_active_judges(session, sample_docs):
    q = add_query(session)
    for doc, (x, y) in zip(sample_docs[:4], [(2, 2), (2, 0), (0, 2), (0, 0)]):
        judge(session, q, doc.id, "Ani", x)
        judge(session, q, doc.id, "Budi", y)
    result = agreement(session)
    assert result["penilai"] == ["Ani", "Budi"]
    assert result["jumlah_pasangan"] == 4 and result["sepakat"] == 2
    assert abs(result["kappa"]) < 1e-9


def test_run_evaluation_is_reproducible(session, index_manager, sample_docs):
    q = add_query(session)
    judge(session, q, sample_docs[0].id, "Ani", 2)
    judge(session, q, sample_docs[1].id, "Ani", 1)
    add_query(session, "kueri tanpa penilaian", "deskriptif")  # dilewati

    run1 = run_evaluation(session, index_manager.active, index_manager.encoder, k=5, depth=10)
    run2 = run_evaluation(session, index_manager.active, index_manager.encoder, k=5, depth=10)
    assert run1.jumlah_kueri == 1
    strip = lambda s: {m: {k: v for k, v in s[m].items() if not k.startswith("waktu")} for m in ("bm25", "sbert")}
    assert strip(run1.ringkasan) == strip(run2.ringkasan)
    bm25 = run1.ringkasan["bm25"]
    assert bm25["p_at_k"] == 2 / 5  # kedua dokumen biomassa ada di 5 teratas BM25
    assert bm25["r_at_k"] == 1.0
    assert run1.per_kueri[0]["pemenang"] in ("bm25", "sbert", "seri")
    assert run1.index_versi == index_manager.active.versi
