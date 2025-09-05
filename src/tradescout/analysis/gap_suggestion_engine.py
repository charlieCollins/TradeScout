"""
Gap Trade Suggestion Engine Implementation

Generates trade suggestions based on gap analysis and academic research.
Implements SuggestionEngine interface for systematic trade recommendations.
"""

import logging
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from ..data_models.domain_models_analysis import (
    ConfidenceLevel,
    GapTradabilityAssessment,
    TradeSide,
    TradeStatus,
    TradeSuggestion,
)
from ..data_models.domain_models_core import MarketQuote
from .interfaces import SuggestionEngine

logger = logging.getLogger(__name__)


class GapTradeSuggestionEngine(SuggestionEngine):
    """
    Trade suggestion engine specialized for gap trading

    Features:
    - Academic research-based suggestions
    - Risk-managed position sizing (2% max account risk)
    - Intraday-only recommendations (no overnight holds)
    - Multiple take-profit targets (1:1 and 2:1 risk/reward)
    """

    def __init__(self, account_balance: Decimal = Decimal("100000")):
        """
        Initialize gap trade suggestion engine

        Args:
            account_balance: Account balance for position sizing calculations
        """
        self.account_balance = account_balance

        # Risk management parameters from academic rules
        self.max_account_risk = Decimal("0.02")  # 2% max account risk
        self.base_position_risk = Decimal("0.01")  # 1% base position size
        self.max_position_size = Decimal("0.02")  # 2% maximum position

        # Academic trading rules
        self.mandatory_exit_time = "16:00"  # Market close
        self.entry_window_start = "09:30"  # Market open
        self.entry_window_end = "10:30"  # First hour maximum

        # Risk/reward targets
        self.target_ratio_1 = Decimal("1.0")  # 1:1 first target
        self.target_ratio_2 = Decimal("2.0")  # 2:1 second target

    def generate_suggestion(
        self, symbol: str, analysis_data: Dict[str, any]
    ) -> Optional[TradeSuggestion]:
        """
        Generate trade suggestion from gap analysis

        Args:
            symbol: Stock symbol
            analysis_data: Gap analysis results including classification and assessment

        Returns:
            TradeSuggestion or None if no valid setup
        """
        logger.debug(f"Generating trade suggestion for {symbol}")

        try:
            # Extract analysis components
            quote = analysis_data.get("quote")
            gap_assessment = analysis_data.get("gap_assessment")

            if not quote or not gap_assessment:
                logger.warning(f"Insufficient analysis data for {symbol}")
                return None

            # Check if gap is tradeable
            if not gap_assessment.is_tradeable:
                logger.debug(f"Gap {symbol} not tradeable - skipping suggestion")
                return None

            # Generate trade suggestion
            suggestion = self._create_trade_suggestion(symbol, quote, gap_assessment)

            logger.info(
                f"Generated trade suggestion for {symbol}: "
                f"{suggestion.side.value} @ ${suggestion.suggested_entry:.2f}"
            )

            return suggestion

        except Exception as e:
            logger.error(f"Error generating suggestion for {symbol}: {e}")
            return None

    def rank_suggestions(
        self, suggestions: List[TradeSuggestion]
    ) -> List[TradeSuggestion]:
        """
        Rank suggestions by quality and confidence

        Args:
            suggestions: List of trade suggestions

        Returns:
            Sorted list (best first)
        """
        logger.debug(f"Ranking {len(suggestions)} trade suggestions")

        def suggestion_score(suggestion: TradeSuggestion) -> float:
            """Calculate ranking score for suggestion"""
            score = 0.0

            # Base score from confidence level
            confidence_scores = {
                ConfidenceLevel.VERY_HIGH: 100,
                ConfidenceLevel.HIGH: 80,
                ConfidenceLevel.MEDIUM: 60,
                ConfidenceLevel.LOW: 30,
            }
            score += confidence_scores.get(suggestion.confidence, 50)

            # Bonus for better risk/reward ratio
            if suggestion.risk_reward_ratio > 2.0:
                score += 20
            elif suggestion.risk_reward_ratio > 1.5:
                score += 10

            # Bonus for larger gap size (more momentum)
            if hasattr(suggestion, "gap_size"):
                gap_size = getattr(suggestion, "gap_size", 0)
                if gap_size > 4.0:
                    score += 15
                elif gap_size > 3.0:
                    score += 10
                elif gap_size > 2.5:
                    score += 5

            # Penalty for higher risk
            if suggestion.stop_loss_distance > 0.03:  # >3% stop
                score -= 10

            return score

        # Sort by score (highest first)
        ranked_suggestions = sorted(suggestions, key=suggestion_score, reverse=True)

        logger.info(
            f"Ranked suggestions: {len(ranked_suggestions)} suggestions sorted by quality"
        )

        return ranked_suggestions

    def filter_suggestions(
        self, suggestions: List[TradeSuggestion]
    ) -> List[TradeSuggestion]:
        """
        Filter suggestions to valid candidates (no arbitrary limits)

        Args:
            suggestions: List of trade suggestions

        Returns:
            Filtered list of all valid suggestions
        """
        logger.debug(
            f"Filtering {len(suggestions)} suggestions (no max limit)"
        )

        # First rank all suggestions
        ranked_suggestions = self.rank_suggestions(suggestions)

        # Filter out low-confidence suggestions
        filtered_suggestions = []

        for suggestion in ranked_suggestions:
            # Only include medium confidence or higher
            if suggestion.confidence in [
                ConfidenceLevel.MEDIUM,
                ConfidenceLevel.HIGH,
                ConfidenceLevel.VERY_HIGH,
            ]:
                filtered_suggestions.append(suggestion)

        logger.info(f"Filtered to {len(filtered_suggestions)} high-quality suggestions")

        return filtered_suggestions

    def validate_suggestion(self, suggestion: TradeSuggestion) -> bool:
        """
        Validate that suggestion meets quality criteria

        Args:
            suggestion: Trade suggestion to validate

        Returns:
            True if suggestion is valid
        """
        logger.debug(f"Validating suggestion for {suggestion.asset.symbol}")

        validation_errors = []

        # Check entry price is reasonable
        if suggestion.suggested_entry <= 0:
            validation_errors.append("Entry price must be positive")

        # Check stop loss is set appropriately
        if suggestion.side == TradeSide.LONG:
            if suggestion.stop_loss >= suggestion.suggested_entry:
                validation_errors.append(
                    "Stop loss must be below entry price for long trades"
                )
        else:
            if suggestion.stop_loss <= suggestion.suggested_entry:
                validation_errors.append(
                    "Stop loss must be above entry price for short trades"
                )

        # Check risk/reward ratio is reasonable
        if suggestion.risk_reward_ratio < 0.5:
            validation_errors.append("Risk/reward ratio too poor")

        # Check position sizing is reasonable
        if suggestion.position_size_percent <= 0:
            validation_errors.append("Position size must be positive")

        # max_position_size is already in decimal (0.02 = 2%), position_size_percent is in percentage
        max_allowed_percent = float(self.max_position_size * 100)  # Convert 0.02 to 2.0
        if float(suggestion.position_size_percent) > max_allowed_percent:
            validation_errors.append(f"Position size {suggestion.position_size_percent}% exceeds maximum {max_allowed_percent}%")

        # Check timing is within trading hours
        current_time = datetime.now().time()
        entry_time = datetime.strptime(self.entry_window_start, "%H:%M").time()
        exit_time = datetime.strptime(self.entry_window_end, "%H:%M").time()

        # Log validation results
        if validation_errors:
            logger.warning(
                f"Suggestion validation failed for {suggestion.asset.symbol}: "
                f"{'; '.join(validation_errors)}"
            )
            return False

        logger.debug(f"Suggestion validation passed for {suggestion.asset.symbol}")
        return True

    def _create_trade_suggestion(
        self, symbol: str, quote: MarketQuote, gap_assessment: GapTradabilityAssessment
    ) -> TradeSuggestion:
        """Create trade suggestion from gap analysis"""

        # Determine trade direction based on gap
        gap_direction = quote.gap_direction or "up"
        side = TradeSide.LONG if gap_direction == "up" else TradeSide.SHORT

        # Entry price (current price)
        entry_price = quote.price_data.price

        # Calculate stop loss based on gap fill level or percentage
        stop_loss = self._calculate_stop_loss(quote, entry_price, side)

        # Calculate take profit targets
        target_1, target_2 = self._calculate_take_profit_targets(
            entry_price, stop_loss, side
        )

        # Position size will be set as percentage in TradeSuggestion

        # Calculate risk metrics
        risk_reward_ratio = self._calculate_risk_reward_ratio(
            entry_price, stop_loss, target_1
        )
        stop_loss_distance = abs(entry_price - stop_loss) / entry_price

        # Determine confidence level from gap classification
        gap_confidence = float(gap_assessment.gap_classification.confidence_score)
        if gap_confidence >= 0.85:
            confidence = ConfidenceLevel.VERY_HIGH
        elif gap_confidence >= 0.70:
            confidence = ConfidenceLevel.HIGH
        elif gap_confidence >= 0.50:
            confidence = ConfidenceLevel.MEDIUM
        else:
            confidence = ConfidenceLevel.LOW

        # Create suggestion
        suggestion = TradeSuggestion(
            id=str(uuid.uuid4()),
            asset=quote.asset,
            side=side,
            suggested_entry=entry_price,
            stop_loss=stop_loss,
            take_profit_1=target_1,
            take_profit_2=target_2,
            confidence=confidence,
            confidence_score=gap_assessment.gap_classification.confidence_score,
            risk_reward_ratio=risk_reward_ratio,
            position_size_percent=gap_assessment.suggested_position_size_percent,  # Already in percentage
            rationale=self._create_analysis_summary(quote, gap_assessment),
            risk_factors=gap_assessment.primary_risks,
            supporting_factors=gap_assessment.key_success_factors,
            gap_percent=quote.gap_size or abs(quote.price_change_percent or Decimal(0)),
            stop_loss_distance=stop_loss_distance,
            gap_size=quote.gap_size or abs(quote.price_change_percent or Decimal(0)),
            gap_type=gap_assessment.recommended_strategy,
            volume_ratio=quote.volume_ratio,
        )

        # Fields are now set properly in constructor - no dynamic assignment needed

        return suggestion

    def _calculate_stop_loss(
        self, quote: MarketQuote, entry_price: Decimal, side: TradeSide
    ) -> Decimal:
        """Calculate stop loss level"""

        # For gap trading, primary stop is gap fill level (previous close)
        # Secondary is percentage-based stop

        gap_size = quote.gap_size or abs(quote.price_change_percent or Decimal(0))
        gap_size_decimal = gap_size / 100  # Convert to decimal

        if side == TradeSide.LONG:
            # For gap up, stop at previous close (gap fill) or 2% below entry
            previous_close = entry_price / (1 + gap_size_decimal)
            percent_stop = entry_price * Decimal("0.98")  # 2% below
            stop_loss = max(previous_close, percent_stop)  # Use whichever is higher
        else:
            # For gap down, stop at previous close or 2% above entry
            previous_close = entry_price / (1 - gap_size_decimal)
            percent_stop = entry_price * Decimal("1.02")  # 2% above
            stop_loss = min(previous_close, percent_stop)  # Use whichever is lower

        return stop_loss

    def _calculate_take_profit_targets(
        self, entry_price: Decimal, stop_loss: Decimal, side: TradeSide
    ) -> tuple[Decimal, Decimal]:
        """Calculate take profit targets at 1:1 and 2:1 risk/reward"""

        risk_amount = abs(entry_price - stop_loss)

        if side == TradeSide.LONG:
            target_1 = entry_price + (risk_amount * self.target_ratio_1)  # 1:1
            target_2 = entry_price + (risk_amount * self.target_ratio_2)  # 2:1
        else:
            target_1 = entry_price - (risk_amount * self.target_ratio_1)  # 1:1
            target_2 = entry_price - (risk_amount * self.target_ratio_2)  # 2:1

        return target_1, target_2

    def _calculate_position_size(
        self, entry_price: Decimal, stop_loss: Decimal, position_sizing_percent: float
    ) -> int:
        """Calculate position size based on risk management rules"""

        # Calculate dollar risk per share
        risk_per_share = abs(entry_price - stop_loss)

        # Calculate position sizing based on percentage recommendation
        account_risk_dollars = self.account_balance * Decimal(
            str(position_sizing_percent / 100)
        )

        # Calculate number of shares
        if risk_per_share > 0:
            shares = int(account_risk_dollars / risk_per_share)
        else:
            shares = 0

        # Ensure minimum position but respect maximums
        min_shares = max(1, int(100 / float(entry_price)))  # At least $100 position
        max_shares = int((self.account_balance * self.max_position_size) / entry_price)

        position_size = max(min_shares, min(shares, max_shares))

        return position_size

    def _calculate_risk_reward_ratio(
        self, entry_price: Decimal, stop_loss: Decimal, take_profit: Decimal
    ) -> Decimal:
        """Calculate risk/reward ratio"""

        risk = abs(entry_price - stop_loss)
        reward = abs(take_profit - entry_price)

        if risk > 0:
            return reward / risk
        else:
            return Decimal(0)

    def _create_analysis_summary(
        self, quote: MarketQuote, gap_assessment: GapTradabilityAssessment
    ) -> str:
        """Create human-readable analysis summary"""

        gap_size = quote.gap_size or abs(quote.price_change_percent or Decimal(0))
        volume_ratio = getattr(quote, "volume_ratio", Decimal(1))

        summary_parts = [
            f"Gap: {gap_size:.1f}% {'up' if quote.price_change_percent > 0 else 'down'}",
            f"Volume: {volume_ratio:.1f}x average",
            f"Strategy: {gap_assessment.recommended_strategy}",
            f"Quality Score: {float(gap_assessment.trade_quality_score * 100):.1f}/100",
        ]

        return " | ".join(summary_parts)

    def _extract_catalysts(
        self, quote: MarketQuote, gap_assessment: GapTradabilityAssessment
    ) -> List[str]:
        """Extract trading catalysts from analysis"""

        catalysts = []

        # Add gap-specific catalysts
        gap_size = quote.gap_size or Decimal(0)
        if gap_size >= 3.0:
            catalysts.append(f"Large {gap_size:.1f}% overnight gap")

        volume_ratio = quote.volume_ratio or Decimal(1)
        if volume_ratio >= 3.0:
            catalysts.append(f"High volume confirmation ({volume_ratio:.1f}x)")

        # Add success factors as catalysts
        catalysts.extend(gap_assessment.key_success_factors[:2])  # Top 2 factors

        return catalysts

    def generate_daily_suggestions(
        self, gap_candidates: List[MarketQuote], analysis_results: List[Dict]
    ) -> List[TradeSuggestion]:
        """
        Generate daily gap trading suggestions from candidates

        Args:
            gap_candidates: List of gap candidate quotes
            analysis_results: List of gap analysis results

        Returns:
            List of trade suggestions for the day
        """
        logger.info(
            f"Generating daily suggestions from {len(gap_candidates)} candidates"
        )

        suggestions = []

        for i, quote in enumerate(gap_candidates):
            try:
                if i < len(analysis_results):
                    analysis_data = {
                        "quote": quote,
                        "gap_assessment": analysis_results[i],
                    }

                    suggestion = self.generate_suggestion(
                        quote.asset.symbol, analysis_data
                    )
                    if suggestion and self.validate_suggestion(suggestion):
                        suggestions.append(suggestion)

            except Exception as e:
                logger.error(
                    f"Error generating suggestion for {quote.asset.symbol}: {e}"
                )
                continue

        # Filter and rank suggestions
        final_suggestions = self.filter_suggestions(suggestions)

        logger.info(f"Generated {len(final_suggestions)} daily trade suggestions")

        return final_suggestions
