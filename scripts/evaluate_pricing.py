"""Verifica dei segnali "Cosa prezza il mercato" (src/classify/pricing.py): aggiungono qualcosa al filtro di tendenza?

Base: SPY, a fine mese sotto la media a 10 mesi -> il mese dopo in cash (BIL), come stress.trend_returns. Ogni variante
aggiunge UNA condizione al filtro, letta a fine mese e applicata il mese dopo:
- uscita in piu': fuori anche se il segnale e' in allarme (credito, curva, struttura del VIX, SKEW, put/call);
- contrarian: dentro anche sotto la media se il put/call e' in allarme (paura alta = occasione).
Dal 28/10/2026 anche liquidita' e politica monetaria (src/classify/liquidity.py): liquidita' netta Fed in calo a 6
mesi, politica restrittiva (Fed Funds oltre 1 punto sopra l'inflazione core), intensita' forte del regime USA
(Stagflazione o Deflazione con almeno 3 fattori su 4). Dati con il loro ritardo di pubblicazione (assess.lagged).
Dal 28/10/2026 anche il canarino del libro (src/classify/risk.py, SPY TIP VWO VEA BND, momentum 13612W mensile), con
le due regole del libro: livello 1-3 (risk off della scala del PAC) e almeno un canarino negativo (Keller, BAA).
Dal 28/10/2026 anche la diffusione del cruscotto USA (src/classify/monitor.py): allarme con meno della meta' delle
serie migliori di 3 mesi prima, dati spostati alla pubblicazione (le revisioni di FRED restano un look-ahead).
Allarme: percentile point-in-time (solo storico fino a quel giorno, almeno 5 anni) >= 80, oppure curva 10a-3m sotto
zero, oppure VIX sopra il VIX a 3 mesi.

Criterio deciso PRIMA di guardare i numeri (28/10/2026): un segnale entra nella regola solo se, nel periodo di
sviluppo (fino al 2018) E nel periodo finale (dal 2019), riduce il drawdown massimo rispetto al solo filtro senza
togliere piu' di 0,5 punti di rendimento annuo. Altrimenti resta descrittivo. Niente costi, niente ottimizzazione
delle soglie: una sola variante per segnale.
Uso (da root): .venv/bin/python code/macro-cycle-tracker/scripts/evaluate_pricing.py   (solo data/cache.db)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src.classify.assess import USED_INPUTS, lagged, point_in_time_history
from src.classify import monitor
from src.classify.liquidity import STRONG_FACTORS, factors, intensity, liquidity_change, real_rate
from src.classify.pricing import ALARM_PCT, PUT_CALL_DAYS, alarms
from src.classify.risk import BOOK_CANARIES, CANARY_RISK_OFF, canary_level, momentum_13612w
from src.classify.score import ASSET_AREA, TREND_MONTHS, complete_months, monthly_prices
from src.classify.stress import summary
from src.data import cache

SPLIT = "2019-01-01"
MAX_CAGR_LOSS = 0.005
DD_EPS = 1e-6  # stesso drawdown = nessun miglioramento (senza, passava per l'arrotondamento in virgola mobile)


def main() -> None:
    m = lambda area, k: cache.read_indicator_series(area, k)
    px = complete_months(monthly_prices({t: m(ASSET_AREA, t) for t in ("SPY", "BIL")}))
    daily = {"credit": m("USA", "credit_spread"), "curve": m("USA", "yield_curve"), "vix": m("Mercati", "vix"),
             "vix3m": m("Mercati", "vix3m"), "skew": m("Mercati", "skew"), "put_call": m("Mercati", "put_call")}
    al = alarms(daily).resample("MS").last().reindex(px.index)  # stato a fine mese
    usa = {n: m("USA", n) for n in USED_INPUTS}
    f = factors(lagged(usa["growth_yoy"], "growth_yoy"), lagged(usa["inflation_yoy"], "inflation_yoy"),
                liquidity_change(m("Mercati", "net_liquidity")),
                real_rate(lagged(m("USA", "fed_funds"), "fed_funds"), lagged(usa["core_inflation_yoy"], "core_inflation_yoy")))
    regime = point_in_time_history("USA", usa)["regime"]
    n = f.sum(axis=1).where(f.notna().all(axis=1))
    strong = pd.Series([intensity(r, k) == "forte" if pd.notna(k) else None for r, k in zip(regime.reindex(n.index), n)],
                       index=n.index, dtype=object)
    liq = pd.DataFrame({"Liquidità in calo": f["Liquidità in calo"], "Politica restrittiva": f["Politica restrittiva"],
                        "Intensità forte": strong.astype(float)})
    # dato mensile = noto a fine mese (lagged lo ha gia' spostato alla pubblicazione); la liquidita' esce ogni giovedi'
    al = al.join(liq.reindex(px.index))
    mom = momentum_13612w(complete_months(monthly_prices({t: m(ASSET_AREA, t) for t in BOOK_CANARIES})))
    level, ok = canary_level(mom), mom.notna().all(axis=1)
    al = al.join(pd.DataFrame({"Canarino libro 1-3": (level <= CANARY_RISK_OFF).astype(float).where(ok),
                               "Canarino uno negativo": (mom < 0).any(axis=1).astype(float).where(ok)}).reindex(px.index))
    dif = monitor.diffusion(monitor.load(m))
    al["Diffusione USA bassa"] = (dif < monitor.DIFFUSION_ALARM).astype(float).where(dif.notna()).reindex(px.index)
    r = px.pct_change(fill_method=None)
    ma = px["SPY"].rolling(TREND_MONTHS).mean()
    up = (px["SPY"] > ma).where(ma.notna())
    hold = lambda inside: r["SPY"].where(inside.shift(1).astype(bool), r["BIL"]).where(inside.shift(1).notna())
    tests = {"Buy & hold SPY": r["SPY"], "Filtro di tendenza": hold(up)}
    for col in al:
        sig = al[col]
        tests[f"Filtro + esci se {col}"] = hold((up & ~sig.astype(bool)).where(up.notna() & sig.notna()))
    pc = al["Put/call"]
    tests["Filtro + resta se Put/call (contrarian)"] = hold((up | pc.astype(bool)).where(up.notna() & pc.notna()))
    print(f"Allarme = percentile >= {ALARM_PCT}, put/call medio {PUT_CALL_DAYS} sedute; intensità forte con {STRONG_FACTORS} fattori su 4. Criterio: drawdown migliore e "
          f"rendimento al massimo -{MAX_CAGR_LOSS:.1%} rispetto al filtro, in entrambi i periodi.\n")
    for name, (lo, hi) in {"Sviluppo": (None, "2018-12-01"), "Finale": (SPLIT, None)}.items():
        print(f"{name}")
        for k, v in tests.items():
            s = summary(v.loc[lo:hi])
            print(f"  {k:42s} " + ("n/d" if s is None else
                  f"dal {s['start']:%Y-%m}  {s['cagr'] * 100:5.1f}%/anno  DD {s['dd'] * 100:5.1f}%"))
    verdict = {}
    for k in tests:
        if not k.startswith("Filtro +"):
            continue
        ok = True
        for lo, hi in ((None, "2018-12-01"), (SPLIT, None)):
            # stessa finestra del segnale per il confronto: il filtro da solo sui mesi in cui il segnale esiste
            win = tests[k].loc[lo:hi].dropna().index
            a, b = summary(tests[k].loc[win]), summary(tests["Filtro di tendenza"].loc[win])
            ok &= a is not None and b is not None and a["dd"] > b["dd"] + DD_EPS and a["cagr"] >= b["cagr"] - MAX_CAGR_LOSS
        verdict[k] = ok
    print("\nEntra nella regola:", ", ".join(k for k, v in verdict.items() if v) or "nessun segnale")


if __name__ == "__main__":
    main()
