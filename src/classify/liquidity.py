"""Liquidita', politica monetaria e intensita' del regime USA (28/10/2026), cap. 7 del libro di riferimento: PIL e CPI
dicono il regime, liquidita' e politica monetaria quanto e' profondo. Conta soprattutto in Stagflazione e Deflazione,
dove la versione debole e quella forte danno settori molto diversi.
Solo lettura descrittiva, come il livello 1: entra in una regola solo se scripts/evaluate_pricing.py lo promuove.
Soglie scelte a priori, una variante ciascuna; il libro non da' numeri, tranne l'inflazione al 2%.
Fonti: FRED (WALCL - WTREGEN - RRPONTSYD, M2SL, DFEDTARU, FEDTARMD, FEDFUNDS) e futures sui Fed Funds (Yahoo).
"""
import pandas as pd

from src.classify.pricing import _num

LIQUIDITY_WEEKS = 26  # liquidita' netta: variazione a 6 mesi, il segno dice espansione o calo
GDP_DROP = 1.0  # calo del PIL "pronunciato": crescita annua scesa di almeno 1 punto in un trimestre
INFLATION_TARGET = 2.0  # la soglia del libro per l'intensita'
REAL_RATE_TIGHT = 1.0  # politica restrittiva: Fed Funds sopra l'inflazione core di oltre 1 punto
STRONG_FACTORS, WEAK_FACTORS = 3, 1  # su 4 fattori: almeno 3 = forte, al massimo 1 = debole, in mezzo = media
INTENSITY_REGIMES = ("Stagflazione", "Deflazione")  # il libro da' la versione debole e forte solo per questi
MOVE = 0.25  # una mossa della Fed


def liquidity_change(net: pd.Series) -> pd.Series:
    """Variazione % della liquidita' netta su LIQUIDITY_WEEKS settimane, alla data di ogni dato."""
    return (net / net.shift(LIQUIDITY_WEEKS) - 1).dropna() * 100


def real_rate(fed_funds: pd.Series, core: pd.Series) -> pd.Series:
    """Fed Funds effettivo meno inflazione core annua, mensile."""
    if fed_funds.empty or core.empty:
        return pd.Series(dtype=float)
    m = lambda s: s.resample("MS").last()
    return (m(fed_funds) - m(core).ffill()).dropna()


def factors(growth: pd.Series, inflation: pd.Series, liq_change: pd.Series, real: pd.Series) -> pd.DataFrame:
    """I 4 fattori d'intensita' del libro, mensili, True quando aggravano: calo del PIL pronunciato, inflazione sopra
    il 2%, liquidita' in calo, politica restrittiva. NaN dove manca il dato."""
    m = lambda s: s.resample("MS").last().ffill()
    g = m(growth)
    cols = {"PIL in calo forte": (g.shift(3) - g) >= GDP_DROP, "Inflazione sopra il 2%": m(inflation) > INFLATION_TARGET,
            "Liquidità in calo": m(liq_change) < 0, "Politica restrittiva": m(real) > REAL_RATE_TIGHT}
    valid = {"PIL in calo forte": g.shift(3), "Inflazione sopra il 2%": m(inflation), "Liquidità in calo": m(liq_change),
             "Politica restrittiva": m(real)}
    # ogni fattore resta valido fino al dato successivo: il PIL e' trimestrale, la liquidita' settimanale
    return pd.DataFrame({k: v.astype(float).where(valid[k].notna()) for k, v in cols.items()}).ffill()


def intensity(regime: str, n_factors: int) -> str | None:
    """'forte', 'media' o 'debole' per Stagflazione e Deflazione, None per gli altri regimi."""
    if regime not in INTENSITY_REGIMES:
        return None
    return "forte" if n_factors >= STRONG_FACTORS else "debole" if n_factors <= WEAK_FACTORS else "media"


def december(curve: pd.Series, year: int) -> float | None:
    """Tasso implicito (100 - prezzo) del future sui Fed Funds di dicembre `year`, None se la curva non ci arriva."""
    d = pd.Timestamp(year=year, month=12, day=1)
    return float(100 - curve[d]) if d in curve.index else None


def policy(target_upper: pd.Series, dots: pd.Series, curve: pd.Series) -> list[dict]:
    """Per fine anno corrente e prossimo: tasso di oggi (meta' forchetta), mediana del dot plot e tasso prezzato dai
    futures, con il numero di mosse da 0,25. Salta gli anni senza dot plot."""
    if target_upper.dropna().empty:
        return []
    now = float(target_upper.dropna().iloc[-1]) - MOVE / 2
    year = target_upper.dropna().index[-1].year
    out = []
    for y in (year, year + 1):
        fed = dots[dots.index.year == y]
        if fed.empty:
            continue
        market = december(curve, y)
        out.append({"year": y, "now": now, "fed": float(fed.iloc[-1]), "market": market,
                    "fed_moves": (float(fed.iloc[-1]) - now) / MOVE, "market_moves": None if market is None else (market - now) / MOVE})
    return out


