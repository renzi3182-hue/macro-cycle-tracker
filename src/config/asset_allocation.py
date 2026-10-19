# Mapping statico regime -> classi di asset storicamente favorite (stile All Weather).
# Non e' un consiglio di investimento personalizzato.
#
# Tabella riallineata il 03/10/2026 al backtest del regime di allora (direzione del CLI). Ricontrollata il
# 09/10/2026 sulla regola attuale del regime (scripts/backtest_assets.py, USA 1960-2026, regime point-in-time,
# rendimento del mese successivo): resta una sola differenza significativa (|t| > 2), materie prime peggiori in
# Stagflazione (-2.8%/anno, t = -2.2), gia' escluse. Spariti i vantaggi di prima (Treasury in Stagflazione,
# materie prime in Goldilocks). Unica stonatura: in Reflazione l'azionario e' l'ultimo dei 5 asset (4.5%/anno,
# t = -1.8, non significativo); resta in tabella perche' lo indicano il libro di riferimento e la teoria. Il cash rende di piu'
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

from src.classify.assess import label_regimes

ASSET_ALLOCATION = {
    "Goldilocks": ["Azionario growth", "Materie prime", "Credito corporate"],
    "Reflazione": ["Azionario", "Oro", "Materie prime", "Obbligazioni indicizzate all'inflazione"],
    "Stagflazione": ["Obbligazioni governative medio termine", "Obbligazioni indicizzate all'inflazione", "Oro", "Cash",
                     "Azionario value/difensivo"],
    "Deflazione": ["Azionario difensivo", "Oro", "Obbligazioni governative lunga durata"],
}

# Fase del ciclo -> (asset da pesare di piu', asset da pesare di meno), dal libro di riferimento (cap. 6: fig. 6.12,
# 6.14, 6.16 e settori difensivi/ciclici). "{paese}" = azionario o titoli di Stato dell'area.
# Verifica 13/10/2026 sui dati USA (fase point-in-time di src/classify/assess.py, rendimento del mese dopo
# annualizzato; azionario e materie prime dal 1985, oro dal 2000, Treasury 10Y dal 1962):
#   Espansione:    materie prime 11,7%, azionario 10,7%, Treasury 2,8% (t = -2,5, l'unica differenza significativa)
#   Ripresa:       materie prime 13,7%, azionario 9,5%, oro 7,5%, Treasury 5,1%
#   Rallentamento: oro 18,6% (t = 1,8), azionario 12,1%, Treasury 6,8%, materie prime 0,1%
#   Recessione:    Treasury 14,3% (t = 1,9), oro 8,5%, azionario -3,2%, materie prime -14,6% (solo 31-67 mesi)
# Direzioni coerenti col libro, ma come la tabella per regime nessun vantaggio dimostrato.
PHASE_ASSETS = {
    "Espansione": (["Azionario {paese}", "Materie prime"], ["Titoli di Stato {paese}"]),
    "Ripresa (sotto trend)": (["Azionario ciclico {paese}", "Materie prime"], ["Titoli di Stato {paese}"]),
    "Rallentamento": (["Oro", "Azionario difensivo {paese}"], ["Materie prime"]),
    "Recessione": (["Titoli di Stato {paese}", "Oro"], ["Azionario {paese}", "Materie prime"]),
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
    """Media equipesata dei portafogli-per-regime di ogni nazione/area. Valori = etichette di regime: un'area
    "Incerto: X / Y" (src/classify/assess.py) pesa meta' il portafoglio di X e meta' quello di Y."""
    n = len(regimes_by_area) or 1
    combined: dict = {}
    for label in regimes_by_area.values():
        regimes = label_regimes(label)
        for regime in regimes:
            for asset, weight in portfolio_weights(regime, risk_profile).items():
                combined[asset] = combined.get(asset, 0.0) + weight / n / len(regimes)
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

# Portafogli pigri (15/10/2026): pesi fissi da confrontare con e senza filtro di tendenza nella pagina Portafoglio.
# Ogni classe usa l'ETF dello stress test (src/classify/stress.py), quindi sono approssimazioni: nel Golden Butterfly
# small cap value e Treasury brevi diventano azionario (SPY) e cash (SHY).
LAZY_PORTFOLIOS = {
    "60/40": {"Azionario": 60.0, "Obbligazioni medio termine": 40.0},
    "Permanent": {"Azionario": 25.0, "Obbligazioni governative lunga durata": 25.0, "Oro": 25.0, "Cash": 25.0},
    "Golden Butterfly": {"Azionario": 40.0, "Obbligazioni governative lunga durata": 20.0, "Oro": 20.0, "Cash": 20.0},
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


# Conferma dei mercati (12/10/2026), la versione dichiarata della % dell'app di riferimento: quanti asset tipici del regime
# dell'area sono in tendenza positiva. Azionario con l'ETF del paese dove c'e' (Canada e Australia non ne hanno,
# l'azionario resta fuori), il resto con TREND_PROXY (ETF quotati in USA). Verifica 2004-2026 su 9 aree
# (scripts/evaluate_model.py, sezione Conferma dei mercati): NON dice se la lettura macro e' giusta. Con conferma
# alta (almeno 2/3 degli asset in salita) il regime del momento coincide con quello a dati completi nel 49% dei
# mesi, con conferma bassa (al massimo 1/3) nel 51%; resta uguale 3 mesi dopo nel 42% contro il 39%.
# Si mostra come descrizione, non come affidabilita'.
AREA_EQUITY = {"USA": "SPY", "Eurozona": "EZU", "Italia": "EWI", "UK": "EWU", "Giappone": "EWJ", "Cina": "EEM", "India": "EEM"}


def confirmation(regime: str, above: dict[str, bool], equity: str | None) -> list[tuple[str, str, bool]]:
    """(asset, ticker, in salita) per gli asset tipici del regime con un ETF e un dato di tendenza."""
    out = []
    for asset in ASSET_ALLOCATION.get(regime, []):
        ticker = equity if "Azionario" in asset else TREND_PROXY.get(asset)
        if ticker in above:
            out.append((asset, ticker, above[ticker]))
    return out


def apply_trend(weights: dict, above: dict[str, bool]) -> dict:
    """Sposta in cash il peso degli asset il cui ETF e' sotto la media (above[ticker] False). Ticker senza dato: invariato."""
    out = {}
    for asset, w in weights.items():
        keep = above.get(TREND_PROXY.get(asset), True)
        key = asset if keep else CASH
        out[key] = out.get(key, 0.0) + w
    return out
