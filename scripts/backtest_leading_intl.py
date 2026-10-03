"""Backtest degli indicatori anticipatori fuori USA contro i rallentamenti del ciclo OCSE.

Riferimento: OECD based Recession Indicators su FRED (EUROREC, ITAREC, GBRREC, JPNREC),
fasi dal picco al minimo del *ciclo di crescita* (deviazione dal trend), fino al 2022.
Non sono recessioni classiche: coprono ~40% dei mesi, quindi il confronto giusto e'
con questo tasso di base, non con 0.
Uso: py -3.12 scripts/backtest_leading_intl.py   (serve FRED_API_KEY in .env)
Scarica dalle fonti, non usa la cache. Non e' parte dell'app.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os

import pandas as pd

from scripts.backtest_nber import months, recessions, runs
from src.classify.leading import HIGH_RISK_MIN_SIGNALS, SIGNALS
from src.data import fetch_boj, fetch_ecb, fetch_fred, fetch_oecd
from src.scheduler.update_data import _load_dotenv

LEAD_WINDOW = 12  # mesi prima dell'inizio del rallentamento in cui un segnale conta come "hit"
REF = {"Eurozona": "EUROREC", "Italia": "ITAREC", "UK": "GBRREC", "Giappone": "JPNREC"}
VARIANTS = {  # soglie alternative provate, stesse regole di leading.py
    "Sentiment economico debole": [90, 95, 100],
    "Spread BTP-Bund alto": [1.5, 2.0, 2.5],
}


def monthly(s: pd.Series) -> pd.Series:
    return s.resample("MS").last().ffill(limit=2)  # trimestrali (Tankan) valgono 3 mesi


def evaluate(sig: pd.Series, rec: pd.Series) -> dict:
    idx = sig.index.intersection(rec.index)
    sig, rec = sig.loc[idx].astype(bool), rec.loc[idx]
    eps = [(s, e) for s, e in recessions(rec) if s >= idx[0] + pd.DateOffset(months=LEAD_WINDOW)]
    leads = []
    for s, _ in eps:
        w = sig.loc[s - pd.DateOffset(months=LEAD_WINDOW):s + pd.DateOffset(months=3)]
        leads.append(months(w.index[w][0], s) if w.any() else None)
    near = pd.Series(False, index=idx)
    for s, e in recessions(rec):
        near.loc[s - pd.DateOffset(months=LEAD_WINDOW):e] = True
    false_runs = [r for r in runs(sig) if not near.loc[r]]
    return {
        "da": idx[0].strftime("%Y-%m"), "episodi": len(eps),
        "presi": sum(l is not None for l in leads),
        "anticipo mediano": pd.Series([l for l in leads if l is not None], dtype=float).median(),
        "falsi allarmi": len(false_runs), "mesi on %": round(sig.mean() * 100),
        "precisione %": round(near[sig].mean() * 100) if sig.any() else None,
        "base %": round(near.mean() * 100),
    }


def main() -> None:
    _load_dotenv()
    key = os.environ["FRED_API_KEY"]
    data = {
        "Eurozona": {"cli": fetch_oecd.fetch_cli("Eurozona"), "esi": fetch_ecb.fetch_sentiment("EA21"),
                     "yield_curve": fetch_fred.fetch_spread(*fetch_fred.CURVES["Eurozona"], key)},
        "Italia": {"cli": fetch_oecd.fetch_cli("Italia"), "esi": fetch_ecb.fetch_sentiment("IT"),
                   "btp_bund": fetch_fred.fetch_spread(*fetch_fred.BTP_BUND, key)},
        "UK": {"cli": fetch_oecd.fetch_cli("UK"), "yield_curve": fetch_fred.fetch_spread(*fetch_fred.CURVES["UK"], key)},
        "Giappone": {"cli": fetch_oecd.fetch_cli("Giappone"), "tankan": fetch_boj.fetch_tankan(),
                     "yield_curve": fetch_fred.fetch_spread(*fetch_fred.CURVES["Giappone"], key)},
    }
    rows = []
    for area, series in data.items():
        rec = fetch_fred._fetch_series(REF[area], key, "lin").astype(bool)
        on = {}
        for label, k, test in SIGNALS[area]:
            s = series[k].dropna()
            on[label] = monthly(test(s).astype(float)).dropna() > 0  # test sulla frequenza nativa, come nell'app
            rows.append({"area": area, "segnale": label, **evaluate(on[label], rec)})
            if label in VARIANTS:
                for th in VARIANTS[label]:
                    alt = monthly(s) < th if "Sentiment" in label else monthly(s) >= th
                    rows.append({"area": area, "segnale": f"  soglia {th}", **evaluate(alt, rec)})
        both = pd.DataFrame(on).dropna()  # composito solo dove tutti i segnali hanno dati
        rows.append({"area": area, "segnale": f"RISCHIO ALTO (>= {HIGH_RISK_MIN_SIGNALS})",
                     **evaluate(both.sum(axis=1) >= HIGH_RISK_MIN_SIGNALS, rec)})
    pd.set_option("display.width", 200)
    print(f"Rallentamenti OCSE, finestra di anticipo {LEAD_WINDOW} mesi. precisione = % mesi 'on' vicino a un rallentamento; base = stessa % se il segnale fosse sempre acceso.\n")
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
