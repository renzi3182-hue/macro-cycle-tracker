"""GET condiviso con retry per tutti i fetcher (FRED, ECB/Eurostat, BoE/ONS, OECD): stesso comportamento
su errori temporanei (5xx, 429, timeout, connessione) invece di duplicarlo in ogni modulo.

Interruttore per fonte: se una fonte esaurisce le retry su CIRCUIT_THRESHOLD fetch consecutivi, le chiamate
successive alla stessa fonte nello stesso processo fanno un solo tentativo con timeout ridotto, cosi' una
fonte completamente giu' (es. FRED, ~35 serie in un run) non fa superare i 15 minuti del workflow. Una
chiamata riuscita azzera il contatore.
"""
import time

import requests

RETRY_STATUS = {429, 500, 502, 503, 504}
RETRYABLE_EXCEPTIONS = (requests.exceptions.Timeout, requests.exceptions.ConnectionError)
CIRCUIT_THRESHOLD = 3
CIRCUIT_TIMEOUT = 5  # secondi, per il tentativo singolo a circuito aperto

_consecutive_failures: dict[str, int] = {}


def get_with_retry(url: str, source: str, max_attempts: int = 4, backoff: tuple = (2, 4, 8), **kwargs) -> requests.Response:
    """GET con retry su errori temporanei. 4xx (eccetto 429) fallisce subito, senza ritentare."""
    circuit_open = _consecutive_failures.get(source, 0) >= CIRCUIT_THRESHOLD
    attempts = 1 if circuit_open else max_attempts
    call_kwargs = {**kwargs, "timeout": CIRCUIT_TIMEOUT} if circuit_open else kwargs
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            resp = requests.get(url, **call_kwargs)
            resp.raise_for_status()
            _consecutive_failures[source] = 0
            return resp
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code not in RETRY_STATUS:
                raise
            last_exc = e
        except RETRYABLE_EXCEPTIONS as e:
            last_exc = e
        if attempt < attempts - 1:
            time.sleep(backoff[attempt])
    _consecutive_failures[source] = _consecutive_failures.get(source, 0) + 1
    raise last_exc
