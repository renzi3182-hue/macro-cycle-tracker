# Mapping statico regime -> classi di asset storicamente favorite (stile All Weather).
# Non e' un consiglio di investimento personalizzato.
#
# Tabella riallineata il 03/10/2026 al backtest del regime di allora (direzione del CLI). Ricontrollata il
# 09/10/2026 sulla regola Casario/Quantaste (scripts/backtest_assets.py, USA 1960-2026, regime point-in-time,
# rendimento del mese successivo): resta una sola differenza significativa (|t| > 2), materie prime peggiori in
# Stagflazione (-2.8%/anno, t = -2.2), gia' escluse. Spariti i vantaggi di prima (Treasury in Stagflazione,
# materie prime in Goldilocks). Unica stonatura: in Reflazione l'azionario e' l'ultimo dei 5 asset (4.5%/anno,
# t = -1.8, non significativo); resta in tabella perche' lo indicano Casario e la teoria. Il cash rende di piu'
# con inflazione alta solo per il livello dei tassi.
# Portafoglio per regime 2000-2026 (profilo Medio): 8.5%/anno contro 5.5% dell'All Weather statico, ma la
# tabella e' stata scelta guardando questi dati: e' un'opinione guidata dai dati, non un vantaggio dimostrato.
#
# Fonti (ricerca 28/09/2026): Bridgewater All Weather, Merrill Lynch Investment
# Clock (Greetham, 2004), letteratura su correlazione azioni-obbligazioni.
#
# Nota 1: la correlazione azioni-obbligazioni NON e' sempre negativa - diventa
# positiva quando l'inflazione sale sopra ~2% (es. 2022, corr. arrivata a +0.52).
# Le obbligazioni nominali perdono quindi la funzione di copertura quando l'inflazione
# accelera (2022). In Stagflazione si usano scadenze medie (rischio tasso minore)
# affiancate da indicizzate e cash, non obbligazioni nominali a lunga durata.
# Nota 2: l'oro ha correlazione storica diretta con l'inflazione debole (~0.07),
# ma resta utile come diversificatore (bassa corr. con azionario/obbligazionario)
# e hedge in crisi/geopolitica (2008, 2020) - per questo compare in Stagflazione.

ASSET_ALLOCATION = {
    "Goldilocks": ["Azionario growth", "Materie prime", "Credito corporate"],
    "Reflazione": ["Azionario", "Oro", "Materie prime", "Obbligazioni indicizzate all'inflazione"],
    "Stagflazione": ["Obbligazioni governative medio termine", "Obbligazioni indicizzate all'inflazione", "Oro", "Cash",
                     "Azionario value/difensivo"],
    "Deflazione": ["Azionario difensivo", "Oro", "Obbligazioni governative lunga durata"],
}

# Quota target sull'azionario per profilo di rischio, il resto va agli asset
# difensivi/diversificatori della allocazione del regime.
RISK_PROFILE_EQUITY_SHARE = {"Basso": 0.3, "Medio": 0.5, "Alto": 0.7}


def portfolio_weights(regime: str, risk_profile: str) -> dict:
    """Pesi % per asset class di un singolo regime, tarati sul profilo di rischio.

    Split binario azionario/difensivo con pesi equamente distribuiti dentro
    ogni bucket: approssimazione grezza, non backtestata.
    """
    assets = ASSET_ALLOCATION.get(regime, [])
    equity = [a for a in assets if "Azionario" in a]
    defensive = [a for a in assets if a not in equity]
    equity_share = RISK_PROFILE_EQUITY_SHARE[risk_profile]

    weights = {}
    if equity:
        each = equity_share / len(equity)
        weights.update({a: each for a in equity})
    if defensive:
        each = (1 - equity_share) / len(defensive)
        weights.update({a: each for a in defensive})

    total = sum(weights.values()) or 1.0
    return {k: v / total * 100 for k, v in weights.items()}


def combined_portfolio_weights(regimes_by_area: dict, risk_profile: str) -> dict:
    """Media equipesata dei portafogli-per-regime di ogni nazione/area."""
    n = len(regimes_by_area) or 1
    combined: dict = {}
    for regime in regimes_by_area.values():
        for asset, weight in portfolio_weights(regime, risk_profile).items():
            combined[asset] = combined.get(asset, 0.0) + weight / n
    return combined


# All Weather (Dalio, versione divulgata in "Money: Master the Game", Robbins 2014):
# pesi statici, NON dipendono dal regime ne' dal profilo di rischio. Approssimazione
# pubblica, non il portafoglio effettivo di Bridgewater (che usa leva e risk parity).
ALL_WEATHER_WEIGHTS = {
    "Azionario": 30.0,
    "Obbligazioni governative lunga durata": 40.0,
    "Obbligazioni medio termine": 15.0,
    "Oro": 7.5,
    "Materie prime": 7.5,
}


# Filtro di tendenza (scripts/backtest_assets.py, 06/10/2026): un asset sotto la sua media a 10 mesi va in cash.
# 2000-2026 su 4 portafogli: drawdown massimo -55/75%, rendimento -0,1/0,9 punti l'anno. Riduce il rischio, non
# aggiunge rendimento. ETF di riferimento fra quelli del punteggio asset (src/classify/score.py); tutto
# l'azionario usa SPY come nel backtest. Senza ETF (credito, cash) il peso resta com'e'.
TREND_PROXY = {
    "Azionario": "SPY", "Azionario growth": "SPY", "Azionario difensivo": "SPY", "Azionario value/difensivo": "SPY",
    "Obbligazioni governative lunga durata": "TLT", "Obbligazioni governative medio termine": "IEF",
    "Obbligazioni medio termine": "IEF", "Obbligazioni indicizzate all'inflazione": "TIP",
    "Oro": "GLD", "Materie prime": "DBC",
}
CASH = "Cash"


def apply_trend(weights: dict, above: dict[str, bool]) -> dict:
    """Sposta in cash il peso degli asset il cui ETF e' sotto la media (above[ticker] False). Ticker senza dato: invariato."""
    out = {}
    for asset, w in weights.items():
        keep = above.get(TREND_PROXY.get(asset), True)
        key = asset if keep else CASH
        out[key] = out.get(key, 0.0) + w
    return out
