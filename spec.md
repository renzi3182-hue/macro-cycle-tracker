# Spec: Dashboard cicli economici e regimi macro (from intent 001-macro-cycle-dashboard.md, 2026-09-27)

## Requirements

### Aree geografiche v1
USA, Eurozona (aggregato + Italia), UK, Giappone.

### Output della dashboard
1. **Regime macro** per ogni area: Espansione, Deflazione, Reflazione, Stagflazione.
2. **Fase ciclo economico** per ogni area: Espansione, Rallentamento, Recessione, Ripresa.
3. **Asset allocation suggerita** per il regime macro attivo (tabella statica).
4. **Grafici storici** degli indicatori usati per la classificazione (crescita, inflazione).
5. **Badge/banner di cambio regime**: evidenzia se l'ultimo aggiornamento ha fatto cambiare regime o fase rispetto al giro precedente.

### v2 — Sentiment e Risk On/Off (da modello Quantaste, fonte: libro "Investire nel breve e lungo termine" di Marco Casario)
6. **Smart Quant Sentiment**: score 0-100 (Sell/Hold/Buy) su sentiment di mercato quantitativo.
7. **Risk On/Off**: score 0-100 (propensione al rischio: Ext. Risk Off → Neutral → Ext. Risk On), con split suggerito Risk assets/Difensivo/Cash.
   **Implementato 06/10/2026** (`src/classify/risk.py`, Panoramica): VIX, spread Baa-10Y e quota di ETF sopra la media a 10 mesi, a pesi uguali. Verificato (`scripts/evaluate_risk.py`): anticipa la volatilità, non il rendimento, quindi niente split suggerito Risk assets/Difensivo/Cash.

Metodologia esatta (indicatori di input, pesi, soglie) da definire dopo aver ricevuto dal libro i capitoli su sentiment quant e risk on/off — non a tavolino. Finché non definita, questi due punti restano requisiti aperti, non implementati.

**Ricerca preliminare (28/09/2026)**: indicatori "risk on/off" tipici in letteratura (NBER, KC Fed) combinano VIX (volatilità equity), credit spread high-yield, e mosse FX/oro come safe-haven. Utile: FRED (fonte già usata per USA) pubblica sia `VIXCLS` (CBOE VIX) sia `BAMLH0A0HYM2` (spread high-yield ICE BofA) gratis, senza bisogno di nuovi fetcher/fonti. Metodologia "Smart Quant Sentiment" (score Sell/Hold/Buy) ancora da definire, in attesa del libro.

### Idea aperta v3 — rotazione settoriale per fase ciclo
Fidelity ("Business Cycle Approach to Equity Sector Investing") mappa 4 fasi cicliche a settori azionari favoriti (early-cycle: consumer discretionary/industrials/tech; late-cycle: difensivi come health care/consumer staples/utilities). Ricerca solo parziale (mid-cycle e recessione non ancora verificati con fonte primaria) — non implementato, da approfondire se si vuole granularità settoriale oltre le 4 classi di asset attuali.
**06/10/2026**: aggiunta la rotazione settori USA (RRG mensile, `src/classify/rrg.py`, pagina Classifica) come mappa descrittiva: verificata con `scripts/evaluate_rrg.py`, il quadrante non prevede l'extra-rendimento. Mappa fase → settori Fidelity ancora non implementata.

### Aggiornamento dati
Automatico, schedulato una volta al giorno (i dati macro escono comunque mensile/trimestrale, giornaliero è più che sufficiente). Windows Task Scheduler lancia lo script di update; la dashboard legge sempre dalla cache locale, mai dalle API in diretta.

## Design

### Stack
- Python. Dashboard con **Streamlit** (nessun frontend separato da costruire, legge dati locali, adatto a uso personale).
- Cache dati locale in **SQLite** (`data/cache.db`), popolata dallo script di update. La dashboard non chiama mai le API esterne direttamente.
- Scheduling: **Windows Task Scheduler** chiama `python src/scheduler/update_data.py` una volta al giorno.

