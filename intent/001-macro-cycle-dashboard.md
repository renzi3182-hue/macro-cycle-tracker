# Intent: Dashboard cicli economici e regimi macro
Author: renzi3182@gmail.com. Status: draft.

## Problem
Manca un tool personale per capire in che fase macro/ciclo economico siamo, tipo Quantaste ma su misura. Oggi bisogna cercare a mano dati sparsi (CPI, PIL, tassi, occupazione) e interpretarli senza un framework unico.

## Proposed outcome
Web app locale che, aperta, mostra subito:
1. Regime macro corrente: espansione, deflazione, reflazione, stagflazione (quadrante crescita/inflazione).
2. Fase del ciclo economico corrente: espansione, rallentamento, recessione, ripresa.
3. Asset allocation suggerita per il regime attivo (storico, tipo All Weather).
4. Grafici storici degli indicatori chiave che alimentano la classificazione.
5. Alert quando il sistema rileva un cambio di regime o fase.

Aggiornamento dati automatico e schedulato (no refresh manuale ogni volta).

## Affected users and systems
- Utente unico: renzi3182@gmail.com, uso personale, no altri utenti.
- Sistemi esterni: FRED API (dati USA), ECB Statistical Data Warehouse / Eurostat (Eurozona/Italia), altre fonti da definire per copertura globale (World Bank o simili).
- Nessun sistema esistente da integrare: progetto nuovo, cartella dedicata `macro-cycle-tracker`, separata dal vault Obsidian del monorepo.

## Constraints
- Uso personale: no autenticazione multi-utente, no deploy pubblico richiesto in v1.
- Web app locale (dashboard in localhost), non app desktop nativa.
- Copertura geografica: globale (USA, Eurozona/Italia, e altre aree principali).
- Aggiornamento dati automatico schedulato — richiede un job/cron locale.
- Nessun vincolo di budget dichiarato; preferire API gratuite (FRED è gratis con API key; ECB/Eurostat gratis).

## Open questions
- Quali paesi/aree oltre USA ed Eurozona rientrano in "globale" (UK? Giappone? Cina?) — impatta quali API integrare. Risposta: [[spec#Aree geografiche v1]].
- Quale framework esatto per classificare il regime macro (soglie su inflazione/crescita, quali indicatori pesano e come)? Risposta: [[spec#Logica di classificazione]].
- Quale framework per la fase del ciclo economico (stile NBER, o euristica su PIL/occupazione/PMI)? Risposta: [[spec#Logica di classificazione]].
- L'asset allocation suggerita si basa su un framework storico noto (es. All Weather di Bridgewater) o va costruita da zero? Risposta: [[spec#Asset allocation]].
- Come deve arrivare l'alert (notifica desktop, email, solo badge nella dashboard)? Risposta: badge, [[spec#Output della dashboard]].
- Ogni quanto gira l'aggiornamento automatico (giornaliero è comunque più che sufficiente, dato che i dati macro escono mensile/trimestrale)? Risposta: [[spec#Aggiornamento dati]].

Seguito: [[spec]] (requisiti e design), poi [[plan]] (piano di build).
