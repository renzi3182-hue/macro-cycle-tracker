import pandas as pd

from src.data.fetch_french import parse_monthly

CSV = """This file was created using the 202608 CRSP database.

  Average Value Weighted Returns -- Monthly
,NoDur,BusEq
192607,   1.44, -99.99
192608,   3.99,   1.98

  Average Equal Weighted Returns -- Monthly
,NoDur,BusEq
192607,   9.99,   9.99
"""


def test_parse_monthly_reads_first_table_in_fractions():
    df = parse_monthly(CSV)
    assert list(df.columns) == ["NoDur", "BusEq"] and len(df) == 2  # solo la prima tabella (pesata per capitalizzazione)
    assert df.index[0] == pd.Timestamp("1926-07-01")
    assert abs(df.loc["1926-08-01", "NoDur"] - 0.0399) < 1e-12
    assert pd.isna(df.loc["1926-07-01", "BusEq"])  # -99.99 = mancante
