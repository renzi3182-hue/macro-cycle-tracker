"""Verifica di affidabilita' del modello di regime e ciclo, con i dati come erano disponibili al momento.

Tutti i calcoli del modello sono causali (deviazioni standard espandenti, isteresi in avanti), quindi la
lettura "in tempo reale" si ottiene spostando ogni serie del suo ritardo di pubblicazione (PIL +4 mesi,
CPI/CLI/disoccupazione +1) e ricalcolando una volta sola. Stampa, dal 2000:
1. Regime: quota di mesi in cui la lettura in tempo reale coincide con quella a posteriori (dati rivisti,
   senza ritardi), cambi di regime l'anno, distribuzione, episodi noti.
2. Ciclo: confronto con NBER (USA) e con i rallentamenti OCSE (EUROREC, ITAREC, GBRREC, JPNREC, fino al 2022).
3. CLI OCSE: quante volte direzione e livello restano gli stessi dopo le revisioni (vintage ALFRED dal 2018).
4. Quantaste: quante letture note di Quantaste/Casario il modello riproduce (riferimento dell'utente).
5. Calibrazione: pesi delle probabilita' (src/classify/regime.py, PROB_*), stimati sul 2000-2014 e provati sul
   2015-2026, poi ristimati su tutto: se cambiano molto, aggiornare le costanti.
Uso, da root del monorepo: .venv/Scripts/python code/macro-cycle-tracker/scripts/evaluate_model.py (serve FRED_API_KEY in .env)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os

import numpy as np
import pandas as pd
import requests

from src.classify.assess import assess
from src.classify.regime import GROWTH_CHANGE_MONTHS, PROB_ACTIVITY_WEIGHT, PROB_INFLATION_WEIGHT, activity_z
from src.data import cache, fetch_fred
from src.scheduler.update_data import _load_dotenv

AREAS = ["USA", "Eurozona", "Italia", "UK", "Giappone", "Canada", "Cina", "Australia", "India"]
INPUTS = ["cli", "growth_yoy", "inflation_yoy", "core_inflation_yoy", "unemployment_rate", "recession_prob", "industrial_production"]
PUBLICATION_LAG_MONTHS = {"growth_yoy": 4, "industrial_production": 2}  # gli altri: 1 mese
START = "2000-01-01"
EPISODES = ["2001-09", "2008-12", "2009-09", "2020-05", "2021-06", "2022-09", "2023-12"]
REFERENCE = {"USA": "USREC", "Eurozona": "EUROREC", "Italia": "ITAREC", "UK": "GBRREC", "Giappone": "JPNREC",
             "Canada": "CANREC", "Cina": "CHNREC", "Australia": "AUSREC", "India": "INDREC"}
# Letture note di Quantaste / Marco Casario (Espansione = Goldilocks). Trimestri 2015-2022: blog marcocasario.com
# "il-gold-e-partito" (area non dichiarata, presunta USA; Q4 2022 escluso perche' etichettato due volte); Q1 2024:
# libro di Casario; 2026Q3: dashboard Quantaste dell'08/10/2026, confrontata con la lettura in tempo reale.
QUANTASTE = [("USA", "2015Q1", "Goldilocks"), ("USA", "2016Q1", "Stagflazione"), ("USA", "2016Q3", "Reflazione"),
             ("USA", "2016Q4", "Reflazione"), ("USA", "2017Q2", "Goldilocks"), ("USA", "2018Q3", "Deflazione"),
             ("USA", "2019Q3", "Goldilocks"), ("USA", "2021Q1", "Reflazione"), ("USA", "2022Q2", "Reflazione"),
             ("USA", "2022Q3", "Stagflazione"), ("USA", "2024Q1", "Stagflazione"), ("Eurozona", "2024Q1", "Reflazione"),
             ("USA", "2026Q3", "Stagflazione"), ("Eurozona", "2026Q3", "Reflazione"),
             # aree aggiunte il 09/10/2026: letture della dashboard dell'08/10, mai usate per scegliere la regola
             ("Canada", "2026Q3", "Stagflazione"), ("Cina", "2026Q3", "Stagflazione"), ("Australia", "2026Q3", "Stagflazione")]
CLI_FRED = {"USA": "USALOLITOAASTSAM", "Eurozona": "G4ELOLITOAASTSAM", "Italia": "ITALOLITOAASTSAM",
            "UK": "GBRLOLITOAASTSAM", "Giappone": "JPNLOLITOAASTSAM", "Canada": "CANLOLITOAASTSAM",
            "Cina": "CHNLOLITOAASTSAM", "Australia": "AUSLOLITOAASTSAM", "India": "INDLOLITOAASTSAM"}


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


def quantaste_report(histories: dict) -> None:
    """histories: area -> (tempo reale, a posteriori). Trimestri passati a posteriori, trimestre in corso in tempo reale."""
    hits, misses = 0, []
    for area, q, label in QUANTASTE:
        p = pd.Period(q, "Q")
        real, hind = histories[area]
        h = real if p.end_time > hind.index[-1] else hind
        seg = h.loc[p.start_time:p.end_time, "regime"]
        got = seg.iloc[-1] if len(seg) else h["regime"].iloc[-1]
        hits += got == label
        if got != label:
            misses.append(f"{area} {q}: {got} invece di {label}")
    print(f"\n== Quantaste: {hits}/{len(QUANTASTE)} letture note riprodotte. " + "; ".join(misses))


def _logit_fit(x: np.ndarray, y: np.ndarray) -> float:
    """Peso di una logistica senza intercetta (Newton), cosi' la soglia della regola resta al 50%."""
    w = 0.0
    for _ in range(50):
        p = 1 / (1 + np.exp(-w * x))
        w -= ((p - y) @ x) / max((p * (1 - p)) @ (x * x), 1e-9)
    return w


