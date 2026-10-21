import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from src.classify import allocation as al
from src.data import fetch_bis, fetch_french, fetch_market, fetch_oecd


def _panel(n_items: int = 8, months: int = 400, seed: int = 0) -> tuple[dict, pd.DataFrame]:
    """Un pilastro informativo (segnale) e uno di rumore; il segnale anticipa l'extra-rendimento."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("1985-01-01", periods=months, freq="MS")
    cols = [f"A{i}" for i in range(n_items)]
    signal = pd.DataFrame(rng.normal(size=(months, n_items)), idx, cols)
    noise = pd.DataFrame(rng.normal(size=(months, n_items)), idx, cols)
    excess = signal * 0.5 + pd.DataFrame(rng.normal(size=(months, n_items)), idx, cols)
    excess = excess.sub(excess.mean(axis=1), axis=0)
    valid = pd.DataFrame(True, idx, cols)
    return al.ranks({"Segnale": signal, "Rumore": -noise}, valid), excess


def test_model_finds_signal_and_beats_random():
    feats, excess = _panel()
    prob, w = al.segmented_prob(feats, excess, al.live_cuts(excess.index))
    assert (w["Segnale"] > 0.5).all() and (w.drop(columns="Costante") >= 0).all().all()
    score = al.to_score(prob)
    mu, t, n = al.ic(score, excess)
    assert mu > 0.2 and t > 3 and n > 300
    assert score.max().max() == 100 and score.min().min() >= 1
    ret1 = excess / 100
    top = al.annual(al.top_returns(score, ret1, 2))
    assert top > np.percentile(al.random_portfolios(score, ret1, 2, n=50), 95)


def test_segments_use_only_the_past():
    feats, excess = _panel()
    cut = pd.Timestamp("2010-01-01")
    full, _ = al.segmented_prob(feats, excess, [cut])
    later = excess.copy()
    later.loc["2009-08-01":] = -later.loc["2009-08-01":]  # esiti noti solo dopo il taglio
    changed, _ = al.segmented_prob(feats, later, [cut])
    pd.testing.assert_frame_equal(full, changed)
    assert full.loc[:"2009-12-01"].isna().all().all()  # prima del taglio nessuna stima


def test_folds_and_holdout_are_separate():
    feats, excess = _panel(months=500)  # 1985-2026
    folds = al.fold_prob(feats, excess)
    assert folds.loc["2019-01-01":].isna().all().all() and folds.loc["2016-01-01":"2018-12-01"].notna().all().all()
    hold, w = al.holdout_prob(feats, excess)
    assert al.months_of(hold.index).min() == pd.Timestamp(al.HOLDOUT_START) and len(w) == 3


def test_panel_rows_rank_within_area():
    feats, excess = _panel(n_items=4, months=200)
    stacked = {k: pd.concat({"X": v, "Y": v}) for k, v in feats.items()}
    ex = pd.concat({"X": excess, "Y": excess})
    prob, _ = al.segmented_prob(stacked, ex, ["2000-01-01"], min_items=3)
    s = al.to_score(prob).dropna()
    assert set(np.unique(s.values)) <= {25, 50, 75, 100}
    assert al.ic(s, ex)[2] == len(set(al.months_of(s.index)))  # IC medio per mese, non per riga


def test_parse_french_country():
    text = """
     Value-Weight Dollar Returns      All 4 Data Items Not Reqd
          Mkt   High    Low
197501   5.27   4.03   4.32
197502  -2.00   1.00   1.00

     Value-Weight Local  Returns      All 4 Data Items Not Reqd
          Mkt   High    Low
197501   4.19   2.96   3.25

     Value-Weight Dollar Returns      All 4 Data Items Required
          Mkt   High    Low
197501  99.00  99.00  99.00

     Value-Weight Dollar Returns      All 4 Data Items Not Reqd
        Mkt   High    Low
1975  20.13  29.82   6.88

Average of Annual Value-Weight Averages
All 4 Data Items Not Reqd
     Firms    B/M    E/P   CE/P    Yld
1975   191  62.55   7.32  19.72   2.88
Average of Annual Value-Weight Averages
All 4 Data Items Required
     Firms    B/M    E/P   CE/P    Yld
1975   100  10.00  99.00  10.00  99.00
"""
    out = fetch_french.parse_country(text)
    assert list(out["usd"].round(4)) == [0.0527, -0.02]  # solo mensili del primo blocco, niente annuali
    assert round(out["local"].iloc[0], 4) == 0.0419
    assert out["ep"].to_dict() == {pd.Timestamp("1975-12-01"): 7.32} and out["dp"].iloc[0] == 2.88


def test_fetch_oecd_sentiment_and_rates(requests_mock):
    fetch_oecd._fetch.cache_clear()
    csv = ("REF_AREA,MEASURE,TIME_PERIOD,OBS_VALUE\nUSA,CCICP,2026-08,96.1\nEA20,CCICP,2026-08,97.0\n"
           "USA,BCICP,2026-08,100.5\nUSA,IRLT,2026-08,4.9\n")
    m = requests_mock.get(re.compile("sdmx.oecd.org"), text=csv)
    assert list(fetch_oecd.fetch_sentiment("Eurozona", "cci").values) == [97.0]  # EA20, non G4E
    assert list(fetch_oecd.fetch_sentiment("USA", "bci").values) == [100.5]
    assert list(fetch_oecd.fetch_finmark("USA", "yield_10y").values) == [4.9]
    assert m.call_count == 2  # una chiamata per dataset
    fetch_oecd._fetch.cache_clear()


def test_fetch_bis_and_gold(requests_mock):
    requests_mock.get(re.compile("stats.bis.org"), text="REF_AREA,TIME_PERIOD,OBS_VALUE\nXM,2026-07,101.2\nXM,2026-08,\nJP,2026-08,66.0\n")
    reer = fetch_bis.fetch_reer()
    assert list(reer["EUR"].values) == [101.2] and reer["JPY"].iloc[0] == 66.0
    requests_mock.get(fetch_market.GOLD_URL, text="Date,Price\n2026-08,4411.0\n2026-09,4319.0\n")
    gold = fetch_market.fetch_gold_monthly()
    assert gold.index[-1] == pd.Timestamp("2026-09-01") and gold.iloc[-1] == 4319.0
