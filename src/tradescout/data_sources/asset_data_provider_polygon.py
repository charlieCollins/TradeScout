"""
Polygon.io Adapter - Implementation using Polygon.io API

Features both free and paid tiers with comprehensive market data.
Documentation: https://polygon.io/docs/stocks
"""

import logging
import requests
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
from ..caches.api_cache import cached_api_call, CachePolicy

logger = logging.getLogger(__name__)


class AssetDataProviderPolygon(AssetDataProvider):
    """
    Polygon.io adapter implementing AssetDataProvider interface
    
    Features:
    - Free tier: 5 API calls per minute
    - Paid tiers: Much higher limits + real-time data
    - Comprehensive market data including extended hours
    - High data quality and reliability
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Polygon adapter
        
        Args:
            api_key: Polygon.io API key (get from environment if None)
        """
        import os
        self.api_key = api_key or os.getenv("POLYGON_API_KEY")
        if not self.api_key:
            raise ValueError("Polygon API key required. Set POLYGON_API_KEY environment variable.")
        
        self.base_url = "https://api.polygon.io"
        self.provider_name = "polygon"

    def get_current_quote(self, asset: Asset) -> Optional[MarketQuote]:
        """Get current market quote for an asset using free tier endpoints"""
        try:
            def fetch_quote() -> Optional[Dict[str, Any]]:
                """Fetch quote from Polygon API using free tier endpoints"""
                # Free tier only has access to previous close data, not real-time quotes
                # Use the aggregates endpoint for the most recent available data
                prev_close_url = f"{self.base_url}/v2/aggs/ticker/{asset.symbol}/prev"
                params = {"apikey": self.api_key}
                
                response = requests.get(prev_close_url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if data.get("status") != "OK":
                    logger.warning(f"Polygon API response: {data}")
                    return None
                
                results = data.get("results", [])
                if not results:
                    logger.warning(f"No previous close data for {asset.symbol}")
                    return None
                
                prev_data = results[0]
                
                # Safe conversion function for numeric values
                def safe_decimal(value, default=0):
                    """Safely convert value to Decimal"""
                    try:
                        if isinstance(value, str):
                            import re
                            clean_value = re.sub(r"[^\d.-]", "", value)
                            return Decimal(clean_value) if clean_value else Decimal(str(default))
                        else:
                            return Decimal(str(value))
                    except (ValueError, TypeError, AttributeError):
                        return Decimal(str(default))
                
                def safe_int(value, default=0):
                    """Safely convert value to int"""
                    try:
                        if isinstance(value, str):
                            import re
                            clean_value = re.sub(r"[^\d]", "", value)
                            return int(clean_value) if clean_value else default
                        else:
                            return int(value)
                    except (ValueError, TypeError, AttributeError):
                        return default
                
                # Extract data from previous close (most recent available in free tier)
                current_price = safe_decimal(prev_data.get("c", 0))  # Previous close as "current"
                open_price = safe_decimal(prev_data.get("o", current_price))  # Open price
                high_price = safe_decimal(prev_data.get("h", current_price))  # High price
                low_price = safe_decimal(prev_data.get("l", current_price))  # Low price
                volume = safe_int(prev_data.get("v", 0))  # Volume
                
                # For previous close comparison, we'd need another day's data
                # For now, calculate change from open to close of the same day
                if open_price > 0:
                    price_change = current_price - open_price
                    price_change_percent = (price_change / open_price) * 100
                else:
                    price_change = Decimal("0")
                    price_change_percent = Decimal("0")
                
                return {
                    "symbol": asset.symbol,
                    "current_price": current_price,
                    "previous_close": open_price,  # Use open as "previous" for day's change
                    "price_change": price_change,
                    "price_change_percent": price_change_percent,
                    "volume": volume,
                    "high": high_price,
                    "low": low_price,
                    "open": open_price,
                    "timestamp": datetime.fromtimestamp(prev_data.get("t", 0) / 1000),  # Convert from milliseconds
                }
            
            # Cache with REAL_TIME policy (2 minutes)
            quote_data = cached_api_call(
                provider=self.provider_name,
                endpoint="last_quote",
                params={"symbol": asset.symbol},
                api_function=fetch_quote,
                policy=CachePolicy.REAL_TIME,
            )
            
            if not quote_data:
                return None
            
            # Create PriceData
            price_data = PriceData(
                asset=asset,
                timestamp=quote_data["timestamp"],
                price=quote_data["current_price"],
                volume=quote_data["volume"],
                open_price=quote_data["open"],
                high_price=quote_data["high"],
                low_price=quote_data["low"],
                session_type=MarketStatus.OPEN,
                bid_price=quote_data.get("bid_price"),
                ask_price=quote_data.get("ask_price"),
                data_source="polygon",
                data_quality="good",
            )
            
            # Create MarketQuote
            return MarketQuote(
                asset=asset,
                price_data=price_data,
                previous_close=quote_data["previous_close"],
                average_volume=None,  # Would need separate API call for this
            )
            
        except Exception as e:
            logger.error(f"Error getting Polygon quote for {asset.symbol}: {e}")
            return None

    def get_extended_hours_data(
        self, asset: Asset, session: MarketStatus
    ) -> Optional[ExtendedHoursData]:
        """Get extended hours trading data"""
        try:
            def fetch_extended_hours() -> Optional[Dict[str, Any]]:
                """Fetch extended hours data from Polygon"""
                # Get today's date
                today = datetime.now().strftime("%Y-%m-%d")
                
                # Polygon aggregates endpoint for minute-level data
                url = f"{self.base_url}/v2/aggs/ticker/{asset.symbol}/range/1/minute/{today}/{today}"
                params = {"apikey": self.api_key, "adjusted": "true", "sort": "asc"}
                
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                if data.get("status") != "OK" or not data.get("results"):
                    logger.warning(f"No extended hours data for {asset.symbol}")
                    return None
                
                # Filter data for the requested session
                session_data = []
                for bar in data["results"]:
                    timestamp = datetime.fromtimestamp(bar["t"] / 1000)  # Polygon uses milliseconds
                    hour = timestamp.hour
                    
                    # Filter by session type
                    if session == MarketStatus.PRE_MARKET and 4 <= hour < 9:
                        session_data.append(bar)
                    elif session == MarketStatus.AFTER_HOURS and 16 <= hour < 20:
                        session_data.append(bar)
                
                if not session_data:
                    return None
                
                # Calculate session metrics
                session_volume = sum(bar["v"] for bar in session_data)
                session_high = max(bar["h"] for bar in session_data)
                session_low = min(bar["l"] for bar in session_data)
                session_open = session_data[0]["o"]
                session_close = session_data[-1]["c"]
                
                return {
                    "session": session,
                    "volume": session_volume,
                    "high": Decimal(str(session_high)),
                    "low": Decimal(str(session_low)),
                    "open": Decimal(str(session_open)),
                    "close": Decimal(str(session_close)),
                    "change": Decimal(str(session_close - session_open)),
                    "timestamp": datetime.now(),
                }
            
            # Cache with INTRADAY policy (15 minutes)
            extended_data = cached_api_call(
                provider=self.provider_name,
                endpoint="extended_hours",
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
                price=extended_data["close"],
                volume=extended_data["volume"],
                open_price=extended_data["open"],
                high_price=extended_data["high"],
                low_price=extended_data["low"],
                session_type=extended_data["session"],
                data_source="polygon",
            )
            
            # Use previous day's close as reference (simplified)
            regular_session_close = extended_data["open"]
            
            return ExtendedHoursData(
                asset=asset,
                session_type=extended_data["session"],
                price_data=price_data,
                regular_session_close=regular_session_close,
            )
            
        except Exception as e:
            logger.error(f"Error getting Polygon extended hours for {asset.symbol}: {e}")
            return None

    def get_historical_quotes(
        self,
        asset: Asset,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1d",
    ) -> List[PriceData]:
        """Get historical price data"""
        try:
            def fetch_historical() -> List[Dict[str, Any]]:
                """Fetch historical data from Polygon"""
                # Map intervals to Polygon format
                multiplier = 1
                timespan = "day"
                
                if interval == "1m":
                    multiplier, timespan = 1, "minute"
                elif interval == "5m":
                    multiplier, timespan = 5, "minute"
                elif interval == "15m":
                    multiplier, timespan = 15, "minute"
                elif interval == "30m":
                    multiplier, timespan = 30, "minute"
                elif interval == "1h":
                    multiplier, timespan = 1, "hour"
                elif interval == "1d":
                    multiplier, timespan = 1, "day"
                
                start_str = start_date.strftime("%Y-%m-%d")
                end_str = end_date.strftime("%Y-%m-%d")
                
                url = f"{self.base_url}/v2/aggs/ticker/{asset.symbol}/range/{multiplier}/{timespan}/{start_str}/{end_str}"
                params = {"apikey": self.api_key, "adjusted": "true", "sort": "asc"}
                
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                if data.get("status") != "OK" or not data.get("results"):
                    logger.warning(f"No historical data for {asset.symbol}")
                    return []
                
                # Convert Polygon format to our format
                price_data = []
                for bar in data["results"]:
                    timestamp = datetime.fromtimestamp(bar["t"] / 1000)  # Convert from milliseconds
                    
                    price_data.append({
                        "timestamp": timestamp,
                        "open": Decimal(str(bar["o"])),
                        "high": Decimal(str(bar["h"])),
                        "low": Decimal(str(bar["l"])),
                        "close": Decimal(str(bar["c"])),
                        "volume": int(bar["v"]),
                    })
                
                return price_data
            
            # Cache with HISTORICAL policy (30 days)
            cache_params = {
                "symbol": asset.symbol,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "interval": interval,
            }
            
            historical_data = cached_api_call(
                provider=self.provider_name,
                endpoint="aggregates",
                params=cache_params,
                api_function=fetch_historical,
                policy=CachePolicy.HISTORICAL,
            )
            
            # Convert to PriceData objects
            return [
                PriceData(
                    asset=asset,
                    timestamp=item["timestamp"],
                    price=item["close"],
                    open_price=item["open"],
                    high_price=item["high"],
                    low_price=item["low"],
                    volume=item["volume"],
                    session_type=MarketStatus.OPEN,
                    data_source="polygon",
                )
                for item in historical_data
            ]
            
        except Exception as e:
            logger.error(f"Error getting Polygon historical data for {asset.symbol}: {e}")
            return []

    def scan_volume_leaders(
        self, assets: List[Asset], min_volume_ratio: Decimal = Decimal("2.0")
    ) -> List[MarketQuote]:
        """Scan for volume leaders using Polygon's market data"""
        volume_leaders = []
        
        for asset in assets:
            try:
                quote = self.get_current_quote(asset)
                if quote and quote.price_data.volume > 0:
                    # For now, just return quotes with volume data
                    # Real implementation would compare against historical averages
                    volume_leaders.append(quote)
                    
            except Exception as e:
                logger.error(f"Error scanning volume for {asset.symbol}: {e}")
                continue
        
        # Sort by volume (highest first)
        return sorted(volume_leaders, key=lambda q: q.price_data.volume, reverse=True)

    def get_fundamental_data(self, asset: Asset) -> Dict[str, Any]:
        """Get fundamental company data"""
        try:
            def fetch_fundamentals() -> Dict[str, Any]:
                """Fetch company details from Polygon"""
                url = f"{self.base_url}/v3/reference/tickers/{asset.symbol}"
                params = {"apikey": self.api_key}
                
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if data.get("status") != "OK" or not data.get("results"):
                    logger.warning(f"No fundamental data for {asset.symbol}")
                    return {}
                
                results = data["results"]
                
                # Map Polygon fields to our format
                fundamentals = {
                    "symbol": asset.symbol,
                    "company_name": results.get("name", ""),
                    "description": results.get("description", ""),
                    "sector": results.get("sic_description", ""),
                    "market_cap": results.get("market_cap", 0),
                    "shares_outstanding": results.get("share_class_shares_outstanding", 0),
                    "homepage_url": results.get("homepage_url", ""),
                    "phone_number": results.get("phone_number", ""),
                    "address": results.get("address", {}),
                    "timestamp": datetime.now().isoformat(),
                }
                
                return fundamentals
            
            # Cache with FUNDAMENTAL policy (1 week)
            return cached_api_call(
                provider=self.provider_name,
                endpoint="ticker_details",
                params={"symbol": asset.symbol},
                api_function=fetch_fundamentals,
                policy=CachePolicy.FUNDAMENTAL,
            )
            
        except Exception as e:
            logger.error(f"Error getting Polygon fundamentals for {asset.symbol}: {e}")
            return {}

    @property
    def rate_limit_per_minute(self) -> int:
        """Return the rate limit for this provider"""
        return 5  # Free tier: 5 calls per minute

    @property
    def supports_extended_hours(self) -> bool:
        """Return whether provider supports extended hours data"""
        return True  # Polygon supports extended hours data


# Convenience function for creating adapter
def create_asset_data_provider_polygon(api_key: Optional[str] = None) -> AssetDataProviderPolygon:
    """
    Create a Polygon asset data provider
    
    Args:
        api_key: Polygon.io API key (uses environment variable if None)
        
    Returns:
        Configured AssetDataProviderPolygon
    """
    return AssetDataProviderPolygon(api_key)


if __name__ == "__main__":
    # Simple test of the adapter
    import os
    
    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        print("❌ POLYGON_API_KEY environment variable not set")
        exit(1)
    
    print("🧪 Testing Polygon Adapter...")
    
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
    adapter = create_polygon_adapter(api_key)
    
    print(f"\n📈 Current Quote for {test_asset.symbol}:")
    quote = adapter.get_current_quote(test_asset)
    if quote:
        print(f"Price: ${quote.price_data.price}")
        print(f"Volume: {quote.price_data.volume:,}")
        print(f"Change: {quote.price_change_percent:.2f}%")
    else:
        print("Failed to get quote")
    
    print(f"\n📊 Fundamental Data for {test_asset.symbol}:")
    fundamentals = adapter.get_fundamental_data(test_asset)
    if fundamentals:
        print(f"Company: {fundamentals.get('company_name', 'N/A')}")
        print(f"Market Cap: ${fundamentals.get('market_cap', 0):,}")
    
    print("\n✅ Polygon Adapter test completed!")