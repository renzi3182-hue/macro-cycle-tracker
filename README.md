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
- **Eurozona / Italia** (Eurostat): funzionante.
- **UK** (ONS, non BoE — il database BoE blocca le richieste automatiche): funzionante.
- **Giappone** (e-Stat): funzionante. CPI è già una serie YoY pronta; il PIL no — e-Stat pubblica solo i livelli reali destagionalizzati, la crescita YoY è calcolata nel codice (`pct_change` a 4 trimestri).

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
   - Programma: `C:\Users\renzi\OneDrive\Desktop\software-investing\.venv\Scripts\python.exe`
   - Argomenti: `-m src.scheduler.update_data`
   - Cartella di lavoro (importante): `C:\Users\renzi\OneDrive\Desktop\software-investing`

## Test

```bash
.venv\Scripts\pytest tests/ -v
```

28 test, tutti con HTTP mockato (nessuna chiamata di rete reale, nessuna API key richiesta per il build).

## Stato deploy

Non è previsto un deploy pubblico (uso personale, gira in locale). Repo pronto per commit; niente da pubblicare online.
