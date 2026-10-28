"""Settori USA per regime macro (26/10/2026): long e short dalle liste del libro di riferimento, cap. 7 (il libro
prevale: scelta dell'utente). Etichetta "Teoria" (src/config/reliability.py): nella Classifica una freccia su o giu'
accanto ai settori USA secondo il regime USA di oggi. I settori non citati per un regime restano neutri.

Incoerenza del libro, segnalata e non risolta qui: in Stagflazione mette le "difensive" sia fra i long sia fra gli
short. Valgono le liste per settore (long utilities, energia, tecnologia, industriali, prima necessita'; short
finanziari, materiali, discrezionali, immobiliare, comunicazioni).

Verifica point-in-time in scripts/backtest_sectors.py (regime USA come si leggeva allora, settori French dal 1926 prima
degli ETF): esito nel commento sotto la tabella.
"""
# ETF SPDR dei settori (src/classify/score.UNIVERSE, gruppo "Settori USA")
SECTOR_NAMES = {"XLK": "tecnologia", "XLY": "discrezionali", "XLB": "materiali", "XLI": "industriali",
                "XLC": "comunicazioni", "XLRE": "immobiliare", "XLU": "utilities", "XLP": "prima necessità",
                "XLF": "finanziari", "XLE": "energia", "XLV": "salute"}

SECTOR_REGIME = {  # regime -> (long, short)
    "Goldilocks": (["XLK", "XLY", "XLB", "XLI", "XLC", "XLRE"], ["XLU", "XLP", "XLF", "XLE"]),
    "Reflazione": (["XLK", "XLY", "XLB", "XLI", "XLE", "XLF"], ["XLU", "XLP", "XLV"]),
    "Stagflazione": (["XLU", "XLE", "XLK", "XLI", "XLP"], ["XLF", "XLB", "XLY", "XLRE", "XLC"]),
    "Deflazione": (["XLP", "XLU", "XLRE", "XLV", "XLC"], ["XLE", "XLK", "XLI", "XLF", "XLB"]),
}
# Verifica (scripts/backtest_sectors.py, 26/10/2026, regime USA point-in-time 1948-08 -> 2026-08, 937 mesi, rendimento
# del mese dopo, pesi uguali, niente costi; regola decisa prima: t >= 2 e positivo nelle due meta'): NESSUN VANTAGGIO.
#   Long meno short +0,2 punti l'anno (t 0,2, positivo il 49% dei mesi); fino al 1987-08 +1,4 (t 1,4), dopo -1,0
#   (t -0,6), dal 2000 -0,7 (t -0,3). Long meno tutti i settori -0,1 (t -0,2), short meno tutti -0,3 (t -0,6).
#   Per regime: Goldilocks +0,6 (t 0,3), Reflazione -0,2 (t -0,1), Stagflazione +3,2 (t 2,1), Deflazione -2,5 (t -1,2):
#   un regime su quattro a t 2 e' quanto ci si aspetta dal caso con quattro prove.
#   Portafogli: long 11,7% l'anno (calo massimo -44%), short 11,4% (-57%), tutti i settori 11,9% (-49%).
#   A 6 mesi: +0,6 punti l'anno (t 0,5), +0,2 e +0,9 nelle due meta'.
# Resta "Teoria": le frecce dicono cosa prevede il libro, non un vantaggio misurato.
SPREAD_BY_REGIME = {"Goldilocks": 0.6, "Reflazione": -0.2, "Stagflazione": 3.2, "Deflazione": -2.5}  # long meno short,
# punti l'anno, dalla verifica qui sopra: riga "com'e' andata" della card Settori per regime

# Versione debole e forte (cap. 7, fig. 7.16-7.17 e 7.19-7.20): il libro le da' solo per questi due regimi; l'intensita'
# di oggi sta nella card Liquidita' e Fed (src/classify/liquidity.py)
INTENSITY_NOTES = {
    "Stagflazione": "Debole (PIL che rallenta di poco, inflazione non preoccupante): negativi solo finanziari e salute, "
                    "bene energia, materiali, tecnologia, utilities. Forte (PIL in calo netto, inflazione sopra il 2%): "
                    "tutto negativo tranne le utilities.",
    "Deflazione": "Debole (PIL che si contrae di poco, inflazione vicino al 2%, politica meno rigida): tutti positivi, in "
                  "testa salute, utilities, prima necessità e immobiliare. Media: positivi solo prima necessità, salute e "
                  "utilities, energia e immobiliare i peggiori.",
}


def sector_arrows(regime: str | None) -> dict[str, int]:
    """Ticker -> +1 (long, piu' peso) o -1 (short, meno peso) per il regime; vuoto per un regime sconosciuto."""
    long, short = SECTOR_REGIME.get(regime, ([], []))
    return {**{t: 1 for t in long}, **{t: -1 for t in short}}
