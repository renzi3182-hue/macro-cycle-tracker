"""Quanto fidarsi di ogni lettura dell'app (26/10/2026): un'etichetta per lettura, usata dai badge delle pagine
(src/ui/cards.reliability_html) e dalla tabella della pagina Metodo, cosi' non divergono. Le pagine principali
mostrano solo l'etichetta e una frase semplice; i numeri delle verifiche (t, IC, soglie, percentuali) stanno qui e
si leggono solo nella pagina Metodo.
- Verificato: vantaggio misurato su dati non usati per costruirlo (walk-forward o periodo tenuto da parte).
- Teoria: tabelle della teoria dei cicli e della letteratura, senza vantaggio dimostrato sui dati.
- Descrittivo: dice com'e' il momento, non prevede i rendimenti.
Ogni etichetta e' controllata contro spec.md e il commento del modulo indicato in `source`."""
from typing import NamedTuple

from src.classify.allocation import VERIFICA

KINDS = {  # etichetta -> (token colore di theme.py, cosa vuol dire)
    "Verificato": ("r-gold", "Ha dato un vantaggio su dati non usati per costruirlo."),
    "Teoria": ("r-defl", "Viene dalla teoria dei cicli e dalla letteratura: nessun vantaggio dimostrato sui dati."),
    "Descrittivo": ("muted", "Descrive il momento, non prevede i rendimenti."),
}


class Reading(NamedTuple):
    name: str
    kind: str
    plain: str  # frase per le pagine, senza numeri
    numbers: str  # verifica, solo nella pagina Metodo
    source: str  # dove sta la verifica


