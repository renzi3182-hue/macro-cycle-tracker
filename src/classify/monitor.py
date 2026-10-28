"""Cruscotto USA (28/10/2026): le serie mensili che il libro di riferimento segue mese su mese (cap. 6, fig. 6.8),
in un foglio dove conta la direzione. Tutte su FRED, salvo il CLI OCSE gia' in cache (area USA).
Sostituzioni: "risparmio in % del PIL" -> tasso di risparmio delle famiglie (PSAVERT, mensile); fiducia del
manifatturiero OCSE -> BSCICP02USM460S (la versione normalizzata BSCICP03USM665S si e' fermata a gennaio 2024).
Diffusione: quota delle serie con un verso (sign != 0) che stanno meglio di 3 mesi prima. Solo lettura descrittiva:
entra in una regola solo se scripts/evaluate_pricing.py la promuove. FRED da' l'ultima versione dei dati, non quella
di allora: nel backtest le revisioni restano un look-ahead.
"""
import pandas as pd

from src.classify.assess import PUBLICATION_LAG_MONTHS

AREA = "Cruscotto USA"
LOOKBACK_MONTHS = 3  # direzione: ultimo dato contro quello di 3 mesi prima (un trimestre per le serie trimestrali)
DIFFUSION_ALARM = 50  # allarme sotto meta' delle serie in miglioramento, scelto prima del backtest
QUARTERLY_LAG = PUBLICATION_LAG_MONTHS["growth_yoy"]  # mesi fra l'inizio del trimestre e la pubblicazione, come il PIL
# (chiave, ID FRED, nome, verso: 1 = salire e' buono per l'economia, -1 = cattivo, 0 = neutro; unita': "pt" = la
# variazione si legge in punti, "%" = in percentuale; trimestrale)
SERIES = [
    ("Lavoro", [
        ("payrolls", "PAYEMS", "Occupati non agricoli", 1, "%", False),
        ("private_payrolls", "USPRIV", "Occupati privati", 1, "%", False),
        ("claims", "ICSA", "Richieste di sussidio (settimanali)", -1, "%", False),
        ("weeks_unemployed", "UEMPMEAN", "Settimane medie di disoccupazione", -1, "pt", False),
        ("hours_mfg", "AWHMAN", "Ore settimanali nel manifatturiero", 1, "pt", False),
        ("ulc_mfg", "ULCMFG", "Costo del lavoro per unità, manifattura", 0, "%", True),
    ]),
    ("Fiducia", [
        ("cli", None, "Leading indicator OCSE", 1, "pt", False),
        ("umich", "UMCSENT", "Fiducia dei consumatori (Michigan)", 1, "pt", False),
        ("mfg_confidence", "BSCICP02USM460S", "Fiducia del manifatturiero (OCSE)", 1, "pt", False),
    ]),
    ("Produzione e ordini", [
        ("industrial_production", "INDPRO", "Produzione industriale", 1, "%", False),
        ("durable_orders", "DGORDER", "Ordini di beni durevoli", 1, "%", False),
        ("durable_ex_defense", "ADXDNO", "Ordini durevoli senza difesa", 1, "%", False),
        ("durable_ex_transport", "ADXTNO", "Ordini durevoli senza trasporti", 1, "%", False),
        ("real_sales", "CMRMTSPL", "Vendite reali di manifattura e commercio", 1, "%", False),
        ("gdp", "GDPC1", "PIL reale", 1, "%", True),
    ]),
    ("Consumi e redditi", [
        ("retail_sales", "RSAFS", "Vendite al dettaglio e ristorazione", 1, "%", False),
        ("real_income", "DSPIC96", "Reddito disponibile reale", 1, "%", False),
        ("income_ex_transfers", "W875RX1", "Reddito reale senza trasferimenti", 1, "%", False),
        ("saving_rate", "PSAVERT", "Tasso di risparmio delle famiglie", 0, "pt", False),
        ("debt_service", "TDSP", "Servizio del debito, % del reddito", -1, "pt", True),
    ]),
    ("Casa", [
        ("permits", "PERMIT", "Permessi edilizi", 1, "%", False),
        ("residential_construction", "PRRESCONS", "Spesa per costruzioni residenziali", 1, "%", False),
    ]),
    ("Scorte", [
        ("business_inventories", "BUSINV", "Scorte totali delle imprese", 0, "%", False),
        ("wholesale_inventories", "WHLSLRIMSA", "Scorte dei grossisti", 0, "%", False),
        ("real_inventories", "INVCMRMTSPL", "Scorte reali di manifattura e commercio", 0, "%", False),
        ("inventory_change", "CBI", "Variazione delle scorte private (mld $)", 0, "pt", True),
    ]),
    ("Credito, prezzi e moneta", [
        ("prime_rate", "MPRIME", "Tasso prime delle banche", 0, "pt", False),
        ("ci_loans", "BUSLOANS", "Prestiti a imprese (C&I)", 1, "%", False),
        ("cpi", "CPIAUCSL", "Prezzi al consumo (CPI)", 0, "%", False),
        ("core_cpi", "CPILFESL", "CPI senza cibo ed energia", 0, "%", False),
        ("m2_velocity", "M2V", "Velocità di M2", 0, "pt", True),
    ]),
    ("Commercio estero", [
        ("exports", "BOPTEXP", "Export di beni e servizi", 1, "%", False),
        ("imports", "BOPTIMP", "Import di beni e servizi", 0, "%", False),
    ]),
]
ALL = [s for _, group in SERIES for s in group]
FRED_SERIES = {key: fred for key, fred, *_ in ALL if fred}


