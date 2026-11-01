import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src.classify.assess import axis_trail, phase_trail
from src.classify.cycle import PHASES
from src.ui import charts as ch


def _hist(phases: list[str | None], start: str = "2026-01-01") -> pd.DataFrame:
    idx = pd.date_range(start, periods=len(phases), freq="MS")
    n = len(phases)
    return pd.DataFrame({"phase": phases, "growth_z": [0.1 * k for k in range(n)],
                         "inflation_score": [0.0] * n, "regime": ["Goldilocks"] * n}, index=idx)


def test_phase_trail_counts_months_in_phase_at_each_offset():
    h = _hist(["Recessione"] * 4 + ["Ripresa (sotto trend)"] * 3 + ["Espansione"] * 5)
    t = phase_trail(h)
    assert [(x["phase"], x["months"]) for x in t] == [("Ripresa (sotto trend)", 2), ("Espansione", 2), ("Espansione", 5)]
    assert t[-1]["month"] == h.index[-1]


def test_phase_trail_skips_months_without_phase():
    t = phase_trail(_hist([None] * 5 + ["Espansione"] * 3))
    assert [x["months"] for x in t] == [3]


def test_axis_trail_last_months_oldest_first():
    t = axis_trail(_hist(["Espansione"] * 10))
    assert len(t) == 7 and t[0]["month"] < t[-1]["month"] and t[-1]["x"] > t[0]["x"]


def test_wave_x_moves_forward_inside_its_quarter():
    q = ch.WAVE_W / 4
    for i, p in enumerate(PHASES):
        xs = [ch.wave_x(p, m) for m in (1, 3, 6, 12, 40)]
        assert xs == sorted(xs) and q * i < xs[0] and xs[-1] < q * (i + 1)
        assert xs[-2] == xs[-1]  # oltre PHASE_FULL_MONTHS non avanza


def test_spread_keeps_order_gap_and_bounds():
    xs = ch._spread([10, 11, 12, 13], 0, 100, 30)
    assert xs == sorted(xs) and xs[0] >= 0 and xs[-1] <= 100
    assert min(b - a for a, b in zip(xs, xs[1:])) >= 30 - 1e-9
    tight = ch._spread([50] * 5, 0, 100, 30)  # non ci stanno: equidistanti dentro i limiti
    assert tight[0] >= 0 and tight[-1] <= 100 and min(b - a for a, b in zip(tight, tight[1:])) >= 25 - 1e-9


def test_wave_points_take_the_short_way_across_the_edge():
    parts = ch._wave_points(ch.WAVE_W - 20, 20)
    assert len(parts) == 2 and parts[0][0][0] > ch.WAVE_W / 2 and parts[1][-1][0] < ch.WAVE_W / 2


def _countries():
    return {"USA": {"trail": [{"phase": "Espansione", "months": 3}, {"phase": "Rallentamento", "months": 1},
                              {"phase": "Rallentamento", "months": 4}], "positive": True, "regime": "Goldilocks"},
            "Canada": {"trail": [{"phase": "Ripresa (sotto trend)", "months": 5}, {"phase": "Espansione", "months": 2}],
                       "positive": False, "regime": "Incerto: Goldilocks / Reflazione"},
            "Cina": {"trail": [], "positive": None, "regime": None}}


def test_world_cycle_draws_each_country_once_with_trend_ring():
    html = ch.world_cycle_html(_countries())
    assert html.count('class="wc-c"') == 2 and "Cina" not in re.sub(r"<div class=\"wc-l\">.*", "", html)
    assert "var(--r-gold)" in html and "var(--r-stag)" in html
    assert html.count("data-trail=") == 1  # Canada passa dal bordo: niente scorrimento
    assert "#" not in html  # nessun esadecimale: colori solo da variabili CSS


def test_world_cycle_lists_countries_under_their_phase():
    html = ch.world_cycle_html(_countries())
    cols = html.split('class="wc-l"')[1]
    assert cols.index("Rallentamento · 1") < cols.index("USA") and "Recessione · 0" in cols


