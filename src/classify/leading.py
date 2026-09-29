import pandas as pd

# USA: tarato su backtest FRED (163 trimestri, 1986-2026): le soglie di spread e
# NFCI sono il 75° percentile storico, la curva e' l'inversione classica.
# Con >= 2 segnali su 3 il rischio e' "Alto" in ~9% dei trimestri, concentrati
# attorno a 1989-90, 2000, 2008-11, 2020 (piu' un falso allarme nel 2023).
CURVE_INVERSION = 0.0  # 10Y-3M sotto zero
CREDIT_SPREAD_STRESS = 2.7  # Baa-10Y, punti %
FIN_CONDITIONS_TIGHT = -0.2  # NFCI
HIGH_RISK_MIN_SIGNALS = 2

# Fuori USA: verificato con scripts/backtest_leading_intl.py (29/09/2026) contro i rallentamenti
# del ciclo di crescita OCSE (FRED EUROREC/ITAREC/GBRREC/JPNREC, fino al 2022). Quei rallentamenti
# coprono ~55-60% dei mesi (finestra 12m inclusa): "precisione" va confrontata con quel tasso di base.
# - CLI in calo sotto 100: precisione 79-87% (base 57-61%) EZ/IT/JP; UK debole (63% vs 53%, 12 falsi allarmi).
# - ESI < 95: 63-66% (base 54-55%), coincidente (segnala 2-3 mesi DOPO l'inizio), pochi falsi allarmi.
#   Soglia 100 non ha informazione (precisione = base), 90 non migliora.
# - BTP-Bund >= 2.0: 75% (base 55%), anticipo mediano 10 mesi. 2.5 piu' preciso (82%) ma perde episodi.
# - Tankan: il livello < 0 non ha informazione (60% = base); il calo su 2 trimestri si':
#   9/10 episodi, anticipo mediano 11 mesi, 78% (base 60%).
# - Curve: Bund 85% (base 58%), gilt 71% (47%), JGB poco informativa (quasi mai invertita, dati dal 2002).
CLI_NEUTRAL = 100.0  # OECD CLI amplitude adjusted: sotto 100 = attivita' sotto il trend
CLI_TREND_MONTHS = 3  # ... e in calo rispetto a 3 mesi prima = fase di rallentamento (convenzione OCSE)
ESI_WEAK = 95.0  # Economic Sentiment Indicator, media storica 100
BTP_BUND_STRESS = 2.0  # punti %
TANKAN_FALL_QUARTERS = 2  # Tankan (trimestrale) sotto il valore di 2 trimestri prima


def cli_downturn(cli: pd.Series) -> pd.Series:
    return (cli < CLI_NEUTRAL) & (cli < cli.shift(CLI_TREND_MONTHS))


# area -> [(etichetta, indicatore in cache, test vettoriale sulla serie)]
SIGNALS = {
    "USA": [
        ("Curva invertita", "yield_curve", lambda s: s < CURVE_INVERSION),
        ("Spread credito alto", "credit_spread", lambda s: s >= CREDIT_SPREAD_STRESS),
        ("Condizioni finanziarie strette", "fin_conditions", lambda s: s >= FIN_CONDITIONS_TIGHT),
    ],
    "Eurozona": [
        ("CLI OCSE in calo sotto 100", "cli", cli_downturn),
        ("Sentiment economico debole", "esi", lambda s: s < ESI_WEAK),
        ("Curva Bund invertita", "yield_curve", lambda s: s < CURVE_INVERSION),
    ],
    "Italia": [
        ("CLI OCSE in calo sotto 100", "cli", cli_downturn),
        ("Sentiment economico debole", "esi", lambda s: s < ESI_WEAK),
        ("Spread BTP-Bund alto", "btp_bund", lambda s: s >= BTP_BUND_STRESS),
    ],
    "UK": [
        ("CLI OCSE in calo sotto 100", "cli", cli_downturn),
        ("Curva gilt invertita", "yield_curve", lambda s: s < CURVE_INVERSION),
    ],
    "Giappone": [
        ("CLI OCSE in calo sotto 100", "cli", cli_downturn),
        ("Tankan in calo", "tankan", lambda s: s < s.shift(TANKAN_FALL_QUARTERS)),
        ("Curva JGB invertita", "yield_curve", lambda s: s < CURVE_INVERSION),
    ],
}


def leading_risk(area: str, series: dict[str, pd.Series]) -> dict | None:
    """Conta quanti indicatori anticipatori dell'area sono in stress. Serie mancanti o vuote = segnale spento.
    UK ha solo 2 segnali (niente ESI dopo la Brexit): "Alto" richiede entrambi."""
    if area not in SIGNALS:
        return None
    signals = {}
    for label, key, test in SIGNALS[area]:
        s = series.get(key)
        signals[label] = s is not None and not s.empty and bool(test(s).iloc[-1])
    score = sum(signals.values())
    level = "Alto" if score >= HIGH_RISK_MIN_SIGNALS else "Medio" if score == 1 else "Basso"
    return {"level": level, "score": score, "total": len(signals), "signals": signals}
