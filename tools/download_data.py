"""
Download daily OHLCV data from Yahoo Finance for all instruments.
Saves to data/ folder in CSV format.

Usage:
    python tools/download_data.py          # Download all instruments
    python tools/download_data.py SPY QQQ  # Download specific tickers
"""

import sys
import os
from pathlib import Path
from datetime import datetime

try:
    import yfinance as yf
    import pandas as pd
except ImportError:
    print("ERROR: Install dependencies first: pip install yfinance pandas")
    sys.exit(1)


# Instrument definitions: ticker -> descriptive name
INSTRUMENTS = {
    # Equity Indices
    "SPY": "SP500",
    "QQQ": "NASDAQ100",
    "^GDAXI": "DAX40",
    "^N225": "NIKKEI225",
    # Commodities
    "GC=F": "GOLD",
    "SI=F": "SILVER",
    # Forex
    "EURUSD=X": "EURUSD",
    "USDJPY=X": "USDJPY",
    "AUDUSD=X": "AUDUSD",
    "GBPUSD=X": "GBPUSD",
}

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
START_DATE = "2000-01-01"


def download_instrument(ticker, name):
    """Download daily OHLCV for a single instrument."""
    print(f"  Downloading {name} ({ticker})...", end=" ")
    try:
        df = yf.download(
            ticker,
            start=START_DATE,
            end=datetime.now().strftime("%Y-%m-%d"),
            interval="1d",
            auto_adjust=True,
            progress=False,
        )

        if df.empty:
            print("EMPTY - no data returned")
            return False

        # Flatten multi-level columns if present (yfinance >= 0.2.31)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Keep only OHLCV
        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.index.name = "Date"

        # Drop rows with all NaN
        df.dropna(how="all", inplace=True)

        # Save
        filepath = DATA_DIR / f"{name}_daily.csv"
        df.to_csv(filepath)

        years = (df.index[-1] - df.index[0]).days / 365.25
        print(f"OK - {len(df)} bars, {years:.1f} years ({df.index[0].date()} to {df.index[-1].date()})")
        return True

    except Exception as e:
        print(f"ERROR - {e}")
        return False


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Filter by command-line args if provided
    if len(sys.argv) > 1:
        tickers_to_download = {}
        for arg in sys.argv[1:]:
            arg_upper = arg.upper()
            # Match by ticker or by name
            for ticker, name in INSTRUMENTS.items():
                if arg_upper in (ticker.upper(), name.upper()):
                    tickers_to_download[ticker] = name
                    break
            else:
                print(f"WARNING: '{arg}' not found in instrument list, skipping")
        instruments = tickers_to_download
    else:
        instruments = INSTRUMENTS

    print(f"Downloading {len(instruments)} instruments to {DATA_DIR}/")
    print(f"Date range: {START_DATE} to {datetime.now().strftime('%Y-%m-%d')}")
    print("-" * 60)

    success = 0
    failed = 0
    for ticker, name in instruments.items():
        if download_instrument(ticker, name):
            success += 1
        else:
            failed += 1

    print("-" * 60)
    print(f"Done: {success} OK, {failed} failed")


if __name__ == "__main__":
    main()
