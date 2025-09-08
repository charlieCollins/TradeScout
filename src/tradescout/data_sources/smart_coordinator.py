"""
Smart Data Collection Coordinator

Uses the data sources configuration to intelligently route different types
of data requests to appropriate providers with fallback strategies.

IMPORTANT: This coordinator is PROVIDER AGNOSTIC and should NEVER make direct API calls.
All data access must be delegated to provider implementations. This class contains
zero networking code directly - all HTTP requests, authentication, and API-specific
logic belongs in the provider layer.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Union

from ..config.data_sources_manager import (
    DataSourcesManager,
    DataSourceType,
    FallbackStrategy,
    get_data_sources_manager,
)
from ..data_models.domain_models_core import (
    Asset,
    AssetType,
    CompanyFundamentals,
    ExtendedHoursData,
    MarketQuote,
    MarketStatus,
    PriceData,
)
from ..data_models.factories import MarketFactory
from ..data_models.interfaces import AssetDataProvider
from ..data_models.market_wide_models import MarketMover, MarketMoversReport
from ..data_sources_api.asset_data_provider_tiingo import AssetDataProviderTiingo
from ..data_sources_api.asset_data_provider_polygon import AssetDataProviderPolygon

logger = logging.getLogger(__name__)


class SmartCoordinator:
    """
    Data collection coordinator using Tiingo as the single data source

    Features:
    - Tiingo commercial API integration
    - Comprehensive caching
    - Error handling and retry logic
    - Simplified single-provider architecture
    """

    def __init__(self, config_manager: Optional[DataSourcesManager] = None):
        """
        Initialize smart coordinator

        Args:
            config_manager: Data sources configuration manager
        """
        self.config_manager = config_manager or get_data_sources_manager()
        self._provider_instances: Dict[str, AssetDataProvider] = {}
        self._nasdaq_market = MarketFactory().create_nasdaq_market()

        # Initialize available providers
        self._initialize_providers()

    def _initialize_providers(self) -> None:
        """Initialize available data provider instances"""
        for provider_id in self.config_manager.config.providers:
            if self.config_manager.is_provider_enabled(provider_id):
                try:
                    provider_config = self._get_provider_config(provider_id)
                    if provider_config and provider_config.type == "api":
                        instance = self._create_provider_instance(provider_id)
                        if instance:
                            self._provider_instances[provider_id] = instance
                            logger.debug(f"Initialized API provider: {provider_id}")
                except Exception as e:
                    logger.error(f"Failed to initialize provider {provider_id}: {e}")

    def _get_provider_config(self, provider_id: str) -> Optional[Any]:
        """Get configuration for a provider from centralized config"""
        if provider_id not in self.config_manager.config.providers:
            return None
        return self.config_manager.config.providers[provider_id]

    def _create_provider_instance(
        self, provider_id: str
    ) -> Optional[AssetDataProvider]:
        """Create an instance of the specified provider"""
        try:
            # Get provider config
            provider_config = self._get_provider_config(provider_id)
            if not provider_config:
                logger.warning(f"No configuration found for provider: {provider_id}")
                return None

            if provider_id == "tiingo":
                import os

                api_key = os.getenv("TIINGO_API_KEY")
                if api_key:
                    return AssetDataProviderTiingo(api_key)
                else:
                    logger.warning("Tiingo API key not found")
                    return None
            elif provider_id == "polygon":
                import os
                from pathlib import Path

                # Try to load from .env file if not in environment
                api_key = os.getenv("POLYGON_API_KEY")
                if not api_key:
                    # Look for .env file in project root
                    project_root = Path(__file__).parent.parent.parent.parent
                    env_file = project_root / ".env"
                    if env_file.exists():
                        try:
                            with open(env_file, "r") as f:
                                for line in f:
                                    line = line.strip()
                                    if line.startswith(
                                        "POLYGON_API_KEY="
                                    ) and not line.startswith("POLYGON_API_KEY=your_"):
                                        api_key = line.split("=", 1)[1]
                                        break
                        except Exception as e:
                            logger.debug(f"Error reading .env file: {e}")

                if api_key:
                    return AssetDataProviderPolygon(api_key)
                else:
                    logger.warning("Polygon API key not found")
                    return None
            # Future providers can be added here
            else:
                logger.warning(f"Unknown provider: {provider_id}")
                return None
        except Exception as e:
            logger.error(f"Error creating provider {provider_id}: {e}")
            return None

    def get_current_quote(self, symbol: str) -> Optional[MarketQuote]:
        """
        Get current quote using smart provider selection

        Args:
            symbol: Stock ticker symbol

        Returns:
            MarketQuote or None if all providers fail
        """
        return self._get_data_with_strategy(
            DataSourceType.CURRENT_QUOTES, self._get_quote_from_provider, symbol=symbol
        )

    def get_historical_data(self, symbol: str, **kwargs) -> List[PriceData]:
        """Get historical price data using smart provider selection"""
        return (
            self._get_data_with_strategy(
                DataSourceType.HISTORICAL_PRICES,
                self._get_historical_from_provider,
                symbol=symbol,
                **kwargs,
            )
            or []
        )

    def get_company_fundamentals(self, symbol: str) -> Optional[CompanyFundamentals]:
        """Get company fundamental data using smart provider selection"""
        return self._get_data_with_strategy(
            DataSourceType.COMPANY_FUNDAMENTALS,
            self._get_fundamentals_from_provider,
            symbol=symbol,
        )

    def get_volume_leaders(self, symbols: List[str], **kwargs) -> List[MarketQuote]:
        """Get volume leaders using smart provider selection"""
        return (
            self._get_data_with_strategy(
                DataSourceType.VOLUME_ANALYSIS,
                self._get_volume_leaders_from_provider,
                symbols=symbols,
                **kwargs,
            )
            or []
        )

    def _get_data_with_strategy(
        self, data_type: DataSourceType, fetch_function, **kwargs
    ) -> Any:
        """
        Get data using the configured fallback strategy

        Args:
            data_type: Type of data being requested
            fetch_function: Function to fetch data from a provider
            **kwargs: Arguments to pass to fetch function

        Returns:
            Data from providers based on fallback strategy
        """
        providers = self.config_manager.get_providers_for_data_type(data_type)
        strategy = self.config_manager.get_fallback_strategy(data_type)

        if not providers:
            logger.warning(f"No providers configured for {data_type.value}")
            return None

        logger.debug(
            f"Getting {data_type.value} using {strategy.value} strategy from {len(providers)} providers"
        )

        if strategy == FallbackStrategy.FIRST_SUCCESS:
            return self._first_success_strategy(providers, fetch_function, **kwargs)
        elif strategy == FallbackStrategy.MERGE_BEST:
            return self._merge_best_strategy(providers, fetch_function, **kwargs)
        elif strategy == FallbackStrategy.MERGE_ALL:
            return self._merge_all_strategy(providers, fetch_function, **kwargs)
        elif strategy == FallbackStrategy.ROUND_ROBIN:
            return self._round_robin_strategy(providers, fetch_function, **kwargs)
        else:
            logger.error(f"Unknown fallback strategy: {strategy}")
            return self._first_success_strategy(providers, fetch_function, **kwargs)

    def _first_success_strategy(self, providers, fetch_function, **kwargs) -> Any:
        """Try providers in order until one succeeds"""
        for provider_id, provider_config in providers:
            if provider_id not in self._provider_instances:
                continue

            provider = self._provider_instances[provider_id]

            try:
                logger.debug(f"Trying provider {provider_id}")
                result = fetch_function(provider, provider_id, **kwargs)
                if result is not None:
                    logger.debug(f"Got data from {provider_id}")
                    self.config_manager.record_provider_success(provider_id)
                    return result
                else:
                    logger.debug(f"No data from {provider_id}")
            except Exception as e:
                logger.warning(f"Error from provider {provider_id}: {e}")
                self.config_manager.record_provider_failure(provider_id)

        logger.error("All providers failed")
        return None

    def _merge_best_strategy(self, providers, fetch_function, **kwargs) -> Any:
        """Get data from multiple providers and merge based on quality"""
        results = {}

        for provider_id, provider_config in providers:
            if provider_id not in self._provider_instances:
                continue

            provider = self._provider_instances[provider_id]

            try:
                logger.debug(f"Getting data from {provider_id} for merge")
                result = fetch_function(provider, provider_id, **kwargs)
                if result is not None:
                    results[provider_id] = {
                        "data": result,
                        "quality": provider_config.quality_weight,
                        "priority": provider_config.priority,
                    }
                    self.config_manager.record_provider_success(provider_id)
                    logger.debug(
                        f"Got data from {provider_id} (quality: {provider_config.quality_weight})"
                    )
            except Exception as e:
                logger.warning(f"Error from provider {provider_id}: {e}")
                self.config_manager.record_provider_failure(provider_id)

        if not results:
            logger.error("No providers returned data for merge")
            return None

        # For now, return the highest quality result
        # In the future, this could be enhanced to actually merge data intelligently
        best_provider = max(results.keys(), key=lambda p: results[p]["quality"])
        logger.info(
            f"Using data from {best_provider} (best quality: {results[best_provider]['quality']})"
        )
        return results[best_provider]["data"]

    def _merge_all_strategy(self, providers, fetch_function, **kwargs) -> List[Any]:
        """Get data from all providers and return combined results"""
        all_results = []

        for provider_id, provider_config in providers:
            if provider_id not in self._provider_instances:
                continue

            provider = self._provider_instances[provider_id]

            try:
                result = fetch_function(provider, provider_id, **kwargs)
                if result is not None:
                    # If result is a list, extend; if single item, append
                    if isinstance(result, list):
                        all_results.extend(result)
                    else:
                        all_results.append(result)
                    self.config_manager.record_provider_success(provider_id)
                    logger.debug(f"Added data from {provider_id}")
            except Exception as e:
                logger.warning(f"Error from provider {provider_id}: {e}")
                self.config_manager.record_provider_failure(provider_id)

        logger.info(f"Combined data from {len(all_results)} sources")
        return all_results

    def _round_robin_strategy(self, providers, fetch_function, **kwargs) -> Any:
        """Use round-robin selection of providers"""
        # For now, just use first success
        # Could be enhanced to track usage and rotate
        return self._first_success_strategy(providers, fetch_function, **kwargs)

    def _get_quote_from_provider(
        self, provider: AssetDataProvider, provider_id: str, symbol: str
    ) -> Optional[MarketQuote]:
        """Get quote from a specific provider"""
        asset = self._create_asset(symbol)
        return provider.get_current_quote(asset)

    def _get_historical_from_provider(
        self, provider: AssetDataProvider, provider_id: str, symbol: str, **kwargs
    ) -> List[PriceData]:
        """Get historical data from a specific provider"""
        asset = self._create_asset(symbol)
        # Extract parameters with defaults
        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date")
        interval = kwargs.get("interval", "1d")

        if start_date and end_date:
            return provider.get_historical_quotes(asset, start_date, end_date, interval)
        else:
            logger.warning("Start date and end date required for historical data")
            return []

    def _get_fundamentals_from_provider(
        self, provider: AssetDataProvider, provider_id: str, symbol: str
    ) -> Optional[CompanyFundamentals]:
        """Get fundamental data from a specific provider"""
        asset = self._create_asset(symbol)
        return provider.get_fundamental_data(asset)

    def _get_volume_leaders_from_provider(
        self,
        provider: AssetDataProvider,
        provider_id: str,
        symbols: List[str],
        **kwargs,
    ) -> List[MarketQuote]:
        """Get volume leaders from a specific provider"""
        assets = [self._create_asset(symbol) for symbol in symbols]
        min_volume_ratio = kwargs.get("min_volume_ratio", Decimal("2.0"))
        return provider.scan_volume_leaders(assets, min_volume_ratio)

    def get_market_gainers(
        self, limit: Optional[int] = 20, force_refresh: bool = False
    ) -> List[MarketMover]:
        """
        Get top market gainers using smart provider selection

        Args:
            limit: Maximum number of gainers to return
            force_refresh: Bypass cache and fetch fresh data

        Returns:
            List of top gaining stocks with performance data
        """
        return (
            self._get_data_with_strategy(
                DataSourceType.MARKET_MOVERS,
                self._get_market_gainers_from_provider,
                limit=limit,
                force_refresh=force_refresh,
            )
            or []
        )

    def get_market_losers(
        self, limit: Optional[int] = 20, force_refresh: bool = False
    ) -> List[MarketMover]:
        """
        Get top market losers using smart provider selection

        Args:
            limit: Maximum number of losers to return
            force_refresh: Bypass cache and fetch fresh data

        Returns:
            List of top losing stocks with performance data
        """
        return (
            self._get_data_with_strategy(
                DataSourceType.MARKET_MOVERS,
                self._get_market_losers_from_provider,
                limit=limit,
                force_refresh=force_refresh,
            )
            or []
        )

    def get_most_active(
        self, limit: int = 20, force_refresh: bool = False
    ) -> List[MarketMover]:
        """
        Get most active stocks by volume using smart provider selection

        Args:
            limit: Maximum number of active stocks to return
            force_refresh: Bypass cache and fetch fresh data

        Returns:
            List of most active stocks by trading volume
        """
        return (
            self._get_data_with_strategy(
                DataSourceType.MARKET_MOVERS,
                self._get_most_active_from_provider,
                limit=limit,
                force_refresh=force_refresh,
            )
            or []
        )

    def get_market_movers_report(
        self, limit: int = 20, force_refresh: bool = False
    ) -> MarketMoversReport:
        """
        Get comprehensive market movers report using smart provider selection

        Args:
            limit: Maximum number of movers in each category
            force_refresh: Bypass cache and fetch fresh data

        Returns:
            Complete report with gainers, losers, and most active
        """
        # Try to get complete report from providers that support it
        report = self._get_data_with_strategy(
            DataSourceType.MARKET_MOVERS,
            self._get_market_movers_report_from_provider,
            limit=limit,
            force_refresh=force_refresh,
        )

        if not report:
            raise RuntimeError("No market movers data available from any provider")

        return report

    def _get_market_gainers_from_provider(
        self, provider: AssetDataProvider, provider_id: str, **kwargs
    ) -> List[MarketMover]:
        """Get market gainers from a specific provider"""
        # Check if provider has market movers capability
        if hasattr(provider, "get_market_gainers"):
            return provider.get_market_gainers(**kwargs)
        return None

    def _get_market_losers_from_provider(
        self, provider: AssetDataProvider, provider_id: str, **kwargs
    ) -> List[MarketMover]:
        """Get market losers from a specific provider"""
        if hasattr(provider, "get_market_losers"):
            return provider.get_market_losers(**kwargs)
        return None

    def _get_most_active_from_provider(
        self, provider: AssetDataProvider, provider_id: str, **kwargs
    ) -> List[MarketMover]:
        """Get most active stocks from a specific provider"""
        if hasattr(provider, "get_most_active"):
            return provider.get_most_active(**kwargs)
        return None

    def _get_market_movers_report_from_provider(
        self, provider: AssetDataProvider, provider_id: str, **kwargs
    ) -> MarketMoversReport:
        """Get complete market movers report from a specific provider"""
        if hasattr(provider, "get_market_movers_report"):
            return provider.get_market_movers_report(**kwargs)
        return None

    def _get_current_market_status(self) -> MarketStatus:
        """Determine current market status"""
        now = datetime.now()
        # Simple check - can be enhanced
        weekday = now.weekday()
        hour = now.hour

        # Market closed on weekends
        if weekday >= 5:
            return MarketStatus.CLOSED

        # Market hours: 9:30 AM - 4:00 PM ET
        if 9 <= hour < 16:
            return MarketStatus.OPEN
        elif hour < 9:
            return MarketStatus.PRE_MARKET
        elif hour < 20:
            return MarketStatus.AFTER_HOURS
        else:
            return MarketStatus.CLOSED

    def _create_asset(self, symbol: str) -> Asset:
        """Create a basic Asset object for the given symbol"""
        return Asset(
            symbol=symbol.upper(),
            name=f"{symbol.upper()} Corp",
            asset_type=AssetType.COMMON_STOCK,
            market=self._nasdaq_market,
            currency="USD",
        )

    def get_provider_status(self) -> Dict[str, Any]:
        """Get status of all providers"""
        return self.config_manager.get_provider_status()

    def get_available_data_types(self) -> List[str]:
        """Get list of available data types"""
        return self.config_manager.list_data_types()

    def reload_config(self) -> None:
        """Reload configuration and reinitialize providers"""
        logger.info("Reloading smart coordinator configuration...")
        self.config_manager.reload_config()
        self._provider_instances.clear()
        self._initialize_providers()

    # Gap Trading Analysis Methods

    def get_daily_gap_suggestions(
        self, min_gap_percent: float = 2.0, movers_limit: Optional[int] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> List[Dict[str, any]]:
        """
        Generate daily gap trading suggestions using integrated analysis workflow

        Args:
            min_gap_percent: Minimum gap size to consider (default: 2.0%)
            movers_limit: Limit market movers to analyze (overrides config if provided)
            progress_callback: Optional callback for progress updates (symbol, current, total)

        Returns:
            List of gap trading suggestions with analysis
        """
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
                Decimal(str(min_gap_percent)), movers_limit, progress_callback
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

            # Step 5: Filter and rank suggestions (no max limit - return ALL valid suggestions)
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

    def scan_gap_opportunities(self, min_gap_percent: float = 2.0) -> Dict[str, any]:
        """
        Comprehensive gap opportunity scan with detailed analysis

        Args:
            min_gap_percent: Minimum gap percentage to scan for

        Returns:
            Dictionary with gap scan results and statistics
        """
        logger.info(f"Scanning for gap opportunities >= {min_gap_percent}%")

        try:
            from ..analysis.gap_market_scanner import GapMarketScanner
            from ..analysis.gap_rules_engine import GapRulesEngine
            from decimal import Decimal

            # Initialize scanner and rules engine
            gap_scanner = GapMarketScanner(self)
            rules_engine = GapRulesEngine()

            # Get comprehensive gap scan
            scan_results = gap_scanner.get_comprehensive_gap_scan(
                Decimal(str(min_gap_percent))
            )

            # Apply rules to all candidates
            rules_analysis = []
            for quote in scan_results["gap_candidates"]:
                evaluation = rules_engine.evaluate_gap_candidate(quote)
                rules_analysis.append(
                    {
                        "symbol": quote.asset.symbol,
                        "evaluation": evaluation,
                        "quote": quote,
                    }
                )

            # Compile statistics
            total_candidates = len(scan_results["gap_candidates"])
            rules_approved = len(
                [r for r in rules_analysis if r["evaluation"]["decision"] == "TRADE"]
            )
            volume_confirmed = len(scan_results["volume_confirmed"])
            high_quality = len(scan_results["high_quality"])

            return {
                "scan_results": scan_results,
                "rules_analysis": rules_analysis,
                "statistics": {
                    "total_candidates": total_candidates,
                    "rules_approved": rules_approved,
                    "volume_confirmed": volume_confirmed,
                    "high_quality": high_quality,
                    "approval_rate": (
                        (rules_approved / total_candidates * 100)
                        if total_candidates > 0
                        else 0
                    ),
                },
                "timestamp": datetime.now(),
            }

        except Exception as e:
            logger.error(f"Error scanning gap opportunities: {e}")
            return {"error": str(e)}

    def get_daily_ohlc(self, symbol: str, date: str = None) -> Optional[Dict[str, Any]]:
        """
        Get daily OHLC data for a symbol using provider delegation.

        Args:
            symbol: Stock symbol
            date: Date string (YYYY-MM-DD), defaults to current date

        Returns:
            Dictionary with OHLC data or None if error
        """
        try:
            # Delegate to provider instead of direct API calls
            polygon_provider = self._provider_instances.get("polygon")
            if polygon_provider and hasattr(polygon_provider, "get_daily_ohlc"):
                return polygon_provider.get_daily_ohlc(symbol, date)

            # No fallback - coordinator should never make direct API calls
            logger.error("No provider available for daily OHLC data")
            return None

        except Exception as e:
            logger.error(f"Error getting daily OHLC for {symbol}: {e}")
            return None

    def get_full_market_snapshot(
        self, force_refresh: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Get full market snapshot for all US stocks using provider caching.

        Returns current prices AND previous/today's close data for gap calculations.
        Uses provider's intelligent caching to avoid unnecessary API calls.

        Args:
            force_refresh: Bypass cache and fetch fresh data

        Returns:
            Dictionary mapping symbol -> snapshot data, or None if error
        """
        try:
            # Use provider's cached market data instead of direct API calls
            polygon_provider = self._provider_instances.get("polygon")
            if polygon_provider and hasattr(polygon_provider, "_get_fresh_market_data"):
                return polygon_provider._get_fresh_market_data(
                    force_refresh=force_refresh
                )

            # No fallback - coordinator should never make direct API calls
            logger.error("No Polygon provider available for market snapshot")
            return None

        except Exception as e:
            logger.error(f"Error getting full market snapshot: {e}")
            return None

    def get_gap_data_from_snapshot(
        self, symbol: str, snapshot_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Extract session-aware gap calculation data using hybrid approach:
        - Snapshot data for reference prices (previous/today's close)
        - Live quotes API for current extended hours pricing

        Args:
            symbol: Stock symbol to get gap data for
            snapshot_data: Result from get_full_market_snapshot()

        Returns:
            Dict with current_price, reference_close, gap_percent, or None if not found
        """
        try:
            from datetime import datetime

            symbol = symbol.upper()
            if symbol not in snapshot_data:
                return None

            ticker_data = snapshot_data[symbol]

            # Always get reference closes from snapshot (reliable for all sessions)
            previous_close = None
            todays_close = None

            if "prevDay" in ticker_data:
                previous_close = ticker_data["prevDay"].get("c")  # Previous day close
            if "day" in ticker_data:
                todays_close = ticker_data["day"].get("c")  # Today's close

            if previous_close is None:
                return None

            # Determine session and reference price
            now = datetime.now()
            current_hour = now.hour

            if 4 <= current_hour < 16:  # Pre-market or regular hours (4 AM - 4 PM)
                reference_close = previous_close
                session_type = "premarket" if current_hour < 9.5 else "regular"
                use_live_quote = (
                    current_hour < 9.5
                )  # Use live quotes for pre-market only
            else:  # After-hours (after 4 PM) or late night (before 4 AM)
                reference_close = todays_close if todays_close else previous_close
                session_type = "afterhours"
                use_live_quote = True  # Always use live quotes for after-hours

            # Get current price - hybrid approach
            current_price = None

            if use_live_quote:
                # Try live extended hours data first
                live_data = self.get_live_extended_hours_quote(symbol)
                if live_data and live_data.get("current_price"):
                    current_price = live_data["current_price"]
                    logger.debug(
                        f"Using live extended hours price for {symbol}: ${current_price:.2f}"
                    )
                elif live_data and live_data.get("midpoint"):
                    # Fallback to midpoint for backward compatibility
                    current_price = live_data["midpoint"]
                    logger.debug(
                        f"Using live midpoint for {symbol}: ${current_price:.2f}"
                    )

            # Fallback to snapshot data if live quote failed or not needed
            if current_price is None:
                if "min" in ticker_data and ticker_data["min"].get("c", 0) > 0:
                    current_price = ticker_data["min"]["c"]
                elif "day" in ticker_data and ticker_data["day"].get("c", 0) > 0:
                    current_price = ticker_data["day"]["c"]

            if current_price is None:
                return None

            # Calculate gap percentage
            gap_amount = current_price - reference_close
            gap_percent = abs((gap_amount / reference_close) * 100)

            return {
                "current_price": current_price,
                "reference_close": reference_close,
                "gap_percent": gap_percent,
                "gap_amount": gap_amount,
                "session_type": session_type,
                "previous_close": previous_close,
                "todays_close": todays_close,
                "used_live_quote": use_live_quote
                and current_price != ticker_data.get("day", {}).get("c"),
            }

        except Exception as e:
            logger.error(f"Error extracting gap data for {symbol}: {e}")
            return None

    def get_live_extended_hours_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get live extended hours pricing for a single symbol using Polygon custom bars endpoint.
        Uses hourly bars covering pre-market, regular market, and after-hours sessions.

        Args:
            symbol: Stock symbol to get live extended hours pricing for

        Returns:
            Dict with current extended hours price or None if error/no data
        """
        try:
            # Delegate to provider instead of direct API calls
            polygon_provider = self._provider_instances.get("polygon")
            if polygon_provider and hasattr(
                polygon_provider, "get_live_extended_hours_quote"
            ):
                return polygon_provider.get_live_extended_hours_quote(symbol)

            # No fallback - coordinator should never make direct API calls
            logger.error("No provider available for live extended hours quotes")
            return None

        except Exception as e:
            logger.error(f"Error getting live extended hours data for {symbol}: {e}")
            return None

    def _get_previous_business_day(self, date_str: str) -> str:
        """Get previous business day string"""
        from datetime import datetime, timedelta

        date_obj = datetime.strptime(date_str, "%Y-%m-%d")

        # Go back one day, then skip weekends
        prev_date = date_obj - timedelta(days=1)

        # If it's a weekend, go to Friday
        while prev_date.weekday() >= 5:  # 5=Saturday, 6=Sunday
            prev_date -= timedelta(days=1)

        return prev_date.strftime("%Y-%m-%d")


# Convenience functions
def create_smart_coordinator() -> SmartCoordinator:
    """Create a smart coordinator with default configuration"""
    return SmartCoordinator()


if __name__ == "__main__":
    # Test the smart coordinator
    print("🧪 Testing Smart Coordinator...")

    import os

    coordinator = create_smart_coordinator()

    print(f"\n📊 Initialized with {len(coordinator._provider_instances)} providers")
    for provider_id in coordinator._provider_instances:
        print(f"  - {provider_id}")

    # Test quote functionality
    print(f"\n📈 Testing quote for AAPL...")
    quote = coordinator.get_current_quote("AAPL")
    if quote:
        print(f"Price: ${quote.price_data.price}")
        print(f"Change: {quote.price_change_percent:.2f}%")
    else:
        print("Failed to get quote")

    # Test fundamentals
    print(f"\n📊 Testing fundamentals for AAPL...")
    fundamentals = coordinator.get_company_fundamentals("AAPL")
    if fundamentals:
        print(f"Company: {fundamentals.get('company_name', 'N/A')}")
        print(f"Market Cap: ${fundamentals.get('market_cap', 0):,}")
    else:
        print("Failed to get fundamentals")

    print("\n✅ Smart Coordinator test completed!")
