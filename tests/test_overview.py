import pandas as pd

from src.ui.overview import overview_html


def test_card_shows_start_date_and_mini_timeline():
    idx = pd.date_range("2021-09-30", periods=20, freq="QE")
    hist = pd.Series(["Reflazione"] * 4 + ["Deflazione"] * 16, index=idx)
    area = {"area": "USA", "code": "USA", "regime": "Deflazione", "phase": "Rallentamento",
            "probs": None, "pos": None, "signals": [], "history": hist, "streak": 16}
    html = overview_html([area])
    assert "da T3 2022 (16 trim.)" in html
    assert html.count('<i class=now') == 1 and ">oggi<" in html
