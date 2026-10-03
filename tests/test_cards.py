import pandas as pd

from src.ui.cards import duration_it, month_it, portfolio_html, prevailing_regime, ribbon_html, weight_deltas
from src.ui.theme import TOKENS, page_css


def test_prevailing_regime_counts_areas():
    assert prevailing_regime({"USA": "Goldilocks", "EZ": "Reflazione", "IT": "Reflazione"}) == ("Reflazione", 2)


def test_weight_deltas_in_whole_points():
    assert weight_deltas({"Oro": 10.4, "Cash": 5.0}, {"Oro": 7.6}) == {"Oro": 2, "Cash": 5}


def test_portfolio_html_has_no_svg_and_shows_equity_share():
    html = portfolio_html({"Azionario": 48.0, "Oro": 52.0}, None, "T", "S")
    assert "<svg" not in html  # st.html rimuove gli svg
    assert ">48<" in html


def test_italian_dates():
    assert month_it(pd.Timestamp("2026-08-01")) == "agosto 2026"
    assert duration_it(pd.Timestamp("2024-03-01"), pd.Timestamp("2026-08-01")) == "2 anni e 6 mesi"
    assert duration_it(pd.Timestamp("2026-08-01"), pd.Timestamp("2026-08-01")) == "1 mese"


def test_ribbon_has_one_cell_per_month_and_uses_theme_variables():
    s = pd.Series(["Goldilocks"] * 40, index=pd.date_range("2020-01-01", periods=40, freq="MS"))
    html = ribbon_html(s, lambda r: "var(--r-gold)", months=36)
    assert html.count("<i ") == 36 and "#" not in html.split("ticks")[0]


def test_both_themes_define_the_same_tokens():
    assert TOKENS["dark"].keys() == TOKENS["light"].keys()
    assert "--r-gold: #177A4D" in page_css("light") and "--r-gold: #7BE0A4" in page_css("dark")
