"""
Gap Analyzer Implementation

Concrete implementation of the GapAnalysisInterface for gap trading analysis.
"""

from datetime import datetime
from decimal import Decimal
from typing import List

from ..data_models.models_asset import PriceData
from ..data_models.models_analysis import (
    GapRules,
    GapCandidate,
    GapAssessment,
    GapType,
    RiskLevel,
    ConfidenceLevel,
)
from ..data_models.models_market import MarketStatus
from ..interfaces.interface_gap_analysis import GapAnalysisInterface


class GapAnalyzer(GapAnalysisInterface):
    """Concrete implementation of gap analysis for trading opportunities"""

    @staticmethod
    def meets_gap_criteria(symbol: str, ticker_data: dict,
                          current_price: float, volume: int, price_change_percent: float) -> bool:
        """
        Check if a ticker meets gap analysis criteria for inclusion in movers list.

        This applies the same academic criteria used in gap analysis to pre-filter
        the universe before returning candidates.

        Args:
            symbol: Stock symbol
            ticker_data: Raw ticker data from market snapshot
            current_price: Current stock price
            volume: Current volume
            price_change_percent: Percentage change from previous close

        Returns:
            True if ticker meets gap criteria, False otherwise
        """
        try:
            from ..config.gap_analysis_config import GAP_TRADING_CRITERIA

            criteria = GAP_TRADING_CRITERIA

            # Gap size check - must meet minimum gap threshold
            if abs(price_change_percent) < criteria["min_gap_percent"]:
                return False

            # Volume checks
            if volume < criteria["min_volume"]:  # Minimum absolute volume
                return False

            # Volume ratio check (if previous day volume available)
            prev_day_data = ticker_data.get("prevDay", {})
            prev_volume = prev_day_data.get("v")
            if prev_volume and prev_volume > 0:
                volume_ratio = volume / prev_volume
                if volume_ratio < criteria["min_volume_ratio"]:
                    return False

            # Spread check (if bid/ask available)
            bid = ticker_data.get("bid")
            ask = ticker_data.get("ask")
            if bid and ask and bid > 0:
                spread_percent = ((ask - bid) / bid) * 100
                if spread_percent > criteria["max_spread_percent"]:
                    return False

            # Market cap check (requires fundamentals data - placeholder for now)
            # TODO: Add market cap filtering when fundamentals API is implemented
            # if market_cap < criteria["min_market_cap"]:
            #     return False

            return True

        except Exception as e:
            # Import logging here to avoid circular imports
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Error checking gap criteria for {symbol}: {e}")
            return True  # Default to include if criteria check fails

    def identify_gap_candidates(
        self,
        price_data_list: List[PriceData],
        rules: GapRules,
        session_type: MarketStatus,
    ) -> List[GapCandidate]:
        """
        Identify gap candidates from a list of price data using specified rules.
        """
        candidates = []

        for price_data in price_data_list:
            # Skip if missing required data
            if (
                price_data.current_price is None
                or price_data.prev_session_close_price is None
                or price_data.prev_session_close_price <= 0
            ):
                continue

            # Calculate gap metrics
            gap_size = price_data.current_price - price_data.prev_session_close_price
            gap_percent = (gap_size / price_data.prev_session_close_price) * 100

            # Check if meets gap size criteria
            if abs(float(gap_percent)) < rules.min_gap_percent:
                continue
            if abs(float(gap_percent)) > rules.max_gap_percent:
                continue

            # Price criteria removed - not based on academic research

            # Check volume criteria
            if price_data.volume < rules.min_volume:
                continue
            if (
                price_data.average_volume
                and price_data.volume / price_data.average_volume
                < rules.min_volume_ratio
            ):
                continue

            # Determine gap type
            gap_type = self._classify_gap_type(abs(gap_percent), rules)

            # Create gap candidate
            candidate = GapCandidate(
                asset=price_data.asset,
                analysis_time=datetime.now(),
                session_type=session_type,
                previous_close=price_data.prev_session_close_price,
                current_price=price_data.current_price,
                gap_size=gap_size,
                gap_percent=gap_percent,
                gap_type=gap_type,
                gap_direction="up" if gap_size > 0 else "down",
                volume=price_data.volume,
            )

            candidates.append(candidate)

        return candidates

    def process_gap_candidate(self, gap_candidate: GapCandidate) -> GapAssessment:
        """
        Analyze risk assessment for a single gap candidate.
        """
        # Calculate probabilities based on gap characteristics
        fill_probability = self._calculate_fill_probability(gap_candidate)
        continuation_probability = Decimal("1.0") - fill_probability

        # Determine risk level and confidence
        risk_level = self._assess_risk_level(gap_candidate)
        confidence = self._assess_confidence(gap_candidate)

        # Calculate trade parameters
        entry_price = gap_candidate.current_price
        stop_loss = self._calculate_stop_loss(gap_candidate)
        take_profit = self._calculate_take_profit(gap_candidate)

        # Calculate position sizing
        risk_amount = abs(entry_price - stop_loss)
        reward_amount = abs(take_profit - entry_price)
        risk_reward_ratio = (
            reward_amount / risk_amount if risk_amount > 0 else Decimal("0")
        )

        # Max position size based on risk
        max_position_size = Decimal("1000")  # Default position size for risk management

        return GapAssessment(
            gap_candidate=gap_candidate,
            fill_probability=fill_probability,
            continuation_probability=continuation_probability,
            risk_level=risk_level,
            confidence=confidence,
            suggested_entry=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            max_position_size=max_position_size,
            risk_reward_ratio=risk_reward_ratio,
        )

    def process_gap_candidates(
        self, gap_candidates: List[GapCandidate]
    ) -> List[GapAssessment]:
        """
        Analyze risk assessment for multiple gap candidates.
        """
        return [self.process_gap_candidate(candidate) for candidate in gap_candidates]

    def get_gap_suggestions(
        self,
        gap_candidates: List[GapCandidate],
        limit: int = 5,
        min_gap_percent: float = 2.0,
    ) -> List[GapAssessment]:
        """
        Get comprehensive gap trading suggestions from identified gap candidates.

        This method processes already identified gap candidates:
        1. Process candidates for risk assessment
        2. Filter and rank results based on criteria
        """
        # Step 1: Process candidates for risk assessment
        gap_assessments = self.process_gap_candidates(gap_candidates)

        # Step 2: Filter by minimum gap percentage
        filtered_assessments = [
            assessment
            for assessment in gap_assessments
            if abs(float(assessment.gap_candidate.gap_percent)) >= min_gap_percent
        ]

        # Step 3: Rank by confidence and risk-reward ratio
        # Map confidence levels to numeric values for sorting
        confidence_rank = {
            ConfidenceLevel.VERY_HIGH: 4,
            ConfidenceLevel.HIGH: 3,
            ConfidenceLevel.MEDIUM: 2,
            ConfidenceLevel.LOW: 1,
        }

        # Sort by confidence (desc), then by risk-reward ratio (desc)
        ranked_assessments = sorted(
            filtered_assessments,
            key=lambda a: (
                confidence_rank.get(a.confidence, 0),
                float(a.risk_reward_ratio),
            ),
            reverse=True,
        )

        # Step 4: Apply limit
        return ranked_assessments[:limit]

    def _classify_gap_type(self, gap_percent: float, rules: GapRules) -> GapType:
        """Classify gap type based on size and characteristics"""
        if gap_percent < 2.0:
            return GapType.COMMON
        elif gap_percent >= rules.exhaustion_threshold:
            return GapType.EXHAUSTION
        elif gap_percent >= rules.breakaway_min:
            return GapType.BREAKAWAY
        else:
            return GapType.CONTINUATION

    def _calculate_fill_probability(self, gap_candidate: GapCandidate) -> Decimal:
        """Calculate probability of gap filling based on historical patterns"""
        # Base probability by gap type
        if gap_candidate.gap_type == GapType.COMMON:
            base_prob = Decimal("0.80")
        elif gap_candidate.gap_type == GapType.EXHAUSTION:
            base_prob = Decimal("0.75")
        elif gap_candidate.gap_type == GapType.BREAKAWAY:
            base_prob = Decimal("0.30")
        else:  # CONTINUATION
            base_prob = Decimal("0.50")

        # Adjust for gap size
        gap_size_factor = min(abs(gap_candidate.gap_percent) / 10, 1)
        adjusted_prob = base_prob * (1 - Decimal(str(gap_size_factor)) * Decimal("0.2"))

        return max(min(adjusted_prob, Decimal("0.95")), Decimal("0.05"))

    def _assess_risk_level(self, gap_candidate: GapCandidate) -> RiskLevel:
        """Assess risk level based on gap characteristics"""
        gap_pct = abs(gap_candidate.gap_percent)

        if gap_pct > 7:
            return RiskLevel.AGGRESSIVE
        elif gap_pct > 3:
            return RiskLevel.MODERATE
        else:
            return RiskLevel.CONSERVATIVE

    def _assess_confidence(self, gap_candidate: GapCandidate) -> ConfidenceLevel:
        """Assess confidence level based on gap analysis"""
        # Higher confidence for common gaps and exhaustion gaps
        if gap_candidate.gap_type in [GapType.COMMON, GapType.EXHAUSTION]:
            return ConfidenceLevel.HIGH
        elif gap_candidate.gap_type == GapType.CONTINUATION:
            return ConfidenceLevel.MEDIUM
        else:  # BREAKAWAY
            return ConfidenceLevel.LOW

    def _calculate_stop_loss(self, gap_candidate: GapCandidate) -> Decimal:
        """Calculate stop loss level"""
        # For gap fill trades, stop beyond the gap
        if gap_candidate.gap_direction == "up":
            # Buying for gap fill down - stop above current price
            return gap_candidate.current_price * Decimal("1.02")
        else:
            # Shorting for gap fill up - stop below current price
            return gap_candidate.current_price * Decimal("0.98")

    def _calculate_take_profit(self, gap_candidate: GapCandidate) -> Decimal:
        """Calculate take profit level"""
        # Target partial gap fill
        gap_fill_target = gap_candidate.previous_close + (
            gap_candidate.gap_size * Decimal("0.5")
        )
        return gap_fill_target
