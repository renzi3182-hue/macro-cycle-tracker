import pandas as pd

from src.ui.cards import portfolio_html, prevailing_regime, regime_streak, weight_deltas


def test_prevailing_regime_counts_areas():
    assert prevailing_regime({"USA": "Espansione", "EZ": "Reflazione", "IT": "Reflazione"}) == ("Reflazione", 2)


def test_regime_streak_counts_trailing_quarters():
    assert regime_streak(pd.Series(["Reflazione", "Deflazione", "Reflazione", "Reflazione"])) == 2
    assert regime_streak(pd.Series(dtype=object)) == 0
    assert regime_streak(None) == 0


def test_weight_deltas_in_whole_points():
    assert weight_deltas({"Oro": 10.4, "Cash": 5.0}, {"Oro": 7.6}) == {"Oro": 2, "Cash": 5}


def test_portfolio_html_has_no_svg_and_shows_equity_share():
    html = portfolio_html({"Azionario": 48.0, "Oro": 52.0}, None, "T", "S")
    assert "<svg" not in html  # st.html rimuove gli svg
    assert ">48<" in html
