"""
YFinance Scanner - Real-time and After-hours Data Collection

Uses Yahoo Finance (via yfinance) for:
- Real-time market prices
- After-hours and pre-market data
- Volume analysis
- Quick market scanning

Free and unlimited API calls.
"""

import yfinance as yf
import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import time

logger = logging.getLogger(__name__)


class YFinanceScanner:
    """Scanner for real-time market data using Yahoo Finance"""

    def __init__(self, delay_seconds: float = 0.1):
        """
        Initialize YFinance Scanner

        Args:
            delay_seconds: Delay between API calls to be respectful
        """
        self.delay_seconds = delay_seconds
        self.cache = {}
        self.cache_timeout = 60  # Cache data for 1 minute

    def get_real_time_quote(self, symbol: str) -> Dict[str, Any]:
        """
        Get real-time quote for a symbol

        Args:
            symbol: Stock symbol (e.g., 'AAPL')

        Returns:
            Dictionary with current price, volume, and market status
        """
        try:
            # Check cache first
            cache_key = f"quote_{symbol}"
            if self._is_cached_valid(cache_key):
                return self.cache[cache_key]["data"]

            ticker = yf.Ticker(symbol)
            info = ticker.info

            # Get recent price data
            hist = ticker.history(period="1d", interval="1m", prepost=True)

            if hist.empty:
                logger.warning(f"No data available for {symbol}")
                return {}

            latest = hist.iloc[-1]

            quote_data = {
                "symbol": symbol,
                "timestamp": datetime.now(),
                "current_price": float(latest["Close"]),
                "volume": int(latest["Volume"]),
                "open": float(latest["Open"]),
                "high": float(latest["High"]),
                "low": float(latest["Low"]),
                "previous_close": info.get("previousClose", 0),
                "market_cap": info.get("marketCap", 0),
                "avg_volume": info.get("averageVolume", 0),
                "is_after_hours": self._is_after_hours(),
                "price_change": 0,
                "price_change_percent": 0,
            }

            # Calculate price change
            if quote_data["previous_close"] > 0:
                quote_data["price_change"] = (
                    quote_data["current_price"] - quote_data["previous_close"]
                )
                quote_data["price_change_percent"] = (
                    quote_data["price_change"] / quote_data["previous_close"]
                ) * 100

            # Cache the result
            self.cache[cache_key] = {"data": quote_data, "timestamp": datetime.now()}

            time.sleep(self.delay_seconds)
            return quote_data

        except Exception as e:
            logger.error(f"Error getting quote for {symbol}: {e}")
            return {}

    def get_after_hours_data(self, symbol: str) -> Dict[str, Any]:
        """
        Get after-hours trading data

        Args:
            symbol: Stock symbol

        Returns:
            After-hours price and volume data
        """
        try:
            ticker = yf.Ticker(symbol)

            # Get extended hours data
            hist = ticker.history(period="1d", interval="1m", prepost=True)

            if hist.empty:
                return {}

            # Filter for after-hours (4 PM - 8 PM ET)
            market_close = hist.index[-1].replace(
                hour=16, minute=0, second=0, microsecond=0
            )
            after_hours_end = market_close + timedelta(hours=4)

            after_hours_data = hist[
                (hist.index > market_close) & (hist.index <= after_hours_end)
            ]

            if after_hours_data.empty:
                return {"has_after_hours_activity": False}

            return {
                "symbol": symbol,
                "has_after_hours_activity": True,
                "after_hours_volume": int(after_hours_data["Volume"].sum()),
                "after_hours_high": float(after_hours_data["High"].max()),
                "after_hours_low": float(after_hours_data["Low"].min()),
                "after_hours_close": float(after_hours_data["Close"].iloc[-1]),
                "after_hours_change": float(
                    after_hours_data["Close"].iloc[-1]
                    - after_hours_data["Open"].iloc[0]
                ),
                "timestamp": datetime.now(),
            }

        except Exception as e:
            logger.error(f"Error getting after-hours data for {symbol}: {e}")
            return {}

    def get_pre_market_data(self, symbol: str) -> Dict[str, Any]:
        """
        Get pre-market trading data

        Args:
            symbol: Stock symbol

        Returns:
            Pre-market price and volume data
        """
        try:
            ticker = yf.Ticker(symbol)

            # Get today's extended hours data
            hist = ticker.history(period="1d", interval="1m", prepost=True)

            if hist.empty:
                return {}

            # Filter for pre-market (4 AM - 9:30 AM ET)
            today = datetime.now().replace(hour=4, minute=0, second=0, microsecond=0)
            market_open = today.replace(hour=9, minute=30)

            pre_market_data = hist[(hist.index >= today) & (hist.index < market_open)]

            if pre_market_data.empty:
                return {"has_pre_market_activity": False}

            # Calculate gap from previous close
            previous_close = ticker.info.get("previousClose", 0)
            current_price = float(pre_market_data["Close"].iloc[-1])
            gap_percent = (
                ((current_price - previous_close) / previous_close * 100)
                if previous_close > 0
                else 0
            )

            return {
                "symbol": symbol,
                "has_pre_market_activity": True,
                "pre_market_volume": int(pre_market_data["Volume"].sum()),
                "pre_market_high": float(pre_market_data["High"].max()),
                "pre_market_low": float(pre_market_data["Low"].min()),
                "pre_market_price": current_price,
                "previous_close": previous_close,
                "gap_amount": current_price - previous_close,
                "gap_percent": gap_percent,
                "is_gap_up": gap_percent > 0,
                "timestamp": datetime.now(),
            }

        except Exception as e:
            logger.error(f"Error getting pre-market data for {symbol}: {e}")
            return {}

    def scan_volume_leaders(
        self, symbols: List[str], min_volume_ratio: float = 2.0
    ) -> List[Dict[str, Any]]:
        """
        Scan for stocks with unusual volume

        Args:
            symbols: List of symbols to scan
            min_volume_ratio: Minimum volume ratio vs average (e.g., 2.0 = 2x normal)

        Returns:
            List of stocks with unusual volume
        """
        volume_leaders = []

        for symbol in symbols:
            try:
                quote = self.get_real_time_quote(symbol)

                if not quote or quote.get("avg_volume", 0) == 0:
                    continue

                current_volume = quote.get("volume", 0)
                avg_volume = quote.get("avg_volume", 1)
                volume_ratio = current_volume / avg_volume

                if volume_ratio >= min_volume_ratio:
                    quote["volume_ratio"] = volume_ratio
                    quote["volume_surge"] = True
                    volume_leaders.append(quote)

                time.sleep(self.delay_seconds)

            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")
                continue

        # Sort by volume ratio (highest first)
        return sorted(
            volume_leaders, key=lambda x: x.get("volume_ratio", 0), reverse=True
        )

    def get_historical_data(
        self, symbol: str, period: str = "1mo", interval: str = "1d"
    ) -> pd.DataFrame:
        """
        Get historical price data

        Args:
            symbol: Stock symbol
            period: Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
            interval: Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)

        Returns:
            Historical price DataFrame
        """
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period, interval=interval)
            time.sleep(self.delay_seconds)
            return hist

        except Exception as e:
            logger.error(f"Error getting historical data for {symbol}: {e}")
            return pd.DataFrame()

    def _is_after_hours(self) -> bool:
        """Check if current time is after market hours"""
        now = datetime.now()
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        after_hours_end = now.replace(hour=20, minute=0, second=0, microsecond=0)

        return market_close <= now <= after_hours_end

    def _is_cached_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid"""
        if cache_key not in self.cache:
            return False

        cache_time = self.cache[cache_key]["timestamp"]
        return (datetime.now() - cache_time).seconds < self.cache_timeout


# Utility function for easy import
def create_scanner() -> YFinanceScanner:
    """Create a YFinanceScanner instance with default settings"""
    return YFinanceScanner()


if __name__ == "__main__":
    # Test the scanner
    scanner = YFinanceScanner()

    # Test symbols
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]

    print("Testing YFinance Scanner...")

    for symbol in symbols[:2]:  # Test first 2 symbols
        print(f"\n--- {symbol} ---")

        # Real-time quote
        quote = scanner.get_real_time_quote(symbol)
        if quote:
            print(f"Current Price: ${quote['current_price']:.2f}")
            print(f"Volume: {quote['volume']:,}")
            print(f"Change: {quote['price_change_percent']:.2f}%")

        # Pre-market data
        pre_market = scanner.get_pre_market_data(symbol)
        if pre_market.get("has_pre_market_activity"):
            print(f"Pre-market Gap: {pre_market['gap_percent']:.2f}%")

    print("\nScanner test completed!")
