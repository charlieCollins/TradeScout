#!/usr/bin/env python3
"""
Ticker Bootstrap Script

Manually run this script to update ticker/asset data from Polygon.io.
Should be run periodically (weekly/monthly) to keep ticker data current.

Usage:
    python -m tradescout.scripts.bootstrap_tickers --help
    python -m tradescout.scripts.bootstrap_tickers --stats-only
    python -m tradescout.scripts.bootstrap_tickers --market-types stocks etf
    python -m tradescout.scripts.bootstrap_tickers --min-market-cap 100000000
"""

from ..bootstrapping.polygon_ticker_bootstrapper import main

if __name__ == "__main__":
    main()
