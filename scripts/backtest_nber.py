"""Backtest dei segnali di recessione USA contro le date NBER (FRED USREC).

Uso: py -3.12 scripts/backtest_nber.py   (serve FRED_API_KEY in .env)
Scarica da FRED, non usa la cache. Non e' parte dell'app.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os

import pandas as pd

from src.classify.leading import CREDIT_SPREAD_STRESS, CURVE_INVERSION, FIN_CONDITIONS_TIGHT, HIGH_RISK_MIN_SIGNALS
from src.classify.recession import CP_CERTAIN, CP_CONFIRM, SAHM_THRESHOLD, sahm_gap
from src.data import fetch_fred
from src.scheduler.update_data import _load_dotenv

LEAD_WINDOW = 24  # mesi prima dell'inizio recessione in cui un segnale anticipatore conta come "hit"
LAG_TOLERANCE = 3  # mesi: un segnale concorrente che parte fino a 3 mesi prima dell'inizio NBER conta
LINGER = 6  # mesi dopo la fine NBER in cui un segnale acceso non e' falso allarme
START = "1970-01-01"


def monthly(s: pd.Series, how: str = "last") -> pd.Series:
    r = s.resample("MS")
    return (r.last() if how == "last" else r.mean()).dropna()


def sahm_signal(unrate: pd.Series) -> pd.Series:
    return sahm_gap(unrate) >= SAHM_THRESHOLD


def leading_signal(curve, credit, nfci, index) -> pd.Series:
    m = pd.DataFrame({"c": monthly(curve), "b": monthly(credit), "n": monthly(nfci)}).reindex(index)
    score = (m.c < CURVE_INVERSION).astype(int) + (m.b >= CREDIT_SPREAD_STRESS).astype(int) \
        + (m.n >= FIN_CONDITIONS_TIGHT).astype(int)
    valid = m.notna().all(axis=1)
    return ((score >= HIGH_RISK_MIN_SIGNALS) & valid).loc[valid.idxmax():]  # parte dal 1o mese con tutti e 3 i dati


def recessions(usrec: pd.Series) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    flag = usrec.astype(bool)
    starts = flag & ~flag.shift(1, fill_value=False)
    ends = flag & ~flag.shift(-1, fill_value=False)
    return list(zip(usrec.index[starts], usrec.index[ends]))


def runs(sig: pd.Series) -> list[pd.Timestamp]:
    """Primo mese di ogni episodio continuo di segnale acceso."""
    return list(sig.index[sig & ~sig.shift(1, fill_value=False)])


def months(a, b) -> int:
    return (b.year - a.year) * 12 + b.month - a.month


def evaluate_concurrent(sig: pd.Series, usrec: pd.Series) -> dict:
    sig = sig.loc[sig.index.intersection(usrec.index)]
    recs = [(s, e) for s, e in recessions(usrec) if s >= sig.index[0]]
    lags = []
    for s, e in recs:
        w = sig.loc[s - pd.DateOffset(months=LAG_TOLERANCE):e]
        lags.append(months(s, w.index[w][0]) if w.any() else None)
    false_runs = [r for r in runs(sig)
                  if not any(s - pd.DateOffset(months=LAG_TOLERANCE) <= r <= e + pd.DateOffset(months=LINGER) for s, e in recs)]
    in_rec = usrec.loc[sig.index].astype(bool)
    return {"n_rec": len(recs), "lags": lags, "false_alarms": len(false_runs),
            "recall_months": round(float(sig[in_rec].mean() * 100)), "from": sig.index[0].strftime("%Y-%m")}


def evaluate_leading(sig: pd.Series, usrec: pd.Series) -> dict:
    sig = sig.loc[sig.index.intersection(usrec.index)]
    recs = [(s, e) for s, e in recessions(usrec) if s >= sig.index[0]]
    leads = []
    for s, e in recs:
        w = sig.loc[s - pd.DateOffset(months=LEAD_WINDOW):s]
        leads.append(months(w.index[w][0], s) if w.any() else None)
    false_runs = [r for r in runs(sig)
                  if not any(s - pd.DateOffset(months=LEAD_WINDOW) <= r <= e for s, e in recs)]
    return {"n_rec": len(recs), "leads": leads, "false_alarms": len(false_runs),
            "share_on": round(float(sig.mean() * 100)), "from": sig.index[0].strftime("%Y-%m")}


def main() -> None:
    _load_dotenv()
    key = os.environ["FRED_API_KEY"]
    usrec = fetch_fred._fetch_series("USREC", key, "lin")
    usrec = usrec.loc[START:]
    unrate = fetch_fred.fetch_unemployment_rate(key)
    cp = monthly(fetch_fred.fetch_recession_probability(key)).loc[START:]
    idx = usrec.index
    print(f"NBER (USREC): {[(s.strftime('%Y-%m'), e.strftime('%Y-%m')) for s, e in recessions(usrec)]}\n")

    sahm = sahm_signal(unrate).loc[START:]
    concurrent = {
        "Sahm (>=0.5)": sahm,
        f"Chauvet-Piger (>={CP_CERTAIN:.0f}%)": cp >= CP_CERTAIN,
        f"REGOLA IN USO: (Sahm & CP>={CP_CONFIRM:.0f}%) | CP>={CP_CERTAIN:.0f}%": (sahm & (cp >= CP_CONFIRM)) | (cp >= CP_CERTAIN),
    }
    print("MODELLI CONCORRENTI (rilevano la recessione in corso). Lag = mesi dall'inizio NBER al primo segnale.")
    for name, sig in concurrent.items():
        r = evaluate_concurrent(sig, usrec)
        print(f"- {name} dal {r['from']}: {r['n_rec']} recessioni | lag {r['lags']} | falsi allarmi {r['false_alarms']} | mesi-recessione coperti {r['recall_months']}%")

    lead = leading_signal(fetch_fred.fetch_yield_curve(key), fetch_fred.fetch_credit_spread(key),
                          fetch_fred.fetch_financial_conditions(key), idx)
    r = evaluate_leading(lead, usrec)
    print(f"\nMODELLO ANTICIPATORE (rischio 'Alto'). Lead = mesi di anticipo sull'inizio NBER, finestra {LEAD_WINDOW}m.")
    print(f"- Curva+Baa+NFCI dal {r['from']}: {r['n_rec']} recessioni | anticipo {r['leads']} | falsi allarmi {r['false_alarms']} | mesi 'Alto' {r['share_on']}%")


if __name__ == "__main__":
    main()
