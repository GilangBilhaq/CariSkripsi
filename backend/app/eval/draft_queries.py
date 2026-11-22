"""Draf 15 kueri uji (5 per kategori) untuk disetujui tim sebelum penilaian dimulai.

Dimuat dengan: python -m app.cli seed-eval-queries   (hanya bila tabel kueri uji masih kosong)
Setelah dimuat, kueri bisa diubah/dihapus di Admin -> Evaluasi Model -> Kueri Uji & Penilaian.

Topik dipilih dari korpus (setiap topik punya kira-kira 10-150 dokumen yang memuat istilah terkait).
Kueri parafrase sengaja memakai bahasa awam yang TIDAK muncul persis di dokumen, untuk menguji
kemampuan pencarian makna.
"""

DRAFT_QUERIES: list[tuple[str, str, str]] = [
    # (teks, kategori, catatan untuk penilai)
    ("briket biomassa", "kata_kunci", "Pembuatan/karakteristik briket dari biomassa atau limbah organik."),
    ("klasifikasi sentimen naive bayes", "kata_kunci", "Analisis sentimen teks dengan metode Naive Bayes."),
    ("tuberkulosis", "kata_kunci", "Penyakit TBC: faktor risiko, pengobatan, atau penanganannya."),
    ("tembakau na-oogst", "kata_kunci", "Tanaman/komoditas tembakau Na-Oogst (khas Jember)."),
    ("budidaya ikan lele", "kata_kunci", "Pemeliharaan, pakan, atau usaha budidaya lele."),
    ("pengaruh literasi keuangan terhadap perilaku konsumtif mahasiswa", "deskriptif",
     "Hubungan pengetahuan keuangan dengan kebiasaan belanja mahasiswa."),
    ("faktor yang berhubungan dengan kejadian stunting pada balita", "deskriptif",
     "Penyebab atau faktor risiko stunting pada anak balita."),
    ("perlindungan hukum bagi konsumen dalam transaksi jual beli online", "deskriptif",
     "Aspek hukum perlindungan konsumen e-commerce/belanja daring."),
    ("pengaruh kualitas pelayanan terhadap kepuasan pasien rumah sakit", "deskriptif",
     "Mutu layanan kesehatan dan kepuasan pasien."),
    ("dampak pernikahan dini terhadap kehidupan keluarga", "deskriptif",
     "Akibat perkawinan usia anak bagi rumah tangga/keluarga."),
    ("rasa tertekan dan kelelahan perawat saat bekerja", "parafrase",
     "Maksudnya: stres kerja atau burnout pada perawat."),
    ("remaja yang tidak bisa lepas dari telepon genggam", "parafrase",
     "Maksudnya: kecanduan smartphone/gawai pada remaja."),
    ("anak sekolah yang diejek dan disakiti temannya", "parafrase",
     "Maksudnya: perundungan (bullying) di sekolah."),
    ("tanah di lereng bukit runtuh saat musim hujan", "parafrase",
     "Maksudnya: bencana tanah longsor."),
    ("membayar belanja memakai uang elektronik di ponsel", "parafrase",
     "Maksudnya: penggunaan dompet digital/e-wallet."),
]
