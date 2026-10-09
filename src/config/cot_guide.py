# Guida al COT report (Commitments of Traders, CFTC): testi della sezione COT dell'app.
# Lettura classica: le posizioni estreme degli speculatori (percentile >= 90 o <= 10 sui 5 anni) segnalano un
# mercato "affollato", vulnerabile a una ricopertura nella direzione opposta. E' un segnale di contesto, non di
# timing: un mercato può restare affollato per mesi. Nel backtest valute (scripts/backtest_currency.py) il COT
# non ha migliorato la previsione a 6-12 mesi: per questo ha peso 0 nel punteggio delle valute.
from src.classify.positioning import CROWDED_PERCENTILE, WASHED_OUT_PERCENTILE

GROUP_INFO = {
    "Dealer": ("Banche e intermediari che fanno mercato.",
               "Stanno quasi sempre dal lato opposto dei clienti: la loro posizione è copertura, non un'opinione."),
    "Asset manager": ("Fondi pensione, assicurazioni, fondi comuni ed ETF.",
                      "Denaro lento e di lungo periodo: un cambio di direzione persistente conta più del livello."),
    "Hedge fund": ("Fondi speculativi e CTA (leveraged funds / managed money).",
                   "Denaro veloce che segue il trend: agli estremi è il gruppo più esposto a ricoperture improvvise."),
    "Altri grandi": ("Altri trader sopra la soglia di segnalazione (tesorerie aziendali, family office).",
                     "Gruppo eterogeneo, di solito poco informativo da solo."),
    "Piccoli": ("Trader sotto la soglia di segnalazione, in buona parte retail.",
                "Posizioni estreme dei piccoli sono storicamente un segnale contrarian debole."),
    "Produttori": ("Chi produce o usa fisicamente la materia prima (miniere, raffinerie, compagnie aeree).",
                   "Coprono la produzione futura: vendono di più quando i prezzi salgono. Il loro short è normale."),
    "Swap dealer": ("Banche che vendono swap e indici su materie prime ai clienti.",
                    "Coprono i prodotti venduti a fondi indicizzati: posizione in gran parte meccanica."),
}

MARKET_INFO = {
    "S&P 500": ("Future sull'indice azionario USA.",
                "Hedge fund molto long: rally maturo, rischio di vendite forzate su uno shock. Molto short: carburante "
                "per rialzi violenti (short squeeze). Gli asset manager sono strutturalmente long."),
    "Nasdaq 100": ("Future sui 100 maggiori titoli tecnologici non finanziari USA.",
                   "Come l'S&P 500 ma più sensibile ai tassi e al sentiment: gli estremi durano meno."),
    "Treasury 10Y": ("Future sul Treasury decennale USA.",
                     "Gli hedge fund sono strutturalmente short per il basis trade (comprano il titolo, vendono il "
                     "future): uno short record non è una scommessa sui tassi ma un rischio di liquidità se si chiude."),
    "Oro": ("Future COMEX sull'oro.",
            "Managed money molto long: rally già affollato, vulnerabile a dollaro forte o tassi reali in salita. "
            "Molto short o vicino a zero: posizionamento pulito, spesso vicino ai minimi."),
    "Petrolio WTI": ("Future NYMEX sul greggio WTI.",
                     "Managed money agli estremi anticipa spesso inversioni di breve. Produttori meno short del solito: "
                     "si aspettano prezzi più alti e coprono meno."),
    "Euro": ("Future sul cambio EUR/USD (Chicago).",
             "Speculatori molto long euro = molto short dollaro: rischio di rimbalzo del dollaro su dati USA forti."),
    "Yen": ("Future sul cambio JPY/USD.",
            "Lo yen è la valuta del carry trade: speculatori molto short yen = carry affollato, che si chiude di colpo "
            "nelle fasi risk-off (es. agosto 2024) con forte apprezzamento dello yen."),
    "Sterlina": ("Future sul cambio GBP/USD.",
                 "Estremi spesso legati a sorprese della Bank of England; mercato più piccolo, estremi più rumorosi."),
    "Dollaro (DXY)": ("Future sull'indice del dollaro contro 6 valute (ICE).",
                      "Mercato sottile: meglio leggere il dollaro dal contrario di euro e yen."),
}


def crowding(pct: float) -> tuple[str, str]:
    """(etichetta, colore badge) dal percentile sui 5 anni."""
    if pct >= CROWDED_PERCENTILE:
        return "Affollato long", "red"
    if pct <= WASHED_OUT_PERCENTILE:
        return "Affollato short", "blue"
    if pct >= 70:
        return "Più long del solito", "orange"
    if pct <= 30:
        return "Più short del solito", "violet"
    return "Neutro", "gray"


def implication(market: str, pct: float, weekly_change: float) -> str:
    """Una frase su cosa implica oggi il posizionamento degli speculatori in quel mercato."""
    label, _ = crowding(pct)
    trend = "in aumento" if weekly_change > 0.5 else "in calo" if weekly_change < -0.5 else "stabile"
    if label == "Affollato long":
        core = "speculatori long come raramente negli ultimi 5 anni: il rialzo è già molto posizionato, una notizia negativa può innescare vendite a catena."
    elif label == "Affollato short":
        core = "speculatori short come raramente negli ultimi 5 anni: basta una sorpresa positiva per una ricopertura veloce (short squeeze)."
    elif label == "Neutro":
        core = "posizionamento nella norma: il COT non aggiunge informazione, conta il resto del quadro."
    else:
        core = f"{label.lower()}, senza estremi: posizionamento da tenere d'occhio se si avvicina al 90/10."
    return f"{market}: {core} Esposizione netta {trend} nell'ultima settimana."
