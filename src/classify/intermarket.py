import math

import pandas as pd

from src.classify.cycle import RECOVERY_BELOW_TREND
from src.classify.score import UNIVERSE, pillars

# Intermarket (11/10/2026), capitolo 5 del libro di riferimento (basato su John Murphy). Nel libro e' un
# controllo: i mercati devono confermare lo scenario macro; se non lo fanno si riduce il rischio, si opera solo dove
# c'e' vantaggio statistico e si preferiscono strumenti meno volatili. Le correlazioni cambiano nel tempo (dopo il
# 2008 sono salite tutte, nel 2022 petrolio e Treasury insieme fino a giugno), quindi si misurano su finestre mobili
# e si confrontano con la loro norma, mai date per fisse. Verifica in scripts/evaluate_intermarket.py.
# Soglie dal libro di riferimento o dalla richiesta dell'utente (finestre, 0,5, 0,7, 30 casi, t 2); scelte qui a priori, una sola
# variante ciascuna: |norma| >= 0,2 per contare il segno opposto, 6 mesi per il drawdown nella verifica.
# Verifica 2000-2026 (11/10/2026): la fase di Murphy non distingue i rendimenti a 3 mesi (3 confronti su 70 con
# |t| >= 2, tutti con 7-10 casi: quanti ne da' il caso); l'allineamento non anticipa i drawdown S&P 500 > 10% entro
# 6 mesi (allineati 25%, parziali 24%, disallineati 31%, tutti i mesi 26%; degli 8 cali dal 2000 1 partiva da
# disallineati). La pagina lo dice: e' una descrizione del momento, non un segnale.

AREA = "Intermarket"  # area in cache: chiusure giornaliere degli ultimi YEARS anni
YEARS = 10
FRED_SERIES = {"DGS10": "Rendimento Treasury 10 anni", "DFII10": "Tasso reale 10 anni", "DTWEXBGS": "Dollaro (broad)",
               "DCOILWTICO": "Petrolio WTI"}
COPPER = "HG=F"  # rame, future COMEX: non c'e' su FRED giornaliero
YAHOO = [*UNIVERSE, COPPER]  # tutti gli ETF del punteggio: servono alla correlazione fra i migliori della storia
RATES = {"DGS10", "DFII10"}  # in %: il "rendimento" giornaliero e' la variazione in punti, non in %
COPPER_GOLD = "Rame/oro"  # colonna derivata HG=F / GLD: il livello e' diverso dall'oro spot, la direzione no
DOLLAR, BENCHMARK = "DTWEXBGS", "SPY"

NORM_WINDOW, NORM_YEARS = 120, 5  # norma = mediana della correlazione a 120 giorni degli ultimi 5 anni
BREAK_GAP = 0.5  # rottura: distanza dalla norma oltre questo valore...
NORM_MIN_SIGN = 0.2  # ...oppure segno opposto, ma solo se la norma ha un segno (con norma ~0 il segno e' rumore)

# Le 4 relazioni chiave: (nome, serie a, serie b, segno atteso dal libro, cosa dice il libro)
RELATIONS = [
    ("Obbligazioni / materie prime", "TLT", "DBC", -1,
     "La più importante: materie prime in salita = crescita e inflazione = obbligazioni in calo."),
    ("Dollaro / materie prime", DOLLAR, "DBC", -1, "Dollaro forte = disinflazione e materie prime in calo."),
    ("Oro / tasso reale", "GLD", "DFII10", -1,
     "La relazione più forte per l'oro (storicamente circa −0,8); con l'inflazione l'oro è quasi scorrelato."),
    ("Rame-oro / rendimento 10 anni", COPPER_GOLD, "DGS10", 1,
     "Rame/oro anticipa crescita e rendimento a 10 anni: in calo = rallentamento o fuga verso i beni rifugio."),
]
DIRECTION_MONTHS = 3  # direzione di rame/oro e del rendimento a 10 anni

# Ciclo in 6 fasi di Murphy/Pring: (obbligazioni, azioni, materie prime) sopra la media a 10 mesi -> fase.
# Stadi di Pring: 1 inizio recessione, 2 fondo, 3 inizio ripresa, 4 espansione, 5 fine espansione, 6 inizio contrazione.
MURPHY_TICKERS = ("TLT", "SPY", "DBC")
MURPHY_PHASES = {
    (True, False, False): 1, (True, True, False): 2, (True, True, True): 3,
    (False, True, True): 4, (False, False, True): 5, (False, False, False): 6,
}
UNDEFINED = "Fase non definita"  # obbligazioni e materie prime nella stessa direzione, azioni contro

# Allineamento fase del ciclo dell'app -> fasi di Murphy (allineate, parziali); le altre due sono disallineate.
# Ogni fase dell'app copre due stadi consecutivi di Pring, i vicini sono parziali, gli opposti disallineati:
# Ripresa = obbligazioni e azioni gia' su, materie prime ultime a girare (2-3); Espansione = azioni e materie prime
# su, obbligazioni giu' con i tassi (3-4); Rallentamento = le azioni girano giu', poi tutto giu' (5-6);
# Recessione = tutto giu', poi le obbligazioni risalgono per prime (6-1).
MACRO_TO_MURPHY = {
    RECOVERY_BELOW_TREND: ({2, 3}, {1, 4}),
    "Espansione": ({3, 4}, {2, 5}),
    "Rallentamento": ({5, 6}, {4, 1}),
    "Recessione": ({6, 1}, {5, 2}),
}
COPPER_GOLD_UP = {RECOVERY_BELOW_TREND: True, "Espansione": True, "Rallentamento": False, "Recessione": False}
ALIGNED, PARTIAL, MISALIGNED = "Allineati", "Parzialmente allineati", "Disallineati"

