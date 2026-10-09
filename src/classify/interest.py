import math

import pandas as pd

# Calcolatore di interesse semplice e composto, con versamenti mensili, inflazione e tassa sugli interessi.
# Semplice: interessi solo sul capitale versato, mai sugli interessi gia' maturati.
# Composto: interessi capitalizzati `per_year` volte l'anno; tra una capitalizzazione e l'altra il calcolo usa il
# tasso mensile equivalente, quindi i versamenti a meta' periodo maturano pro rata.
# Tassa (Italia: 26% in generale, 12,5% sui titoli di Stato) applicata sugli interessi a fine periodo, come se si
# vendesse tutto in quell'anno: niente tassazione anno per anno (vale per ETF ad accumulazione, non per i conti).


def schedule(principal: float, monthly: float, rate_pct: float, years: int, per_year: int = 12,
             inflation_pct: float = 0.0, tax_pct: float = 0.0) -> pd.DataFrame:
    """Una riga per anno (0 = oggi): versato, valore e interessi con interesse semplice e composto, valori netti e reali."""
    r = rate_pct / 100
    monthly_rate = (1 + r / per_year) ** (per_year / 12) - 1
    simple = compound = principal
    deposited, simple_interest = principal, 0.0
    rows = [(0, principal, principal, principal)]
    for m in range(1, years * 12 + 1):
        simple_interest += deposited * r / 12  # su quanto versato fino al mese prima
        compound = compound * (1 + monthly_rate) + monthly
        deposited += monthly
        if m % 12 == 0:
            rows.append((m // 12, deposited, deposited + simple_interest, compound))
    df = pd.DataFrame(rows, columns=["Anno", "Versato", "Semplice", "Composto"]).set_index("Anno")
    tax = tax_pct / 100
    deflator = (1 + inflation_pct / 100) ** df.index.to_series()
    for col in ("Semplice", "Composto"):
        df[f"Interessi {col.lower()}"] = df[col] - df["Versato"]
        df[f"{col} netto"] = df[col] - df[f"Interessi {col.lower()}"].clip(lower=0) * tax
        df[f"{col} netto reale"] = df[f"{col} netto"] / deflator
    return df


def years_to_double(rate_pct: float) -> float | None:
    """Anni per raddoppiare con interesse composto annuo (esatto, non la regola del 72)."""
    return None if rate_pct <= 0 else math.log(2) / math.log(1 + rate_pct / 100)
