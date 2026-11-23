"""Tests for the intraday price cleaning and window-return calculations."""

from datetime import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from calc_intraday_window_returns import calc_window_returns
from clean_intraday_prices import get_price_at_time
from settings import config

DATA_DIR = Path(config("DATA_DIR"))
RETURNS_FILE = DATA_DIR / "intraday_window_returns.parquet"

# Fixed before looking at the result: SPY and E-mini track the same index,
# so their daily 2pm-to-2pm returns should be almost perfectly correlated.
MIN_SPY_ES_CORRELATION = 0.99


def test_price_at_time_is_last_price_before_cutoff():
    """The 2pm price is the 13:59 bar, not the 14:00 bar."""
    bars = pd.DataFrame(
        {
            "minute": pd.to_datetime(
                ["2020-01-02 13:58", "2020-01-02 13:59", "2020-01-02 14:00"]
            ),
            "price": [100.0, 101.0, 102.0],
        }
    )
    assert get_price_at_time(bars, time(14, 0)).iloc[0] == 101.0


def test_window_returns_add_up():
    """2pm-to-2pm equals the prior day's 2pm-to-close plus close-to-2pm."""
    prices = pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=4),
            "price_2pm": [100.0, 102.0, 101.0, 105.0],
            "price_close": [101.0, 101.5, 103.0, 104.0],
        }
    )
    returns = calc_window_returns(prices)
    pieces = returns["r_2pm_close"].shift(1) + returns["r_close_2pm"]
    np.testing.assert_allclose(returns["r_2pm2pm"].iloc[1:], pieces.iloc[1:])


@pytest.mark.skipif(not RETURNS_FILE.exists(), reason="needs downloaded data")
def test_spy_and_es_returns_agree():
    """Validation: SPY (TAQ) and E-mini (Databento) give the same daily returns."""
    df = pd.read_parquet(RETURNS_FILE)
    wide = df.pivot(index="date", columns="source", values="r_2pm2pm").dropna()
    assert wide["spy"].corr(wide["es"]) >= MIN_SPY_ES_CORRELATION
    