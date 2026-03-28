"""
Download central bank interest rates from FRED (Federal Reserve Economic Data).

No API key needed -- uses direct CSV export URLs.
Saves to data/interest_rates.csv (monthly rates, % per annum).

Usage:
    python tools/download_rates.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import numpy as np


# FRED series IDs for central bank policy rates (monthly, % per annum)
# All freely available at https://fred.stlouisfed.org/
FRED_SERIES = {
    "USD": "FEDFUNDS",            # Federal Funds Effective Rate
    "EUR": "ECBDFR",              # ECB Deposit Facility Rate (daily on FRED)
    "JPY": "IRSTCI01JPM156N",     # Japan Short-Term Rate (OECD)
    "AUD": "IRSTCI01AUM156N",     # Australia Short-Term Rate (OECD)
    "GBP": "IRSTCI01GBM156N",     # UK Short-Term Rate (OECD)
}

START_DATE = "2000-01-01"


def download_single_series(series_id, start_date=START_DATE):
    """
    Download a single FRED series as a DataFrame.

    Args:
        series_id: FRED series identifier (e.g. 'FEDFUNDS')
        start_date: start date string (YYYY-MM-DD)

    Returns:
        pd.DataFrame with DatetimeIndex and one column named after the series
    """
    url = (
        f"https://fred.stlouisfed.org/graph/fredgraph.csv"
        f"?id={series_id}&cosd={start_date}"
    )
    df = pd.read_csv(url, parse_dates=["observation_date"],
                     index_col="observation_date", na_values=".")
    df.index.name = "Date"
    df.columns = [series_id]
    return df


def download_all_rates():
    """
    Download all central bank rates from FRED and combine into one DataFrame.

    Returns:
        pd.DataFrame with columns: USD, EUR, JPY, AUD, GBP (rates in % p.a.)
    """
    frames = {}
    for currency, series_id in FRED_SERIES.items():
        print(f"  Downloading {currency} ({series_id})...", end=" ")
        try:
            df = download_single_series(series_id)
            # Convert to numeric, handling any non-numeric values
            df[series_id] = pd.to_numeric(df[series_id], errors="coerce")
            frames[currency] = df[series_id]
            n_rows = df[series_id].dropna().shape[0]
            first = df.index[0].strftime("%Y-%m")
            last = df.index[-1].strftime("%Y-%m")
            print(f"OK ({n_rows} rows, {first} to {last})")
        except Exception as e:
            print(f"FAILED: {e}")

    if not frames:
        raise RuntimeError("No rate series could be downloaded")

    # Combine all into one DataFrame (outer join to keep all dates)
    combined = pd.DataFrame(frames)

    # Some series are daily (ECBDFR), others monthly.
    # Resample everything to monthly (end of month) then forward-fill.
    combined = combined.resample("MS").last()  # month start frequency
    combined = combined.ffill()

    # Sort by date
    combined.sort_index(inplace=True)

    return combined


def main():
    print("Downloading central bank interest rates from FRED...")
    print(f"Start date: {START_DATE}\n")

    rates = download_all_rates()

    # Save to CSV
    out_path = ROOT / "data" / "interest_rates.csv"
    rates.to_csv(out_path, float_format="%.4f")
    print(f"\nSaved to {out_path}")
    print(f"Shape: {rates.shape}")
    print(f"\nLast 6 months:")
    print(rates.tail(6).to_string())

    # Summary
    print(f"\nRate ranges (% p.a.):")
    for col in rates.columns:
        s = rates[col].dropna()
        print(f"  {col}: {s.min():.2f}% to {s.max():.2f}% "
              f"(current: {s.iloc[-1]:.2f}%)")


if __name__ == "__main__":
    main()
