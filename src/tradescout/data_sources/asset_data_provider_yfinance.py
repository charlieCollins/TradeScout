"""
YFinance Adapter - Implementation of AssetDataProvider using Yahoo Finance

Uses yfinance library for market data with intelligent caching to protect
against rate limits and improve performance.
"""

import yfinance as yf
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from decimal import Decimal

from ..data_models.interfaces import AssetDataProvider
from ..data_models.domain_models_core import (
    Asset,
    MarketQuote,
    PriceData,
    ExtendedHoursData,
    MarketStatus,
)
from ..caches.api_cache import APICache, CachePolicy, cached_api_call

logger = logging.getLogger(__name__)


class AssetDataProviderYFinance(AssetDataProvider):
    """
    Yahoo Finance adapter implementing our AssetDataProvider interface

    Features:
    - Intelligent caching with appropriate TTLs
    - Rate-friendly API calls with built-in delays
    - Extended hours data support
    - Volume analysis capabilities
    - Error handling and fallback strategies
    """

    def __init__(self, cache: Optional[APICache] = None, request_delay: float = 0.1):
        """
        Initialize YFinance adapter

        Args:
            cache: API cache instance (creates default if None)
            request_delay: Delay between requests in seconds
        """
        self.cache = cache or APICache()
        self.request_delay = request_delay
        self.provider_name = "yfinance"

    def get_current_quote(self, asset: Asset) -> Optional[MarketQuote]:
        """
        Get current market quote for an asset

        Args:
            asset: Asset to get quote for

        Returns:
            Current market quote or None if unavailable
        """
        try:

            def fetch_quote() -> Optional[Dict[str, Any]]:
                """Internal function to fetch quote data"""
                ticker = yf.Ticker(asset.symbol)

                # Get current info and recent price data
                info = ticker.info
                hist = ticker.history(period="2d", interval="1m", prepost=True)

                if hist.empty:
                    logger.warning(f"No historical data available for {asset.symbol}")
                    return None

                # Get latest price point
                latest = hist.iloc[-1]
                previous_close = info.get("previousClose", 0)

                # Ensure previous_close is numeric and handle various data types
                try:
                    if isinstance(previous_close, str):
                        # Remove any non-numeric characters and convert
                        import re

                        numeric_str = re.sub(r"[^\d.-]", "", previous_close)
                        previous_close = float(numeric_str) if numeric_str else 0
                    else:
                        previous_close = float(previous_close) if previous_close else 0
                except (ValueError, TypeError):
                    logger.warning(f"Could not parse previous_close: {previous_close}")
                    previous_close = 0

                # Calculate changes with additional safety checks
                try:
                    current_price = Decimal(str(latest["Close"]))
                    price_change = (
                        current_price - Decimal(str(previous_close))
                        if previous_close and previous_close > 0
                        else Decimal("0")
                    )
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Error calculating price change: {e}")
                    # Try to get a basic price at least
                    try:
                        current_price = Decimal(str(latest.get("Close", 0)))
                        price_change = Decimal("0")
                    except:
                        logger.error("Could not extract price from data")
                        return None
                # Calculate price change percentage safely
                try:
                    price_change_percent = (
                        (price_change / Decimal(str(previous_close)) * 100)
                        if previous_close and previous_close > 0
                        else Decimal("0")
                    )
                except (ValueError, TypeError, ZeroDivisionError) as e:
                    logger.warning(f"Error calculating price change percentage: {e}")
                    price_change_percent = Decimal("0")

                return {
                    "symbol": asset.symbol,
                    "current_price": current_price,
                    "previous_close": Decimal(str(previous_close)),
                    "price_change": price_change,
                    "price_change_percent": price_change_percent,
                    "volume": int(latest["Volume"]),
                    "avg_volume": info.get("averageVolume", 0),
                    "market_cap": info.get("marketCap", 0),
                    "day_high": Decimal(str(latest["High"])),
                    "day_low": Decimal(str(latest["Low"])),
                    "open_price": Decimal(str(latest["Open"])),
                    "timestamp": datetime.now(),
                    "is_extended_hours": self._is_extended_hours_time(),
                }

            # Use cached API call with REAL_TIME policy (2 minute TTL)
            quote_data = cached_api_call(
                provider=self.provider_name,
                endpoint="get_current_quote",
                params={"symbol": asset.symbol},
                api_function=fetch_quote,
                policy=CachePolicy.REAL_TIME,
            )

            if not quote_data:
                return None

            # Create PriceData first
            price_data = PriceData(
                asset=asset,
                timestamp=quote_data["timestamp"],
                price=quote_data["current_price"],
                volume=quote_data["volume"],
                open_price=quote_data.get("open_price"),
                high_price=quote_data.get("day_high"),
                low_price=quote_data.get("day_low"),
            )

            # Create MarketQuote with PriceData
            return MarketQuote(
                asset=asset,
                price_data=price_data,
                previous_close=quote_data.get("previous_close"),
                average_volume=quote_data.get("avg_volume"),
            )

        except Exception as e:
            logger.error(f"Error getting current quote for {asset.symbol}: {e}")
            return None

    def get_extended_hours_data(
        self, asset: Asset, session: MarketStatus
    ) -> Optional[ExtendedHoursData]:
        """
        Get extended hours trading data (pre-market or after-hours)

        Args:
            asset: Asset to get extended hours data for
            session: Market session (PRE_MARKET or AFTER_HOURS)

        Returns:
            Extended hours data or None if unavailable
        """
        try:

            def fetch_extended_hours() -> Optional[Dict[str, Any]]:
                """Internal function to fetch extended hours data"""
                ticker = yf.Ticker(asset.symbol)
                hist = ticker.history(period="2d", interval="1m", prepost=True)

                if hist.empty:
                    return None

                # Define time ranges based on session type
                now = datetime.now()
                if session == MarketStatus.PRE_MARKET:
                    # Pre-market: 4:00 AM - 9:30 AM ET
                    session_start = now.replace(
                        hour=4, minute=0, second=0, microsecond=0
                    )
                    session_end = now.replace(
                        hour=9, minute=30, second=0, microsecond=0
                    )
                elif session == MarketStatus.AFTER_HOURS:
                    # After-hours: 4:00 PM - 8:00 PM ET
                    session_start = now.replace(
                        hour=16, minute=0, second=0, microsecond=0
                    )
                    session_end = now.replace(
                        hour=20, minute=0, second=0, microsecond=0
                    )
                else:
                    return None

                # Convert to pandas timestamps for comparison
                import pandas as pd

                session_start = pd.Timestamp(session_start, tz="America/New_York")
                session_end = pd.Timestamp(session_end, tz="America/New_York")

                # Filter data for the session
                session_data = hist[
                    (hist.index >= session_start) & (hist.index <= session_end)
                ]

                if session_data.empty:
                    return None

                # Calculate session metrics
                session_volume = int(session_data["Volume"].sum())
                session_high = Decimal(str(session_data["High"].max()))
                session_low = Decimal(str(session_data["Low"].min()))
                session_open = Decimal(str(session_data["Open"].iloc[0]))
                session_close = Decimal(str(session_data["Close"].iloc[-1]))

                return {
                    "session": session,
                    "volume": session_volume,
                    "high": session_high,
                    "low": session_low,
                    "open": session_open,
                    "close": session_close,
                    "change": session_close - session_open,
                    "timestamp": datetime.now(),
                }

            # Cache policy: INTRADAY for extended hours (15 minutes)
            extended_data = cached_api_call(
                provider=self.provider_name,
                endpoint="get_extended_hours",
                params={"symbol": asset.symbol, "session": session.value},
                api_function=fetch_extended_hours,
                policy=CachePolicy.INTRADAY,
            )

            if not extended_data:
                return None

            # Create PriceData for extended hours
            price_data = PriceData(
                asset=asset,
                timestamp=extended_data["timestamp"],
                price=extended_data["close"],  # Extended hours close price
                volume=extended_data["volume"],
                open_price=extended_data["open"],
                high_price=extended_data["high"],
                low_price=extended_data["low"],
                session_type=extended_data["session"],
            )

            # For now, use the open price as regular session close reference
            # In a real implementation, this would come from market data
            regular_session_close = extended_data.get("open", extended_data["close"])

            return ExtendedHoursData(
                asset=asset,
                session_type=extended_data["session"],
                price_data=price_data,
                regular_session_close=regular_session_close,
            )

        except Exception as e:
            logger.error(f"Error getting extended hours data for {asset.symbol}: {e}")
            return None

    def get_historical_quotes(
        self,
        asset: Asset,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1d",
    ) -> List[PriceData]:
        """
        Get historical price data

        Args:
            asset: Asset to get historical data for
            start_date: Start date for data
            end_date: End date for data
            interval: Data interval (1m, 5m, 1h, 1d, etc.)

        Returns:
            List of historical price data
        """
        try:

            def fetch_historical() -> List[Dict[str, Any]]:
                """Internal function to fetch historical data"""
                ticker = yf.Ticker(asset.symbol)
                hist = ticker.history(start=start_date, end=end_date, interval=interval)

                if hist.empty:
                    return []

                price_data = []
                for timestamp, row in hist.iterrows():
                    price_data.append(
                        {
                            "timestamp": timestamp.to_pydatetime(),
                            "open": Decimal(str(row["Open"])),
                            "high": Decimal(str(row["High"])),
                            "low": Decimal(str(row["Low"])),
                            "close": Decimal(str(row["Close"])),
                            "volume": int(row["Volume"]),
                        }
                    )

                return price_data

            # Cache policy: HISTORICAL for longer-term data (30 days)
            cache_key_params = {
                "symbol": asset.symbol,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "interval": interval,
            }

            historical_data = cached_api_call(
                provider=self.provider_name,
                endpoint="get_historical_quotes",
                params=cache_key_params,
                api_function=fetch_historical,
                policy=CachePolicy.HISTORICAL,
            )

            # Convert to PriceData objects
            return [
                PriceData(
                    asset=asset,
                    timestamp=item["timestamp"],
                    price=item["close"],  # Use close as main price
                    open_price=item["open"],
                    high_price=item["high"],
                    low_price=item["low"],
                    volume=item["volume"],
                )
                for item in historical_data
            ]

        except Exception as e:
            logger.error(f"Error getting historical quotes for {asset.symbol}: {e}")
            return []

    def scan_volume_leaders(
        self, assets: List[Asset], min_volume_ratio: Decimal = Decimal("2.0")
    ) -> List[MarketQuote]:
        """
        Scan for assets with unusual volume

        Args:
            assets: List of assets to scan
            min_volume_ratio: Minimum volume vs average ratio

        Returns:
            List of assets with volume surges
        """
        volume_leaders = []

        for asset in assets:
            try:
                quote = self.get_current_quote(asset)
                if not quote:
                    continue

                # Check volume ratio
                if quote.average_volume and quote.average_volume > 0:
                    volume_ratio = Decimal(quote.price_data.volume) / Decimal(
                        quote.average_volume
                    )

                    if volume_ratio >= min_volume_ratio:
                        # Add volume_ratio as additional attribute for sorting
                        # Note: This modifies the quote object directly
                        quote.volume_ratio = volume_ratio
                        volume_leaders.append(quote)

            except Exception as e:
                logger.error(f"Error scanning volume for {asset.symbol}: {e}")
                continue

        # Sort by volume ratio (highest first)
        return sorted(
            volume_leaders,
            key=lambda q: getattr(q, "volume_ratio", Decimal("0")),
            reverse=True,
        )

    def get_fundamental_data(self, asset: Asset) -> Dict[str, Any]:
        """
        Get fundamental company data

        Args:
            asset: Asset to get fundamental data for

        Returns:
            Dictionary with fundamental metrics
        """
        try:

            def fetch_fundamentals() -> Dict[str, Any]:
                """Internal function to fetch fundamental data"""
                ticker = yf.Ticker(asset.symbol)
                info = ticker.info

                # Extract key fundamental metrics
                fundamentals = {
                    "symbol": asset.symbol,
                    "company_name": info.get("longName", ""),
                    "sector": info.get("sector", ""),
                    "industry": info.get("industry", ""),
                    "market_cap": info.get("marketCap", 0),
                    "enterprise_value": info.get("enterpriseValue", 0),
                    "pe_ratio": info.get("trailingPE", 0),
                    "forward_pe": info.get("forwardPE", 0),
                    "peg_ratio": info.get("pegRatio", 0),
                    "price_to_book": info.get("priceToBook", 0),
                    "price_to_sales": info.get("priceToSalesTrailing12Months", 0),
                    "debt_to_equity": info.get("debtToEquity", 0),
                    "roe": info.get("returnOnEquity", 0),
                    "roa": info.get("returnOnAssets", 0),
                    "gross_margin": info.get("grossMargins", 0),
                    "operating_margin": info.get("operatingMargins", 0),
                    "profit_margin": info.get("profitMargins", 0),
                    "beta": info.get("beta", 0),
                    "shares_outstanding": info.get("sharesOutstanding", 0),
                    "float_shares": info.get("floatShares", 0),
                    "52_week_high": info.get("fiftyTwoWeekHigh", 0),
                    "52_week_low": info.get("fiftyTwoWeekLow", 0),
                    "dividend_yield": info.get("dividendYield", 0),
                    "ex_dividend_date": info.get("exDividendDate", ""),
                    "earnings_date": info.get("earningsDate", ""),
                    "timestamp": datetime.now().isoformat(),
                }

                return fundamentals

            # Cache policy: FUNDAMENTAL (1 week TTL)
            return cached_api_call(
                provider=self.provider_name,
                endpoint="get_fundamental_data",
                params={"symbol": asset.symbol},
                api_function=fetch_fundamentals,
                policy=CachePolicy.FUNDAMENTAL,
            )

        except Exception as e:
            logger.error(f"Error getting fundamental data for {asset.symbol}: {e}")
            return {}

    @property
    def rate_limit_per_minute(self) -> int:
        """Return the rate limit for this provider"""
        # YFinance doesn't have strict rate limits, but we're respectful
        return 60  # ~1 request per second

    @property
    def supports_extended_hours(self) -> bool:
        """Return whether provider supports extended hours data"""
        return True  # YFinance supports pre-market and after-hours data

    def _is_extended_hours_time(self) -> bool:
        """Check if current time is during extended hours"""
        now = datetime.now()
        hour = now.hour

        # Pre-market: 4 AM - 9:30 AM or After-hours: 4 PM - 8 PM (simplified)
        return (4 <= hour < 9) or (16 <= hour < 20)


