import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src.classify.changes import cells_by_month, moves_sentence, regime_phase, summary, top_moves, trend_crossings

MONTHS = pd.date_range("2026-07-01", periods=3, freq="MS")


def test_regime_and_phase_changes_read_as_short_sentences():
    hist = {
        "USA": pd.DataFrame({"regime": ["Stagflazione", "Stagflazione", "Deflazione"],
                             "phase": ["Espansione", "Espansione", "Espansione"]}, index=MONTHS),
        "Italia": pd.DataFrame({"regime": ["Goldilocks", "Goldilocks", "Goldilocks"],
                                "phase": ["Espansione", "Espansione", "Rallentamento"]}, index=MONTHS),
        "UK": pd.DataFrame({"regime": ["Goldilocks", "Goldilocks", "Stagflazione"], "phase": [None, None, None]}, index=MONTHS),
        "Cina": None,
    }
    assert regime_phase(hist) == [
        ("regime", "USA: l'inflazione ora rallenta. Regime da Stagflazione a Deflazione."),
        ("phase", "Italia: fase del ciclo da Espansione a Rallentamento."),
        ("regime", "UK: la crescita ora rallenta e l'inflazione ora accelera. Regime da Goldilocks a Stagflazione."),
    ]


def test_trend_crossings_only_where_the_sign_changed():
    trend = pd.DataFrame({"GLD": [0.02, -0.01], "DBC": [-0.03, 0.04], "SPY": [0.05, 0.06], "TLT": [-0.1, -0.2],
                          "XLE": [-0.01, 0.02], "EWJ": [None, 0.1]}, index=MONTHS[1:])
    names = {"GLD": "Oro", "DBC": "Materie prime", "XLE": "Energia"}
    assert trend_crossings(trend, names) == ["Tornano sopra la media a 10 mesi: Materie prime (DBC), Energia (XLE).",
                                             "Scende sotto la media a 10 mesi: Oro (GLD)."]
    assert trend_crossings(trend.iloc[:1], names) == []


def test_top_moves_and_sentences():
    v = pd.DataFrame({"USA": [90, 60], "Cina": [80, 95], "Italia": [70, 85], "Giappone": [50, 88], "UK": [40, 10]},
                     index=MONTHS[1:], dtype=float)
    moves = top_moves(v)
    assert moves == (["Giappone"], ["USA"])  # entra Giappone, esce USA; Cina e Italia restano
    assert moves_sentence("Paesi", moves) == "Paesi, entra nei primi 3: Giappone. Esce: USA."
    assert moves_sentence("Paesi", (["A", "B"], [])) == "Paesi, entrano nei primi 3: A, B."
    assert moves_sentence("Paesi", ([], [])) is None
    assert top_moves(v.assign(USA=[90, None])) == ([], [])  # USA senza dato oggi: non "esce", Giappone non "entra"


def test_cells_by_month_and_summary():
    idx = pd.MultiIndex.from_product([["USA", "Italia"], MONTHS[1:]])
    prob = pd.DataFrame({"Azioni": [.6, .7, .5, .4], "Oro": [.4, .45, .55, .65]}, index=idx)
    cells = cells_by_month(prob, {"Azioni": "Azioni", "Oro": "Oro"})
    assert list(cells.index) == list(MONTHS[1:]) and cells.loc[MONTHS[2], "Oro · Italia"] == .65
    out = summary({"USA": None}, pd.DataFrame({"GLD": [0.1, -0.1]}, index=MONTHS[1:]), {"GLD": "Oro"},
                  {"Classi di asset": ("asset_classes", cells)})
    assert out[0] == ("trend", "Scende sotto la media a 10 mesi: Oro (GLD).")
    assert out[1] == ("asset_classes", "Classi di asset, entra nei primi 3: Oro · USA. Esce: Azioni · Italia.")