def test_regime_quadrant_marks_uncertain_and_keeps_bubbles_apart():
    pt = lambda x, y, r="Goldilocks": {"month": pd.Timestamp("2026-01-01"), "x": x, "y": y, "regime": r}
    html = ch.regime_quadrant_html({"USA": {"trail": [pt(0.5, -0.5)] * 7, "label": "Goldilocks"},
                                    "UK": {"trail": [pt(0.5, -0.5)], "label": "Incerto: Goldilocks / Reflazione"}})
    assert html.count('class="rq-b"') == 1 and html.count('class="rq-b unc"') == 1
    pos = [tuple(map(float, m)) for m in re.findall(r'class="rq-b[^"]*" transform="translate\(([\d.]+) ([\d.]+)\)', html)]
    (x1, y1), (x2, y2) = pos
    assert ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5 >= 2 * ch.BUBBLE_R


def test_quad_xy_clips_extremes():
    lo = ch._quad_xy(-99, 99)
    hi = ch._quad_xy(99, -99)
    assert lo[0] >= ch.QUAD_PAD and lo[1] >= ch.QUAD_PAD and hi[0] <= ch.QUAD_S - ch.QUAD_PAD and hi[1] <= ch.QUAD_S - ch.QUAD_PAD
    assert ch._quad_xy(0, 0) == (ch.QUAD_S / 2, ch.QUAD_S / 2)


def test_country_card_shows_state_currency_and_near_warning():
    trend = {"label": "Tendenza negativa", "positive": False, "dist_pct": -0.4, "near": True, "since": "2026-10",
             "history": [{"month": "2026-10", "positive": False, "dist_pct": -0.4}]}
    html = ch.country_card_html({"area": "Italia", "href": "paese?area=Italia", "trend": trend, "regime": "Reflazione",
                                 "phase": "Rallentamento", "ccy_up": False, "assets": [("Oro", True), ("Titoli di Stato", False)],
                                 "change": "Tendenza passata da positiva a negativa"}, i=3)
    assert "Tendenza negativa" in html and "vicina alla media" in html and "€ EUR" in html and "▼" in html
    assert "−0,4%" in html and "--i:3" in html and "Crescita accelera, inflazione accelera" in html
    assert html.count('class="chip tint"') == 3  # 2 asset + avviso


def test_country_card_without_trend():
    html = ch.country_card_html({"area": "Cina", "href": "x", "trend": None, "regime": None, "phase": None})
    assert "Tendenza n/d" in html and "元 CNY" in html


def test_heatmap_colors_by_sign_and_marks_missing():
    html = ch.heatmap_html({"USA": {"Azioni": 5.3, "Valuta": -12.0}}, ["Azioni", "Obbligazioni", "Valuta"],
                           pd.Timestamp("2026-10-01"))
    assert "var(--r-gold) 43%" in html and "var(--r-stag) 70%" in html and "hm-na" in html
    assert "+5,3%" in html and "−12,0%" in html and "ottobre 2026" in html


def test_pct_it():
    assert ch.pct_it(-3.04) == "−3,0%" and ch.pct_it(0) == "+0,0%"


def test_country_hero_shows_currency_image_state_and_rule_sentence():
    trend = {"label": "Tendenza negativa", "positive": False, "dist_pct": -3.7, "near": False, "since": "2026-08",
             "history": [{"month": "2026-10", "positive": False, "dist_pct": -3.7}]}
    html = ch.country_hero_html("Italia", trend, pd.Timestamp("2026-10-01"))
    assert "/media/valuta-eur.webp" in html and "€ EUR" in html and "lettura di ottobre 2026" in html
    assert "sotto la media a 10 mesi da agosto 2026" in html and "−3,7%" in html and "liquidità" in html
    assert "vicina alla media" not in html and not re.search(r"#[0-9a-fA-F]{3,6}\b", html)


def test_country_hero_without_trend():
    html = ch.country_hero_html("Cina", None, None)
    assert "Tendenza n/d" in html and "valuta-cny.webp" in html and "lettura" not in html
