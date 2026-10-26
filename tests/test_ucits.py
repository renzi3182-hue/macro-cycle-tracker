import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.classify.score import UNIVERSE
from src.classify.stress import PROXY
from src.config.ucits import NO_EQUIVALENT, UCITS
from src.ui.cards import ucits_html


def isin_ok(isin: str) -> bool:
    """Cifra di controllo ISIN (Luhn sulle lettere convertite in numeri): scopre gli errori di battitura."""
    if len(isin) != 12 or not isin[:2].isalpha() or not isin[-1].isdigit():
        return False
    digits = "".join(str(int(c, 36)) for c in isin[:-1])
    total = 0
    for i, d in enumerate(reversed(digits)):
        n = int(d) * (2 if i % 2 == 0 else 1)
        total += n // 10 + n % 10
    return (10 - total % 10) % 10 == int(isin[-1])


def test_every_etf_in_the_app_has_a_row():
    assert set(UNIVERSE) | set(PROXY.values()) == set(UCITS)
    assert all(t in NO_EQUIVALENT for t, u in UCITS.items() if u is None)


def test_isin_check_digits_and_no_duplicates():
    isins = [u.isin for u in UCITS.values() if u]
    assert all(isin_ok(i) for i in isins), [i for i in isins if not isin_ok(i)]
    assert len(set(isins)) == len(isins)
    assert not isin_ok("IE00B5BMR088")  # una cifra sbagliata si vede


def test_table_shows_isin_note_and_missing_equivalent():
    html = ucits_html(["SPY", "GLD", "UUP", "XYZ"], {"SPY": "Azionario"})
    assert "IE00B5BMR087" in html and "CSSPX" in html and "ETC" in html and "Nessun equivalente UCITS" in html
    assert "XYZ" not in html and "justETF" in html