# Extra-rendimento della verifica (scripts/evaluate_intermarket.py) a 3 mesi, come la Classifica fino al 26/10/2026:
# i numeri in spec.md sono a 3 mesi. La Classifica ora guarda a 6 (score.HORIZON_MONTHS).
HORIZON_MONTHS = 3


def levels(series: dict[str, pd.Series]) -> pd.DataFrame:
    """Chiusure giornaliere, una colonna per serie, piu' Rame/oro. Prezzi <= 0 scartati (WTI a -37$ il 20/04/2020)."""
    df = pd.DataFrame({k: s for k, s in series.items() if not s.empty})
    prices = [c for c in df if c not in RATES]
    df[prices] = df[prices].where(df[prices] > 0)
    if COPPER in df and "GLD" in df:
        df[COPPER_GOLD] = df[COPPER] / df["GLD"]
    return df


def pair_returns(lv: pd.DataFrame, a: str, b: str) -> pd.DataFrame:
    """Rendimenti giornalieri di a e b sulle sole date comuni (calendari FRED e Yahoo diversi, dollaro settimanale)."""
    both = lv[[a, b]].dropna()
    return pd.DataFrame({c: both[c].diff() if c in RATES else both[c].pct_change() for c in (a, b)}).dropna()


def rolling_corr(lv: pd.DataFrame, a: str, b: str, window: int) -> pd.Series:
    r = pair_returns(lv, a, b)
    return r[a].rolling(window).corr(r[b]).dropna()


def norm(corr_120: pd.Series) -> float:
    """Correlazione "normale": mediana della correlazione a 120 giorni degli ultimi NORM_YEARS anni."""
    if corr_120.empty:
        return math.nan
    return corr_120[corr_120.index >= corr_120.index[-1] - pd.DateOffset(years=NORM_YEARS)].median()


def is_break(current: float, usual: float) -> bool:
    """Correlazione attuale fuori dalla norma: segno opposto (se la norma ha un segno) o distanza oltre BREAK_GAP."""
    if math.isnan(current) or math.isnan(usual):
        return False
    return (abs(usual) >= NORM_MIN_SIGN and current * usual < 0) or abs(current - usual) > BREAK_GAP


def relation_state(current: float, usual: float, expected_sign: int) -> str:
    if math.isnan(current):
        return "n/d"
    if current * expected_sign < 0:
        return "rotta"
    if is_break(current, usual) and abs(current) < abs(usual):
        return "più debole del solito"
    return "regolare"


def change(s: pd.Series, months: int = DIRECTION_MONTHS) -> pd.Series:
    """Variazione rispetto all'ultimo valore di `months` mesi prima (serie giornaliera o mensile)."""
    s = s.dropna()
    past = s.reindex(s.index - pd.DateOffset(months=months), method="ffill")
    return pd.Series(s.to_numpy() - past.to_numpy(), index=s.index).dropna()


def murphy_phase(bonds_up: bool, stocks_up: bool, commodities_up: bool) -> int | None:
    """Fase 1-6, None se la combinazione non e' una fase del ciclo (UNDEFINED)."""
    return MURPHY_PHASES.get((bool(bonds_up), bool(stocks_up), bool(commodities_up)))


def murphy_history(px: pd.DataFrame, tickers: tuple = MURPHY_TICKERS) -> pd.Series:
    """Fase per mese da prezzi mensili a mese chiuso, stessa regola del filtro di tendenza (media a 10 mesi).
    tickers: (obbligazioni, azioni, materie prime). Fase 0 = non definita, NaN senza dati."""
    trend = pillars(px[list(tickers)])["Tendenza"].dropna()
    return pd.Series([murphy_phase(*(row > 0)) or 0 for row in trend.to_numpy()], index=trend.index, dtype=int)


def phase_label(phase: int) -> str:
    return f"Fase {phase}" if phase else UNDEFINED


def murphy_check(macro_phase: str, phase: int) -> str:
    """Fase di Murphy rispetto alla fase del ciclo: 'allineata', 'parziale' (anche se non definita) o 'disallineata'."""
    aligned, partial = MACRO_TO_MURPHY[macro_phase]
    return "allineata" if phase in aligned else "parziale" if not phase or phase in partial else "disallineata"


def alignment(macro_phase: str, phase: int, copper_gold_up: bool) -> str:
    """Controllo del libro di riferimento: la fase del ciclo dell'app e' confermata da fase di Murphy e direzione di rame/oro?
    Allineati = entrambi d'accordo; Disallineati = Murphy non allineata e rame/oro contrario; il resto e' parziale."""
    murphy_ok = murphy_check(macro_phase, phase) == "allineata"
    copper_ok = copper_gold_up == COPPER_GOLD_UP[macro_phase]
    if murphy_ok and copper_ok:
        return ALIGNED
    return MISALIGNED if not murphy_ok and not copper_ok else PARTIAL
