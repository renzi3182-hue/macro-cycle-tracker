# Macro Cycle Tracker

Dashboard locale, uso personale: regime macro (Espansione/Deflazione/Reflazione/Stagflazione) e fase del ciclo economico (Espansione/Rallentamento/Recessione/Ripresa) per USA, Eurozona/Italia, UK, Giappone.

Vedi [intent](intent/001-macro-cycle-dashboard.md), [spec.md](spec.md), [plan.md](plan.md) per il processo che ha portato a questo codice.

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

La dashboard avvisa se un dato ha piu' di 250 giorni: di solito la fonte ha cambiato dataset.

Se un'area fallisce, l'update la salta e continua con le altre (vedi `src/scheduler/update_data.py`), quindi non blocca il resto della dashboard.

## Uso

```bash
.venv\Scripts\python -m src.scheduler.update_data   # aggiorna la cache locale
.venv\Scripts\streamlit run src/app.py               # apre la dashboard
```

## Aggiornamento automatico (Windows Task Scheduler)

Da fare manualmente (è una modifica di sistema, non automatizzata da questo repo):

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

63 test, tutti con HTTP mockato (nessuna chiamata di rete reale, nessuna API key richiesta per il build).

## Backtest (script, scaricano dalle fonti, non usano l'app)

```bash
.venv\Scripts\python scripts/backtest_nber.py            # segnali di recessione USA vs date NBER
.venv\Scripts\python scripts/backtest_alfred.py          # stessi segnali con i dati real-time ALFRED
.venv\Scripts\python scripts/backtest_leading_intl.py    # anticipatori fuori USA vs rallentamenti OCSE
.venv\Scripts\python scripts/backtest_assets.py [--alfred]  # regime -> rendimenti asset
.venv\Scripts\python scripts/backtest_currency.py        # punteggio valute (legge la cache)
```

## Stato deploy

Non è previsto un deploy pubblico (uso personale, gira in locale). Repo pronto per commit; niente da pubblicare online.
