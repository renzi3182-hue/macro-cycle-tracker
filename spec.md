# Spec: Dashboard cicli economici e regimi macro (from intent [[001-macro-cycle-dashboard]], 2026-09-27)

Piano di build: [[plan]] · comandi e convenzioni: [[CLAUDE]] · setup e fonti: [[README]].

## Requirements

### Aree geografiche v1
USA, Eurozona (aggregato + Italia), UK, Giappone. Dal 09/10/2026 anche Canada, Cina, Australia, India (PIL, CPI e produzione industriale dall'OCSE, disoccupazione OCSE via FRED per Canada e Australia): le stesse aree della dashboard Quantaste, piu' l'India.

### Output della dashboard
1. **Regime macro** per ogni area: Espansione, Deflazione, Reflazione, Stagflazione.
2. **Fase ciclo economico** per ogni area: Espansione, Rallentamento, Recessione, Ripresa (sotto trend).
3. **Asset allocation suggerita** per il regime macro attivo (tabella statica). Dal 12/10/2026 la pagina Aree mostra quali asset tipici sono in tendenza positiva ("Conferma mercati", `asset_allocation.confirmation`, azionario con l'ETF del paese): descrittiva, perché non dice se il regime è giusto (verifica in `scripts/evaluate_model.py`, numeri nel commento accanto a `AREA_EQUITY`).
4. **Grafici storici** degli indicatori usati per la classificazione (crescita, inflazione).
5. **Badge/banner di cambio regime**: evidenzia se l'ultimo aggiornamento ha fatto cambiare regime o fase rispetto al giro precedente.

### v2 — Sentiment e Risk On/Off (da modello Quantaste, fonte: libro "Investire nel breve e lungo termine" di Marco Casario)
6. **Smart Quant Sentiment**: score 0-100 (Sell/Hold/Buy) su sentiment di mercato quantitativo.
7. **Risk On/Off**: score 0-100 (propensione al rischio: Ext. Risk Off → Neutral → Ext. Risk On), con split suggerito Risk assets/Difensivo/Cash.
   **Implementato 06/10/2026** (`src/classify/risk.py`, Panoramica): VIX, spread Baa-10Y e quota di ETF sopra la media a 10 mesi, a pesi uguali. Verificato (`scripts/evaluate_risk.py`): anticipa la volatilità, non il rendimento, quindi niente split suggerito Risk assets/Difensivo/Cash.
   **Giornaliero dal 12/10/2026**: aggiunte struttura del VIX (VIX / VIX a 3 mesi) e consumi (XLY/XLP), prese dal Risk On/Off di Quantaste; il canarino TIP (momentum 13612W) è mostrato a parte, fuori dal punteggio. Numeri della verifica nel commento in cima a `risk.py`.

Metodologia esatta (indicatori di input, pesi, soglie) da definire dopo aver ricevuto dal libro i capitoli su sentiment quant e risk on/off — non a tavolino. Finché non definita, questi due punti restano requisiti aperti, non implementati.

**Ricerca preliminare (28/09/2026)**: indicatori "risk on/off" tipici in letteratura (NBER, KC Fed) combinano VIX (volatilità equity), credit spread high-yield, e mosse FX/oro come safe-haven. Utile: FRED (fonte già usata per USA) pubblica sia `VIXCLS` (CBOE VIX) sia `BAMLH0A0HYM2` (spread high-yield ICE BofA) gratis, senza bisogno di nuovi fetcher/fonti. Metodologia "Smart Quant Sentiment" (score Sell/Hold/Buy) ancora da definire, in attesa del libro.

### Idea aperta v3 — rotazione settoriale per fase ciclo
Fidelity ("Business Cycle Approach to Equity Sector Investing") mappa 4 fasi cicliche a settori azionari favoriti (early-cycle: consumer discretionary/industrials/tech; late-cycle: difensivi come health care/consumer staples/utilities). Ricerca solo parziale (mid-cycle e recessione non ancora verificati con fonte primaria) — non implementato, da approfondire se si vuole granularità settoriale oltre le 4 classi di asset attuali.
**06/10/2026**: aggiunta la rotazione settori USA (RRG mensile, `src/classify/rrg.py`, pagina Classifica) come mappa descrittiva: verificata con `scripts/evaluate_rrg.py`, il quadrante non prevede l'extra-rendimento. Mappa fase → settori Fidelity ancora non implementata.
**12/10/2026**: rotazione settimanale su tutti i gruppi della Classifica (paesi, settori, indici, obbligazioni, materie prime) contro l'S&P 500, con le etichette in ingresso / in testa / in raffreddamento / in coda. Anche la settimanale non prevede l'extra-rendimento: resta una mappa descrittiva.

### v4 — Intermarket (11/10/2026, capitolo 5 del libro di Casario, su John Murphy)
Pagina Intermarket (gruppo Mercati), logica in `src/classify/intermarket.py`. Per Casario è un controllo: i mercati devono confermare lo scenario macro.
- **Dati**: chiusure giornaliere degli ultimi 10 anni nell'area di cache `Intermarket`: tutti i 28 ETF della Classifica e il rame (Yahoo, HG=F); da FRED rendimento 10 anni (DGS10), tasso reale 10 anni (DFII10), dollaro broad (DTWEXBGS), WTI. Aggiunti alla Classifica XLC, XLRE, QQQ, IWM, IWF, IWD, SMH (tenuti: l'IC totale non peggiora, quello prima del 2014 sì; una sola variante provata).
- **Matrice delle correlazioni**: 15/30/90/120 giorni contro S&P 500 e dollaro, con la norma (mediana della correlazione a 120 giorni degli ultimi 5 anni). Fuori dalla norma = segno opposto (solo se la norma è almeno ±0,2) o distanza oltre 0,5.
- **Quattro relazioni del libro**: obbligazioni/materie prime, dollaro/materie prime, oro/tasso reale, rame-oro/rendimento 10 anni. Stato: come da libro, più debole del solito, rotta (segno opposto a quello del libro). Rame/oro: divergenza se la direzione a 3 mesi è opposta a quella del rendimento.
- **Fase di Murphy 1-6** da TLT, SPY, DBC contro la media a 10 mesi a mese chiuso; le altre due combinazioni sono "Fase non definita".
- **Allineamento** fra fase del ciclo USA, fase di Murphy e rame/oro (mappa in `MACRO_TO_MURPHY` e `COPPER_GOLD_UP`): Allineati, Parzialmente allineati, Disallineati; da disallineati il messaggio del libro (ridurre il rischio, solo vantaggio statistico, strumenti meno volatili).
- **Cosa ha funzionato storicamente**: mesi con lo stesso regime USA point-in-time e la stessa fase di Murphy, extra-rendimento a 3 mesi come nella Classifica (`score.forward_excess`). In evidenza i primi 3 per asset class e per settori solo con almeno 30 casi e t sopra 2 (solo positivo: un t negativo dice cosa evitare); altrimenti "Nessun vantaggio statistico in questa situazione". Due in evidenza con correlazione a 120 giorni sopra 0,7: rischio doppio, scegli uno o dimezza la size (link a Size Monte Carlo).
- **Verifica** (`scripts/evaluate_intermarket.py`, 2000-2026, serie lunghe al posto degli ETF, fase uguale a quella degli ETF nel 79% dei mesi): la fase di Murphy non distingue i rendimenti a 3 mesi di azioni, Treasury, materie prime, oro e cash (3 confronti su 70 a |t| 2, tutti con 7-10 casi); l'allineamento non anticipa i cali dell'S&P 500 oltre il 10% entro 6 mesi (allineati 25%, parziali 24%, disallineati 31%, tutti i mesi 26%). La pagina lo dice: descrizione del momento, non segnale. Una variante per scelta: |norma| ≥ 0,2, orizzonte del drawdown 6 mesi.

### Aree: fase del ciclo sull'onda (11/10/2026)
Nella card Storico il regime resta un quadratino per mese; la fase del ciclo è un punto sull'onda (un periodo di sinusoide come nel logo: Espansione sale al picco, Rallentamento scende, Recessione tocca il fondo, Ripresa risale verso il trend). I quadratini colorati della fase si confondevano con quelli del regime. Il punto sta al centro del quarto della fase: la posizione dentro la fase non è stimata.

### Aggiornamento dati
Automatico. Prima versione: Windows Task Scheduler una volta al giorno. Dal 30/09/2026 un workflow GitHub Actions ogni 30 minuti nei giorni feriali (una volta nel weekend) aggiorna la cache e la pubblica come release `data-latest`; l'app pubblicata (https://macrocycletracker.streamlit.app/) la scarica all'avvio. La dashboard legge sempre dalla cache, mai dalle API in diretta.

## Design

### Stack
- Python. Dashboard con **Streamlit** (nessun frontend separato da costruire, legge dati locali, adatto a uso personale).
- Cache dati locale in **SQLite** (`data/cache.db`), popolata dallo script di update. La dashboard non chiama mai le API esterne direttamente.
- Scheduling: **GitHub Actions** (`.github/workflows/update-data.yml`) chiama `python -m src.scheduler.update_data`; in locale si può usare Windows Task Scheduler.

### Fonti dati per area
| Area | Fonte | Indicatori |
|---|---|---|
| USA | FRED API (serve API key gratuita) | PIL reale YoY, CPI YoY, PMI (proxy se disponibile su FRED) |
| Eurozona / Italia | ECB Statistical Data Warehouse + Eurostat | PIL reale YoY, HICP YoY |
| UK | Bank of England API | PIL reale YoY, CPI YoY |
| Giappone | e-Stat API (serve application ID gratuito) | PIL reale YoY, CPI YoY |
| Canada, Cina, Australia, India | OCSE SDMX; disoccupazione OCSE via FRED (Canada, Australia) | PIL reale YoY, CPI YoY (core per l'Australia), produzione industriale (Canada, India) |
| Tutte | OCSE SDMX (senza chiave) | Composite Leading Indicator (Eurozona = G4E) |
| Anticipatori | Eurostat, FRED/OCSE, Bank of Japan | ESI, curve 10Y-breve, spread BTP-Bund, Tankan |

Aggiornamento 29/09/2026: soglie degli anticipatori fuori USA verificate con `scripts/backtest_leading_intl.py`; con rischio "Alto" un'Espansione diventa Rallentamento in ogni area (prima solo USA). Backtest regime -> rendimenti (`scripts/backtest_assets.py`) e con dati real-time ALFRED (`scripts/backtest_alfred.py`): vedi i commenti in `src/config/asset_allocation.py` e [[#Areas of concern]].

### Logica di classificazione

Regime riscritto l'08/10/2026: trasparente, regolabile, no black box. Tutto mensile, un solo calcolo per scheduler e app (`src/classify/assess.py`). Costanti in cima a `regime.py`, `cycle.py`, `recession.py`.

**Regime macro** = velocità della crescita x pressione dell'inflazione, con la regola di Marco Casario usata da Quantaste (riferimento dell'utente):

| Crescita (PIL annuo vs trimestre prima) | Inflazione (media 3 mesi totale+core > 2,5%, oppure in salita sui 3 mesi prima) | Regime |
|---|---|---|
| in accelerazione | sotto controllo | Goldilocks |
| in accelerazione | alta o in salita | Reflazione |
| in rallentamento | alta o in salita | Stagflazione |
| in rallentamento | sotto controllo | Deflazione |

Nessuna banda né conferma: il PIL cambia una volta a trimestre. Senza PIL la crescita usa la direzione del CLI OCSE. La vicinanza a una soglia si mostra come "solidità" (Alta/Media/Bassa). **"Regime attuale" vs "Stima a fine trimestre"** (14/10/2026): sono due letture diverse, non una contraddizione. L'etichetta ("Regime attuale") viene dalla regola sopra sugli assi `growth_z`/`inflation_score`; quando uno dei due assi è vicino alla propria soglia (stessa soglia di "solidità", `CONFIDENCE_MEDIUM`) l'etichetta diventa "Incerto: X / Y" (regime attuale e regime se quell'asse flippasse, sempre nell'ordine Goldilocks, Reflazione, Stagflazione, Deflazione, cosi' la stessa coppia conta come un solo regime nel prevalente; quale dei due e' l'attuale lo dice la frase sotto il titolo dell'area) con colore neutro, invece di un nome secco. La card "Stima a fine trimestre" (sotto) usa le probabilità calibrate — un modello diverso, non ricalibrato per "spiegare" l'etichetta — e mostra un regime come "più probabile" solo se la differenza con il secondo è almeno 8 punti percentuali, altrimenti solo le barre senza nome secco.

**Probabilità** (09/10/2026, card "Stima a fine trimestre"): del regime del trimestre in corso a dati completi, calibrate con una logistica sulle 9 aree 2000-2026 (`scripts/evaluate_model.py`, sezione Calibrazione). Inflazione: indovinata l'88% dei mesi dal 2015. Crescita: l'ultimo PIL pubblicato non dice nulla sul trimestre dopo; la produzione industriale mensile (CLI dove manca) poco o niente (Brier 0,250 come il 50% fisso), quindi la parte crescita resta vicina al 50% — per questo può indicare un regime diverso dall'etichetta "Regime attuale": sono domande diverse (stato di oggi vs stima a fine trimestre), tenute volutamente separate in UI invece di forzarle a coincidere. Provato anche a usare la produzione industriale nell'etichetta del regime: media con il PIL 11/17 letture Quantaste e cambi di regime quasi doppi, prolungamento del PIL invariato (14/17). Scartato.

**Fase del ciclo**: momentum = direzione 3 mesi del CLI OCSE (isteresi, conferma 2 mesi), separato dall'asse crescita del regime dall'08/10/2026; livello = PIL annuo contro la sua media 10 anni (la disoccupazione contro la media 10 anni, usata fino al 03/10/2026, coincideva con la crescita sopra il trend a posteriori solo nel 42-57% dei mesi: in Europa e Giappone scende da anni per demografia); Recessione solo con conferma dura (Sahm, negli USA con Chauvet-Piger, fuori dagli USA per 2 mesi; oppure PIL annuo <= 0). Gli anticipatori (`leading.py`) si mostrano a parte e non cambiano la fase. Regime e fase possono quindi divergere (es. USA 10/2026: Stagflazione in fase di Ripresa (sotto trend)). "Ripresa" rinominato "Ripresa (sotto trend)" il 14/10/2026: il nome originale suggeriva un rimbalzo breve, ma la fase può durare anni (Eurozona/UK dal 2022).

**Media vs mediana vs esclusione 2020-2021 dalla finestra di 10 anni** (14/10/2026): provate tutte tre su `above_potential()` (livello del ciclo). Su USA il riconoscimento NBER è identico (il PIL attuale è sotto la media in tutte e tre le varianti, non solo per via del Covid). Sulle altre 8 aree, la quota di mesi 2022-oggi in "sotto trend" è uguale o **peggiore** (più mesi, non meno) con mediana ed esclusione Covid rispetto alla media semplice: Eurozona 72% (media) contro 77%/77%, UK 66% contro 66%/77%, Giappone 38% contro 43%/52%. La crescita debole di Europa/UK dal 2022 è reale, non un artefatto del crollo/rimbalzo Covid sulla media: tenuta la media semplice, invariata.

**Perché** (`scripts/evaluate_model.py`): il modello 03/10 (direzione del CLI + inflazione contro il 2%) riproduceva solo 5 delle 14 letture note di Quantaste/Casario, quanto il caso; questa regola 13 (manca solo USA Q2 2022). Con le 3 letture di Canada, Cina e Australia (dashboard 08/10, non usate per scegliere la regola) 14/17: Canada e Cina diverse. 27 varianti di finestre e soglie provate il 09/10: nessuna fa meglio. Per Casario la crescita è la velocità del PIL, non il livello di attività in salita: a ottobre 2026 il CLI USA saliva ancora, ma il PIL annuo era passato dal 2,7% al 2,1%, quindi rallentamento e Stagflazione come Quantaste. Prezzo: ~3 cambi di regime l'anno (prima ~1) e lettura in tempo reale uguale a quella a posteriori nel 46-58% dei mesi (prima 90-95%), perché il PIL esce tardi e viene rivisto. Usare la velocità del CLI al posto del PIL faceva crollare il riconoscimento delle recessioni NBER (100% -> 54%), per questo la fase resta sulla direzione del CLI: invariata (NBER 100%, Recessione fuori 1%).

### Asset allocation
Tabella statica in config (`src/config/asset_allocation.py`), regime → classi di asset favorite (azioni, obbligazioni, materie prime, oro, cash), basata su framework storico noto (stile All Weather). Non dinamica, non backtestata in v1. Backtest successivi: [[#Areas of concern]].

### Struttura file
```
macro-cycle-tracker/
  intent/
  spec.md
  plan.md
  CLAUDE.md
  src/
    data/          fetch_fred.py, fetch_ecb.py, fetch_boe.py, fetch_japan.py, cache.py
    classify/       regime.py, cycle.py
    config/         asset_allocation.py
    scheduler/      update_data.py
    app.py          entry point Streamlit
  tests/
  data/cache.db     (locale, gitignored)
```

## Areas of concern
- **Giappone**: e-Stat richiede registrazione per application ID; dati meno standardizzati di FRED/ECB. Se il setup si rivela troppo fragile durante il build, va segnalato e si può derubricare il Giappone a v2 invece di bloccare tutto il resto.
- **Soglie**: in unità di deviazione standard della stessa serie (crescita) o in punti % contro il 2% (inflazione), uguali per tutte le aree.
- **Ciclo UK e Giappone**: poco preciso contro i rallentamenti OCSE (UK 51% dentro / 45% fuori, Giappone 61% / 17%).
- **Regime -> rendimenti (USA 1960-2026, `scripts/backtest_assets.py`)**: con il nuovo regime le differenze hanno senso economico (Treasury migliori in Stagflazione t=2.8, materie prime migliori in Goldilocks t=2.4 e peggiori in Stagflazione t=-2.1), ma la tabella statica di `asset_allocation.py` ([[#Asset allocation]]) le contraddice in parte: da rivedere con l'utente.
- **Asset allocation storica**: è un mapping statico dichiarato come tale nella UI (non un consiglio di investimento personalizzato/dinamico), per restare nei limiti di "solo dati macro" richiesti dall'[[001-macro-cycle-dashboard|intent]].
