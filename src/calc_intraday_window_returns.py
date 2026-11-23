"""Compute intraday window returns and relative volume from daily intraday prices.

Reads DATA_DIR/clean_intraday_prices.parquet and computes, for SPY and E-mini,
log price returns (in percent) over the windows used in Table 2 of Lucca and
Moench (2015), plus volume relative to its prior 21-day average.
Saves DATA_DIR/intraday_window_returns.parquet.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from settings import config

DATA_DIR = Path(config("DATA_DIR"))


def calc_window_returns(prices):
    """Return log price returns (percent) over each window, one row per day."""
    log_2pm = np.log(prices["price_2pm"])
    log_close = np.log(prices["price_close"])
    returns = pd.DataFrame({"date": prices["date"]})
    returns["r_2pm2pm"] = 100 * (log_2pm - log_2pm.shift(1))
    returns["r_2pm_close"] = 100 * (log_close - log_2pm)
    returns["r_close_2pm"] = 100 * (log_2pm - log_close.shift(1))
    returns["r_close2_2pm"] = 100 * (log_2pm - log_close.shift(2))
    returns["r_close_close"] = 100 * (log_close - log_close.shift(1))
    return returns


def calc_relative_volume(prices):
    """Return each day's volume divided by its average over the prior 21 days."""
    prior_average = prices["volume"].shift(1).rolling(21).mean()
    return prices["volume"] / prior_average


def add_dividends_and_rf(window_returns, daily):
    """Turn raw log price returns into cum-dividend log excess returns (percent).

    daily: one row per day from the daily-returns step, in decimals
    (ret, retx, rf), where ret and retx are SPY's own returns.
    """
    df = window_returns.merge(
        daily[["date", "ret", "retx", "rf"]], on="date", how="left"
    ).sort_values("date")
    div = 100 * (np.log1p(df["ret"]) - np.log1p(df["retx"]))
    rf = 100 * np.log1p(df["rf"])
    df["rx_2pm2pm"] = df["r_2pm2pm"] + div - rf
    df["rx_close_2pm"] = df["r_close_2pm"] + div - rf
    df["rx_close2_2pm"] = df["r_close2_2pm"] + div + div.shift(1) - rf - rf.shift(1)
    return df.drop(columns=["ret", "retx", "rf"])


if __name__ == "__main__":
    prices = pd.read_parquet(DATA_DIR / "clean_intraday_prices.parquet")
    trading_days = prices.loc[prices["source"] == "spy", "date"].sort_values()

    results = []
    for source, group in prices.groupby("source"):
        days = trading_days[trading_days >= group["date"].min()]
        group = group.set_index("date").reindex(days).rename_axis("date").reset_index()
        returns = calc_window_returns(group)
        returns["volume_rel"] = calc_relative_volume(group)
        returns["source"] = source
        results.append(returns)

    df = pd.concat(results, ignore_index=True)
    df.to_parquet(DATA_DIR / "intraday_window_returns.parquet")
    print(df.groupby("source")[["r_2pm2pm", "r_2pm_close", "r_close_2pm"]].mean())