def load(read) -> dict[str, pd.Series]:
    """Serie dalla cache; read(area, indicatore) -> pd.Series, come pricing.load."""
    return {"net": read("Mercati", "net_liquidity"), "m2": read("Mercati", "m2_yoy"), "target": read("Mercati", "fed_target"),
            "dots": read("Mercati", "dot_plot"), "curve": read("Futures", "fed_funds"), "fed_funds": read("USA", "fed_funds"),
            "growth": read("USA", "growth_yoy"), "inflation": read("USA", "inflation_yoy"), "core": read("USA", "core_inflation_yoy")}


def rows(d: dict[str, pd.Series], regime: str | None) -> list[dict]:
    """Righe per la card (stesso formato di pricing.rows): intensita' del regime USA, liquidita', M2, Fed contro
    mercato, tasso reale. I pezzi senza dati si saltano."""
    out = []

    def add(name: str, s: pd.Series, value: str, state: str, tone: str, note: str) -> None:
        out.append({"name": name, "value": value, "state": state, "tone": tone, "pct": None, "note": note, "date": s.index[-1]})

    liq, real = liquidity_change(d["net"].dropna()), real_rate(d["fed_funds"].dropna(), d["core"].dropna())
    inputs = (d["growth"].dropna(), d["inflation"].dropna(), liq, real)
    f = factors(*inputs).dropna() if all(not s.empty for s in inputs) else pd.DataFrame()
    if regime and not f.empty:
        last = f.iloc[-1].astype(bool)
        level = intensity(regime, int(last.sum()))
        on = [k.lower() for k, v in last.items() if v]
        add(f"Intensità del regime USA: {regime}", f, f"{int(last.sum())} fattori su 4", level or "solo per stagflazione e deflazione",
            {"forte": "r-stag", "media": "r-refl", "debole": "r-gold"}.get(level, "muted"),
            ("Presenti: " + ", ".join(on) + "." if on else "Nessun fattore che aggrava.") +
            f" Forte con almeno {STRONG_FACTORS}, debole con al massimo {WEAK_FACTORS}: la versione forte e quella debole "
            "favoriscono settori diversi.")
    if not liq.empty:
        v = liq.iloc[-1]
        add("Liquidità netta della Fed", d["net"].dropna(), f"{_num(d['net'].dropna().iloc[-1] / 1000, 2)} mila mld $",
            "in calo" if v < 0 else "in aumento", "r-refl" if v < 0 else "r-gold",
            f"Attivi della Fed meno il conto del Tesoro e i reverse repo: il denaro che resta ai mercati. {_num(v, 1, True)}% in 6 mesi.")
    if not (s := d["m2"].dropna()).empty:
        v = s.iloc[-1]
        add("Massa monetaria M2 USA, annua", s, f"{_num(v, 1, True)}%", "in calo" if v < 0 else "in crescita",
            "r-refl" if v < 0 else "muted", "Contante, conti e depositi: cresce quando banche e Fed creano credito.")
    for p in policy(d["target"], d["dots"], d["curve"].dropna()):
        gap = None if p["market"] is None else p["market"] - p["fed"]
        state = ("dati mancanti" if gap is None else "mercato più rigido della Fed" if gap >= MOVE
                 else "mercato più morbido della Fed" if gap <= -MOVE else "mercato e Fed d'accordo")
        moves = lambda m: f"{_num(abs(m), 1)} {'rialzi' if m > 0 else 'tagli'} da 0,25" if abs(m) >= 0.5 else "tassi fermi"
        add(f"Tassi Fed a fine {p['year']}: Fed contro mercato", d["target"].dropna(),
            f"Fed {_num(p['fed'], 2)}% · mercato {'n/d' if p['market'] is None else _num(p['market'], 2) + '%'}", state,
            "muted" if gap is None or abs(gap) < MOVE else "r-refl",
            f"Oggi {_num(p['now'], 2)}% (metà forchetta). Dot plot della Fed: {moves(p['fed_moves'])}; futures: "
            f"{'n/d' if p['market_moves'] is None else moves(p['market_moves'])}.")
    if not real.empty:
        v = real.iloc[-1]
        add("Tasso reale della Fed", real, f"{_num(v, 2, True)} pt",
            "restrittivo" if v > REAL_RATE_TIGHT else "espansivo" if v < 0 else "neutro",
            "r-refl" if v > REAL_RATE_TIGHT else "r-gold" if v < 0 else "muted",
            "Fed Funds meno inflazione core. Sopra 1 punto la Fed frena l'economia, sotto zero la spinge.")
    return out
