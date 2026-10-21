import pandas as pd

from src.ui.cards import (
    duration_it, month_it, portfolio_html, prevailing_regime, ribbon_html, rrg_html, weight_deltas,
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


def test_why_text_names_pillars_pushing_up_and_down():
    assert why_text({"Tendenza": 0.2, "Momentum": 0.05, "Stagionalità": -0.1}) == "spinge tendenza · frena stagionalità"
    assert why_text({"Tendenza": 0.2, "Momentum": 0.0}) == "spinge tendenza"
    assert why_text({"Tendenza": 0.0, "Momentum": 0.0}) == "nessun pilastro si distingue"


def test_rrg_html_lists_assets_entering_and_cooling():
    rows = [{"ticker": "EWJ", "nome": "Giappone", "ratio": 98.0, "momentum": 102.0, "quadrante": "Migliora"},
            {"ticker": "EWI", "nome": "Italia", "ratio": 103.0, "momentum": 99.0, "quadrante": "Indebolisce"}]
    html = rrg_html(rows, "Rotazione · Paesi", "settimanale")
    assert "<b>In ingresso</b>: Giappone (EWJ)" in html and "<b>In raffreddamento</b>: Italia (EWI)" in html
    assert "<svg" not in html


def test_today_blocks_cover_every_phase_and_asset():
    from src.config.asset_allocation import PHASE_ASSETS
    from src.ui.cards import asset_matrix_html, cycle_wave_html, risk_explain_html
    from src.ui.theme import PHASE_VARS
    assert set(PHASE_ASSETS) == set(PHASE_VARS)
    phases = {"Italia": "Recessione", "USA": "Ripresa (sotto trend)", "Cina": None}
    m = asset_matrix_html(phases)
    assert m.count("▲") == 4 and m.count("▼") == 3 and "▲ ciclico" in m and "n/d" in m  # Cina senza fase: riga vuota
    w = cycle_wave_html(phases)
    assert w.count('class="wl') == 2 and "Recessione · 1" in w and "{paese}" not in w
    r = risk_explain_html(61.4, "Risk On", "14/10/2026", [("Calma in borsa", "x", 66), ("Voglia di spendere", "y", 13)], True)
    assert "61/100" in r and "left:61%" in r and "voglia di spendere</b> (13)" in r and "in allarme" in r and "<svg" not in r


def test_relations_one_row_each_with_state_color_and_no_svg():
    from src.ui.cards import relations_html
    html = relations_html([("Oro / tasso reale", -0.45, -0.3, "regolare", "x"), ("Dollaro", 0.2, -0.4, "rotta", "y"),
                           ("Rame", float("nan"), 0.1, "n/d", "z")], "16/10/2026")
    assert html.count('class="row"') == 3 and "−0,45" in html and "norma −0,30" in html and "var(--r-stag)" in html
    assert "n/d" in html and "<svg" not in html