READINGS = {
    "trend": Reading(
        "Filtro di tendenza", "Verificato",
        "Nel passato ha ridotto molto le perdite nei crolli lunghi, al prezzo di un rendimento un po' più basso.",
        "Asset sotto la media a 10 mesi in liquidità. Backtest 2000-2026 su 4 portafogli: calo massimo ridotto del "
        "55-75% (60/40 da −31% a −13%), rendimento da 0,1 a 0,9 punti l'anno in meno. Aiuta nei crolli lunghi, nei "
        "rimbalzi veloci fa ricomprare tardi.",
        "scripts/backtest_assets.py, asset_allocation.py"),
    "ranking": Reading(
        "Classifica degli asset", "Verificato",
        "Stimata ogni mese solo sul passato: in alto chi ha più probabilità di battere la media nei 6 mesi dopo. "
        "Il vantaggio è piccolo e sta più nel ridurre le perdite.",
        "Walk-forward 1999-2026, 32 ETF, orizzonte 6 mesi: IC +0,119 (t 2,8), positivo prima e dopo il 2014. "
        "Migliori 5 ribilanciati ogni mese 13,3% l'anno con calo massimo −24% (S&P 500 11,2% e −51%, pesi uguali "
        "9,6% e −44%). Segnale attivo (entra sopra 80, esce sotto 60) 11,4% e −27%. Verde sopra 80, rosso fino a "
        "40. Taratura: quando la probabilità dice 55-60% l'asset ha battuto la media il 54% delle volte.",
        "scripts/evaluate_score.py, score.py"),
    "asset_classes": Reading(
        "Classi di asset nel paese (azioni, titoli di Stato, oro, liquidità)", "Verificato",
        "Ha superato anche il test finale sugli anni tenuti da parte: la classe in testa ha reso più delle altre.",
        "Quattro periodi di verifica 1995-2018 IC +0,21 (t 2,9); test finale 2019-2026, usato una volta: " + VERIFICA["Classi di asset"] + ".",
        "scripts/evaluate_allocation.py, allocation.py"),
    "regime_assets": Reading(
        "Asset tipici per regime", "Teoria",
        "Cosa tende ad andare bene con questa combinazione di crescita e inflazione, secondo la teoria dei cicli.",
        "Backtest USA 2000-2026, profilo Medio: 7,5% l'anno, volatilità 11,8%, calo massimo −35,7%; All Weather 5,5% "
        "e −16,8%; 60/40 5,6% e −30,7%. Nessuna differenza fra regimi significativa (|t| < 2 su azioni, Treasury, "
        "oro, materie prime). Non batte i portafogli statici.",
        "scripts/backtest_assets.py, asset_allocation.py"),
    "phase_assets": Reading(
        "Cosa pesare per fase del ciclo", "Teoria",
        "Più peso e meno peso per fase vengono dalla teoria dei cicli: tendenze storiche, non previsioni.",
        "Dati USA dal 1985 (oro dal 2000, Treasury dal 1962), fase letta come allora: le direzioni tornano, ma "
        "l'unica differenza netta è che i titoli di Stato rendono meno in Espansione (2,8% l'anno, t −2,5). Oro in "
        "Rallentamento 18,6% (t 1,8), Treasury in Recessione 14,3% (t 1,9).",
        "asset_allocation.py (PHASE_ASSETS)"),
    "map": Reading(
        "Mappa delle occasioni", "Descrittivo",
        "Mette insieme punteggio, teoria e tendenza: quando sono d'accordo non è andata meglio che col solo punteggio.",
        "Classe in testa al paese con freccia della teoria su e tendenza in salita contro classe in testa senza: "
        "periodi di verifica 1995-2018 +1,00% contro +0,02% a 6 mesi, differenza +0,85 punti (t 0,4); test finale "
        "2019-2026 +2,73% contro +2,96%. La classe più concorde è quasi sempre quella col punteggio più alto (99,8%). "
        "IC: concordanza poi punteggio +0,207 (t 2,5) contro +0,225 (t 2,9) del solo punteggio.",
        "scripts/evaluate_opportunities.py, opportunities.py"),
    "sector_regime": Reading(
        "Settori USA per regime", "Teoria",
        "Più peso e meno peso ai settori per il regime USA di oggi, dalla teoria dei cicli: tendenze attese, non previsioni.",
        "Regime USA come si leggeva allora, 1948-2026, settori French prima degli ETF: settori long meno short +0,2 punti "
        "l'anno (t 0,2); +1,4 fino al 1987, −1,0 dopo. Per regime: Stagflazione +3,2 (t 2,1), Goldilocks +0,6, "
        "Reflazione −0,2, Deflazione −2,5 (t −1,2). A 6 mesi +0,6 (t 0,5). Nessun vantaggio.",
        "scripts/backtest_sectors.py, sector_regime.py"),
    "regime": Reading(
        "Regime (crescita e inflazione)", "Descrittivo",
        "Dice come si muovono oggi crescita e inflazione: non prevede i rendimenti.",
        "Lettura del momento uguale a quella a dati completi nel 41-57% dei mesi (il PIL esce tardi e viene "
        "rivisto), 2,5-4,4 cambi l'anno. Riproduce 18 di 29 letture già documentate. Vicino a una soglia l'area è "
        "«Incerto». I portafogli per regime non battono quelli statici.",
        "scripts/evaluate_model.py, regime.py"),
    "phase": Reading(
        "Fase del ciclo", "Descrittivo",
        "Dice dove sta l'economia nel ciclo: non prevede i rendimenti.",
        "USA: tutti i mesi di recessione NBER in Rallentamento o Recessione, Recessione fuori dalle recessioni 1%. "
        "Fuori dagli USA, contro i rallentamenti OCSE, dal 48% (Australia) al 92% (India) dei mesi dentro. "
        "Recessione solo con conferma: regola di Sahm sopra 0,5 punti (USA con Chauvet-Piger) o PIL annuo negativo.",
        "scripts/evaluate_model.py, cycle.py, recession.py"),
    "quarter": Reading(
        "Stima a fine trimestre", "Descrittivo",
        "Stima del regime a dati completi: l'inflazione si prevede, la crescita no.",
        "Probabilità calibrate su 9 aree dal 2000: un 70% si è avverato circa 7 volte su 10. Inflazione prevista "
        "bene, accelerazione del PIL del trimestre quasi come una moneta. Più probabile mostrato solo con 8 punti "
        "di distacco dal secondo.",
        "scripts/evaluate_model.py, regime.py"),
    "leading": Reading(
        "Indicatori anticipatori", "Descrittivo",
        "Segnali di stress su curva, credito e fiducia: non cambiano regime né fase.",
        "Contro i rallentamenti OCSE: CLI in calo sotto 100 precisione 79-87% (base 57-61%), sentiment ESI sotto 95 "
        "63-66% (base 54-55%), spread BTP-Bund da 2 punti 75% (base 55%), calo del Tankan su 2 trimestri 78% (base "
        "60%). USA: curva invertita, spread Baa sopra 2,7 punti, NFCI sopra −0,2; rischio Alto con 2 segnali su 3. "
        "Non testati sui rendimenti.",
        "scripts/backtest_leading_intl.py, leading.py"),
    "risk": Reading(
        "Nervosismo dei mercati (Risk On/Off)", "Descrittivo",
        "Dice quanto può oscillare la borsa nel mese dopo, non se salirà.",
        "Sei misure a pesi uguali, ognuna 0-100 rispetto alla sua storia; fasce ogni 20 punti. 2012-2026: "
        "correlazione con la volatilità dei 21 giorni dopo −0,48 (−0,51 con cinque misure, che col rendimento "
        "avevano −0,17); sotto 20 l'S&P 500 ha "
        "oscillato al 29-30% annuo, sopra 60 all'11-13%. Canarino: momentum 13612W di TIP, in allarme sotto zero "
        "(2004-2026: calo dell'S&P 500 oltre il 10% entro 3 mesi nel 20% dei casi contro l'11%). Come segnale "
        "operativo il risultato dipende dalla variante.",
        "scripts/evaluate_risk.py, risk.py"),
    "confirmation": Reading(
        "Conferma dei mercati", "Descrittivo",
        "Dice se i mercati si muovono come il regime, non se il regime è giusto.",
        "2004-2026, 9 aree: con almeno 2 asset tipici su 3 in salita la lettura del momento è confermata a dati "
        "completi nel 49% dei mesi, con al massimo 1 su 3 nel 48%; resta uguale 3 mesi dopo nel 37% contro il 34%.",
        "scripts/evaluate_model.py, asset_allocation.py"),
    "countries": Reading(
        "Classifica dei paesi", "Descrittivo",
        "Ordina i paesi per i segnali di oggi: nel test finale non ha dato vantaggio.",
        "Test finale 2019-2026: " + VERIFICA["Paesi"] + ".",
        "scripts/evaluate_allocation.py, allocation.py"),
    "currencies": Reading(
        "Classifica delle valute", "Descrittivo",
        "Conta soprattutto il tasso d'interesse: ha funzionato fino al 2018, non dopo.",
        "Periodi di verifica 1995-2018 IC +0,26 (t 3,5), quasi tutto dal tasso; test finale 2019-2026: "
        + VERIFICA["Valute"] + ".",
        "scripts/evaluate_allocation.py, allocation.py"),
    "cot": Reading(
        "COT report", "Descrittivo",
        "Mostra chi è affollato su un mercato: contesto, non tempismo.",
        "Nella classifica delle valute il pilastro COT da solo ha IC +0,07 (t 0,6) nei periodi di verifica. "
        "Estremi: percentile sui 5 anni oltre 90 o sotto 10.",
        "allocation.py, cot_guide.py"),
    "rrg": Reading(
        "Rotazione (forza relativa)", "Descrittivo",
        "Mappa di chi guida e chi arretra contro l'S&P 500: chi è in testa non ha fatto meglio dopo.",
        "Settimanale 1996-2026, 27 ETF, a 13 settimane: in testa meno in coda −0,08 punti (t −0,2); in ingresso meno "
        "in raffreddamento −0,55 (t −1,1). Mensile sui settori 1999-2026: differenza t 0,5.",
        "scripts/evaluate_rrg.py, rrg.py"),
    "relations": Reading(
        "Relazioni fra mercati", "Descrittivo",
        "Dice se i mercati si muovono fra loro come di solito: non anticipa i rendimenti.",
        "Correlazione a 120 giorni contro la mediana di 5 anni; rotta = segno opposto (norma almeno ±0,2) o distanza "
        "oltre 0,5. 2000-2026: la fase dei mercati non distingue i rendimenti a 3 mesi (3 confronti su 70 a |t| 2).",
        "scripts/evaluate_intermarket.py, intermarket.py"),
}