def to_monthly(s: pd.Series) -> pd.Series:
    """Valore di fine mese (le richieste di sussidio sono settimanali)."""
    s = s.dropna()
    if s.empty:
        return pd.Series(dtype=float, index=pd.DatetimeIndex([]))
    return s.resample("MS").last().dropna()


def change(s: pd.Series, unit: str, months: int) -> float | None:
    """Ultimo dato contro quello di `months` mesi prima o meno recente: in punti o in %; None senza storia."""
    s = to_monthly(s)
    if s.empty:
        return None
    before = s[s.index <= s.index[-1] - pd.DateOffset(months=months)]
    if before.empty:
        return None
    a, b = s.iloc[-1], before.iloc[-1]
    return a - b if unit == "pt" else (a / b - 1) * 100 if b else None


def published(s: pd.Series, quarterly: bool) -> pd.Series:
    """Serie mensile spostata alla data di pubblicazione: 1 mese, 4 per i trimestrali (come assess.lagged)."""
    out = to_monthly(s)
    out.index = out.index + pd.DateOffset(months=QUARTERLY_LAG if quarterly else 1)
    return out


def diffusion(series: dict[str, pd.Series], today: pd.Timestamp | None = None) -> pd.Series:
    """Per ogni mese fino a oggi, % delle serie con un verso che stanno meglio di LOOKBACK_MONTHS prima, con i soli
    dati gia' pubblicati. NaN finche' non ci sono almeno meta' delle serie."""
    cols = {}
    for key, _, _, sign, _, quarterly in ALL:
        if sign == 0 or key not in series or series[key].dropna().empty:
            continue
        s = published(series[key], quarterly)
        s = s.reindex(pd.date_range(s.index[0], s.index[-1], freq="MS")).ffill()
        cols[key] = ((s - s.shift(LOOKBACK_MONTHS)) * sign > 0).astype(float).where(s.shift(LOOKBACK_MONTHS).notna())
    df = pd.DataFrame(cols).ffill(limit=LOOKBACK_MONTHS)  # serie uscite prima delle altre: valgono fino al dato dopo
    df = df[df.index <= (pd.Timestamp.today() if today is None else today)]  # le richieste settimanali escono subito
    n = df.notna().sum(axis=1)
    return (df.sum(axis=1) / n * 100).where(n >= sum(1 for s in ALL if s[3]) / 2)


def load(read) -> dict[str, pd.Series]:
    """read(area, indicatore) -> pd.Series; il CLI viene dall'area USA."""
    return {key: read("USA", "cli") if fred is None else read(AREA, key) for key, fred, *_ in ALL}


def rows(d: dict[str, pd.Series]) -> list[tuple[str, list[dict]]]:
    """Per gruppo, una riga per serie con dati: ultimo mese, variazione sul periodo prima (mese o trimestre) e su
    LOOKBACK_MONTHS mesi, verso. Gruppi senza dati saltati."""
    out = []
    for group, items in SERIES:
        r = [{"name": name, "quarterly": quarterly, "date": to_monthly(d[key]).index[-1], "sign": sign, "unit": unit,
              "prev": change(d[key], unit, 3 if quarterly else 1), "lookback": change(d[key], unit, LOOKBACK_MONTHS)}
             for key, _, name, sign, unit, quarterly in items if not to_monthly(d.get(key, pd.Series(dtype=float))).empty]
        if r:
            out.append((group, r))
    return out
