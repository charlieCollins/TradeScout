"""
Finnhub.io Adapter - Implementation using Finnhub.io API

High-quality real-time market data with good free tier.
Documentation: https://finnhub.io/docs/api
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


class AssetDataProviderFinnhub(AssetDataProvider):
    """
    Finnhub.io adapter implementing AssetDataProvider interface
    
    Features:
    - Free tier: 60 API calls per minute
    - Real-time quotes and market data
    - Good data quality and reliability
    - Company fundamentals included
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Finnhub adapter
        
        Args:
            api_key: Finnhub.io API key (get from environment if None)
        """
        import os
        self.api_key = api_key or os.getenv("FINNHUB_API_KEY")
        if not self.api_key:
            raise ValueError("Finnhub API key required. Set FINNHUB_API_KEY environment variable.")
        
        self.base_url = "https://finnhub.io/api/v1"
        self.provider_name = "finnhub"

    def get_current_quote(self, asset: Asset) -> Optional[MarketQuote]:
        """Get current market quote for an asset"""
        try:
            def fetch_quote() -> Optional[Dict[str, Any]]:
                """Fetch quote from Finnhub API"""
                # Get current price from quote endpoint
                url = f"{self.base_url}/quote"
                params = {
                    "symbol": asset.symbol,
                    "token": self.api_key
                }
                
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                # Check for valid response
                if not data or data.get("c", 0) == 0:
                    logger.warning(f"No quote data for {asset.symbol} from Finnhub")
                    return None
                
                # Robust conversion with error handling
                def safe_decimal(value, default=0):
                    """Safely convert value to Decimal"""
                    try:
                        if value is None:
                            return Decimal(str(default))
                        # Handle various numeric types
                        if isinstance(value, (int, float)):
                            return Decimal(str(value))
                        elif isinstance(value, str):
                            # Clean string of any non-numeric characters except decimal point and minus
                            import re
                            clean_value = re.sub(r"[^\d.-]", "", value)
                            return Decimal(clean_value) if clean_value else Decimal(str(default))
                        else:
                            return Decimal(str(value))
                    except (ValueError, TypeError, Exception) as e:
                        logger.warning(f"Error converting {value} to Decimal: {e}")
                        return Decimal(str(default))
                
                current_price = safe_decimal(data.get("c", 0))  # Current price
                previous_close = safe_decimal(data.get("pc", 0))  # Previous close
                high_price = safe_decimal(data.get("h", current_price))  # High price
                low_price = safe_decimal(data.get("l", current_price))  # Low price  
                open_price = safe_decimal(data.get("o", current_price))  # Open price
                
                # Calculate changes
                if previous_close > 0:
                    price_change = current_price - previous_close
                    price_change_percent = (price_change / previous_close) * 100
                else:
                    price_change = Decimal("0")
                    price_change_percent = Decimal("0")
                
                return {
                    "symbol": asset.symbol,
                    "current_price": current_price,
                    "previous_close": previous_close,
                    "price_change": price_change,
                    "price_change_percent": price_change_percent,
                    "volume": 0,  # Volume not included in basic quote endpoint
                    "high": high_price,
                    "low": low_price,
                    "open": open_price,
                    "timestamp": datetime.now(),
                }
            
            # Cache with REAL_TIME policy (2 minutes)
            quote_data = cached_api_call(
                provider=self.provider_name,
                endpoint="quote",
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
                data_source="finnhub",
                data_quality="good",
            )
            
            # Debug logging
            logger.debug(f"Creating MarketQuote for {asset.symbol}:")
            logger.debug(f"  current_price: {quote_data['current_price']} (type: {type(quote_data['current_price'])})")
            logger.debug(f"  previous_close: {quote_data['previous_close']} (type: {type(quote_data['previous_close'])})")
            
            # Create MarketQuote
            return MarketQuote(
                asset=asset,
                price_data=price_data,
                previous_close=quote_data["previous_close"],
                average_volume=None,  # Would need separate API call for this
            )
            
        except Exception as e:
            logger.error(f"Error getting Finnhub quote for {asset.symbol}: {e}")
            return None

    def get_extended_hours_data(
        self, asset: Asset, session: MarketStatus
    ) -> Optional[ExtendedHoursData]:
        """Get extended hours trading data"""
        # Finnhub free tier doesn't include detailed extended hours data
        # This is a simplified implementation
        logger.info(f"Extended hours data not available in Finnhub free tier for {asset.symbol}")
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
                """Fetch historical data from Finnhub"""
                # Convert to UNIX timestamps
                start_timestamp = int(start_date.timestamp())
                end_timestamp = int(end_date.timestamp())
                
                # Map intervals to Finnhub resolution
                resolution_map = {
                    "1m": "1",
                    "5m": "5", 
                    "15m": "15",
                    "30m": "30",
                    "1h": "60",
                    "1d": "D",
                    "1w": "W",
                    "1M": "M"
                }
                resolution = resolution_map.get(interval, "D")
                
                url = f"{self.base_url}/stock/candle"
                params = {
                    "symbol": asset.symbol,
                    "resolution": resolution,
                    "from": start_timestamp,
                    "to": end_timestamp,
                    "token": self.api_key
                }
                
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                if data.get("s") != "ok" or not data.get("c"):
                    logger.warning(f"No historical data for {asset.symbol}")
                    return []
                
                # Convert Finnhub format to our format
                price_data = []
                timestamps = data.get("t", [])
                opens = data.get("o", [])
                highs = data.get("h", [])
                lows = data.get("l", [])
                closes = data.get("c", [])
                volumes = data.get("v", [])
                
                for i in range(len(timestamps)):
                    timestamp = datetime.fromtimestamp(timestamps[i])
                    
                    price_data.append({
                        "timestamp": timestamp,
                        "open": Decimal(str(opens[i])),
                        "high": Decimal(str(highs[i])),
                        "low": Decimal(str(lows[i])),
                        "close": Decimal(str(closes[i])),
                        "volume": int(volumes[i]) if volumes else 0,
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
                endpoint="candle",
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
                    data_source="finnhub",
                )
                for item in historical_data
            ]
            
        except Exception as e:
            logger.error(f"Error getting Finnhub historical data for {asset.symbol}: {e}")
            return []

    def scan_volume_leaders(
        self, assets: List[Asset], min_volume_ratio: Decimal = Decimal("2.0")
    ) -> List[MarketQuote]:
        """Scan for volume leaders using Finnhub's market data"""
        volume_leaders = []
        
        for asset in assets:
            try:
                quote = self.get_current_quote(asset)
                if quote:
                    # Basic implementation - just return quotes
                    # Real volume leader detection would need historical volume data
                    volume_leaders.append(quote)
                    
            except Exception as e:
                logger.error(f"Error scanning volume for {asset.symbol}: {e}")
                continue
        
        # Sort by price change (since we don't have volume data in basic quotes)
        return sorted(volume_leaders, key=lambda q: abs(q.price_change_percent or 0), reverse=True)

    def get_fundamental_data(self, asset: Asset) -> Dict[str, Any]:
        """Get fundamental company data"""
        try:
            def fetch_fundamentals() -> Dict[str, Any]:
                """Fetch company profile from Finnhub"""
                url = f"{self.base_url}/stock/profile2"
                params = {
                    "symbol": asset.symbol,
                    "token": self.api_key
                }
                
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if not data or not data.get("name"):
                    logger.warning(f"No fundamental data for {asset.symbol}")
                    return {}
                
                # Map Finnhub fields to our format
                fundamentals = {
                    "symbol": asset.symbol,
                    "company_name": data.get("name", ""),
                    "description": data.get("finnhubIndustry", ""),
                    "sector": data.get("gics", ""),
                    "industry": data.get("finnhubIndustry", ""),
                    "market_cap": data.get("marketCapitalization", 0) * 1000000 if data.get("marketCapitalization") else 0,  # Convert from millions
                    "shares_outstanding": data.get("shareOutstanding", 0) * 1000000 if data.get("shareOutstanding") else 0,  # Convert from millions
                    "homepage_url": data.get("weburl", ""),
                    "phone_number": data.get("phone", ""),
                    "country": data.get("country", ""),
                    "currency": data.get("currency", "USD"),
                    "exchange": data.get("exchange", ""),
                    "ipo_date": data.get("ipo", ""),
                    "timestamp": datetime.now().isoformat(),
                }
                
                return fundamentals
            
            # Cache with FUNDAMENTAL policy (1 week)
            return cached_api_call(
                provider=self.provider_name,
                endpoint="profile2",
                params={"symbol": asset.symbol},
                api_function=fetch_fundamentals,
                policy=CachePolicy.FUNDAMENTAL,
            )
            
        except Exception as e:
            logger.error(f"Error getting Finnhub fundamentals for {asset.symbol}: {e}")
            return {}

    @property
    def rate_limit_per_minute(self) -> int:
        """Return the rate limit for this provider"""
        return 60  # Free tier: 60 calls per minute

    @property
    def supports_extended_hours(self) -> bool:
        """Return whether provider supports extended hours data"""
        return False  # Free tier doesn't include extended hours


