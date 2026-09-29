import math

import pandas as pd

# Punteggio forza 1-100 = media pesata di 3 componenti, ognuna scalata linearmente
# fra (min -> 0) e (max -> 100) e tagliata. Scale fisse = punteggio assoluto, non ranking.
# real_rate a 0: backtest 1999-2026 mostra IC negativo a tutti gli orizzonti (resta in tabella, non nel punteggio)
# cot a 0 (29/09/2026): il peso 25% era stato scelto con COT in cache solo da ott 2021. Con lo storico
# completo, fuori campione (1999-2021) il COT contrarian ha IC negativo a 1-6 mesi (t = -2.5 a 3 mesi):
# era sovra-adattamento. Resta in tabella come informazione, non nel punteggio.
# Momentum a 12 mesi invece di 3: l'uso e' allocazione a 6-12 mesi; nel backtest il punteggio con
# momentum 12m e senza COT ha IC positivo a tutti gli orizzonti e in entrambi i periodi
# (3m fuori campione: 0.06 vs -0.01 della versione precedente). Vedi scripts/backtest_currency.py.
WEIGHTS = {"real_rate": 0.0, "growth": 0.25, "momentum": 0.20, "cot": 0.0, "vix": 0.30}
# Sensibilita' al risk-off: score_vix = 50 + beta * (percentile VIX - 50). JPY rifugio (+), GBP rischiosa (-).
VIX_BETA = {"JPY": 1.0, "USD": 0.5, "EUR": -0.25, "GBP": -0.5}
REAL_RATE_RANGE = (-3.0, 3.0)  # tasso a breve - inflazione YoY, punti %
GROWTH_RANGE = (-2.0, 4.0)  # PIL reale YoY, %
MOMENTUM_RANGE = (-12.0, 12.0)  # rendimento 12 mesi vs media delle 4 valute, %
MOMENTUM_DAYS = 252
BUY_ABOVE = 60  # punteggio coppia: >= BUY_ABOVE buy, <= SELL_BELOW sell, altrimenti neutra
SELL_BELOW = 40
CURRENCIES = ["USD", "EUR", "GBP", "JPY"]
PAIRS = [("EUR", "USD"), ("GBP", "USD"), ("USD", "JPY"), ("EUR", "GBP"), ("EUR", "JPY"), ("GBP", "JPY")]


def _scale(x: float, lo_hi: tuple[float, float]) -> float:
    lo, hi = lo_hi
    return min(100.0, max(0.0, (x - lo) / (hi - lo) * 100))


def momentum_returns(eurusd: pd.Series, gbpusd: pd.Series, usdjpy: pd.Series, days: int = MOMENTUM_DAYS) -> dict[str, float]:
    """Rendimento % a `days` giorni di borsa di ogni valuta vs USD, poi centrato sulla media delle 4."""
    def ret(s: pd.Series) -> float:
        s = s.dropna()
        return math.log(s.iloc[-1] / s.iloc[-1 - days]) * 100

    vs_usd = {"USD": 0.0, "EUR": ret(eurusd), "GBP": ret(gbpusd), "JPY": -ret(usdjpy)}
    mean = sum(vs_usd.values()) / len(vs_usd)
    return {c: v - mean for c, v in vs_usd.items()}


def cot_component(cot_percentile: float | None) -> float | None:
    """Contrarian: speculatori molto long (percentile alto) = valuta affollata = punteggio basso."""
    return None if cot_percentile is None else 100 - cot_percentile


def vix_component(ccy: str, vix_percentile: float | None) -> float | None:
    return None if vix_percentile is None else min(100.0, max(0.0, 50 + VIX_BETA[ccy] * (vix_percentile - 50)))


def strength_score(real_rate: float | None, growth: float | None, momentum: float | None,
                   cot: float | None = None, vix: float | None = None, cot_weight: float | None = None) -> dict:
    """cot e vix sono gia' punteggi 0-100 (vedi cot_component/vix_component). Componenti mancanti (None) escono e i pesi si rinormalizzano.
    cot_weight sostituisce WEIGHTS["cot"] (solo per il backtest delle varianti)."""
    weights = WEIGHTS if cot_weight is None else {**WEIGHTS, "cot": cot_weight}
    parts = {
        "real_rate": None if real_rate is None else _scale(real_rate, REAL_RATE_RANGE),
        "growth": None if growth is None else _scale(growth, GROWTH_RANGE),
        "momentum": None if momentum is None else _scale(momentum, MOMENTUM_RANGE),
        "cot": cot,
        "vix": vix,
    }
    used = {k: v for k, v in parts.items() if v is not None and weights[k] > 0}
    if not used:
        return {"score": None, "parts": parts}
    total_w = sum(weights[k] for k in used)
    score = sum(weights[k] * v for k, v in used.items()) / total_w
    return {"score": max(1, round(score)), "parts": parts}


def pair_view(base: float, quote: float) -> dict:
    """Score 1-100 in direzione base/quote: alto = base sale vs quote (buy)."""
    score = max(1, min(100, round(50 + (base - quote) / 2)))
    label = "Buy" if score >= BUY_ABOVE else "Sell" if score <= SELL_BELOW else "Neutra"
    return {"score": score, "label": label}
