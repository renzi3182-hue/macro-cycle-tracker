# Mapping statico regime -> classi di asset storicamente favorite (stile All Weather).
# Non e' un consiglio di investimento personalizzato, non e' backtestato.
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
    "Reflazione": ["Azionario growth", "Obbligazioni lunga durata", "Credito corporate"],
    "Espansione": ["Azionario", "Materie prime", "Obbligazioni indicizzate all'inflazione", "Immobiliare"],
    "Stagflazione": ["Oro", "Materie prime", "Obbligazioni indicizzate all'inflazione", "Cash", "Azionario value/difensivo"],
    "Deflazione": ["Obbligazioni governative lunga durata", "Cash", "Azionario difensivo"],
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