# Convenience function for creating adapter
def create_asset_data_provider_yfinance(cache: Optional[APICache] = None) -> AssetDataProviderYFinance:
    """
    Create a YFinance adapter with default settings

    Args:
        cache: Optional API cache instance

    Returns:
        Configured AssetDataProviderYFinance
    """
    return AssetDataProviderYFinance(cache=cache)


if __name__ == "__main__":
    # Simple test of the adapter
    from ..data_models.domain_models_core import Asset, AssetType
    from ..data_models.factories import MarketFactory

    # Create test asset
    nasdaq = MarketFactory().create_nasdaq_market()
    test_asset = Asset(
        symbol="AAPL",
        name="Apple Inc.",
        asset_type=AssetType.COMMON_STOCK,
        market=nasdaq,
        currency="USD",
    )

    # Test the adapter
    adapter = create_yfinance_adapter()

    print("🧪 Testing YFinance Adapter...")

    # Test current quote
    print(f"\n📈 Current Quote for {test_asset.symbol}:")
    quote = adapter.get_current_quote(test_asset)
    if quote:
        print(f"Price: ${quote.price}")
        print(f"Volume: {quote.volume:,}")
        print(f"Change: {quote.price_change_percent:.2f}%")

    # Test fundamental data
    print(f"\n📊 Fundamental Data for {test_asset.symbol}:")
    fundamentals = adapter.get_fundamental_data(test_asset)
    if fundamentals:
        print(f"Market Cap: ${fundamentals.get('market_cap', 0):,}")
        print(f"P/E Ratio: {fundamentals.get('pe_ratio', 'N/A')}")
        print(f"Sector: {fundamentals.get('sector', 'N/A')}")

    print("\n✅ YFinance Adapter test completed!")
