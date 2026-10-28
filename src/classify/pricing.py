"""Livello 1 della pagina Oggi, "Cosa prezza il mercato" (28/10/2026): tassi, credito, volatilita', opzioni e futures.
Guardano avanti e si aggiornano ogni giorno, al contrario dei dati macro (livello 2). Solo lettura descrittiva: la
regola che decide resta il filtro di tendenza (livello 3), finche' scripts/evaluate_pricing.py non mostra che un
segnale migliora il drawdown senza costare rendimento sia prima sia dopo il 2019.
Verifica del 28/10/2026 (SPY mensile, criterio fissato prima): nessun segnale passa. Credito, curva, struttura del VIX e
SKEW come uscita in piu' tolgono rendimento in almeno un periodo (SKEW: 2,6% l'anno dal 2019 contro 9,7% del filtro).
Il put/call letto al contrario (restare investiti con paura estrema) e' il piu' vicino: 2012-2018 10,6% contro 9,7%
con lo stesso drawdown (-14,9%), dal 2019 16,7% e -16,1% contro 9,7% e -21,9%; ma solo 13 mesi di allarme su 179 e
drawdown non migliore nel primo periodo: non entra, da rivedere con piu' storia.
Fonti: FRED (curva, credito, VIX, breakeven, dollaro), Yahoo (MOVE, SKEW, futures, rame), CBOE (put/call).
Le curve dei futures hanno storico solo da quando l'app le salva (Yahoo non ha i contratti scaduti): niente percentile
finche' non ci sono MIN_HISTORY_DAYS sedute, lo stato si legge dal segno.
"""
import pandas as pd

from src.classify.risk import FILL_DAYS, MIN_HISTORY_DAYS, expanding_percentile

ALARM_PCT = 80  # percentile oltre il quale un segnale "in tensione" e' in allarme (stessa soglia per tutti, non ottimizzata)
CALM_PCT = 20
PUT_CALL_DAYS = 10  # il put/call giornaliero e' rumoroso: media di due settimane
CHANGE_DAYS = 63  # rame/oro e dollaro: variazione dei 3 mesi
FUTURES_AREA = "Futures"


def load(read) -> dict[str, pd.Series]:
    """Serie giornaliere dalla cache; read(area, indicatore) -> pd.Series (src/ui/data.load_indicator o cache)."""
    d = {"curve": read("USA", "yield_curve"), "credit": read("USA", "credit_spread"), "vix": read("Mercati", "vix"),
         "vix3m": read("Mercati", "vix3m"), "move": read("Mercati", "move"), "skew": read("Mercati", "skew"),
         "put_call": read("Mercati", "put_call"), "breakeven": read("Mercati", "breakeven_5y5y"),
         "dollar": read("Intermarket", "DTWEXBGS"), "copper": read("Intermarket", "HG=F"), "gold": read("Intermarket", "GLD"),
         **{f"fut_{n}": read("Mercati", f"futures_{n}") for n in ("petrolio", "rame", "oro", "fed_funds")}}
    d["curves"] = {n: read(FUTURES_AREA, n) for n in ("petrolio", "rame", "oro", "fed_funds")}
    return d


def _flag(cond: pd.Series, valid: pd.Series) -> pd.Series:
    return cond.astype(float).where(valid.notna())


def alarms(d: dict[str, pd.Series]) -> pd.DataFrame:
    """Allarme giornaliero per segnale: 1 in allarme, 0 no, NaN se manca il dato o lo storico per il percentile."""
    credit, skew = expanding_percentile(d["credit"]), expanding_percentile(d["skew"])
    put_call = expanding_percentile(d["put_call"].rolling(PUT_CALL_DAYS).mean())
    structure = (d["vix"] / d["vix3m"]).dropna()
    return pd.DataFrame({
        "Credito": _flag(credit >= ALARM_PCT, credit),
        "Curva": _flag(d["curve"] < 0, d["curve"]),
        "Struttura VIX": _flag(structure > 1, structure),
        "SKEW": _flag(skew >= ALARM_PCT, skew),
        "Put/call": _flag(put_call >= ALARM_PCT, put_call),
    }).ffill(limit=FILL_DAYS)


