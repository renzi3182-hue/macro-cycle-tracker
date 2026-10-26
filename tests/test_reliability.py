import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.classify.allocation import EDGE
from src.config.reliability import KINDS, READINGS
from src.ui.cards import badge_html, reliability_html, reliability_table_html


def test_each_reading_has_the_agreed_label():
    expected = {
        "Verificato": {"trend", "ranking", "asset_classes"},
        "Teoria": {"regime_assets", "phase_assets", "sector_regime"},
        "Descrittivo": {"risk", "confirmation", "countries", "currencies", "cot", "rrg", "regime", "phase"},
    }
    for kind, keys in expected.items():
        assert all(READINGS[k].kind == kind for k in keys), kind
    assert all(r.kind in KINDS for r in READINGS.values())


def test_allocation_labels_follow_the_out_of_sample_test():
    for name, key in {"Paesi": "countries", "Classi di asset": "asset_classes", "Valute": "currencies"}.items():
        assert (READINGS[key].kind == "Verificato") == EDGE[name]


def test_page_sentences_have_no_technical_statistics():
    # t, IC, soglie e percentuali solo nella pagina Metodo (campo numbers)
    for key, r in READINGS.items():
        assert not re.search(r"\bIC\b|\(t |\bt \d|%|13612W|soglia", r.plain), key
        assert r.numbers and r.source


def test_badge_uses_theme_variables_and_metodo_lists_every_reading():
    assert "var(--r-gold)" in badge_html("Verificato") and "#" not in badge_html("Teoria")
    assert "Descrive il momento" not in reliability_html("trend") and "Verificato" in reliability_html("trend")
    table = reliability_table_html()
    assert all(r.name.split(" (")[0] in table for r in READINGS.values())
    assert table.index("Verificato") < table.index("Teoria") < table.index("Descrittivo")
