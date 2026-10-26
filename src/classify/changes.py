"""Cosa e' cambiato dal mese scorso (26/10/2026, pagina Oggi): frasi brevi, riusabili come post social.
- Regime e fase: ultime due righe mensili dello storico di assess (regime e fase del mese prima ricalcolati con i dati
  di oggi, non la lettura mostrata allora: la tabella classifications salva solo i cambi da ottobre 2026 e anche quelli
  dovuti a cambi di regola).
- Tendenza: ETF della Classifica che a fine mese hanno incrociato la media a 10 mesi (pilastro Tendenza di score.py).
- Primi 3: chi entra o esce dalla testa della classifica dei paesi, delle classi di asset (celle paese-classe per
  probabilita' di battere la media del paese) e della Classifica degli asset, ultimo mese chiuso contro il precedente.
Il calcolo sta qui, la pagina mostra solo le frasi.
"""
import pandas as pd

from src.classify.regime import REGIME_AXES

TOP = 3
AXIS_NOW = {"up": "accelera", "down": "rallenta"}


def _last_two(s: pd.Series) -> tuple | None:
    s = s.dropna()
    return (s.iloc[-2], s.iloc[-1]) if len(s) > 1 else None


def regime_phase(histories: dict[str, pd.DataFrame | None]) -> list[tuple[str, str]]:
    """(lettura, frase) per ogni paese con regime ("regime") o fase ("phase") diversi dal mese prima.
    histories: area -> assess()["history"]."""
    out = []
    for area, h in histories.items():
        if h is None:
            continue
        reg = _last_two(h["regime"])
        if reg and reg[0] != reg[1]:
            (g0, i0), (g1, i1) = REGIME_AXES[reg[0]], REGIME_AXES[reg[1]]
            what = ([f"la crescita ora {AXIS_NOW[g1]}"] if g0 != g1 else []) + ([f"l'inflazione ora {AXIS_NOW[i1]}"] if i0 != i1 else [])
            out.append(("regime", f"{area}: {' e '.join(what)}. Regime da {reg[0]} a {reg[1]}."))
        ph = _last_two(h["phase"])
        if ph and ph[0] != ph[1]:
            out.append(("phase", f"{area}: fase del ciclo da {ph[0]} a {ph[1]}."))
    return out


def trend_crossings(trend: pd.DataFrame, names: dict[str, str]) -> list[str]:
    """ETF che nell'ultimo mese chiuso hanno incrociato la media a 10 mesi. trend: pilastro Tendenza (prezzo / media
    - 1), una riga per mese; names: ticker -> nome."""
    if len(trend) < 2:
        return []
    prev, now = trend.iloc[-2], trend.iloc[-1]
    both = prev.notna() & now.notna()
    up = [t for t in trend.columns[both] if prev[t] <= 0 < now[t]]
    down = [t for t in trend.columns[both] if now[t] <= 0 < prev[t]]
    label = lambda ts: ", ".join(f"{names.get(t, t)} ({t})" for t in ts)
    return ([f"Tornano sopra la media a 10 mesi: {label(up)}." if len(up) > 1 else f"Torna sopra la media a 10 mesi: {label(up)}."] if up else []) \
        + ([f"Scendono sotto la media a 10 mesi: {label(down)}." if len(down) > 1 else f"Scende sotto la media a 10 mesi: {label(down)}."] if down else [])


def top_moves(values: pd.DataFrame, k: int = TOP) -> tuple[list[str], list[str]]:
    """Chi entra e chi esce dai primi k fra l'ultima riga e quella prima (valori piu' alti = meglio), nell'ordine
    della classifica di oggi (entrati) e di quella del mese prima (usciti)."""
    rows = values.dropna(how="all")
    if len(rows) < 2:
        return [], []
    # solo chi ha un valore in tutti e due i mesi: un dato mancante non e' un'uscita dai primi k
    both = rows.iloc[-2:].dropna(axis=1)
    prev, now = (both.iloc[i].sort_values(ascending=False).index[:k] for i in (-2, -1))
    return [x for x in now if x not in prev], [x for x in prev if x not in now]


def cells_by_month(prob: pd.DataFrame, names: dict[str, str]) -> pd.DataFrame:
    """Classi di asset (indice (area, mese), colonne classi) -> una riga per mese, una colonna "Classe · Paese"."""
    long = prob.stack()
    long.index = pd.MultiIndex.from_arrays([long.index.get_level_values(1),
                                           [f"{names.get(c, c)} · {a}" for a, c in zip(long.index.get_level_values(0), long.index.get_level_values(2))]])
    return long.unstack()


def moves_sentence(group: str, moves: tuple[list[str], list[str]], k: int = TOP) -> str | None:
    """Frase di top_moves: "Paesi, entra nei primi 3: Giappone. Esce: Canada." None se nulla cambia."""
    entered, left = moves
    if not entered and not left:
        return None
    parts = []
    if entered:
        parts.append(f"{'entrano' if len(entered) > 1 else 'entra'} nei primi {k}: {', '.join(entered)}")
    if left:
        parts.append(f"{'escono' if len(left) > 1 else 'esce'}: {', '.join(left)}")
    return f"{group}, " + ". ".join(p if i == 0 else p[0].upper() + p[1:] for i, p in enumerate(parts)) + "."


def summary(histories: dict[str, pd.DataFrame | None], trend: pd.DataFrame, names: dict[str, str],
            rankings: dict[str, tuple[str, pd.DataFrame]]) -> list[tuple[str, str]]:
    """Tutti i cambi del mese come (lettura di src/config/reliability.py, frase), nell'ordine regime e fase, tendenza,
    primi 3. rankings: gruppo -> (lettura, valori per mese, alto = meglio)."""
    out = regime_phase(histories) + [("trend", x) for x in trend_crossings(trend, names)]
    for group, (key, values) in rankings.items():
        if (sentence := moves_sentence(group, top_moves(values))) is not None:
            out.append((key, sentence))
    return out
