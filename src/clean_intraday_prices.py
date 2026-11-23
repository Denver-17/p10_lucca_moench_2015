"""Clean intraday minute bars into one row per trading day.

Reads the SPY (TAQ) and E-mini (Databento) one-minute bars and keeps, for each
trading day, the price at the open (9:30), at 2pm, and at the close (4pm),
plus total volume in regular trading hours. All times are US Eastern.
Saves DATA_DIR/clean_intraday_prices.parquet.
"""

from datetime import time
from pathlib import Path

import pandas as pd

from settings import config

DATA_DIR = Path(config("DATA_DIR"))

MARKET_OPEN = time(9, 30)
OPEN_CUTOFF = time(9, 31)
TWO_PM_CUTOFF = time(14, 0)
CLOSE_CUTOFF = time(16, 1)


def load_spy_bars(data_dir=DATA_DIR):
    """Load SPY one-minute bars (timestamps are already in US Eastern time)."""
    files = sorted((data_dir / "taq_spy_minute").glob("*.parquet"))
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    df = df.rename(columns={"last_price": "price"})
    df[["price", "volume"]] = df[["price", "volume"]].astype(float)
    return df[["minute", "price", "volume"]]


def load_es_bars(data_dir=DATA_DIR):
    """Load E-mini one-minute bars and convert timestamps from UTC to US Eastern."""
    files = sorted((data_dir / "databento_es_minute").glob("*.parquet"))
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    eastern = df["ts_event"].dt.tz_convert("America/New_York")
    df["minute"] = eastern.dt.tz_localize(None)
    df = df.rename(columns={"close": "price"})
    df[["price", "volume"]] = df[["price", "volume"]].astype(float)
    return df[["minute", "price", "volume"]]


def get_price_at_time(bars, cutoff):
    """Return each day's last price before a clock time (e.g. the price as of 2pm)."""
    before = bars[bars["minute"].dt.time < cutoff]
    return before.groupby(before["minute"].dt.date)["price"].last()


def build_daily_prices(bars):
    """Return one row per day: open, 2pm and close prices, and regular-hours volume."""
    bars = bars.sort_values("minute")
    clock = bars["minute"].dt.time
    bars = bars[(clock >= MARKET_OPEN) & (clock < CLOSE_CUTOFF)]
    daily = pd.DataFrame(
        {
            "price_open": get_price_at_time(bars, OPEN_CUTOFF),
            "price_2pm": get_price_at_time(bars, TWO_PM_CUTOFF),
            "price_close": get_price_at_time(bars, CLOSE_CUTOFF),
            "volume": bars.groupby(bars["minute"].dt.date)["volume"].sum(),
        }
    )
    daily.index = pd.to_datetime(daily.index)
    return daily.rename_axis("date").reset_index()


if __name__ == "__main__":
    spy = build_daily_prices(load_spy_bars()).assign(source="spy")
    es = build_daily_prices(load_es_bars()).assign(source="es")
    es = es[es["date"].isin(spy["date"])]
    df = pd.concat([spy, es], ignore_index=True)
    df.to_parquet(DATA_DIR / "clean_intraday_prices.parquet")
    print(df.groupby("source")["date"].agg(["min", "max", "count"]))
    