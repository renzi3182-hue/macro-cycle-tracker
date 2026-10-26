"""ETF quotati in USA usati dall'app -> un esempio di equivalente UCITS, che chi investe dall'Italia puo' comprare
(gli ETF USA non hanno il documento KID europeo e di solito non sono acquistabili dai privati in Italia). Solo nomi
d'esempio, non consigli: lo stesso indice e' spesso offerto da piu' emittenti.

Fonte: justETF, pagina di ogni fondo trovata per ISIN, verificato il 26/10/2026; nessun ISIN o ticker scritto a
memoria. Il ticker e' quello indicato da justETF (primario o della borsa indicata) e cambia da borsa a borsa: per
cercare il fondo vale l'ISIN. Dove justETF non mostra un equivalente chiaro la riga lo dice (ucits None per il
dollaro; per Italia, oro, materie prime, semiconduttori e immobiliare la nota spiega cosa cambia).
"""
from typing import NamedTuple

SOURCE = "justETF, verificato il 26/10/2026"


class Ucits(NamedTuple):
    name: str
    isin: str
    ticker: str | None  # come lo riporta justETF; None se justETF non lo indica chiaramente
    note: str  # "" = stesso indice dell'ETF USA


UCITS: dict[str, Ucits | None] = {
    # Azioni per paese
    "SPY": Ucits("iShares Core S&P 500 UCITS ETF USD (Acc)", "IE00B5BMR087", "CSSPX (Borsa Italiana)", ""),
    "EZU": Ucits("iShares Core MSCI EMU UCITS ETF EUR (Acc)", "IE00B53QG562", "CSEMU", ""),
    "EWI": Ucits("iShares FTSE MIB UCITS ETF (Acc)", "IE00B53L4X51", "CSMIB (Milano)",
                 "indice diverso: FTSE MIB, 40 titoli, al posto di MSCI Italy. Su justETF nessun MSCI Italy UCITS attivo "
                 "(Amundi liquidato, Lyxor con dati fermi)"),
    "EWU": Ucits("iShares MSCI UK UCITS ETF (Acc)", "IE00B539F030", "CSUK", ""),
    "EWJ": Ucits("iShares MSCI Japan UCITS ETF USD (Acc)", "IE00B53QDK08", "SXR5 (Xetra)", ""),
    "EEM": Ucits("iShares MSCI EM UCITS ETF (Dist)", "IE00B0M63177", "IQQE (Xetra)", ""),
    "EWC": Ucits("iShares MSCI Canada UCITS ETF (Acc)", "IE00B52SF786", "CCAU", ""),
    "EWA": Ucits("iShares MSCI Australia UCITS ETF", "IE00B5377D42", "IAUS (Londra, USD)", ""),
    "MCHI": Ucits("iShares MSCI China UCITS ETF USD (Acc)", "IE00BJ5JPG56", "ICHN", ""),
    "INDA": Ucits("iShares MSCI India UCITS ETF USD (Acc)", "IE00BZCQB185", "NDIA", ""),
    # Settori USA: stessa famiglia di indici Select Sector, versione con tetto 35/20
    "XLK": Ucits("State Street SPDR S&P U.S. Technology Select Sector UCITS ETF USD", "IE00BWBXM948", "ZPDT", ""),
    "XLF": Ucits("State Street SPDR S&P U.S. Financials Select Sector UCITS ETF USD", "IE00BWBXM500", "ZPDF", ""),
    "XLV": Ucits("State Street SPDR S&P U.S. Health Care Select Sector UCITS ETF USD", "IE00BWBXM617", "ZPDH", ""),
    "XLE": Ucits("State Street SPDR S&P U.S. Energy Select Sector UCITS ETF USD", "IE00BWBXM492", "ZPDE", ""),
    "XLI": Ucits("State Street SPDR S&P U.S. Industrials Select Sector UCITS ETF USD", "IE00BWBXM724", "ZPDI", ""),
    "XLY": Ucits("State Street SPDR S&P U.S. Consumer Discretionary Select Sector UCITS ETF USD", "IE00BWBXM278", "ZPDD", ""),
    "XLP": Ucits("State Street SPDR S&P U.S. Consumer Staples Select Sector UCITS ETF USD", "IE00BWBXM385", "SXLP (Borsa Italiana)", ""),
    "XLU": Ucits("State Street SPDR S&P U.S. Utilities Select Sector UCITS ETF USD", "IE00BWBXMB69", "SXLU (Borsa Italiana)", ""),
    "XLB": Ucits("State Street SPDR S&P U.S. Materials Select Sector UCITS ETF USD", "IE00BWBXM831", "SXLB", ""),
    "XLC": Ucits("State Street SPDR S&P U.S. Communication Services Select Sector UCITS ETF USD", "IE00BFWFPX50", "ZPDK", ""),
    "XLRE": Ucits("Invesco US Real Estate Sector UCITS ETF", "IE00BYM8JD58", "XRES",
                  "emittente diverso, indice S&P Select Sector Real Estate con tetto 20%, replica sintetica (swap)"),
    # Indici USA
    "QQQ": Ucits("Invesco EQQQ Nasdaq-100 UCITS ETF Acc", "IE00BFZXGZ54", "EQAC (Milano)", ""),
    "IWM": Ucits("State Street SPDR Russell 2000 U.S. Small Cap UCITS ETF USD", "IE00BJ38QD84", "ZPRR", ""),
    "IWF": Ucits("iShares Russell 1000 Growth UCITS ETF USD (Acc)", "IE000NITTFF2", "R1GR",
                 "versione con tetto 30/18 dello stesso indice"),
    "IWD": Ucits("iShares Russell 1000 Value UCITS ETF USD (Acc)", "IE0002EKOXU6", "R1VL",
                 "versione con tetto 30/18 dello stesso indice"),
    "SMH": Ucits("VanEck Semiconductor UCITS ETF", "IE00BMC38736", "SMH",
                 "indice simile: MarketVector US Listed Semiconductor 10% Capped Screened"),
    # Obbligazioni e liquidita'
    "TLT": Ucits("iShares USD Treasury Bond 20+yr UCITS ETF USD (Dist)", "IE00BSKRJZ44", "IS04 (Xetra)", ""),
    "IEF": Ucits("iShares USD Treasury Bond 7-10yr UCITS ETF (Acc)", "IE00B3VWN518", "SXRM (Xetra)", ""),
    "TIP": Ucits("iShares USD TIPS UCITS ETF USD (Acc)", "IE00B1FZSC47", "ITPS",
                 "titoli di Stato USA legati all'inflazione, indice Bloomberg US Government Inflation-Linked"),
    "SHY": Ucits("iShares USD Treasury Bond 1-3yr UCITS ETF (Dist)", "IE00B14X4S71", "IBTS", ""),
    "LQD": Ucits("iShares USD Corporate Bond UCITS ETF (Dist)", "IE0032895942", "LQDE", ""),
    "BIL": Ucits("State Street SPDR Bloomberg 1-3 Month T-Bill UCITS ETF USD Unhedged (Acc)", "IE00BJXRT698", None, ""),
    # Materie prime e valute
    "GLD": Ucits("iShares Physical Gold ETC", "IE00B4ND3602", "SGLN (Borsa Italiana)",
                 "non è un UCITS: in Europa l'oro fisico si compra con un ETC, stessa esposizione al prezzo dell'oro"),
    "DBC": Ucits("iShares Diversified Commodity Swap UCITS ETF", "IE00BDFL4P12", "ICOM",
                 "indice diverso: Bloomberg Commodity al posto del DBIQ Optimum Yield, replica sintetica"),
    "UUP": None,  # indice del dollaro: su justETF nessun UCITS che lo segua
}
NO_EQUIVALENT = {"UUP": "Nessun equivalente UCITS chiaro per l'indice del dollaro."}
