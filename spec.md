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

Metodologia esatta (indicatori di input, pesi, soglie) da definire dopo aver ricevuto dal libro i capitoli su sentiment quant e risk on/off — non a tavolino. Finché non definita, questi due punti restano requisiti aperti, non implementati.

**Ricerca preliminare (28/09/2026)**: indicatori "risk on/off" tipici in letteratura (NBER, KC Fed) combinano VIX (volatilità equity), credit spread high-yield, e mosse FX/oro come safe-haven. Utile: FRED (fonte già usata per USA) pubblica sia `VIXCLS` (CBOE VIX) sia `BAMLH0A0HYM2` (spread high-yield ICE BofA) gratis, senza bisogno di nuovi fetcher/fonti. Metodologia "Smart Quant Sentiment" (score Sell/Hold/Buy) ancora da definire, in attesa del libro.

### Idea aperta v3 — rotazione settoriale per fase ciclo
Fidelity ("Business Cycle Approach to Equity Sector Investing") mappa 4 fasi cicliche a settori azionari favoriti (early-cycle: consumer discretionary/industrials/tech; late-cycle: difensivi come health care/consumer staples/utilities). Ricerca solo parziale (mid-cycle e recessione non ancora verificati con fonte primaria) — non implementato, da approfondire se si vuole granularità settoriale oltre le 4 classi di asset attuali.

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

### Logica di classificazione (trasparente, regolabile — no black box)

**Regime macro** = funzione di (direzione crescita, direzione inflazione), ciascuna calcolata come trend su finestra mobile (es. valore corrente vs media dei 3 periodi precedenti):

| Crescita | Inflazione | Regime |
|---|---|---|
| ↑ | ↓ (o bassa) | Reflazione |
| ↑ | ↑ | Espansione |
| ↓ | ↑ | Stagflazione |
| ↓ | ↓ | Deflazione |

**Fase ciclo economico** = funzione di (livello crescita, momentum crescita — variazione vs periodo precedente):

| Livello PIL YoY | Momentum | Fase |
|---|---|---|
| > 0 | in accelerazione | Espansione |
| > 0 | in decelerazione | Rallentamento |
| < 0 | in ulteriore calo | Recessione |
| < 0 | in miglioramento | Ripresa |

**Soglie tarate su dati storici reali (FRED USA, 1948-2026, 310+ trimestri)**: senza una soglia minima di variazione ("deadband"), il regime cambiava nel 45.5% dei trimestri e la fase nel 47.6% — quasi sempre rumore statistico, non veri cambi di ciclo. Soglie scelte al 75° percentile delle variazioni trimestrali osservate (crescita 2.0pp, inflazione 1.4pp, momentum 1.4pp): riducono i cambi al 15.5%/13.7%, mantenendo rilevabili le crisi vere (2008-09, Covid 2020, inflazione 2021-22). Vedi `src/classify/regime.py` e `cycle.py` per le costanti, `wiki/macro-cycle-tracker.md` per il dettaglio del backtest.

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
- **Soglie di classificazione**: calibrate su backtest storico reale USA (vedi sopra). Non ancora ricalibrate separatamente per Eurozona/UK/Giappone (usano le stesse soglie USA per ora — verificare se serve differenziare quando ci sono più anni di dati cache accumulati).
- **Asset allocation storica**: è un mapping statico dichiarato come tale nella UI (non un consiglio di investimento personalizzato/dinamico), per restare nei limiti di "solo dati macro" richiesti dall'intent.
