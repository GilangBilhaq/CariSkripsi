from datetime import date

from app.data.clean import clean_abstract, clean_text, detect_language, normalize_key, parse_year

LONG_ID = (
    "Penelitian ini bertujuan untuk menganalisis pengaruh literasi keuangan terhadap perilaku konsumtif "
    "mahasiswa dalam berbelanja secara daring di Kabupaten Jember dengan metode kuantitatif."
)
LONG_EN = (
    "This study aims to analyze the effect of financial literacy on the consumptive behavior of students "
    "in online shopping in Jember Regency using a quantitative method with a survey of respondents."
)


def test_clean_text_unescapes_html_and_collapses_whitespace():
    assert clean_text("  a &lt;b&gt;\n\t c\x07 ") == "a <b> c"
    assert clean_text(None) == ""


def test_normalize_key_ignores_case_and_punctuation():
    assert normalize_key("Pra-Rancangan Pabrik: Mucic Acid!") == normalize_key("pra rancangan pabrik mucic acid")


def test_clean_abstract_rejects_empty_placeholder_and_title_copy():
    title = "Analisis Produksi Biogas dari Limbah Kulit Kopi"
    assert clean_abstract("", title) is None
    assert clean_abstract("Abstrak tidak tersedia dalam metadata publikasi ini.", title) is None
    assert clean_abstract("Dosen Pembimbing Utama : Dra. Susanti, M.Si Dosen Pembimbing Anggota : Drs. X", title) is None
    assert clean_abstract(title + ".", title) is None
    assert clean_abstract(LONG_ID, title) == LONG_ID


def test_parse_year_range():
    today = date(2026, 11, 21)
    assert parse_year("2024-07-22", today) == 2024
    assert parse_year("2027", today) == 2027
    assert parse_year("2029-01-01", today) is None
    assert parse_year("0026", today) is None
    assert parse_year("1975", today) is None
    assert parse_year("", today) is None


def test_detect_language_abstract_and_short_title():
    assert detect_language(LONG_ID) == "id"
    assert detect_language(LONG_EN) == "en"
    assert detect_language("Pengaruh Literasi Keuangan Terhadap Perilaku Konsumtif") == "id"
    assert detect_language("Hyperreality in Adaptation: Comparing the Novel and Film Versions") == "en"
    assert detect_language("") == "lain"
