"""Dati giornalieri e parametri degli scenari dalla sola cache."""
import math
from statistics import mean, stdev

from src.data import cache

# Simbolo, descrizione, mercato del calendario, contratto COT pertinente.
INSTRUMENTS = [
    ("SPY", "S&P 500", "USD", "S&P 500"), ("EZU", "Azionario eurozona", "EUR", ""),
    ("MCHI", "Azionario Cina", "CNY", ""), ("EEM", "Azionario emergenti", "", ""),
    ("QQQ", "Nasdaq 100", "USD", "Nasdaq 100"), ("IEF", "Treasury USA 7–10 anni", "USD", "Treasury 10Y"),
    ("TLT", "Treasury USA oltre 20 anni", "USD", ""), ("GLD", "Oro", "USD", "Oro"),
]
WINDOW = 36
Z = 1.644854


def model(monthly):
    returns = [math.log(b/a) for a, b in zip(monthly, monthly[1:])]
    if len(returns) < WINDOW:
        return None
    history = []
    for i in range(WINDOW, len(returns)):
        sample = returns[i-WINDOW:i]
        history.append([i, mean(sample), stdev(sample)])
    return dict(drift=mean(returns[-WINDOW:]), vol=stdev(returns[-WINDOW:]), checks=history, levels=monthly)


def catalog():
    assets = {}
    for symbol, name, currency, contract in INSTRUMENTS:
        prices = cache.read_indicator_series("Intermarket", symbol).dropna().sort_index()
        monthly = prices.groupby(prices.index.to_period("M")).last() if len(prices) else prices
        # Escludi il mese finale: la cache potrebbe fermarsi prima della chiusura.
        item = dict(name=name, kind="ETF", country=currency, history=[
            [date.date().isoformat(), round(float(price), 4)] for date, price in prices.items() if price > 0],
            model=model(monthly.iloc[:-1].tolist()), contract=contract)
        if contract:
            cot = cache.read_indicator_series("Mercati", "cot_" + contract).dropna().sort_index()
            if len(cot) >= 2:
                item["cot"] = [cot.index[-1].date().isoformat(), round(float(cot.iloc[-1]-cot.iloc[-2]), 2)]
        assets[symbol] = item
    return {"assets": assets, "events": cache.read_events()}
