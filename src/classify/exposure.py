"""Stato della tendenza per paese: la risposta unica della dashboard (plan-dashboard-paesi.md, sezione 1).

Borsa del paese (rendimento totale in dollari, allocation.equity_usd_returns) contro la sua media a 10 mesi, letta a
fine mese. Due stati: tendenza positiva (sopra la media) o negativa (sotto). Entro BAND dalla media lo stato non cambia
ma la scheda avvisa "vicina alla media". Un terzo stato e il regime come condizione in piu' sono stati provati e scartati:
scripts/evaluate_exposure.py, esito in spec.md ("Stato della tendenza per paese").
"""
import pandas as pd

from src.classify import allocation as al
from src.classify.score import ASSET_AREA, HISTORY_AREA, TREND_MONTHS, monthly_prices

BAND = 0.01  # entro l'1% dalla media: avviso "vicina alla media", senza cambiare stato
HISTORY_MONTHS = 36  # mesi di storia dello stato esportati per paese (striscia e archivio delle letture)
POSITIVE, NEGATIVE = "Tendenza positiva", "Tendenza negativa"


def distance(r: pd.Series) -> pd.Series:
    """Distanza a fine mese dell'indice dalla sua media a TREND_MONTHS mesi (0.05 = 5% sopra), dai rendimenti mensili.
    NaN prima del primo rendimento e nei primi mesi senza media."""
    px = (1 + r.fillna(0)).cumprod().where(r.notna().cummax())
    return px / px.rolling(TREND_MONTHS).mean() - 1


def states(r: pd.Series) -> pd.DataFrame:
    """Per mese: distanza, stato positivo (bool), vicino alla media (bool). Solo i mesi con la media."""
    d = distance(r).dropna()
    return pd.DataFrame({"dist": d, "positive": d >= 0, "near": d.abs() <= BAND})


def summary(r: pd.Series) -> dict | None:
    """Lettura dell'ultimo mese chiuso: stato, distanza in %, da quando dura e la storia recente. None senza dati."""
    s = states(r)
    if s.empty:
        return None
    last = s.iloc[-1]
    changed = s["positive"].ne(s["positive"].shift())
    start = s.index[changed][-1]
    tail = s.tail(HISTORY_MONTHS)
    return {
        "month": f"{s.index[-1]:%Y-%m}",
        "positive": bool(last["positive"]),
        "label": POSITIVE if last["positive"] else NEGATIVE,
        "dist_pct": round(float(last["dist"]) * 100, 1),
        "near": bool(last["near"]),
        "since": f"{start:%Y-%m}",
        "months": int((s.index >= start).sum()),
        "first_reading": bool(start == s.index[0]),  # lo stato dura da tutta la storia disponibile
        "history": [{"month": f"{m:%Y-%m}", "positive": bool(p), "dist_pct": round(float(d) * 100, 1)}
                    for m, p, d in zip(tail.index, tail["positive"], tail["dist"])],
    }


def countries(equity_usd: pd.DataFrame) -> dict[str, dict]:
    """summary() per ogni area di allocation.AREAS con dati."""
    out = {}
    for a in al.AREAS:
        if a in equity_usd:
            s = summary(equity_usd[a])
            if s is not None:
                out[a] = s
    return out


def equity_from_cache(read, today: pd.Timestamp | None = None) -> pd.DataFrame:
    """Rendimenti mensili in dollari per area fino all'ultimo mese chiuso, dalla cache. read(area, indicatore)."""
    today = pd.Timestamp.today() if today is None else today
    grid = pd.date_range("1975-01-01", today.normalize().replace(day=1) - pd.offsets.MonthBegin(), freq="MS")
    asset_px = monthly_prices({t: read(ASSET_AREA, t) for t in al.COUNTRY_ETF.values()})
    return al.equity_usd_returns(read, asset_px, read(HISTORY_AREA, "Mkt"), grid)
