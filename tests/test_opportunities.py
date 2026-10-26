import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src.classify.opportunities import agreement, arrows, best, cells, grid, sentence, theory


def test_theory_maps_phase_items_to_the_four_classes():
    assert theory("Recessione") == {"Obbligazioni": (1, ""), "Oro": (1, ""), "Azioni": (-1, "")}
    assert theory("Rallentamento") == {"Oro": (1, ""), "Azioni": (1, "difensivo"), "Obbligazioni": (1, "")}
    assert theory("Ripresa (sotto trend)") == {"Azioni": (1, "ciclico")}  # materie prime non e' una classe qui
    assert theory(None) == {}


def test_arrows_and_agreement_count_the_readings_that_say_more_weight():
    idx = pd.MultiIndex.from_tuples([("USA", pd.Timestamp("2020-01-01")), ("Italia", pd.Timestamp("2020-01-01"))])
    arr = arrows(pd.Series(["Espansione", None], index=idx))
    assert arr.loc[("USA", pd.Timestamp("2020-01-01"))].to_dict() == {"Azioni": 1, "Obbligazioni": -1, "Liquidità": 0, "Oro": 0}
    assert (arr.iloc[1] == 0).all()  # senza fase: neutre
    score = pd.DataFrame({"Azioni": [100.0, 75.0], "Obbligazioni": [25.0, None], "Liquidità": [50.0, 100.0], "Oro": [75.0, 25.0]}, index=idx)
    trend = pd.DataFrame({"Azioni": [0.1, -0.1], "Obbligazioni": [0.1, 0.1], "Liquidità": [-0.1, 0.1], "Oro": [0.0, 0.1]}, index=idx)
    a = agreement(score, arr, trend)
    assert a.iloc[0].tolist() == [3, 1, 0, 0] and a.iloc[1]["Liquidità"] == 2 and pd.isna(a.iloc[1]["Obbligazioni"])


def test_best_ranks_by_agreement_then_probability_and_reads_in_words():
    trend = pd.Series({"Azioni": 0.1, "Obbligazioni": 0.1, "Liquidità": -0.1, "Oro": 0.2})
    usa = cells(pd.Series({"Azioni": 75.0, "Obbligazioni": 50.0, "Liquidità": 25.0, "Oro": 100.0}),
                pd.Series({"Azioni": .56, "Obbligazioni": .5, "Liquidità": .4, "Oro": .6}), trend, "Rallentamento")
    ita = cells(pd.Series({"Azioni": 100.0, "Obbligazioni": 75.0, "Liquidità": 25.0, "Oro": 50.0}),
                pd.Series({"Azioni": .7, "Obbligazioni": .55, "Liquidità": .4, "Oro": .5}), trend, "Recessione")
    top = best({"USA": usa, "Italia": ita})
    # USA oro: tre letture a favore; poi due a favore per probabilita' (Italia azioni ha la teoria contro: la frase lo dice)
    assert [(a, c["classe"]) for a, c in top] == [("USA", "Oro"), ("Italia", "Azioni"), ("USA", "Azioni")]
    assert sentence(*top[0]) == "Oro · USA: teoria ▲, in salita, punteggio 100"
    assert sentence("Italia", ita[0]) == "Azioni · Italia: teoria ▼, in salita, punteggio 100"
    assert sentence("USA", usa[0]) == "Azioni · USA: teoria ▲ (difensivo), in salita, punteggio 75"


def test_grid_uses_the_last_month_with_a_score():
    months = pd.to_datetime(["2026-08-01", "2026-09-01"])
    idx = pd.MultiIndex.from_product([["USA", "UK"], months])
    score = pd.DataFrame({"Azioni": [100, None, 50, None], "Obbligazioni": [75, None, 100, None],
                          "Liquidità": [25, None, 25, None], "Oro": [50, None, 75, None]}, index=idx, dtype=float)
    score.loc[("USA", months[1])] = [25.0, 50.0, 75.0, 100.0]
    month, g = grid(score, score / 200, score * 0 + 0.1, {"USA": "Espansione", "UK": None, "Cina": None})
    assert month == months[1] and list(g) == ["USA"] and g["USA"][3]["punteggio"] == 100
