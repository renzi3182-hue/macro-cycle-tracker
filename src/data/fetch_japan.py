import pandas as pd
import requests

BASE_URL = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"

# Verificato con dati reali (28/09/2026): PIL reale destagionalizzato trimestrale
# (国内総生産の支出側、実質季節調整系列), tab=11 (livello in miliardi di yen, non
# esiste una serie YoY pronta in questa tabella), cat01=11 (aggregato, non un
# singolo componente). La crescita YoY viene calcolata da noi (pct_change a 4
# trimestri), come faremmo per qualsiasi altra serie di livelli.
STATS_DATA_ID_GROWTH = "0003109750"
GROWTH_FILTERS = {"cdTab": "11", "cdCat01": "11"}

# Verificato con dati reali (28/09/2026): CPI 2020-base, tab=3 (variazione YoY),
# cat01=0001 (tutti gli articoli), area=00000 (tutto il Giappone). Funziona.
STATS_DATA_ID_INFLATION = "0003427113"
INFLATION_FILTERS = {"cdTab": "3", "cdCat01": "0001", "cdArea": "00000"}

# Verificato con dati reali (29/09/2026): Labour Force Survey, tabella 1-1-5,
# whole Japan, mensile. tab="02" (率, tasso) e cat01="000" (全産業) hanno un solo
# valore ciascuno; cat02 (就業状態, stato occupazionale) ha 3 righe (labour force
# / occupati / 完全失業者=disoccupati) e cat03 (性別, sesso) ha 3 righe (totale/M/F).
# Il codice numerico esatto varia da tabella a tabella, quindi lo cerchiamo nel
# CLASS_INF per nome invece di indovinarlo.
STATS_DATA_ID_UNEMPLOYMENT = "0003005865"
UNEMPLOYED_CAT02_NAME = "完全失業者"  # riga cat02 = disoccupati (con tab="率" e' gia' un tasso %)
TOTAL_CAT03_NAME = "総数"  # riga cat03 = totale (non solo maschi o femmine)


def _parse_estat_time(time_code: str) -> pd.Timestamp:
    # verificato sulla tabella CPI reale: mensile e' YYYY + "00" + MM + MM
    # (es. "2026000808" = agosto 2026). Il formato per altre tabelle (es. GDP
    # trimestrale) non e' ancora verificato.
    if len(time_code) == 10:
        return pd.Timestamp(year=int(time_code[:4]), month=int(time_code[6:8]), day=1)
    if len(time_code) == 6:
        return pd.Timestamp(year=int(time_code[:4]), month=int(time_code[4:6]), day=1)
    if len(time_code) == 4:
        return pd.Timestamp(year=int(time_code), month=1, day=1)
    raise ValueError(f"formato time_code e-Stat non gestito: {time_code!r}")


def _fetch_series(stats_data_id: str, app_id: str, extra_params: dict | None = None) -> pd.Series:
    if not stats_data_id:
        raise ValueError(
            "STATS_DATA_ID non configurato in fetch_japan.py: cerca la tabella su e-stat.go.jp"
        )
    params = {"appId": app_id, "statsDataId": stats_data_id}
    if extra_params:
        params.update(extra_params)
    resp = requests.get(BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    values = resp.json()["GET_STATS_DATA"]["STATISTICAL_DATA"]["DATA_INF"]["VALUE"]
    dates = [_parse_estat_time(v["@time"]) for v in values]
    vals = [float(v["$"]) for v in values]
    return pd.Series(vals, index=dates).sort_index()


def fetch_growth_yoy(app_id: str) -> pd.Series:
    levels = _fetch_series(STATS_DATA_ID_GROWTH, app_id, extra_params=GROWTH_FILTERS)
    return (levels.pct_change(periods=4) * 100).dropna()


def fetch_inflation_yoy(app_id: str) -> pd.Series:
    return _fetch_series(STATS_DATA_ID_INFLATION, app_id, extra_params=INFLATION_FILTERS)


def _is_number(raw: str) -> bool:
    try:
        float(raw)
        return True
    except ValueError:
        return False  # placeholder e-stat per dato mancante (es. "…" marzo-agosto 2011, sospensione post-terremoto)


def _find_class_code(class_objs: list, class_id: str, name_contains: str) -> str:
    target = next(c for c in class_objs if c["@id"] == class_id)
    items = target["CLASS"] if isinstance(target["CLASS"], list) else [target["CLASS"]]
    return next(item["@code"] for item in items if name_contains in item["@name"])


def fetch_unemployment_rate(app_id: str) -> pd.Series:
    resp = requests.get(
        BASE_URL,
        params={"appId": app_id, "statsDataId": STATS_DATA_ID_UNEMPLOYMENT},
        timeout=30,
    )
    resp.raise_for_status()
    statistical_data = resp.json()["GET_STATS_DATA"]["STATISTICAL_DATA"]
    class_objs = statistical_data["CLASS_INF"]["CLASS_OBJ"]
    cat02_code = _find_class_code(class_objs, "cat02", UNEMPLOYED_CAT02_NAME)
    cat03_code = _find_class_code(class_objs, "cat03", TOTAL_CAT03_NAME)

    values = statistical_data["DATA_INF"]["VALUE"]
    filtered = [
        v for v in values
        if v.get("@cat02") == cat02_code and v.get("@cat03") == cat03_code and _is_number(v["$"])
    ]
    dates = [_parse_estat_time(v["@time"]) for v in filtered]
    vals = [float(v["$"]) for v in filtered]
    return pd.Series(vals, index=dates).sort_index()
