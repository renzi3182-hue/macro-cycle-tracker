"""Backtest del PAC dinamico del libro di riferimento (26/10/2026): solo i numeri, nell'app solo con un vantaggio.

Regola del libro: PAC pieno sempre (es. 100 euro al mese), piu' un versamento extra (150-200 euro) dalla liquidita'
accantonata quando l'indicatore e' in risk off. Scala dell'indicatore: 1 risk off estremo, 2 risk off alto, 3 risk off
basso, 4 risk on alto, 5 risk on estremo. Il libro chiama "alto risk off" anche il 3-4: e' un'incoerenza, qui risk off
= 1-3. Il primo tentativo del libro (investire l'80% in risk on e il 120-140% in risk off) era fallito: rifatto qui
come controllo ("versione 1").

Indicatore: canarino del libro, momentum 13612W (src/classify/risk.canary, su mesi: 1, 3, 6, 12 pesati 12, 4, 2, 1) di
SPY, TIP, VWO, VEA, BND a fine mese; scala = canarini con momentum positivo (0 o 1 -> 1, 2 -> 2, ... 5 -> 5). VWO, VEA e
BND non sono in cache (Yahoo non raggiungibile dal cloud il 26/10/2026): al loro posto EEM (emergenti, stesso indice
MSCI di VWO prima del 2013), media di EZU, EWJ, EWU (sviluppati fuori dagli USA) e IEF (Treasury 7-10 anni, BND e'
l'aggregato USA). In piu', come seconda lettura, il canarino dell'app (solo TIP, risk off col momentum sotto zero).

Confronto a parita' di budget, in euro (chi investe dall'Italia), senza costi ne' tasse: ogni mese entrano 150 euro.
- PAC costante: compra 150 euro di S&P 500 (SPY in euro, senza copertura del cambio).
- PAC dinamico: compra 100 euro e mette 50 euro da parte; con il segnale di fine mese precedente in risk off compra
  in piu' 150 o 200 euro dalla liquidita' accantonata, se c'e'. La liquidita' rende l'Euribor 3 mesi (OCSE).
- Versione 1 del libro: entrano 100 euro, ne compra 80 in risk on (20 da parte) e 120 o 140 in risk off.
Misure: capitale finale (azioni + liquidita'), guadagno sui versamenti, rendimento annuo dei versamenti (tasso
interno), calo massimo del conto, prezzo medio d'acquisto contro quello del PAC costante.
Regola decisa prima: vantaggio se il dinamico chiude con piu' capitale del costante sul periodo intero e in tutte e
due le meta' (simulate separatamente), con entrambi gli extra. Il periodo non e' fuori campione per il libro (non
sappiamo su quali anni e' stata scelta la regola), lo e' per l'app: nessun parametro scelto qui guardando i risultati.
Esito (26/10/2026, febbraio 2005 -> settembre 2026, 260 mesi; meta' 2005-2015 e 2015-2026): NESSUN VANTAGGIO, il PAC
dinamico chiude sotto il costante in tutti e tre i periodi, con tutte le varianti e con tutti e due gli indicatori.
- Canarino del libro (risk off nel 44% dei mesi): extra 150 capitale -0,5% (meta' -0,3% e -1,5%), extra 200 -0,6%
  (-0,4% e -1,2%); prezzo medio -0,7% e -0,2%, ma la liquidita' ferma costa di piu'. Tasso sui versamenti 14,0%
  l'anno per tutti, calo massimo -20% contro -19%. Versione 1: 80/120 -1,5%, 80/140 -0,3%.
- Canarino dell'app (solo TIP, risk off nel 28% dei mesi): extra 150 -8,5%, extra 200 -4,4%; versione 1 -8,7% e -5,1%;
  prezzo medio piu' alto (+3,8/+4,6%): il TIP in allarme non coincide con i cali della borsa.
Quindi niente PAC dinamico nell'app: restano questi numeri.
Uso, da root del monorepo: .venv/Scripts/python code/macro-cycle-tracker/scripts/backtest_pac.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src.classify.allocation import fx_usd_per_local
from src.classify.risk import canary_level, momentum_13612w
from src.classify.score import ASSET_AREA, complete_months, monthly_prices
from src.data import cache

INFLOW, BASE, EXTRAS = 150.0, 100.0, (150.0, 200.0)
V1_INFLOW, V1_ON, V1_OFF = 100.0, 80.0, (120.0, 140.0)
RISK_OFF_MAX = 3  # scala 1-5: 1-3 risk off (il libro chiama "alto risk off" anche il 3-4)
CANARIES = {"SPY": ["SPY"], "TIP": ["TIP"], "VWO": ["EEM"], "VEA": ["EZU", "EWJ", "EWU"], "BND": ["IEF"]}


def simulate(price: pd.Series, cash_rate: pd.Series, risk_off: pd.Series, inflow: float, invest_on: float,
             invest_off: float) -> pd.DataFrame:
    """PAC mensile. Ogni mese entrano `inflow` euro; si comprano invest_on (o invest_off se risk_off del mese prima)
    euro dell'asset al prezzo di fine mese, quanto la cassa permette; il resto resta in cassa e rende cash_rate (%
    annuo) nel mese dopo. Ritorna per mese: versato, investito, quote, cassa, valore."""
    units, cash, paid, rows = 0.0, 0.0, 0.0, {}
    for t, p in price.items():
        paid += inflow
        cash += inflow
        want = invest_off if bool(risk_off.get(t, False)) else invest_on
        buy = min(want, cash)
        units += buy / p
        cash -= buy
        rows[t] = {"versato": paid, "investito": buy, "quote": units, "cassa": cash, "valore": units * p + cash}
        cash *= 1 + cash_rate.get(t, 0.0) / 1200
    return pd.DataFrame(rows).T


def irr(flows: list[float]) -> float:
    """Tasso interno mensile (bisezione) di flussi mensili, annualizzato in %."""
    lo, hi = -0.05, 0.05
    npv = lambda r: sum(f / (1 + r) ** i for i, f in enumerate(flows))
    for _ in range(100):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if npv(mid) > 0 else (lo, mid)
    return ((1 + (lo + hi) / 2) ** 12 - 1) * 100


def summary(sim: pd.DataFrame, inflow: float) -> dict:
    v = sim["valore"]
    bought = sim["investito"].sum()
    flows = [-inflow] * len(sim)
    flows[-1] += v.iloc[-1]  # versamento e valore finale nello stesso ultimo mese
    return {"finale": v.iloc[-1], "versato": sim["versato"].iloc[-1], "guadagno": (v.iloc[-1] / sim["versato"].iloc[-1] - 1) * 100,
            "irr": irr(flows),
            "calo": (v / v.cummax() - 1).min() * 100, "prezzo_medio": bought / sim["quote"].iloc[-1],
            "cassa": sim["cassa"].iloc[-1], "mesi_extra": int((sim["investito"] > inflow).sum())}


def load() -> tuple[pd.Series, pd.Series, pd.DataFrame]:
    """SPY in euro, Euribor 3 mesi (% annuo) e prezzi mensili dei canarini (dollari), a mese chiuso."""
    read = cache.read_indicator_series
    tickers = sorted({t for v in CANARIES.values() for t in v})
    px = complete_months(monthly_prices({t: read(ASSET_AREA, t) for t in tickers}))
    usd_per_eur = fx_usd_per_local(read, px.index)["Eurozona"]
    rate = read("Allocazione", "Eurozona_rate_3m").resample("MS").last().reindex(px.index).ffill()
    canaries = pd.DataFrame({k: px[v].pct_change(fill_method=None).mean(axis=1) for k, v in CANARIES.items()})
    canaries = (1 + canaries.fillna(0)).cumprod().where(canaries.notna().cummax())  # VEA: media dei rendimenti
    return (px["SPY"] / usd_per_eur).dropna(), rate, canaries


def line(name: str, s: dict, ref: dict | None) -> str:
    vs = "" if ref is None else (f" · capitale {(s['finale'] / ref['finale'] - 1) * 100:+.1f}% e prezzo medio "
                                 f"{(s['prezzo_medio'] / ref['prezzo_medio'] - 1) * 100:+.1f}% contro il costante")
    return (f"  {name:24s} finale {s['finale']:>8,.0f} su {s['versato']:,.0f} versati ({s['guadagno']:+.0f}%), tasso "
            f"{s['irr']:.1f}%/anno, calo massimo {s['calo']:.0f}%, cassa finale {s['cassa']:,.0f}, mesi con extra {s['mesi_extra']}{vs}")


def run(price: pd.Series, rate: pd.Series, off: pd.Series, label: str) -> dict[str, bool]:
    """Stampa le strategie e ritorna, per ogni variante, se chiude con piu' capitale del suo PAC costante."""
    print(f"\n{label}: {price.index[0]:%Y-%m} -> {price.index[-1]:%Y-%m}, {len(price)} mesi, risk off nel "
          f"{off.reindex(price.index).mean() * 100:.0f}% dei mesi")
    better = {}
    for inflow, on, offs, tag in ((INFLOW, BASE, [BASE + e for e in EXTRAS], "Dinamico 100 + {:.0f}"),
                                  (V1_INFLOW, V1_ON, list(V1_OFF), "Versione 1, 80 / {:.0f}")):
        ref = summary(simulate(price, rate, off, inflow, inflow, inflow), inflow)
        print(line(f"PAC costante {inflow:.0f}", ref, None))
        for o in offs:
            name = tag.format(o - BASE if inflow == INFLOW else o)
            s = summary(simulate(price, rate, off, inflow, on, o), inflow)
            better[name] = s["finale"] > ref["finale"]
            print(line(name, s, ref))
    return better


