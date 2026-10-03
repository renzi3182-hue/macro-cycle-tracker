"""Verifica di affidabilita' del modello di regime e ciclo, con i dati come erano disponibili al momento.

Tutti i calcoli del modello sono causali (deviazioni standard espandenti, isteresi in avanti), quindi la
lettura "in tempo reale" si ottiene spostando ogni serie del suo ritardo di pubblicazione (PIL +4 mesi,
CPI/CLI/disoccupazione +1) e ricalcolando una volta sola. Stampa, dal 2000:
1. Regime: quota di mesi in cui la lettura in tempo reale coincide con quella a posteriori (dati rivisti,
   senza ritardi), cambi di regime l'anno, distribuzione, episodi noti.
2. Ciclo: confronto con NBER (USA) e con i rallentamenti OCSE (EUROREC, ITAREC, GBRREC, JPNREC, fino al 2022).
3. CLI OCSE: quante volte direzione e livello restano gli stessi dopo le revisioni (vintage ALFRED dal 2018).
Uso, da root del monorepo: .venv/Scripts/python code/macro-cycle-tracker/scripts/evaluate_model.py (serve FRED_API_KEY in .env)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os

import pandas as pd
import requests

from src.classify.assess import assess
from src.classify.regime import GROWTH_CHANGE_MONTHS
from src.data import cache, fetch_fred
from src.scheduler.update_data import _load_dotenv

AREAS = ["USA", "Eurozona", "Italia", "UK", "Giappone"]
INPUTS = ["cli", "growth_yoy", "inflation_yoy", "core_inflation_yoy", "unemployment_rate", "recession_prob"]
PUBLICATION_LAG_MONTHS = {"growth_yoy": 4}  # gli altri: 1 mese
START = "2000-01-01"
EPISODES = ["2001-09", "2008-12", "2009-09", "2020-05", "2021-06", "2022-09", "2023-12"]
REFERENCE = {"USA": "USREC", "Eurozona": "EUROREC", "Italia": "ITAREC", "UK": "GBRREC", "Giappone": "JPNREC"}
CLI_FRED = {"USA": "USALOLITOAASTSAM", "Eurozona": "G4ELOLITOAASTSAM", "Italia": "ITALOLITOAASTSAM",
            "UK": "GBRLOLITOAASTSAM", "Giappone": "JPNLOLITOAASTSAM"}


def lagged(s: pd.Series, name: str) -> pd.Series:
    out = s.copy()
    out.index = out.index + pd.DateOffset(months=PUBLICATION_LAG_MONTHS.get(name, 1))
    return out


def per_year(s: pd.Series) -> float:
    return (s != s.shift()).iloc[1:].sum() / (len(s) / 12)


def regime_report(area: str, series: dict) -> pd.DataFrame:
    real = assess(area, {n: lagged(s, n) for n, s in series.items()})["history"]
    hind = assess(area, series)["history"]
    df = pd.DataFrame({"rt": real["regime"], "ex": hind["regime"], "phase": real["phase"]}).dropna().loc[START:]
    shares = (df["rt"].value_counts(normalize=True) * 100).round().astype(int).to_dict()
    print(f"\n== {area}: regime in tempo reale = a posteriori nel {(df.rt == df.ex).mean() * 100:.0f}% dei mesi, "
          f"cambi di regime {per_year(df.rt):.1f}/anno, di fase {per_year(df.phase):.1f}/anno")
    print(f"   quote regime %: {shares}")
    print("   episodi: " + ", ".join(f"{e}={df.rt.get(pd.Timestamp(e + '-01'), '?')}/{df.phase.get(pd.Timestamp(e + '-01'), '?')}" for e in EPISODES))
    return df


def cycle_report(area: str, df: pd.DataFrame, key: str) -> None:
    ref = fetch_fred._fetch_series(REFERENCE[area], key, "lin").resample("MS").last()
    d = df.join(ref.rename("ref"), how="inner").dropna()
    inside, weak, rec = d["ref"].astype(bool), d["phase"].isin(["Rallentamento", "Recessione"]), d["phase"] == "Recessione"
    print(f"   ciclo vs {REFERENCE[area]} ({d.index[0]:%Y}-{d.index[-1]:%Y}): dentro Rall.+Rec. {weak[inside].mean() * 100:.0f}% "
          f"(Recessione {rec[inside].mean() * 100:.0f}%), fuori Rall.+Rec. {weak[~inside].mean() * 100:.0f}% "
          f"(Recessione {rec[~inside].mean() * 100:.0f}%)")


def cli_vintages(area: str, key: str) -> None:
    resp = requests.get(fetch_fred.BASE_URL, params={
        "series_id": CLI_FRED[area], "api_key": key, "file_type": "json",
        "realtime_start": "1776-07-04", "realtime_end": "9999-12-31"}, timeout=120)
    resp.raise_for_status()
    obs = pd.DataFrame(resp.json()["observations"])
    obs = obs[obs["value"] != "."].assign(value=lambda x: x["value"].astype(float), date=lambda x: pd.to_datetime(x["date"]))
    final = cache.read_indicator_series(area, "cli")
    same_dir, same_lvl = [], []
    for v in sorted(obs["realtime_start"].unique()):
        s = obs[(obs["realtime_start"] <= v) & (obs["realtime_end"] >= v)].set_index("date")["value"].sort_index()
        t, t0 = s.index[-1], s.index[-1] - pd.DateOffset(months=GROWTH_CHANGE_MONTHS)
        if t in final.index and t0 in final.index and t0 in s.index:
            same_dir.append((s[t] > s[t0]) == (final[t] > final[t0]))
            same_lvl.append((s[t] >= 100) == (final[t] >= 100))
    if same_dir:
        print(f"   CLI dopo le revisioni ({len(same_dir)} vintage): direzione 3m uguale {sum(same_dir) / len(same_dir) * 100:.0f}%, "
              f"livello sopra/sotto 100 uguale {sum(same_lvl) / len(same_lvl) * 100:.0f}%")


def main() -> None:
    _load_dotenv()
    key = os.environ["FRED_API_KEY"]
    for area in AREAS:
        series = {n: s for n in INPUTS if not (s := cache.read_indicator_series(area, n)).empty}
        df = regime_report(area, series)
        for step in (cycle_report, cli_vintages):
            try:
                step(area, df, key) if step is cycle_report else step(area, key)
            except (requests.RequestException, KeyError, IndexError) as e:
                print(f"   {step.__name__}: non disponibile ({e})")


if __name__ == "__main__":
    main()
