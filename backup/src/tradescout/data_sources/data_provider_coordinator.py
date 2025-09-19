"""
Data Source Coordinator

Manages the single Polygon.io data provider and implements interfaces.
Acts as a facade for the underlying data provider while implementing all required interfaces.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..config.data_source_config import get_simple_config
from ..config.gap_analysis_config import get_gap_rules_config
from ..interfaces.interface_provider import DataProvider as DataProviderInterface
from ..data_models.models_asset import PriceData
from ..data_models.models_market import MarketMover, MarketStatus
from ..data_models.models_analysis import GapAssessment, GapCandidate
from ..analysis.gap_analyzer import GapAnalyzer
from .data_provider_polygon import DataProviderPolygon

logger = logging.getLogger(__name__)


class DataProviderCoordinator(DataProviderInterface):
    """
    Data provider coordinator

    Features:
    - Implements AssetDataInterface and MarketDataInterface
    - Manages single Polygon.io provider
    - Simple configuration (just loads API key)
    - Direct delegation to Polygon provider
    """

    def __init__(self, db_manager=None):
        """Initialize data provider coordinator with Polygon provider"""
        self.config = get_simple_config()
        self.polygon_provider: Optional[DataProviderPolygon] = None
        self.gap_analyzer: Optional[GapAnalyzer] = None

        # Initialize Polygon provider if we have an API key
        if self.config.has_polygon_key():
            try:
                self.polygon_provider = DataProviderPolygon(
                    self.config.get_polygon_key(), db_manager=db_manager
                )
                logger.debug("Initialized Polygon provider")

                # Initialize gap analyzer
                self.gap_analyzer = GapAnalyzer()
                logger.debug("Initialized gap analyzer")
            except Exception as e:
                logger.error(f"Failed to initialize Polygon provider: {e}")
        else:
            logger.warning("No Polygon API key found - provider will not be available")

    # ========================================
    # Public Interface Properties
    # ========================================

    @property
    def provider_name(self) -> str:
        return "DataProviderCoordinator"

    @property
    def supports_extended_hours(self) -> bool:
        return True

    @property
    def rate_limit_per_minute(self) -> Optional[int]:
        return None  # Premium Polygon subscription - no rate limiting needed

    # ========================================
    # AssetDataInterface Implementation
    # ========================================

    def get_current_quote(self, symbol: str) -> Optional[PriceData]:
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

    def get_ohlc(
        self, symbol: str, date: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get OHLC data for a date"""
        if not self.polygon_provider:
            logger.error("No Polygon provider available")
            return None

        return self.polygon_provider.get_ohlc(symbol, date)

    # ========================================
    # MarketDataInterface Implementation
    # ========================================

    def get_market_gainers(
        self, limit: int = 20, force_refresh: bool = False
    ) -> List[MarketMover]:
        """Get top market gainers"""
        if not self.polygon_provider:
            logger.error("No Polygon provider available")
            return []

        return self.polygon_provider.get_market_gainers(limit, force_refresh)

    def get_market_losers(
        self, limit: int = 20, force_refresh: bool = False
    ) -> List[MarketMover]:
        """Get top market losers"""
        if not self.polygon_provider:
            logger.error("No Polygon provider available")
            return []

        return self.polygon_provider.get_market_losers(limit, force_refresh)

    def get_market_snapshot(
        self, force_refresh: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Get complete market snapshot"""
        if not self.polygon_provider:
            logger.error("No Polygon provider available")
            return None

        return self.polygon_provider.get_market_snapshot(force_refresh)

    # ========================================
    # Gap Analysis Methods
    # ========================================

    def get_gap_suggestions(
        self,
        session_type: MarketStatus,
        limit: int = 5,
        min_gap_percent: float = 2.0,
        movers_limit: int = 100,
    ) -> List[GapAssessment]:
        """
        Get gap trading suggestions using GapAnalyzer.

        Args:
            session_type: Current market session type
            limit: Maximum number of suggestions to return
            min_gap_percent: Minimum gap percentage threshold
            movers_limit: Number of market movers to analyze

        Returns:
            List of GapAssessment objects with trading suggestions
        """
        if not self.polygon_provider or not self.gap_analyzer:
            logger.error("Polygon provider or gap analyzer not available")
            return []

        # TODO: Gap candidate identification not yet implemented
        # Current implementation incorrectly uses gainers/losers which shows total displacement
        # from previous close to current price. This is WRONG for gap analysis.
        #
        # REQUIRED: Implement extended hours gap identification that compares:
        # - Previous regular session close price
        # - Current extended hours price (pre-market or after-hours)
        # - Identify stocks with gaps that occurred during extended hours ONLY
        #
        # This is the core purpose of this project - extended hours gap discovery
        logger.warning("Gap candidate identification not yet implemented - requires extended hours data")
        return []

    def get_daily_gap_suggestions(
        self, min_gap_percent: float = 2.0, movers_limit: int = 100
    ) -> Dict[str, Any]:
        """
        Legacy method name for engine compatibility.

        Args:
            min_gap_percent: Minimum gap percentage threshold
            movers_limit: Number of market movers to analyze

        Returns:
            Dictionary with suggestions and analysis stats for engine display
        """
        # Determine current session type (this should be moved to config later)
        from datetime import datetime, time

        now = datetime.now()
        current_time = now.time()

        # Hardcoded for now - should come from market config
        if time(4, 0) <= current_time < time(9, 30):
            session_type = MarketStatus.PRE_MARKET
        elif time(9, 30) <= current_time < time(16, 0):
            session_type = MarketStatus.OPEN
        elif time(16, 0) <= current_time < time(20, 0):
            session_type = MarketStatus.AFTER_HOURS
        else:
            session_type = MarketStatus.CLOSED

        # Get gap suggestions
        suggestions = self.get_gap_suggestions(
            session_type=session_type,
            limit=5,
            min_gap_percent=min_gap_percent,
            movers_limit=movers_limit,
        )

        # Return new format with GapAssessment objects
        return {
            "suggestions": suggestions,  # List[GapAssessment] objects directly
            "gap_candidates": len(suggestions),
            "approved_candidates": len(suggestions),
            "scanning_stats": {
                "movers_analyzed": movers_limit,
                "data_available": len(suggestions),
            },
        }

    # ========================================
    # Utility Methods
    # ========================================

    def get_provider_status(self) -> Dict[str, Any]:
        """Get status of the provider"""
        return {
            "polygon": {
                "available": self.polygon_provider is not None,
                "has_api_key": self.config.has_polygon_key(),
                "provider_name": "Polygon.io" if self.polygon_provider else None,
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
                "fundamentals",
            ]
        return []

    # ========================================
    # Private Methods
    # ========================================

    @property
    def _provider_instances(self) -> Dict[str, DataProviderPolygon]:
        """Compatibility property for legacy engine code"""
        if self.polygon_provider:
            return {"polygon": self.polygon_provider}
        return {}


# Convenience functions for compatibility
