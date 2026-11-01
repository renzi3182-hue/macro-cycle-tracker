import re

import pytest

from src.data.cache import DB_PATH
from src.scheduler.export_site import md


def test_md_bold_lists_and_escaping():
    assert md("**Ciao** <b>") == "<p><b>Ciao</b> &lt;b&gt;</p>"
    assert md("- uno\n- **due**") == "<ul><li>uno</li><li><b>due</b></li></ul>"
    assert md("#### Titolo\nriga") == "<h3>Titolo</h3><p>riga</p>"


@pytest.mark.skipif(not DB_PATH.exists(), reason="serve data/cache.db")
def test_every_variant_and_chart_has_its_switch_and_data():
    from src.scheduler.export_site import build

    site = build()
    for name, html in site["pages"].items():
        assert html, name
        switches = set(re.findall(r'data-switch="([^"]+)"', html))
        for cond in re.findall(r'data-when="([^"]+)"', html):
            for part in cond.replace("&amp;", "&").split(";"):
                assert part.split("=")[0] in switches, (name, part)
        for key in re.findall(r'data-chart="([^"]+)"', html):
            assert site["charts"][key.replace("&amp;", "&")]["series"], (name, key)
    assert set(site["stress"]["bases"]) >= {"Basso", "Medio", "Alto"}


def _assessment(phases: list[str], regimes: list[str]) -> dict:
    import pandas as pd

    n = len(phases)
    h = pd.DataFrame({"phase": phases, "regime": regimes, "growth_z": [0.2] * n, "inflation_score": [0.1] * n},
                     index=pd.date_range("2026-01-01", periods=n, freq="MS"))
    return {"history": h, "phase": phases[-1], "regime_label": regimes[-1]}


def _trend(positive: bool, dist: float, months: int = 4, first: bool = False) -> dict:
    return {"month": "2026-10", "positive": positive, "label": "x", "dist_pct": dist, "near": abs(dist) < 1,
            "since": "2026-07", "months": months, "first_reading": first, "history": []}


def test_asset_trend_maps_phase_assets_to_classes_and_dbc():
    from src.scheduler.export_site import asset_trend

    cls, mk = {"Azioni": 0.05, "Obbligazioni": -0.01, "Oro": float("nan")}, {"DBC": 0.15}
    assert asset_trend("Azionario ciclico {paese}", cls, mk) == 0.05
    assert asset_trend("Titoli di Stato {paese}", cls, mk) == -0.01
    assert asset_trend("Materie prime", cls, mk) == 0.15
    assert asset_trend("Oro", cls, mk) is None and asset_trend("Immobiliare", cls, mk) is None


def test_change_text_lists_trend_phase_and_regime_changes():
    from src.scheduler.export_site import change_text

    h = _assessment(["Espansione"] * 3 + ["Rallentamento"], ["Goldilocks"] * 4)["history"]
    assert change_text(h, _trend(False, -2.0, months=1)) == "Borsa passata in tendenza negativa · Fase da Espansione a Rallentamento"
    assert change_text(h.iloc[:3], _trend(True, 3.0)) is None
    assert change_text(h.iloc[:3], _trend(True, 3.0, months=1, first=True)) is None  # stato da sempre: non è un cambio


def test_world_page_counts_sorts_and_fills_heatmap():
    import pandas as pd

    from src.scheduler.export_site import world_page

    assessments = {"USA": _assessment(["Espansione"] * 4, ["Goldilocks"] * 4),
                   "Italia": _assessment(["Ripresa (sotto trend)"] * 4, ["Reflazione"] * 4),
                   "Canada": _assessment(["Ripresa (sotto trend)"] * 4, ["Reflazione"] * 4)}
    trends = {"USA": _trend(True, 5.0), "Italia": _trend(False, -2.0), "Canada": _trend(True, 1.5)}
    cls = {"USA": {"Azioni": 0.05, "Obbligazioni": -0.012}, "Italia": {"Azioni": -0.02, "Obbligazioni": 0.004}}
    html = world_page(assessments, trends, cls, {"USD": 70, "EUR": 30}, {"USD": 0.031}, {"GLD": -0.102, "DBC": 0.155},
                      pd.Timestamp("2026-10-01"))
    assert "<b>2 paesi su 3</b>" in html and "<b>Ripresa</b>" in html and 'href="/paese?area=USA"' in html
    by_trend, by_name = html.split('data-when="ordine=nome"')
    by_trend = by_trend.split('data-when="ordine=tendenza"')[1]
    assert by_trend.index("USA") < by_trend.index("Canada") < by_trend.index("Italia")
    assert by_name.index("Canada") < by_name.index("Italia") < by_name.index("USA")
    assert "−1,2%" in html and "+3,1%" in html  # obbligazioni USA e dollaro nella mappa di calore
    assert "Oro −10,2% · Materie prime +15,5%" in html


def test_favored_html_splits_more_and_less_weight_with_trend_colors():
    from src.scheduler.export_site import favored_html

    html = favored_html("Rallentamento", {"Obbligazioni": 0.01, "Azioni": -0.02}, {"DBC": 0.15})
    more, less = html.split("Meno peso")
    assert "Oro" in more and "Azionario difensivo" in more and "Titoli di Stato" in more and "Materie prime" in less
    assert "var(--r-gold)\">Titoli di Stato" in more and "var(--r-stag)\">Azionario difensivo" in more
    assert "var(--muted)\">Oro" in more and "{paese}" not in html
    assert "Nessuno." in favored_html("Ripresa (sotto trend)", {}, {})
