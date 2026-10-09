import pandas as pd
import requests

BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
SERIES_GROWTH = "GDPC1"  # Real GDP
SERIES_INFLATION = "CPIAUCSL"  # CPI All Urban Consumers
SERIES_CORE_INFLATION = "CPILFESL"  # CPI escluso cibo ed energia
SERIES_UNEMPLOYMENT = "UNRATE"  # Civilian Unemployment Rate
# Disoccupazione OCSE via FRED per le aree senza fonte nazionale (Cina e India non la pubblicano mensile).
UNEMPLOYMENT_INTL = {"Canada": "LRUNTTTTCAM156S", "Australia": "LRUNTTTTAUM156S"}
SERIES_YIELD_CURVE = "T10Y3M"  # 10Y - 3M Treasury spread, punti %
# Baa - 10Y Treasury. Non uso BAMLH0A0HYM2 (HY OAS): FRED ne espone solo 3 anni,
# inutili per tarare le soglie. BAA10Y parte dal 1986.
SERIES_CREDIT_SPREAD = "BAA10Y"
SERIES_VIX = "VIXCLS"  # CBOE VIX, chiusura giornaliera
SERIES_RECESSION_PROB = "RECPROUSM156N"  # Chauvet-Piger: prob. che gli USA SIANO in recessione ora (coincidente, non previsionale), %
SERIES_BREAKEVEN_5Y = "T5YIE"  # inflazione attesa a 5 anni (breakeven), %
SERIES_BREAKEVEN_5Y5Y = "T5YIFR"  # inflazione attesa 5 anni fra 5 anni (forward), %
SERIES_INDUSTRIAL_PRODUCTION = "INDPRO"  # produzione industriale, YoY mensile: proxy di crescita piu' tempestivo del PIL
SERIES_FED_FUNDS = "FEDFUNDS"  # tasso Fed Funds effettivo, %
SERIES_FIN_CONDITIONS = "NFCI"  # Chicago Fed National Financial Conditions Index, >0 = piu' stretto della media
SERIES_CLAIMS = "ICSA"  # richieste iniziali sussidi disoccupazione, settimanali
SERIES_PERMITS = "PERMIT"  # permessi di costruzione, migliaia di unita' annualizzate
# ISM PMI non e' su FRED (rimosso nel 2016) ne' su altre fonti gratuite affidabili: la survey
# manifatturiera della Philadelphia Fed e' il proxy regionale piu' usato (diffusion index, <0 = contrazione).
SERIES_PHILLY_FED = "GACDFSA066MSFRBPHI"
SERIES_GDPNOW = "GDPNOW"  # Atlanta Fed GDPNow: stima del PIL del trimestre in corso, % t/t annualizzata
# Rendimenti mensili OCSE (via FRED) per le curve fuori USA: decennale - tasso breve.
# UK: il 3 mesi interbancario (IR3TIB01GBM156N) e' fermo a gen 2026, si usa il tasso overnight.
CURVES = {
    "Eurozona": ("IRLTLT01DEM156N", "IR3TIB01DEM156N"),  # Bund 10Y - 3M (Germania, riferimento dell'area)
    "UK": ("IRLTLT01GBM156N", "IRSTCI01GBM156N"),
    "Giappone": ("IRLTLT01JPM156N", "IR3TIB01JPM156N"),
}
BTP_BUND = ("IRLTLT01ITM156N", "IRLTLT01DEM156N")  # BTP 10Y - Bund 10Y


def _fetch_series(series_id: str, api_key: str, units: str = "pc1") -> pd.Series:
    resp = requests.get(
        BASE_URL,
        params={
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "units": units,  # pc1 = percent change from a year ago (YoY diretto da FRED)
        },
        timeout=30,
    )
    resp.raise_for_status()
    observations = resp.json()["observations"]
    dates = [pd.Timestamp(o["date"]) for o in observations if o["value"] != "."]
    values = [float(o["value"]) for o in observations if o["value"] != "."]
    return pd.Series(values, index=dates).sort_index()


def fetch_growth_yoy(api_key: str) -> pd.Series:
    return _fetch_series(SERIES_GROWTH, api_key)


def fetch_inflation_yoy(api_key: str) -> pd.Series:
    return _fetch_series(SERIES_INFLATION, api_key)


def fetch_core_inflation_yoy(api_key: str) -> pd.Series:
    return _fetch_series(SERIES_CORE_INFLATION, api_key)


def fetch_unemployment_rate(api_key: str, series_id: str = SERIES_UNEMPLOYMENT) -> pd.Series:
    return _fetch_series(series_id, api_key, units="lin")  # gia' un tasso %, no trasformazione


def fetch_yield_curve(api_key: str) -> pd.Series:
    return _fetch_series(SERIES_YIELD_CURVE, api_key, units="lin")


def fetch_credit_spread(api_key: str) -> pd.Series:
    return _fetch_series(SERIES_CREDIT_SPREAD, api_key, units="lin")


def fetch_financial_conditions(api_key: str) -> pd.Series:
    return _fetch_series(SERIES_FIN_CONDITIONS, api_key, units="lin")


def fetch_vix(api_key: str) -> pd.Series:
    return _fetch_series(SERIES_VIX, api_key, units="lin")


def fetch_recession_probability(api_key: str) -> pd.Series:
    return _fetch_series(SERIES_RECESSION_PROB, api_key, units="lin")


def fetch_breakeven_5y(api_key: str) -> pd.Series:
    return _fetch_series(SERIES_BREAKEVEN_5Y, api_key, units="lin")


def fetch_breakeven_5y5y(api_key: str) -> pd.Series:
    return _fetch_series(SERIES_BREAKEVEN_5Y5Y, api_key, units="lin")


def fetch_industrial_production_yoy(api_key: str) -> pd.Series:
    return _fetch_series(SERIES_INDUSTRIAL_PRODUCTION, api_key)


def fetch_fed_funds(api_key: str) -> pd.Series:
    return _fetch_series(SERIES_FED_FUNDS, api_key, units="lin")


def fetch_claims(api_key: str) -> pd.Series:
    return _fetch_series(SERIES_CLAIMS, api_key, units="lin")


def fetch_permits(api_key: str) -> pd.Series:
    return _fetch_series(SERIES_PERMITS, api_key, units="lin")


def fetch_philly_fed(api_key: str) -> pd.Series:
    return _fetch_series(SERIES_PHILLY_FED, api_key, units="lin")


def fetch_gdpnow(api_key: str) -> pd.Series:
    return _fetch_series(SERIES_GDPNOW, api_key, units="lin")


def fetch_spread(long_id: str, short_id: str, api_key: str) -> pd.Series:
    """Differenza fra due serie di tassi (punti %), solo date presenti in entrambe."""
    return (_fetch_series(long_id, api_key, units="lin") - _fetch_series(short_id, api_key, units="lin")).dropna()