### Fonti dati per area
| Area | Fonte | Indicatori |
|---|---|---|
| USA | FRED API (serve API key gratuita) | PIL reale YoY, CPI YoY, PMI (proxy se disponibile su FRED) |
| Eurozona / Italia | ECB Statistical Data Warehouse + Eurostat | PIL reale YoY, HICP YoY |
| UK | Bank of England API | PIL reale YoY, CPI YoY |
| Giappone | e-Stat API (serve application ID gratuito) | PIL reale YoY, CPI YoY |
| Tutte | OCSE SDMX (senza chiave) | Composite Leading Indicator (Eurozona = G4E) |
| Anticipatori | Eurostat, FRED/OCSE, Bank of Japan | ESI, curve 10Y-breve, spread BTP-Bund, Tankan |

Aggiornamento 29/09/2026: soglie degli anticipatori fuori USA verificate con `scripts/backtest_leading_intl.py`; con rischio "Alto" un'Espansione diventa Rallentamento in ogni area (prima solo USA). Backtest regime -> rendimenti (`scripts/backtest_assets.py`) e con dati real-time ALFRED (`scripts/backtest_alfred.py`): vedi i commenti in `src/config/asset_allocation.py` e sotto "Areas of concern".

### Logica di classificazione (riscritta il 03/10/2026, trasparente, regolabile — no black box)

Tutto mensile, un solo calcolo per scheduler e app (`src/classify/assess.py`). Costanti in cima a `regime.py`, `cycle.py`, `recession.py`.

**Regime macro** = direzione della crescita x pressione dell'inflazione:

| Crescita (CLI OCSE, direzione 3 mesi) | Inflazione (media totale+core vs 2%, + direzione 3 mesi) | Regime |
|---|---|---|
| in accelerazione | sotto controllo | Goldilocks |
| in accelerazione | alta o in salita | Reflazione |
| in rallentamento | alta o in salita | Stagflazione |
| in rallentamento | sotto controllo | Deflazione |

Isteresi e conferma di 2 mesi per asse. Niente stato "Transizione": la vicinanza a una soglia si mostra come "solidità" (Alta/Media/Bassa) e come probabilità.

**Fase del ciclo**: momentum = asse crescita del regime; livello = PIL annuo contro la sua media 10 anni (la disoccupazione contro la media 10 anni, usata fino al 03/10/2026, coincideva con la crescita sopra il trend a posteriori solo nel 42-57% dei mesi: in Europa e Giappone scende da anni per demografia); Recessione solo con conferma dura (Sahm, negli USA con Chauvet-Piger, fuori dagli USA per 2 mesi; oppure PIL annuo <= 0). Gli anticipatori (`leading.py`) si mostrano a parte e non cambiano la fase.

**Perché** (`scripts/evaluate_model.py`, con ritardi di pubblicazione veri): il modello precedente (trimestrale, z della variazione di PIL e CPI) coincideva con la lettura a posteriori nel 5-20% dei mesi ed era "Transizione" il 40-60% del tempo. Il nuovo: 90-95%, ~1 cambio di regime l'anno. Il livello del CLI rispetto a 100 viene rivisto troppo (66-88% di coerenza nelle vintage ALFRED 2018-2026), la direzione no (79-93%).

### Asset allocation
Tabella statica in config (`src/config/asset_allocation.py`), regime → classi di asset favorite (azioni, obbligazioni, materie prime, oro, cash), basata su framework storico noto (stile All Weather). Non dinamica, non backtestata in v1.

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
- **Regime -> rendimenti (USA 1960-2026, `scripts/backtest_assets.py`)**: con il nuovo regime le differenze hanno senso economico (Treasury migliori in Stagflazione t=2.8, materie prime migliori in Goldilocks t=2.4 e peggiori in Stagflazione t=-2.1), ma la tabella statica di `asset_allocation.py` le contraddice in parte: da rivedere con l'utente.
- **Asset allocation storica**: è un mapping statico dichiarato come tale nella UI (non un consiglio di investimento personalizzato/dinamico), per restare nei limiti di "solo dati macro" richiesti dall'intent.