def calibration_report(samples: list[pd.DataFrame]) -> None:
    """samples: per area, tempo reale (attivita', punteggio inflazione) e stato a posteriori degli assi."""
    d = pd.concat(samples).sort_index().loc[START:]
    train, test = d.loc[:"2014"], d.loc["2015":]
    print(f"\n== Calibrazione probabilita' ({len(d)} mesi-area dal 2000)")
    for name, x, y, current in [("crescita (attivita' mensile)", "act", "g_up", PROB_ACTIVITY_WEIGHT),
                                ("inflazione", "isc", "i_up", PROB_INFLATION_WEIGHT)]:
        w = _logit_fit(train[x].values, train[y].values)
        p = 1 / (1 + np.exp(-current * test[x].values))
        bins = pd.cut(p, [0, .3, .45, .55, .7, 1])
        rel = test.groupby(bins, observed=True)[y].agg(["mean", "count"])
        print(f"   {name}: peso attuale {current}, stimato 2000-2014 {w:.2f}, su tutto {_logit_fit(d[x].values, d[y].values):.2f}; "
              f"2015-2026 Brier {np.mean((p - test[y]) ** 2):.3f} (50% fisso: 0.250), azzeccato {np.mean((p > .5) == test[y]) * 100:.0f}%")
        print("      prob. stimata -> quota vera: " + ", ".join(f"{i.left:.0%}-{i.right:.0%}: {r['mean'] * 100:.0f}% (n {r['count']:.0f})" for i, r in rel.iterrows()))


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
    histories, samples = {}, []
    for area in AREAS:
        series = {n: s for n in INPUTS if not (s := cache.read_indicator_series(area, n)).empty}
        if not series:
            print(f"\n== {area}: nessun dato in cache")
            continue
        late = {n: lagged(s, n) for n, s in series.items()}
        histories[area] = (assess(area, late)["history"], assess(area, series)["history"])
        rt, ex = histories[area]
        samples.append(pd.DataFrame({"act": activity_z(late.get("industrial_production"), late.get("cli")), "isc": rt["inflation_score"],
                                     "g_up": (ex["growth"] == "up").astype(float), "i_up": (ex["inflation"] == "up").astype(float)}).dropna())
        df = regime_report(area, series)
        for step in (cycle_report, cli_vintages):
            try:
                step(area, df, key) if step is cycle_report else step(area, key)
            except (requests.RequestException, KeyError, IndexError) as e:
                print(f"   {step.__name__}: non disponibile ({e})")
    quantaste_report(histories)
    calibration_report(samples)


if __name__ == "__main__":
    main()
