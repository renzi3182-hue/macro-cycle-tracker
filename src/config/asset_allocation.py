# Mapping statico regime -> classi di asset storicamente favorite (stile All Weather).
# Non e' un consiglio di investimento personalizzato.
#
# Nomi dei regimi rinominati il 30/09/2026 (Goldilocks = ex Reflazione, Reflazione = ex Espansione, come
# Hedgeye/mercato); il backtest sotto e' stato fatto con la logica e i nomi vecchi.
# Backtest USA (scripts/backtest_assets.py, 29/09/2026, regime point-in-time, mese successivo):
# nessuna differenza di rendimento fra regimi e' statisticamente significativa per azioni, Treasury
# e oro (|t| < 2); solo il cash (livello dei tassi) e, al limite, le materie prime (meglio in
# Deflazione, t = 2.0, contrario alla tabella). Portafoglio per regime 2000-2026 (profilo Medio):
# 5.2%/anno, vol 9.9%, drawdown -26% con PIL rivisto; 6.0%, 9.3%, -19% con PIL real-time ALFRED.
# All Weather statico: 4.9%, 6.4%, -14%; pesi uguali: 5.5%, 7.7%, -19%. Rischio/rendimento simile
# o peggiore dei portafogli statici: la tabella e' un'opinione ragionata, non un vantaggio dimostrato.
#
# Fonti (ricerca 28/09/2026): Bridgewater All Weather, Merrill Lynch Investment
# Clock (Greetham, 2004), letteratura su correlazione azioni-obbligazioni.
#
# Nota 1: la correlazione azioni-obbligazioni NON e' sempre negativa - diventa
# positiva quando l'inflazione sale sopra ~2% (es. 2022, corr. arrivata a +0.52).
# Le obbligazioni nominali perdono quindi la funzione di copertura proprio in
# Stagflazione. Per questo qui si usano obbligazioni indicizzate all'inflazione
# e cash in quello scenario, non obbligazioni nominali a lunga durata.
# Nota 2: l'oro ha correlazione storica diretta con l'inflazione debole (~0.07),
# ma resta utile come diversificatore (bassa corr. con azionario/obbligazionario)
# e hedge in crisi/geopolitica (2008, 2020) - per questo compare in Stagflazione.

ASSET_ALLOCATION = {
    "Goldilocks": ["Azionario growth", "Obbligazioni lunga durata", "Credito corporate"],
    "Reflazione": ["Azionario", "Materie prime", "Obbligazioni indicizzate all'inflazione", "Immobiliare"],
    "Stagflazione": ["Oro", "Materie prime", "Obbligazioni indicizzate all'inflazione", "Cash", "Azionario value/difensivo"],
    "Deflazione": ["Obbligazioni governative lunga durata", "Cash", "Azionario difensivo"],
    # Almeno un asse laterale: nessuna scommessa direzionale, mix diversificato stile All Weather.
    "Transizione": ["Azionario", "Obbligazioni governative lunga durata", "Oro", "Materie prime", "Cash"],
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
