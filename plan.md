# Plan: Dashboard cicli economici e regimi macro (from spec.md, 2026-09-27)

## Files that change
Tutto nuovo, nessun codice esistente da toccare.

```
macro-cycle-tracker/
  .gitignore
  requirements.txt
  CLAUDE.md
  README.md
  .env.example
  src/
    __init__.py
    data/
      __init__.py
      cache.py
      fetch_fred.py
      fetch_ecb.py
      fetch_boe.py
      fetch_japan.py
    classify/
      __init__.py
      regime.py
      cycle.py
    config/
      __init__.py
      asset_allocation.py
    scheduler/
      __init__.py
      update_data.py
    app.py
  tests/
    test_regime.py
    test_cycle.py
    test_cache.py
    test_fetch_fred.py
    test_fetch_ecb.py
    test_fetch_boe.py
    test_fetch_japan.py
```

## Order of work

1. **Scaffold**: `git init`, `.gitignore` (venv, `data/cache.db`, `.env`), `requirements.txt` (`requests`, `pandas`, `streamlit`, `pytest`, `requests-mock`), `.env.example` (FRED_API_KEY, ESTAT_APP_ID), `CLAUDE.md` minimo (stack, come lanciare test/app).

2. **Cache SQLite** (`src/data/cache.py`): schema con 2 tabelle.
   - `indicators(area, indicator, date, value)` — serie storiche grezze.
   - `classifications(area, computed_at, regime, phase)` — storico classificazioni, usato per il badge di cambio.
   Funzioni: `write_indicator_series(...)`, `read_indicator_series(...)`, `write_classification(...)`, `read_last_two_classifications(...)`.

3. **Fetcher per area** (uno alla volta, stesso pattern: funzione che chiama l'API e ritorna una serie pandas `date -> value`):
   - `fetch_fred.py`: PIL reale YoY, CPI YoY, PMI se disponibile. Legge `FRED_API_KEY` da env.
   - `fetch_ecb.py`: PIL reale YoY e HICP YoY per Eurozona e Italia via ECB SDW REST.
   - `fetch_boe.py`: PIL reale YoY e CPI YoY UK.
   - `fetch_japan.py`: PIL reale YoY e CPI YoY via e-Stat, legge `ESTAT_APP_ID` da env. Se l'API si rivela troppo fragile, isolare il fallimento (loggare e skippare l'area) invece di far crashare l'intero update.
   Ogni fetcher testato con `requests-mock` (nessuna chiamata di rete reale nei test).

4. **Classificazione** (`src/classify/regime.py`, `src/classify/cycle.py`): funzioni pure, input = serie pandas di crescita e inflazione, output = stringa regime/fase secondo le tabelle in spec.md. Direzione = confronto valore corrente vs media mobile a 3 periodi precedenti. Soglie iniziali semplici (>0 = su, <0 = giù), da poter aggiustare come costanti in cima al file.

5. **Asset allocation** (`src/config/asset_allocation.py`): dict statico `regime -> {asset_class: peso/etichetta}`.

6. **Orchestratore update** (`src/scheduler/update_data.py`): per ogni area, chiama il fetcher, scrive su cache, calcola regime+fase, scrive in `classifications`. Un'area che fallisce non blocca le altre (try/except per area, log errore).

7. **Dashboard** (`src/app.py`, Streamlit): per ogni area mostra regime attuale, fase attuale, badge "cambiato dall'ultimo aggiornamento" (confronto ultime due righe di `classifications`), grafico storico crescita/inflazione (`st.line_chart`), tabella asset allocation per il regime attivo.

8. **README**: come ottenere le API key (FRED, e-Stat), come lanciare l'app (`streamlit run src/app.py`), come creare il task schedulato in Windows Task Scheduler (istruzioni manuali per l'utente — non è una modifica che lo script deve fare da solo, è una modifica di sistema).

Non chiedere conferma ad ogni passo. Fermarsi solo se un'API esterna cambia radicalmente lo scope (es. e-Stat non praticabile → derubricare Giappone, come da spec).

## Risks

- **API key mancanti**: build e test non devono dipendere da chiavi vere (test con mock). Solo l'update reale in produzione le richiede.
- **e-Stat (Giappone) fragile**: isolato per area, non deve bloccare le altre 3 aree.
- **Revisioni dati storici**: le serie macro vengono riviste nel tempo; il cache overwrite (non append-only) evita di accumulare versioni vecchie.
- **Rate limit API**: update una volta al giorno è ben sotto i limiti di FRED/ECB/BoE; e-Stat da verificare in fase di build.

## Proof

- `pytest tests/` verde: casi di test su `regime.py`/`cycle.py` che coprono tutti e 4 i quadranti/fasi con serie sintetiche (10-15 casi), test cache read/write, test fetcher con risposte HTTP mockate (successo + errore).
- Smoke test manuale: `streamlit run src/app.py` con dati di test in cache, verificare a occhio che le 4 aree mostrino regime/fase/grafico/allocation senza errori.
- Nessun secret in git: verificare che `.env` sia in `.gitignore` e non committato.
