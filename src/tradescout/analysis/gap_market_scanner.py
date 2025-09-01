"""
Gap Market Scanner Implementation

Scans the market for overnight gaps based on academic research criteria.
Implements MarketScanner interface to detect gap trading opportunities.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from ..data_models.domain_models_core import Asset, AssetType, MarketQuote, NewsItem
from ..data_models.domain_models_analysis import MarketEvent
from ..data_models.factories import MarketFactory
from ..data_sources.smart_coordinator import SmartCoordinator
from .interfaces import MarketScanner

logger = logging.getLogger(__name__)


class GapMarketScanner(MarketScanner):
    """
    Market scanner specifically designed for gap trading opportunities

    Features:
    - Overnight gap detection (close to open)
    - Volume ratio analysis
    - Market cap filtering
    - Academic research-based thresholds
    """

    def __init__(self, coordinator: SmartCoordinator):
        """
        Initialize gap market scanner

        Args:
            coordinator: Smart coordinator for data access
        """
        self.coordinator = coordinator
        self.nasdaq_market = MarketFactory().create_nasdaq_market()

        # Academic research thresholds
        self.min_gap_threshold = Decimal("2.0")  # 2.0% minimum from research
        self.min_volume_ratio = Decimal("2.0")  # 2x average volume minimum
        self.min_market_cap = 1_000_000_000  # $1B minimum market cap
        self.max_bid_ask_spread = Decimal("1.0")  # 1% maximum spread

    def scan_pre_market_gaps(
        self, min_gap_percent: Decimal = Decimal("2.0")
    ) -> List[MarketQuote]:
        """
        Scan for significant pre-market gaps using market movers data

        Args:
            min_gap_percent: Minimum gap percentage (default from research: 2.0%)

        Returns:
            List of stocks with significant overnight gaps
        """
        logger.info(f"Scanning for pre-market gaps >= {min_gap_percent}%")

        gap_candidates = []

        try:
            # Get market movers (gainers + losers) as gap candidates
            # These represent stocks with significant overnight price movement
            gainers = self.coordinator.get_market_gainers(limit=50, force_refresh=False)
            losers = self.coordinator.get_market_losers(limit=50, force_refresh=False)

            # Combine and analyze all movers
            all_movers = []
            if gainers:
                all_movers.extend(gainers)
            if losers:
                all_movers.extend(losers)

            logger.info(f"Analyzing {len(all_movers)} market movers for gap patterns")

            for mover in all_movers:
                try:
                    # Calculate gap size from price change percentage
                    # Market movers already represent overnight gaps
                    gap_percent = abs(mover.price_change_percent)

                    if gap_percent >= min_gap_percent:
                        # Get current quote for additional data
                        quote = self.coordinator.get_current_quote(mover.asset.symbol)

                        if quote and self._meets_basic_criteria(quote, gap_percent):
                            # Add gap information to quote
                            quote.gap_size = gap_percent
                            quote.gap_direction = (
                                "up" if mover.price_change_percent > 0 else "down"
                            )
                            gap_candidates.append(quote)

                            logger.debug(
                                f"Found gap candidate: {mover.asset.symbol} "
                                f"({gap_percent:.2f}% gap)"
                            )

                except Exception as e:
                    logger.warning(f"Error analyzing mover {mover.asset.symbol}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error scanning for pre-market gaps: {e}")

        logger.info(f"Found {len(gap_candidates)} gap candidates >= {min_gap_percent}%")
        return gap_candidates

    def scan_volume_spikes(
        self, min_volume_ratio: Decimal = Decimal("2.0")
    ) -> List[MarketQuote]:
        """
        Scan for unusual volume activity using volume leaders

        Args:
            min_volume_ratio: Minimum volume ratio vs average

        Returns:
            List of stocks with volume spikes
        """
        logger.info(f"Scanning for volume spikes >= {min_volume_ratio}x average")

        volume_candidates = []

        try:
            # Use existing volume leaders functionality
            # Scan a broad set of symbols for volume spikes
            major_symbols = [
                # Large cap tech
                "AAPL",
                "MSFT",
                "GOOGL",
                "GOOG",
                "AMZN",
                "TSLA",
                "NVDA",
                "META",
                # Financial
                "JPM",
                "BAC",
                "WFC",
                "C",
                "GS",
                "MS",
                # Healthcare
                "JNJ",
                "PFE",
                "UNH",
                "ABBV",
                "MRK",
                "TMO",
                # Consumer
                "WMT",
                "PG",
                "KO",
                "PEP",
                "NKE",
                "HD",
                # Industrial
                "CAT",
                "BA",
                "GE",
                "MMM",
                "HON",
                "UPS",
            ]

            volume_leaders = self.coordinator.get_volume_leaders(
                major_symbols, min_volume_ratio=min_volume_ratio
            )

            if volume_leaders:
                volume_candidates.extend(volume_leaders)
                logger.info(f"Found {len(volume_leaders)} volume leaders")

        except Exception as e:
            logger.error(f"Error scanning for volume spikes: {e}")

        return volume_candidates

    def scan_news_catalysts(
        self, max_age_hours: int = 24
    ) -> List[Tuple[str, List[NewsItem]]]:
        """
        Scan for stocks with recent news catalysts

        Args:
            max_age_hours: Maximum age of news to consider

        Returns:
            List of (symbol, news_items) tuples
        """
        logger.info(f"Scanning for news catalysts within {max_age_hours} hours")

        # This would require NewsAPI implementation
        # For now, return empty list as placeholder
        logger.warning("News catalyst scanning not yet implemented - requires NewsAPI")
        return []

    def scan_earnings_plays(self, days_ahead: int = 1) -> List[MarketEvent]:
        """
        Scan for upcoming earnings that could create momentum

        Args:
            days_ahead: Days to look ahead for earnings

        Returns:
            List of earnings events
        """
        logger.info(f"Scanning for earnings plays {days_ahead} days ahead")

        # This would require earnings calendar data
        # For now, return empty list as placeholder
        logger.warning(
            "Earnings scanning not yet implemented - requires earnings calendar"
        )
        return []

    def get_comprehensive_gap_scan(
        self, min_gap_percent: Decimal = Decimal("2.0")
    ) -> Dict[str, List[MarketQuote]]:
        """
        Comprehensive scan combining gap detection with volume confirmation

        Args:
            min_gap_percent: Minimum gap percentage threshold

        Returns:
            Dictionary with categorized gap opportunities
        """
        logger.info("Running comprehensive gap scan")

        results = {
            "gap_candidates": [],
            "volume_confirmed": [],
            "high_quality": [],
            "rejected": [],
        }

        # Get gap candidates
        gap_candidates = self.scan_pre_market_gaps(min_gap_percent)
        results["gap_candidates"] = gap_candidates

        # Filter for volume confirmation
        volume_confirmed = []
        high_quality = []
        rejected = []

        for quote in gap_candidates:
            try:
                # Check volume confirmation
                volume_ratio = getattr(quote, "volume_ratio", None)
                if volume_ratio and volume_ratio >= self.min_volume_ratio:
                    volume_confirmed.append(quote)

                    # Check for high quality setup
                    if self._is_high_quality_setup(quote):
                        high_quality.append(quote)
                else:
                    rejected.append(quote)

            except Exception as e:
                logger.warning(f"Error analyzing quote {quote.asset.symbol}: {e}")
                rejected.append(quote)
                continue

        results["volume_confirmed"] = volume_confirmed
        results["high_quality"] = high_quality
        results["rejected"] = rejected

        logger.info(
            f"Gap scan results: {len(gap_candidates)} candidates, "
            f"{len(volume_confirmed)} volume confirmed, "
            f"{len(high_quality)} high quality"
        )

        return results

    def _meets_basic_criteria(self, quote: MarketQuote, gap_percent: Decimal) -> bool:
        """
        Check if quote meets basic gap trading criteria

        Args:
            quote: Market quote to evaluate
            gap_percent: Gap percentage for this stock

        Returns:
            True if meets basic criteria
        """
        try:
            # Check market cap requirement (if available)
            if hasattr(quote, "market_cap") and quote.market_cap:
                if quote.market_cap < self.min_market_cap:
                    logger.debug(f"Rejected {quote.asset.symbol}: Market cap too small")
                    return False

            # Check volume exists
            if not quote.price_data.volume or quote.price_data.volume == 0:
                logger.debug(f"Rejected {quote.asset.symbol}: No volume data")
                return False

            # Check price is reasonable (basic sanity check)
            if quote.price_data.price <= 0 or quote.price_data.price > 10000:
                logger.debug(f"Rejected {quote.asset.symbol}: Unreasonable price")
                return False

            return True

        except Exception as e:
            logger.warning(
                f"Error checking basic criteria for {quote.asset.symbol}: {e}"
            )
            return False

    def _is_high_quality_setup(self, quote: MarketQuote) -> bool:
        """
        Determine if this is a high-quality gap setup

        Args:
            quote: Market quote to evaluate

        Returns:
            True if high quality setup
        """
        try:
            # High quality requires:
            # 1. Large gap (>3%)
            # 2. High volume (>3x average)
            # 3. Large market cap (if available)

            gap_size = getattr(quote, "gap_size", Decimal(0))
            volume_ratio = getattr(quote, "volume_ratio", Decimal(0))

            if gap_size >= 3.0 and volume_ratio >= 3.0:
                return True

            return False

        except Exception as e:
            logger.warning(f"Error assessing quality for {quote.asset.symbol}: {e}")
            return False