def _num(x: float, digits: int = 1, sign: bool = False) -> str:
    return f"{x:{'+' if sign else ''}.{digits}f}".replace(".", ",").replace("-", "−")


def _pct_state(s: pd.Series, high: str, low: str, high_tone: str = "r-stag", low_tone: str = "r-gold") -> tuple[str, str, float | None]:
    """Stato dal percentile point-in-time dell'ultimo valore: (stato, token colore, percentile o None)."""
    p = expanding_percentile(s).dropna() if len(s.dropna()) > MIN_HISTORY_DAYS else pd.Series(dtype=float)
    if p.empty:
        return "storico breve", "muted", None
    last = p.iloc[-1]
    if last >= ALARM_PCT:
        return high, high_tone, last
    if last <= CALM_PCT:
        return low, low_tone, last
    return "normale", "muted", last


def _curve_note(curve: pd.Series, unit: str) -> str:
    if len(curve) < 2:
        return ""
    far = curve.index[abs(curve.index - (curve.index[0] + pd.DateOffset(months=12))).argmin()]
    return f" Primo contratto {_num(curve.iloc[0], 2)} {unit}, scadenza {far.month:02d}/{far.year} {_num(curve[far], 2)} {unit}."


def rows(d: dict[str, pd.Series]) -> list[dict]:
    """Una riga per segnale con l'ultimo valore: name, value, state, tone (token colore), pct (o None), note, date.
    I segnali senza dati in cache si saltano."""
    out = []

    def add(key: str, name: str, s: pd.Series, value: str, state: str, tone: str, pct: float | None, note: str) -> None:
        out.append({"key": key, "name": name, "value": value, "state": state, "tone": tone, "pct": pct, "note": note,
                    "date": s.index[-1]})

    if not (s := d["curve"].dropna()).empty:
        v = s.iloc[-1]
        state, tone = ("invertita", "r-stag") if v < 0 else ("piatta", "r-refl") if v < 0.5 else ("normale", "r-gold")
        add("curve", "Curva dei tassi USA 10 anni − 3 mesi", s, f"{_num(v, 2, True)} pt", state, tone, None,
            "Sotto zero il mercato si aspetta tassi più bassi in futuro: negli USA è arrivata prima di ogni recessione dal "
            "1970, con mesi o anni di anticipo e qualche falso allarme.")
    if not (s := d["credit"].dropna()).empty:
        state, tone, p = _pct_state(s, "teso", "calmo")
        add("credit", "Credito: rendimento Baa − Treasury 10 anni", s, f"{_num(s.iloc[-1], 2)} pt", state, tone, p,
            "Quanto chiedono in più gli investitori per prestare alle aziende. Si allarga quando temono fallimenti.")
    if not (s := d["breakeven"].dropna()).empty:
        state, tone, p = _pct_state(s, "alta", "bassa", "r-refl", "r-defl")
        add("breakeven", "Inflazione attesa fra 5 e 10 anni", s, f"{_num(s.iloc[-1], 2)}%", state, tone, p,
            "Inflazione media che il mercato dei titoli indicizzati prezza dal quinto al decimo anno. Vicino al 2-2,5% = ancorata.")
    if not (s := d["fut_fed_funds"].dropna()).empty:
        v = s.iloc[-1]
        state = "tagli" if v <= -0.25 else "rialzi" if v >= 0.25 else "tassi fermi"
        add("fed", "Tassi Fed attesi fra 12 mesi (futures)", s, f"{_num(v, 2, True)} pt", state,
            "r-defl" if v <= -0.25 else "r-refl" if v >= 0.25 else "muted", None,
            f"Differenza fra il tasso implicito nei futures sui Fed Funds a 12 mesi e quello del primo contratto: "
            f"{_num(abs(v) / 0.25, 1)} mosse da 0,25 prezzate.")
    if not (s := (d["vix"] / d["vix3m"]).dropna()).empty:
        v = s.iloc[-1]
        state, tone = ("paura sul breve", "r-stag") if v > 1 else ("in salita", "r-refl") if v > 0.9 else ("normale", "r-gold")
        add("structure", "Opzioni: VIX a 1 mese / VIX a 3 mesi", s, _num(v, 2), state, tone, None,
            f"Sopra 1 le opzioni costano più sul mese che sui tre mesi: la paura è concentrata ora. VIX {_num(d['vix'].dropna().iloc[-1])}.")
    if not (s := d["skew"].dropna()).empty:
        state, tone, p = _pct_state(s, "molto richiesta", "poco richiesta", "r-refl", "muted")
        add("skew", "Opzioni: SKEW, protezione dai crolli", s, _num(s.iloc[-1], 0), state, tone, p,
            "Quanto costano le put molto lontane sull'S&P 500. Alto = chi investe si assicura contro un crollo; da solo "
            "non ha mai anticipato bene i ribassi.")
    if not (s := d["put_call"].dropna()).empty:
        m = s.rolling(PUT_CALL_DAYS).mean().dropna()
        state, tone, p = _pct_state(m, "paura", "euforia", "r-refl", "r-refl")
        add("put_call", f"Opzioni: put/call azionario, media {PUT_CALL_DAYS} sedute", s, _num(m.iloc[-1], 2), state, tone, p,
            "Put comprate per ogni call sulle azioni USA. Si legge al contrario: paura e euforia estreme spesso arrivano vicino "
            "a un punto di svolta.")
    if not (s := d["move"].dropna()).empty:
        state, tone, p = _pct_state(s, "alta", "bassa", "r-stag", "r-gold")
        add("move", "Volatilità dei titoli di Stato (MOVE)", s, _num(s.iloc[-1], 0), state, tone, p,
            "Il VIX delle obbligazioni USA. Alta = incertezza sui tassi, che di solito pesa anche sulle azioni.")
    for name, label, unit in (("petrolio", "Petrolio", "$"), ("rame", "Rame", "$"), ("oro", "Oro", "$")):
        if (s := d[f"fut_{name}"].dropna()).empty:
            continue
        v = s.iloc[-1]
        state, tone = ("backwardation", "r-refl") if v < -2 else ("contango", "muted") if v > 2 else ("piatta", "muted")
        add(f"fut_{name}", f"{label}: curva dei futures a 12 mesi", s, f"{_num(v, 1, True)}% l'anno", state, tone, None,
            "Futures a 12 mesi contro il primo, in % l'anno." + _curve_note(d["curves"][name], unit))
    copper, gold = d["copper"].dropna(), d["gold"].dropna()
    if not copper.empty and not gold.empty:
        ratio = (copper / gold).dropna()
        v = (ratio.iloc[-1] / ratio.iloc[-1 - CHANGE_DAYS] - 1) * 100 if len(ratio) > CHANGE_DAYS else None
        if v is not None:
            add("copper_gold", "Rame / oro, 3 mesi", ratio, f"{_num(v, 1, True)}%", "in salita" if v > 0 else "in calo",
                "r-gold" if v > 0 else "r-refl", None,
                "Rame (industria) contro oro (rifugio): sale quando il mercato si aspetta più crescita.")
    if len(s := d["dollar"].dropna()) > CHANGE_DAYS:
        v = (s.iloc[-1] / s.iloc[-1 - CHANGE_DAYS] - 1) * 100
        add("dollar", "Dollaro contro le principali valute, 3 mesi", s, f"{_num(v, 1, True)}%",
            "in salita" if v > 0 else "in calo", "muted", None,
            "Un dollaro forte stringe le condizioni finanziarie nel mondo e pesa su emergenti e materie prime.")
    return out
