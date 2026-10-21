# Macro Cycle Tracker

Dashboard per uso personale: regime macro (Goldilocks/Deflazione/Reflazione/Stagflazione) e fase del ciclo economico (Espansione/Rallentamento/Recessione/Ripresa (sotto trend)) per nove aree: USA, Eurozona, Italia, UK, Giappone, Canada, Cina, Australia, India. Pubblicata su https://macrocycletracker.streamlit.app/, con dati aggiornati da GitHub Actions.

## Setup

```bash
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

Copia `.env.example` in `.env` e riempi:
- `FRED_API_KEY`: gratuita, registrati su https://fred.stlouisfed.org/docs/api/api_key.html
- `ESTAT_APP_ID`: gratuito, registrati su https://www.e-stat.go.jp/api/ (necessario solo per l'area Giappone)

## Stato fonti dati (verificato con chiamate reali, tutte e 5 funzionanti)

- **USA** (FRED): funzionante.
- **Eurozona / Italia** (Eurostat): funzionante. Inflazione da `prc_hicp_minr` (il vecchio `prc_hicp_manr` e' fermo a dic 2025); Eurozona = `EA21`.
- **UK** (ONS, non BoE — il database BoE blocca le richieste automatiche): funzionante.
- **Giappone** (e-Stat): funzionante. CPI è già una serie YoY pronta; il PIL no — e-Stat pubblica solo i livelli reali destagionalizzati, la crescita YoY è calcolata nel codice (`pct_change` a 4 trimestri).

Indicatori anticipatori (tutte le aree, vedi `src/classify/leading.py`): OECD CLI (API SDMX OCSE, senza chiave), Economic Sentiment Indicator (Eurostat), curve dei tassi e spread BTP-Bund (FRED/OCSE), Tankan (API Bank of Japan, senza chiave). USA, solo informativi: sussidi di disoccupazione, permessi di costruzione, Philly Fed (proxy dell'ISM PMI, non disponibile gratis), GDPNow.

Storico lungo per la Classifica (`src/data/fetch_french.py`, area di cache `Storico`): rendimenti mensili di mercato e 12 settori USA dalla Kenneth French Data Library (Dartmouth, gratuita, senza chiave, dal 1926) e rendimenti Treasury GS10/GS1 da FRED.

La dashboard avvisa se un dato ha piu' di 250 giorni: di solito la fonte ha cambiato dataset.

Se un'area fallisce, l'update la salta e continua con le altre (vedi `src/scheduler/update_data.py`), quindi non blocca il resto della dashboard.

## Uso

```bash
.venv\Scripts\python -m src.scheduler.update_data   # aggiorna la cache locale
.venv\Scripts\streamlit run src/app.py               # apre la dashboard
```

## Aggiornamento automatico

In produzione: il workflow `.github/workflows/update-data.yml` gira ogni 30 minuti nei giorni feriali solo per macro e calendario (`--macro-only`), completo alle 21:45 UTC dopo la chiusura USA e una volta nel weekend, aggiorna `data/cache.db` e la pubblica come asset della release `data-latest`; l'app la scarica all'avvio se è più recente di quella locale (`src/data/sync.py`).

In locale, facoltativo, con Windows Task Scheduler (modifica di sistema, da fare a mano):

1. Apri **Utilità di pianificazione** (Task Scheduler).
2. Crea attività di base → trigger giornaliero, orario a scelta.
3. Azione: avvia programma.
   - Programma: `C:\Users\renzi\OneDrive\Desktop\soft-investing\.venv\Scripts\python.exe`
   - Argomenti: `-m src.scheduler.update_data`
   - Cartella di lavoro (importante): `C:\Users\renzi\OneDrive\Desktop\soft-investing`

## Test

```bash
.venv\Scripts\pytest tests/ -v
```

163 test, tutti con HTTP mockato (nessuna chiamata di rete reale, nessuna API key richiesta per il build).

## Backtest (script, scaricano dalle fonti, non usano l'app)

```bash
.venv\Scripts\python scripts/backtest_nber.py            # segnali di recessione USA vs date NBER
.venv\Scripts\python scripts/backtest_leading_intl.py    # anticipatori fuori USA vs rallentamenti OCSE
.venv\Scripts\python scripts/backtest_assets.py          # regime -> rendimenti asset
.venv\Scripts\python scripts/backtest_currency.py        # punteggio valute (legge la cache)
.venv\Scripts\python scripts/evaluate_intermarket.py    # fase di Murphy e allineamento macro/mercati dal 2000
```

## Pagine

Oggi (pagina iniziale: fase del ciclo e asset per area, nervosismo e tendenza). Macro: Aree (regime mese per mese e fase del ciclo come punto sull'onda), Metodo. Mercati: Classifica, Mercati (VIX, MOVE, inflazione attesa, prossimi eventi, le quattro relazioni intermarket del libro), COT report, Valute, Calendario. Strumenti: Portafoglio, Size Monte Carlo, Interesse composto.

## Stato deploy

Live su https://macrocycletracker.streamlit.app/ (Streamlit Community Cloud), da un repo pubblico separato e piatto. I dati arrivano dal workflow GitHub Actions descritto sopra.
