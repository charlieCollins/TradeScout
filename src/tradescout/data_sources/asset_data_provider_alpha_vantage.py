"""
Alpha Vantage Adapter - Implementation using Alpha Vantage API

Free tier: 500 API calls per day, 5 API calls per minute
Documentation: https://www.alphavantage.co/documentation/
"""

import logging
import requests
from datetime import datetime
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


class AssetDataProviderAlphaVantage(AssetDataProvider):
    """
    Alpha Vantage adapter implementing AssetDataProvider interface
    
    Features:
    - Free tier: 500 calls/day, 5 calls/minute
    - Real-time and historical data
    - Fundamental data
    - Good reliability and data quality
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Alpha Vantage adapter
        
        Args:
            api_key: Alpha Vantage API key (get from environment if None)
        """
        import os
        self.api_key = api_key or os.getenv("ALPHA_VANTAGE_API_KEY", "demo")
        self.base_url = "https://www.alphavantage.co/query"
        self.provider_name = "alphavantage"

    def get_current_quote(self, asset: Asset) -> Optional[MarketQuote]:
        """Get current market quote for an asset"""
        try:
            def fetch_quote() -> Optional[Dict[str, Any]]:
                """Fetch quote from Alpha Vantage API"""
                params = {
                    "function": "GLOBAL_QUOTE",
                    "symbol": asset.symbol,
                    "apikey": self.api_key,
                }
                
                response = requests.get(self.base_url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                # Check for API limit error
                if "Error Message" in data:
                    logger.error(f"Alpha Vantage error: {data['Error Message']}")
                    return None
                
                if "Note" in data:
                    logger.warning(f"Alpha Vantage rate limit: {data['Note']}")
                    return None
                
                quote_data = data.get("Global Quote", {})
                if not quote_data:
                    logger.warning(f"No quote data for {asset.symbol}")
                    return None
                
                # Parse Alpha Vantage response
                current_price = float(quote_data.get("05. price", 0))
                previous_close = float(quote_data.get("08. previous close", 0))
                change = float(quote_data.get("09. change", 0))
                change_percent = quote_data.get("10. change percent", "0%")
                
                # Clean up change percent (remove % and convert to float)
                try:
                    change_percent_num = float(change_percent.replace("%", ""))
                except (ValueError, AttributeError):
                    change_percent_num = 0.0
                
                volume = int(quote_data.get("06. volume", 0))
                
                return {
                    "symbol": asset.symbol,
                    "current_price": Decimal(str(current_price)),
                    "previous_close": Decimal(str(previous_close)),
                    "price_change": Decimal(str(change)),
                    "price_change_percent": Decimal(str(change_percent_num)),
                    "volume": volume,
                    "high": Decimal(str(quote_data.get("03. high", current_price))),
                    "low": Decimal(str(quote_data.get("04. low", current_price))),
                    "open": Decimal(str(quote_data.get("02. open", current_price))),
                    "timestamp": datetime.now(),
                }
            
            # Cache with REAL_TIME policy (2 minutes)
            quote_data = cached_api_call(
                provider=self.provider_name,
                endpoint="global_quote",
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
                data_source="alphavantage",
                data_quality="good",
            )
            
            # Create MarketQuote
            return MarketQuote(
                asset=asset,
                price_data=price_data,
                previous_close=quote_data["previous_close"],
                average_volume=None,  # Not provided by this endpoint
            )
            
        except Exception as e:
            logger.error(f"Error getting Alpha Vantage quote for {asset.symbol}: {e}")
            return None

    def get_extended_hours_data(
        self, asset: Asset, session: MarketStatus
    ) -> Optional[ExtendedHoursData]:
        """Get extended hours trading data - not supported by Alpha Vantage free tier"""
        logger.warning("Extended hours data not supported by Alpha Vantage free tier")
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
                """Fetch historical data from Alpha Vantage"""
                # Map intervals
                av_function = "TIME_SERIES_DAILY"
                if interval in ["1m", "5m", "15m", "30m", "60m"]:
                    av_function = "TIME_SERIES_INTRADAY"
                    
                params = {
                    "function": av_function,
                    "symbol": asset.symbol,
                    "apikey": self.api_key,
                }
                
                if av_function == "TIME_SERIES_INTRADAY":
                    params["interval"] = interval
                    params["outputsize"] = "full"
                
                response = requests.get(self.base_url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                # Check for errors
                if "Error Message" in data or "Note" in data:
                    logger.error(f"Alpha Vantage error: {data}")
                    return []
                
                # Find the time series key
                time_series_key = None
                for key in data.keys():
                    if "Time Series" in key:
                        time_series_key = key
                        break
                
                if not time_series_key:
                    logger.warning(f"No time series data found for {asset.symbol}")
                    return []
                
                time_series = data[time_series_key]
                
                # Convert to our format
                price_data = []
                for timestamp_str, ohlcv in time_series.items():
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str.replace(" ", "T"))
                        
                        # Skip data outside our date range
                        if timestamp.date() < start_date.date() or timestamp.date() > end_date.date():
                            continue
                        
                        price_data.append({
                            "timestamp": timestamp,
                            "open": Decimal(str(ohlcv.get("1. open", 0))),
                            "high": Decimal(str(ohlcv.get("2. high", 0))),
                            "low": Decimal(str(ohlcv.get("3. low", 0))),
                            "close": Decimal(str(ohlcv.get("4. close", 0))),
                            "volume": int(ohlcv.get("5. volume", 0)),
                        })
                    except Exception as e:
                        logger.warning(f"Error parsing historical data point: {e}")
                        continue
                
                return sorted(price_data, key=lambda x: x["timestamp"])
            
            # Cache with HISTORICAL policy (30 days)
            cache_params = {
                "symbol": asset.symbol,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "interval": interval,
            }
            
            historical_data = cached_api_call(
                provider=self.provider_name,
                endpoint="time_series",
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
                    data_source="alphavantage",
                )
                for item in historical_data
            ]
            
        except Exception as e:
            logger.error(f"Error getting Alpha Vantage historical data for {asset.symbol}: {e}")
            return []

    def scan_volume_leaders(
        self, assets: List[Asset], min_volume_ratio: Decimal = Decimal("2.0")
    ) -> List[MarketQuote]:
        """Scan for volume leaders - limited by API quotas"""
        volume_leaders = []
        
        for asset in assets[:10]:  # Limit to 10 to preserve API quota
            try:
                quote = self.get_current_quote(asset)
                if quote and quote.average_volume:
                    # Calculate volume ratio (would need historical average)
                    # For now, just return quotes with volume > 0
                    if quote.price_data.volume > 0:
                        volume_leaders.append(quote)
            except Exception as e:
                logger.error(f"Error scanning volume for {asset.symbol}: {e}")
                continue
        
        return volume_leaders

    def get_fundamental_data(self, asset: Asset) -> Dict[str, Any]:
        """Get fundamental company data"""
        try:
            def fetch_fundamentals() -> Dict[str, Any]:
                """Fetch company overview from Alpha Vantage"""
                params = {
                    "function": "OVERVIEW",
                    "symbol": asset.symbol,
                    "apikey": self.api_key,
                }
                
                response = requests.get(self.base_url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if "Error Message" in data or "Note" in data:
                    logger.error(f"Alpha Vantage fundamentals error: {data}")
                    return {}
                
                # Map Alpha Vantage fields to our format
                fundamentals = {
                    "symbol": asset.symbol,
                    "company_name": data.get("Name", ""),
                    "sector": data.get("Sector", ""),
                    "industry": data.get("Industry", ""),
                    "market_cap": int(data.get("MarketCapitalization", 0)),
                    "pe_ratio": float(data.get("PERatio", 0)) if data.get("PERatio") != "None" else 0,
                    "price_to_book": float(data.get("PriceToBookRatio", 0)) if data.get("PriceToBookRatio") != "None" else 0,
                    "dividend_yield": float(data.get("DividendYield", 0)) if data.get("DividendYield") != "None" else 0,
                    "beta": float(data.get("Beta", 0)) if data.get("Beta") != "None" else 0,
                    "52_week_high": float(data.get("52WeekHigh", 0)),
                    "52_week_low": float(data.get("52WeekLow", 0)),
                    "description": data.get("Description", ""),
                    "timestamp": datetime.now().isoformat(),
                }
                
                return fundamentals
            
            # Cache with FUNDAMENTAL policy (1 week)
            return cached_api_call(
                provider=self.provider_name,
                endpoint="overview",
                params={"symbol": asset.symbol},
                api_function=fetch_fundamentals,
                policy=CachePolicy.FUNDAMENTAL,
            )
            
        except Exception as e:
            logger.error(f"Error getting Alpha Vantage fundamentals for {asset.symbol}: {e}")
            return {}

    @property
    def rate_limit_per_minute(self) -> int:
        """Return the rate limit for this provider"""
        return 5  # 5 calls per minute

    @property
    def supports_extended_hours(self) -> bool:
        """Return whether provider supports extended hours data"""
        return False  # Not available in free tier


# Convenience function for creating adapter
def create_asset_data_provider_alpha_vantage(api_key: Optional[str] = None) -> AssetDataProviderAlphaVantage:
    """
    Create an Alpha Vantage asset data provider
    
    Args:
        api_key: Alpha Vantage API key (uses environment variable if None)
        
    Returns:
        Configured AssetDataProviderAlphaVantage
    """
    return AssetDataProviderAlphaVantage(api_key)