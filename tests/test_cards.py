import pandas as pd

from src.ui.cards import (
    duration_it, group_summary, month_it, portfolio_html, prevailing_regime, regime_groups_html, ribbon_html, rrg_html, weight_deltas,
    why_text,
)
from src.ui.theme import TOKENS, page_css


def test_prevailing_regime_counts_areas():
    assert prevailing_regime({"USA": "Goldilocks", "EZ": "Reflazione", "IT": "Reflazione"}) == ("Reflazione", 2)


def test_prevailing_regime_counts_uncertain_pair_once():
    from src.classify.assess import uncertain_pair
    labels = {area: "Incerto: {} / {}".format(*uncertain_pair(g, "up", xg=0.1 if g == "up" else -0.1, xi=2.0))
              for area, g in {"India": "down", "Italia": "up", "UK": "up"}.items()}
    assert prevailing_regime({**labels, "USA": "Stagflazione"}) == ("Incerto: Reflazione / Stagflazione", 3)


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


def test_wave_dot_sits_on_the_quarter_of_the_phase():
    import re
    from src.ui.cards import wave_html

    def dot(phase):
        m = re.search(r"left:([\d.]+)%;top:([\d.]+)%", wave_html(phase))
        return float(m[1]), float(m[2])

    assert dot("Espansione")[0] < dot("Rallentamento")[0] < dot("Recessione")[0] < dot("Ripresa (sotto trend)")[0]
    assert dot("Espansione")[1] < 50 and dot("Rallentamento")[1] < 50  # sopra il trend
    assert dot("Recessione")[1] > 50 and dot("Ripresa (sotto trend)")[1] > 50  # sotto il trend
    assert "<b" not in wave_html(None) and "<svg" not in wave_html("Espansione")


def test_regime_groups_most_common_first_uncertain_split_and_empty_regimes_last():
    html = regime_groups_html({"USA": "Stagflazione", "EZ": "Reflazione", "IT": "Incerto: Reflazione / Stagflazione",
                               "JP": "Reflazione", "UK": "Incerto: Reflazione / Stagflazione"})
    order = [html.index(f"<b>{n}</b>") for n in ("Reflazione", "Incerte", "Stagflazione", "Goldilocks", "Deflazione")]
    assert order == sorted(order)
    assert "fra Reflazione e Stagflazione" in html and html.count("nessuna area") == 2
    assert "<svg" not in html and "#" not in html  # st.html rimuove gli svg; colori solo da variabili CSS


def test_group_summary_names_groups_all_up_or_all_down():
    groups = {"Paesi": [("SPY", True), ("EWJ", True)], "Settori": [("XLK", True), ("XLU", False)], "Bond": [("TLT", False)]}
    assert group_summary(groups) == "Tutti in salita: Paesi. Tutti in calo: Bond."
    assert group_summary({"Settori": groups["Settori"]}) == "Nessun gruppo tutto in salita o tutto in calo."


def test_why_text_names_best_and_worst_pillar():
    assert why_text({"Tendenza": 3, "Momentum": 15}, 28) == "meglio in tendenza (3° su 28) che in momentum (15°)"
    assert why_text({"Tendenza": 4, "Momentum": 4}, 28) == "tendenza e momentum entrambi 4° su 28"


def test_rrg_html_lists_assets_entering_and_cooling():
    rows = [{"ticker": "EWJ", "nome": "Giappone", "ratio": 98.0, "momentum": 102.0, "quadrante": "Migliora"},
            {"ticker": "EWI", "nome": "Italia", "ratio": 103.0, "momentum": 99.0, "quadrante": "Indebolisce"}]
    html = rrg_html(rows, "Rotazione · Paesi", "settimanale")
    assert "<b>In ingresso</b>: Giappone (EWJ)" in html and "<b>In raffreddamento</b>: Italia (EWI)" in html
    assert "<svg" not in html


def test_answer_card_clips_score_and_links():
    from src.ui.cards import answer_card_html
    html = answer_card_html("aree", "In che fase siamo", 0.2, "Espansione", "frase", "", "nota")
    assert 'href="aree"' in html and ">1</span>" in html and "width:1%" in html
