import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src.classify.regime import REGIMES
from src.classify.score import UNIVERSE
from src.config.reliability import READINGS
from src.config.sector_regime import SECTOR_NAMES, SECTOR_REGIME, sector_arrows


def names(tickers):
    return {SECTOR_NAMES[t] for t in tickers}


def test_lists_follow_the_book_chapter_7():
    assert names(SECTOR_REGIME["Goldilocks"][0]) == {"tecnologia", "discrezionali", "materiali", "industriali", "comunicazioni", "immobiliare"}
    assert names(SECTOR_REGIME["Goldilocks"][1]) == {"utilities", "prima necessità", "finanziari", "energia"}
    assert names(SECTOR_REGIME["Reflazione"][0]) == {"tecnologia", "discrezionali", "materiali", "industriali", "energia", "finanziari"}
    assert names(SECTOR_REGIME["Reflazione"][1]) == {"utilities", "prima necessità", "salute"}
    assert names(SECTOR_REGIME["Stagflazione"][0]) == {"utilities", "energia", "tecnologia", "industriali", "prima necessità"}
    assert names(SECTOR_REGIME["Stagflazione"][1]) == {"finanziari", "materiali", "discrezionali", "immobiliare", "comunicazioni"}
    assert names(SECTOR_REGIME["Deflazione"][0]) == {"prima necessità", "utilities", "immobiliare", "salute", "comunicazioni"}
    assert names(SECTOR_REGIME["Deflazione"][1]) == {"energia", "tecnologia", "industriali", "finanziari", "materiali"}


def test_every_sector_is_in_the_ranking_and_never_both_sides():
    assert set(SECTOR_NAMES) == {t for t, (_, g) in UNIVERSE.items() if g == "Settori USA"}
    assert set(SECTOR_REGIME) == set(REGIMES)
    for long, short in SECTOR_REGIME.values():
        assert not set(long) & set(short)
    assert sector_arrows("Deflazione")["XLV"] == 1 and sector_arrows("Deflazione")["XLK"] == -1
    assert "XLY" not in sector_arrows("Deflazione") and sector_arrows(None) == {}
    assert READINGS["sector_regime"].kind == "Teoria"


def test_ranking_shows_the_arrow_next_to_the_sector():
    from src.ui.cards import ranking_html
    row = {"ticker": "XLV", "nome": "Salute", "gruppo": "Settori USA", "punteggio": 91.0, "delta": None, "Tendenza": 0.05,
           "prob": 0.57, "attivo": False, "storico": pd.Series(dtype=float), "perche": "x", "freccia": 1}
    html = ranking_html([row, {**row, "ticker": "SPY", "nome": "USA", "freccia": None}], pd.Timestamp("2026-09-01"))
    assert html.count("▲") == 1 and "Teoria" in html
