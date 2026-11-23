"""Riferimenti in euro per la simulazione della home Consulenza (23/11/2026).

Servono per i prodotti senza uno storico mensile scaricabile: la posizione segue un riferimento con storia lunga e
dati gratuiti, e il costo annuo del prodotto si toglie a parte (campo "Costi annui" della pagina).

- Azioni mondo: 60% SPY, 30% VEA (sviluppati fuori dagli USA), 10% EEM (emergenti), ribilanciati ogni mese e
  convertiti in euro senza copertura del cambio. Da luglio 2007 (VEA).
- Obbligazioni area euro: rendimento sintetico dal decennale dell'area euro (media mensile OCSE), cedola del mese
  prima / 12 - durata * variazione del rendimento, durata 6 anni.
- Liquidità area euro: stesso calcolo sul tasso a 3 mesi, durata 0,5.

Verifica sui rendimenti annuali ufficiali 2016-2025 di tre fondi attivi in euro (classe con proventi reinvestiti,
rendimenti al netto dei costi correnti), togliendo al riferimento i costi correnti del fondo:
- azionario globale: correlazione 1,00, il fondo ha reso in media 2,0 punti l'anno meno del riferimento
  (deviazione standard 1,4 punti). Con il solo SPY lo scarto saliva a 4,6 punti (deviazione 5,4);
- obbligazionario euro investment grade: correlazione 0,93, scarto medio 0,0 punti (deviazione 2,4);
  2022 -14,9% contro -16,9% del fondo. Con durata 5 lo scarto era -0,2, con 7 +0,2;
- monetario euro a breve: correlazione 0,95, il fondo +0,5 punti l'anno (deviazione 0,6), soprattutto negli anni
  dei tassi negativi.
"""
import pandas as pd

from src.classify.stress import eur_returns

EQUITY_WORLD = {"SPY": 0.6, "VEA": 0.3, "EEM": 0.1}
BOND_DURATION = 6.0
CASH_DURATION = 0.5
LABELS = {
    "Azioni mondo": "60% SPY, 30% VEA, 10% EEM",
    "Obbligazioni area euro": "decennale, durata 6",
    "Liquidità area euro": "tasso a 3 mesi",
}


def rate_returns(rate_pct: pd.Series, duration: float) -> pd.Series:
    """Rendimento mensile di un titolo a tasso fisso tenuto a durata costante: cedola del mese prima / 12 meno
    durata per la variazione del tasso. rate_pct in % annuo, indice mensile. NaN il primo mese e dove manca il tasso."""
    y = rate_pct / 100
    return y.shift(1) / 12 - duration * y.diff()


def equity_world(px: pd.DataFrame, usd_per_eur: pd.Series) -> pd.Series:
    """Rendimenti mensili in euro del paniere EQUITY_WORLD, ribilanciato ogni mese. NaN se manca un ETF o il cambio."""
    cols = [eur_returns(px[t].pct_change(fill_method=None), usd_per_eur) * w for t, w in EQUITY_WORLD.items()]
    return pd.concat(cols, axis=1).sum(axis=1, min_count=len(cols))


def references(index: pd.DatetimeIndex, px: pd.DataFrame, usd_per_eur: pd.Series,
               yield_10y: pd.Series, rate_3m: pd.Series) -> dict[str, pd.Series]:
    """Le tre serie di LABELS sull'indice mensile della simulazione (inizio mese). px: chiusure mensili con le
    colonne di EQUITY_WORLD; yield_10y e rate_3m: tassi dell'area euro in % annuo, indice inizio mese."""
    monthly = lambda s: s.resample("MS").last().reindex(index)
    return {
        "Azioni mondo": equity_world(px.reindex(index), usd_per_eur.reindex(index)),
        "Obbligazioni area euro": rate_returns(monthly(yield_10y), BOND_DURATION),
        "Liquidità area euro": rate_returns(monthly(rate_3m), CASH_DURATION),
    }
