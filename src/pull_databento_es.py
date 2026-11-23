"""Pull E-mini S&P 500 futures one-minute bars from Databento, June 2010 onward.

Uses the continuous symbol ES.v.0, which follows the E-mini contract with the
highest volume each day. Timestamps are in UTC.
Saves one parquet file per year in DATA_DIR/databento_es_minute/.
"""

from pathlib import Path

import databento as db
import pandas as pd

from settings import config

DATA_DIR = Path(config("DATA_DIR"))
START_DATE = config("START_DATE")
END_DATE = config("END_DATE")
DATABENTO_API_KEY = config("DATABENTO_API_KEY")

FIRST_AVAILABLE_DATE = pd.Timestamp("2010-06-06")


def pull_es_minute_bars(client, start, end):
    """Return E-mini one-minute bars (open, high, low, close, volume) from start to end."""
    data = client.timeseries.get_range(
        dataset="GLBX.MDP3",
        symbols=["ES.v.0"],
        stype_in="continuous",
        schema="ohlcv-1m",
        start=start,
        end=end,
    )
    return data.to_df().reset_index()


if __name__ == "__main__":
    output_dir = DATA_DIR / "databento_es_minute"
    output_dir.mkdir(parents=True, exist_ok=True)
    first_date = max(FIRST_AVAILABLE_DATE, pd.Timestamp(START_DATE))
    last_date = pd.Timestamp(END_DATE)

    client = db.Historical(DATABENTO_API_KEY)
    for year in range(first_date.year, last_date.year + 1):
        path = output_dir / f"databento_es_minute_{year}.parquet"
        if path.exists():
            print(f"{year}: already downloaded, skipping")
            continue
        start = max(first_date, pd.Timestamp(year=year, month=1, day=1))
        end = min(last_date, pd.Timestamp(year=year, month=12, day=31))
        end = end + pd.Timedelta(days=1)
        df = pull_es_minute_bars(
            client, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
        )
        df.to_parquet(path)
        print(f"{year}: saved {len(df):,} rows")