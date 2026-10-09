import numpy as np
import pandas as pd

# Position sizing con Monte Carlo (09/10/2026): rischio fisso in % del capitale per trade (fixed fractional).
# Ogni trade: vinto con probabilita' win_rate e guadagna risk * reward_risk del capitale, perso e perde risk.
# Trade indipendenti: ignora serie di perdite correlate (stesso regime di mercato), quindi drawdown e strisce
# reali possono essere peggiori. Stesse estrazioni per tutti i livelli di rischio, cosi' il confronto e' pulito.
RISK_LEVELS = (0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0)  # % del capitale per trade
PERCENTILES = (5, 25, 50, 75, 95)


def outcomes(win_rate: float, trades: int, runs: int, seed: int = 0) -> np.ndarray:
    """True = trade vinto. Forma (runs, trades)."""
    return np.random.default_rng(seed).random((runs, trades)) < win_rate


def equity_paths(wins: np.ndarray, risk: float, reward_risk: float) -> np.ndarray:
    """Capitale relativo (parte da 1) dopo ogni trade, forma (runs, trades + 1). risk in frazione (0.01 = 1%)."""
    growth = np.cumprod(np.where(wins, 1 + risk * reward_risk, 1 - risk), axis=1)
    return np.hstack([np.ones((len(wins), 1)), growth])


def max_drawdown(paths: np.ndarray) -> np.ndarray:
    """Massima perdita dal picco per ogni simulazione, in frazione (0.2 = -20%)."""
    return 1 - (paths / np.maximum.accumulate(paths, axis=1)).min(axis=1)


def longest_losing_streak(wins: np.ndarray) -> np.ndarray:
    streak, best = np.zeros(len(wins), dtype=int), np.zeros(len(wins), dtype=int)
    for col in (~wins).T:
        streak = np.where(col, streak + 1, 0)
        best = np.maximum(best, streak)
    return best


def expectancy(win_rate: float, reward_risk: float) -> float:
    """Guadagno medio per trade in multipli del rischio (R)."""
    return win_rate * reward_risk - (1 - win_rate)


def kelly(win_rate: float, reward_risk: float) -> float:
    """Frazione di Kelly: rischio per trade che massimizza la crescita attesa. <= 0 = sistema perdente."""
    return win_rate - (1 - win_rate) / reward_risk


def summary(paths: np.ndarray, ruin: float) -> dict:
    """ruin: drawdown (frazione) oltre il quale il conto si considera compromesso."""
    final, dd = paths[:, -1], max_drawdown(paths)
    return {
        "final": {p: float(np.percentile(final, p)) for p in PERCENTILES},
        "dd_median": float(np.median(dd)),
        "dd_p95": float(np.percentile(dd, 95)),
        "p_ruin": float((dd >= ruin).mean()),
        "p_loss": float((final < 1).mean()),
    }


def risk_table(wins: np.ndarray, reward_risk: float, ruin: float, levels=RISK_LEVELS) -> pd.DataFrame:
    rows = []
    for level in levels:
        s = summary(equity_paths(wins, level / 100, reward_risk), ruin)
        rows.append({"Rischio %": level, "Mediana": s["final"][50], "Caso cattivo (5%)": s["final"][5],
                     "Drawdown mediano": s["dd_median"], "Drawdown 95%": s["dd_p95"], "Prob. rovina": s["p_ruin"]})
    return pd.DataFrame(rows)


def fan(paths: np.ndarray) -> pd.DataFrame:
    """Percentili del capitale dopo ogni trade (righe = trade, colonne = percentili)."""
    return pd.DataFrame({f"p{p}": np.percentile(paths, p, axis=0) for p in PERCENTILES})
