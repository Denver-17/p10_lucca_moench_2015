"""Pull SPY one-minute bars from WRDS Daily TAQ, 2003 onward.

For each trading day, keep the last trade price and total volume in each
minute between 9:30 and 16:00 (including the closing auction at 16:00).
Saves one parquet file per year in DATA_DIR/taq_spy_minute/.
"""
import re
from pathlib import Path

import pandas as pd
import wrds

from settings import config

DATA_DIR = Path(config("DATA_DIR"))
START_DATE = config("START_DATE")
END_DATE = config("END_DATE")
WRDS_USERNAME = config("WRDS_USERNAME")

def get_trading_days(db, year):
    """Return the daily TAQ trade tables (one per trading day) for a given year."""
    tables = db.list_tables(f"taqm_{year}")
    day_tables = [t for t in tables if re.fullmatch(r"ctm_\d{8}", t)]
    return sorted(day_tables)

def pull_one_day(db, year, table):
    """Return SPY one-minute bars (last trade price, volume) for one trading day."""
    query = f"""
        select date_trunc('minute', date + time_m) as minute,
               (array_agg(price order by time_m desc))[1] as last_price,
               sum(size) as volume
        from taqm_{year}.{table}
        where sym_root = 'SPY' and sym_suffix is null
          and tr_corr = '00'
          and time_m between '09:30:00' and '16:00:59'
        group by 1
        order by 1
    """
    return db.raw_sql(query)

def pull_one_year(db, year, output_dir):
    """Pull SPY one-minute bars for every trading day in a year and save to parquet."""
    tables = get_trading_days(db, year)
    daily_bars = []
    for i, table in enumerate(tables, start=1):
        daily_bars.append(pull_one_day(db, year, table))
        print(f"{year}: {i}/{len(tables)} days", end="\r")
    df = pd.concat(daily_bars, ignore_index=True)

    output_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_dir / f"taq_spy_minute_{year}.parquet")
    print(f"\n{year}: saved {len(df):,} rows")
    return df

if __name__ == "__main__":
    output_dir = DATA_DIR / "taq_spy_minute"
    first_year = max(2003, pd.Timestamp(START_DATE).year)
    last_year = pd.Timestamp(END_DATE).year

    db = wrds.Connection(wrds_username=WRDS_USERNAME)
    for year in range(first_year, last_year + 1):
        if (output_dir / f"taq_spy_minute_{year}.parquet").exists():
            print(f"{year}: already downloaded, skipping")
            continue
        pull_one_year(db, year, output_dir)
    db.close()