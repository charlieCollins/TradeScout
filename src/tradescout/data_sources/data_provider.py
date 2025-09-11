"""
Data Source Coordinator

Manages the single Polygon.io data provider and implements interfaces.
Acts as a facade for the underlying data provider while implementing all required interfaces.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..config.data_source_config import get_simple_config
from ..interfaces.interface_provider import DataProvider as DataProviderInterface
from ..data_models.models_asset import MarketQuote, PriceData
from ..data_models.models_market import MarketMover
from .data_provider_polygon import DataProviderPolygon

logger = logging.getLogger(__name__)


class DataProviderCoordinator(DataProviderInterface):
    """
    Data provider coordinator
    
    Features:
    - Implements AssetDataInterface, MarketDataInterface, and SentimentDataInterface
    - Manages single Polygon.io provider
    - Simple configuration (just loads API key)
    - Direct delegation to Polygon provider
    """

    def __init__(self):
        """Initialize data provider coordinator with Polygon provider"""
        self.config = get_simple_config()
        self.polygon_provider: Optional[DataProviderPolygon] = None
        
        # Initialize Polygon provider if we have an API key
        if self.config.has_polygon_key():
            try:
                self.polygon_provider = DataProviderPolygon(self.config.get_polygon_key())
                logger.debug("Initialized Polygon provider")
            except Exception as e:
                logger.error(f"Failed to initialize Polygon provider: {e}")
        else:
            logger.warning("No Polygon API key found - provider will not be available")

    @property
    def provider_name(self) -> str:
        return "DataProviderCoordinator"
    
    @property
    def supports_extended_hours(self) -> bool:
        return True
    
    @property
    def supports_sentiment(self) -> bool:
        return False  # Polygon doesn't provide sentiment data
    
    @property
    def rate_limit_per_minute(self) -> Optional[int]:
        return None  # Premium Polygon subscription - no rate limiting needed

    # AssetDataInterface implementation
    def get_current_quote(self, symbol: str) -> Optional[MarketQuote]:
        """Get current quote for a symbol"""
        if not self.polygon_provider:
            logger.error("No Polygon provider available")
            return None
            
        return self.polygon_provider.get_current_quote(symbol)

    def get_fundamentals(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get fundamental data for a symbol"""
        if not self.polygon_provider:
            logger.error("No Polygon provider available")
            return None
            
        return self.polygon_provider.get_fundamentals(symbol)

    def get_historical_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1d"
    ) -> List[PriceData]:
        """Get historical price data"""
        if not self.polygon_provider:
            logger.error("No Polygon provider available")
            return []
            
        return self.polygon_provider.get_historical_data(symbol, start_date, end_date, interval)

    def get_ohlc(self, symbol: str, date: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get OHLC data for a date"""
        if not self.polygon_provider:
            logger.error("No Polygon provider available")
            return None
            
        return self.polygon_provider.get_ohlc(symbol, date)

    # MarketDataInterface implementation
    def get_market_gainers(
        self, 
        limit: int = 20,
        force_refresh: bool = False
    ) -> List[MarketMover]:
        """Get top market gainers"""
        if not self.polygon_provider:
            logger.error("No Polygon provider available")
            return []
            
        return self.polygon_provider.get_market_gainers(limit, force_refresh)

    def get_market_losers(
        self,
        limit: int = 20,
        force_refresh: bool = False
    ) -> List[MarketMover]:
        """Get top market losers"""
        if not self.polygon_provider:
            logger.error("No Polygon provider available") 
            return []
            
        return self.polygon_provider.get_market_losers(limit, force_refresh)

    def get_most_active(
        self,
        limit: int = 20,
        force_refresh: bool = False
    ) -> List[MarketMover]:
        """Get most active stocks by volume"""
        if not self.polygon_provider:
            logger.error("No Polygon provider available")
            return []
            
        return self.polygon_provider.get_most_active(limit, force_refresh)

    def get_market_snapshot(
        self,
        force_refresh: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Get complete market snapshot"""
        if not self.polygon_provider:
            logger.error("No Polygon provider available")
            return None
            
        return self.polygon_provider.get_market_snapshot(force_refresh)

    # SentimentDataInterface implementation (not supported by Polygon)
    def get_asset_sentiment(
        self,
        symbol: str,
        lookback_hours: int = 24
    ) -> Optional[Dict[str, Any]]:
        """Polygon doesn't provide sentiment data"""
        return None

    def get_market_sentiment(
        self,
        market: str = "overall",
        lookback_hours: int = 24
    ) -> Optional[Dict[str, Any]]:
        """Polygon doesn't provide market sentiment data"""
        return None

    def get_trending_sentiment(
        self,
        limit: int = 20,
        sentiment_threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """Polygon doesn't provide trending sentiment data"""
        return []

    def get_news_sentiment(
        self,
        symbols: Optional[List[str]] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Polygon doesn't provide news sentiment data"""
        return []

    def get_social_sentiment(
        self,
        symbol: str,
        platforms: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Polygon doesn't provide social sentiment data"""
        return {}

    def get_analyst_sentiment(
        self,
        symbol: str,
        days_back: int = 30
    ) -> Optional[Dict[str, Any]]:
        """Polygon doesn't provide analyst sentiment data"""
        return None

    # Legacy methods for compatibility with existing gap trading system
    def get_gap_data_from_snapshot(
        self, symbol: str, snapshot_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Extract gap data from snapshot for a symbol"""
        if not snapshot_data or symbol not in snapshot_data:
            return None
            
        ticker_data = snapshot_data[symbol]
        
        # Get previous close from snapshot
        previous_close = None
        if "prevDay" in ticker_data and ticker_data["prevDay"]:
            previous_close = ticker_data["prevDay"].get("c")
            
        # Get current price from minute data (real-time)
        current_price = None
        if "min" in ticker_data and ticker_data["min"]:
            current_price = ticker_data["min"].get("c")
        elif "day" in ticker_data and ticker_data["day"]:
            current_price = ticker_data["day"].get("c")
            
        if not previous_close or not current_price:
            return None
            
        # Calculate gap
        gap_amount = current_price - previous_close
        gap_percent = abs((gap_amount / previous_close) * 100)
        
        return {
            "current_price": current_price,
            "reference_close": previous_close,
            "gap_percent": gap_percent,
            "gap_amount": gap_amount,
            "session_type": "current",  # Simplified
        }

    def get_daily_gap_suggestions(
        self, min_gap_percent: float = 2.0, movers_limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """Generate daily gap trading suggestions"""
        logger.debug(f"Generating daily gap suggestions (min gap: {min_gap_percent}%)")

        try:
            from ..analysis.gap_market_scanner import GapMarketScanner
            from ..analysis.gap_rules_engine import GapRulesEngine
            from ..analysis.academic_gap_analyzer import AcademicGapTypeAnalyzer
            from ..analysis.gap_suggestion_engine import GapTradeSuggestionEngine
            from decimal import Decimal

            # Initialize gap analysis components
            gap_scanner = GapMarketScanner(self)
            rules_engine = GapRulesEngine()
            gap_analyzer = AcademicGapTypeAnalyzer()
            suggestion_engine = GapTradeSuggestionEngine()

            # Step 1: Scan for gap candidates
            gap_candidates, scanning_stats = gap_scanner.scan_pre_market_gaps(
                Decimal(str(min_gap_percent)), movers_limit
            )
            logger.debug(f"Found {len(gap_candidates)} gap candidates")

            if not gap_candidates:
                return {
                    "suggestions": [],
                    "gap_candidates": len(gap_candidates),
                    "approved_candidates": 0,
                    "scanning_stats": scanning_stats,
                }

            # Step 2: Apply binary classification rules
            approved_candidates = []
            for quote in gap_candidates:
                evaluation = rules_engine.evaluate_gap_candidate(quote)
                if evaluation["decision"] == "TRADE":
                    approved_candidates.append(quote)

            logger.debug(f"{len(approved_candidates)} candidates passed binary rules")

            if not approved_candidates:
                return {
                    "suggestions": [],
                    "gap_candidates": len(gap_candidates),
                    "approved_candidates": len(approved_candidates),
                    "scanning_stats": scanning_stats,
                }

            # Step 3: Analyze gap types and generate suggestions
            gap_assessments = gap_analyzer.batch_analyze_candidates(approved_candidates)

            # Step 4: Generate trade suggestions
            suggestions = []
            for i, assessment in enumerate(gap_assessments):
                if i < len(approved_candidates) and assessment.is_tradeable:
                    analysis_data = {
                        "quote": approved_candidates[i],
                        "gap_assessment": assessment,
                    }

                    suggestion = suggestion_engine.generate_suggestion(
                        approved_candidates[i].asset.symbol, analysis_data
                    )

                    if suggestion and suggestion_engine.validate_suggestion(suggestion):
                        suggestions.append(
                            {
                                "suggestion": suggestion,
                                "assessment": assessment,
                                "quote": approved_candidates[i],
                            }
                        )

            # Step 5: Filter and rank suggestions
            final_suggestions = suggestion_engine.filter_suggestions(
                [s["suggestion"] for s in suggestions]
            )

            # Return enriched suggestions
            result = []
            for suggestion in final_suggestions:
                # Find matching assessment and quote
                matching_data = next(
                    (s for s in suggestions if s["suggestion"].id == suggestion.id),
                    None,
                )
                if matching_data:
                    result.append(
                        {
                            "suggestion": suggestion,
                            "assessment": matching_data["assessment"],
                            "quote": matching_data["quote"],
                            "analysis_summary": suggestion.rationale,
                        }
                    )

            logger.debug(f"Generated {len(result)} daily gap trading suggestions")
            return {
                "suggestions": result,
                "gap_candidates": len(gap_candidates),
                "approved_candidates": len(approved_candidates),
                "scanning_stats": scanning_stats,
            }

        except Exception as e:
            logger.error(f"Error generating gap suggestions: {e}")
            return {
                "suggestions": [],
                "gap_candidates": 0,
                "approved_candidates": 0,
                "scanning_stats": {
                    "movers_analyzed": 0,
                    "movers_processed": 0,
                    "data_available": 0,
                    "gap_candidates": 0,
                },
            }

    # Utility methods
    def get_provider_status(self) -> Dict[str, Any]:
        """Get status of the provider"""
        return {
            "polygon": {
                "available": self.polygon_provider is not None,
                "has_api_key": self.config.has_polygon_key(),
                "provider_name": "Polygon.io" if self.polygon_provider else None
            }
        }

    def get_available_data_types(self) -> List[str]:
        """Get list of available data types"""
        if self.polygon_provider:
            return [
                "current_quotes",
                "historical_prices", 
                "market_movers",
                "market_snapshot",
                "fundamentals"
            ]
        return []

    def reload_config(self) -> None:
        """Reload configuration and reinitialize provider"""
        logger.info("Reloading data provider coordinator configuration...")
        self.config = get_simple_config()
        
        # Reinitialize Polygon provider
        if self.config.has_polygon_key():
            try:
                self.polygon_provider = DataProviderPolygon(self.config.get_polygon_key())
                logger.debug("Reinitialized Polygon provider")
            except Exception as e:
                logger.error(f"Failed to reinitialize Polygon provider: {e}")
        else:
            self.polygon_provider = None
            logger.warning("No Polygon API key found after reload")


# Convenience functions for compatibility
def create_data_provider() -> DataProviderCoordinator:
    """Create a data provider coordinator with default configuration"""
    return DataProviderCoordinator()


if __name__ == "__main__":
    # Test the data provider coordinator
    print("🧪 Testing Data Provider Coordinator...")

    coordinator = create_data_provider()

    print(f"\n📊 Provider Status:")
    status = coordinator.get_provider_status()
    polygon_status = status["polygon"]
    
    if polygon_status["available"]:
        print("  ✅ Polygon provider available")
        print(f"  🏷️  Provider name: {coordinator.provider_name}")
        print(f"  🕐 Supports extended hours: {coordinator.supports_extended_hours}")
        print(f"  💭 Supports sentiment: {coordinator.supports_sentiment}")
        print(f"  ⚡ Rate limit: {coordinator.rate_limit_per_minute} calls/min")
    else:
        print("  ❌ Polygon provider unavailable")
        if not polygon_status["has_api_key"]:
            print("     Missing API key")

    print(f"\n📈 Available data types: {coordinator.get_available_data_types()}")

    # Test quote functionality if available
    if polygon_status["available"]:
        print(f"\n📈 Testing quote for AAPL...")
        quote = coordinator.get_current_quote("AAPL")
        if quote:
            print(f"Price: ${quote.price_data.price}")
        else:
            print("Failed to get quote")

    print("\n✅ Data Provider Coordinator test completed!")