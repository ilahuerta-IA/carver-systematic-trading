# Carver Systematic Trading

Systematic portfolio trading system based on Robert Carver's "Advanced Futures Trading Strategies".

## Overview

Multi-asset trend following + carry system operating on daily timeframe with continuous position sizing via volatility targeting. Zero optimized parameters — all values from published literature.

## Key Principles

- **EWMAC** (Exponentially Weighted Moving Average Crossover) for trend signals
- **Carry** (interest rate differentials) as complementary signal
- **Volatility Targeting** for position sizing and risk management
- **Buffering** to minimize transaction costs
- **Multi-asset diversification** (equity, bonds, commodities, FX)

## Architecture

```
core/       - Forecast calculation, vol targeting, position sizing, buffering
backtest/   - Pandas-based daily backtest engine with plotting
live/       - MT5 connector for daily position adjustments
config/     - Instrument definitions, portfolio parameters
tools/      - Data download, analysis, validation utilities
data/       - Daily OHLCV from Yahoo Finance
```

## Data

- **Backtest**: Yahoo Finance daily OHLCV (20+ years, free)
- **Live**: MT5 feed (Darwinex)

## Status

Work in progress.

## License

MIT