def main() -> None:
    price, rate, canaries = load()
    scale = canary_level(momentum_13612w(canaries))
    tip_alarm = momentum_13612w(canaries[["TIP"]])["TIP"] < 0
    signals = {"Canarino del libro (5 ETF, risk off = scala 1-3)": (scale <= RISK_OFF_MAX).where(scale.notna()),
               "Canarino dell'app (solo TIP sotto zero)": tip_alarm.where(momentum_13612w(canaries[["TIP"]])["TIP"].notna())}
    for name, sig in signals.items():
        off = sig.shift(1)  # segnale di fine mese precedente: nessun dato futuro
        start = off.first_valid_index()
        p = price.loc[start:]
        off = off.reindex(p.index).fillna(False).astype(bool)
        mid = p.index[len(p) // 2]
        print(f"\n===== {name} =====")
        if "libro" in name:
            print("Mesi per livello della scala:", scale.loc[start:].value_counts().sort_index().astype(int).to_dict())
        res = [run(p, rate, off, "Periodo intero"), run(p.loc[:mid - pd.offsets.MonthBegin()], rate, off, "Prima meta'"),
               run(p.loc[mid:], rate, off, "Seconda meta'")]
        for k in res[0]:
            ok = all(r[k] for r in res)
            print(f"  Esito {k}: {'VANTAGGIO (meglio in tutti e tre i periodi)' if ok else 'nessun vantaggio'}"
                  f" ({', '.join('meglio' if r[k] else 'peggio' for r in res)})")


if __name__ == "__main__":
    main()