# Convenience function for creating adapter
def create_asset_data_provider_finnhub(api_key: Optional[str] = None) -> AssetDataProviderFinnhub:
    """
    Create a Finnhub asset data provider
    
    Args:
        api_key: Finnhub.io API key (uses environment variable if None)
        
    Returns:
        Configured AssetDataProviderFinnhub
    """
    return AssetDataProviderFinnhub(api_key)


if __name__ == "__main__":
    # Simple test of the adapter
    import os
    
    api_key = os.getenv("FINNHUB_API_KEY")
    if not api_key:
        print("❌ FINNHUB_API_KEY environment variable not set")
        exit(1)
    
    print("🧪 Testing Finnhub Adapter...")
    
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
    adapter = create_finnhub_adapter(api_key)
    
    print(f"\n📈 Current Quote for {test_asset.symbol}:")
    quote = adapter.get_current_quote(test_asset)
    if quote:
        print(f"Price: ${quote.price_data.price}")
        print(f"Change: {quote.price_change_percent:.2f}%")
        print(f"High: ${quote.price_data.high_price}")
        print(f"Low: ${quote.price_data.low_price}")
    else:
        print("Failed to get quote")
    
    print(f"\n📊 Fundamental Data for {test_asset.symbol}:")
    fundamentals = adapter.get_fundamental_data(test_asset)
    if fundamentals:
        print(f"Company: {fundamentals.get('company_name', 'N/A')}")
        print(f"Market Cap: ${fundamentals.get('market_cap', 0):,}")
        print(f"Industry: {fundamentals.get('industry', 'N/A')}")
    
    print("\n✅ Finnhub Adapter test completed!")