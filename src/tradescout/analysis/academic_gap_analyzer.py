"""
Academic Gap Type Analyzer Implementation

Implements gap classification based on academic research from:
- Plastun et al. (2019)
- Caporale & Plastun (2016)
- Van Rensburg & Van Zyl (2025)

Classifies gaps into four types with statistical continuation probabilities.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from ..data_models.domain_models_core import (
    ExtendedHoursData,
    MarketQuote,
    MarketStatus,
)
from ..data_models.domain_models_analysis import (
    ConfidenceLevel,
    GapClassification,
    GapRiskLevel,
    GapStrength,
    GapStrengthMetrics,
    GapTradabilityAssessment,
    GapType,
    TradeSide,
)
from .interfaces import CandidateGapTypeAnalyzer

logger = logging.getLogger(__name__)


class AcademicGapTypeAnalyzer(CandidateGapTypeAnalyzer):
    """
    Academic research-based gap type classifier

    Gap Types and Expected Continuation Rates:
    - Common: <1.5% size, 25% continuation rate
    - Breakaway: 2-5% size, 70% continuation rate
    - Continuation: 2-7% size, 80% continuation rate
    - Exhaustion: >5% size, 20% continuation rate
    """

    def __init__(self):
        """Initialize with academic research thresholds"""
        # Gap type size thresholds from research
        self.common_gap_max = Decimal("1.5")  # <1.5% = Common
        self.breakaway_gap_min = Decimal("2.0")  # 2-5% = Breakaway
        self.breakaway_gap_max = Decimal("5.0")
        self.continuation_gap_min = Decimal("2.0")  # 2-7% = Continuation
        self.continuation_gap_max = Decimal("7.0")
        self.exhaustion_gap_min = Decimal("5.0")  # >5% = Exhaustion

        # Statistical continuation rates from academic research
        self.continuation_rates = {
            GapType.COMMON: 0.25,  # 25% continuation rate
            GapType.BREAKAWAY: 0.70,  # 70% continuation rate
            GapType.CONTINUATION: 0.80,  # 80% continuation rate
            GapType.EXHAUSTION: 0.20,  # 20% continuation rate
            GapType.UNKNOWN: 0.50,  # 50% default for unknown
        }

        # Volume confirmation thresholds
        self.min_volume_ratio = Decimal("2.0")  # 2x for confirmation
        self.high_volume_ratio = Decimal("3.0")  # 3x for strong confirmation

    def classify_gap_type(
        self,
        quote: MarketQuote,
        extended_data: ExtendedHoursData,
        historical_context: Optional[Dict[str, any]] = None,
    ) -> GapClassification:
        """
        Classify gap into academic research-based type

        Args:
            quote: Market quote with gap information
            extended_data: Pre-market/after-hours context
            historical_context: Optional trend and pattern context

        Returns:
            GapClassification with type, confidence, and probabilities
        """
        logger.debug(f"Classifying gap type for {quote.asset.symbol}")

        # Extract gap size
        gap_size = getattr(quote, "gap_size", None)
        if gap_size is None:
            gap_size = abs(quote.price_change_percent or Decimal(0))

        # Determine primary gap type based on size
        primary_type = self._classify_by_size(gap_size)

        # Refine classification using volume and context
        final_type, confidence = self._refine_classification(
            primary_type, quote, extended_data, historical_context
        )

        # Calculate confidence metrics
        confidence_level = self._determine_confidence_level(confidence)
        continuation_probability = self.continuation_rates[final_type]

        # Calculate gap characteristics
        gap_amount = (
            quote.price_data.price - quote.previous_close
            if quote.previous_close
            else Decimal("0")
        )

        # Generate classification result
        classification = GapClassification(
            asset=quote.asset,
            timestamp=datetime.now(),
            gap_type=final_type,
            confidence_score=Decimal(str(confidence / 100)),  # Convert to 0-1 scale
            gap_percent=gap_size,
            gap_amount=gap_amount,
            size_category=self._categorize_gap_size(gap_size),
            expected_fill_probability=Decimal(str(1 - continuation_probability)),
            expected_continuation_probability=Decimal(str(continuation_probability)),
            classification_reason=f"Classified as {final_type.value} gap based on academic research thresholds",
            supporting_factors=self._generate_classification_reasons(
                final_type, gap_size, quote
            ),
            warning_flags=self._identify_warning_flags(quote, gap_size),
        )

        logger.info(
            f"Classified {quote.asset.symbol} as {final_type.value} gap "
            f"({confidence:.1f}% confidence, {continuation_probability:.0%} continuation rate)"
        )

        return classification

    def analyze_gap_strength(
        self,
        gap_classification: GapClassification,
        volume_data: Dict[str, Decimal],
        market_context: Dict[str, any],
    ) -> GapStrengthMetrics:
        """
        Analyze gap strength and quality indicators

        Args:
            gap_classification: Classified gap from classify_gap_type()
            volume_data: Volume ratios and surge indicators
            market_context: Market conditions and catalyst information

        Returns:
            GapStrengthMetrics with comprehensive strength assessment
        """
        logger.debug(
            f"Analyzing gap strength for {gap_classification.gap_type.value} gap"
        )

        # Assess volume strength
        volume_strength = self._assess_volume_strength(volume_data)

        # Assess technical context
        technical_strength = self._assess_technical_strength(market_context)

        # Assess catalyst quality
        catalyst_strength = self._assess_catalyst_strength(market_context)

        # Calculate overall strength
        overall_strength = self._calculate_overall_strength(
            gap_classification, volume_strength, technical_strength, catalyst_strength
        )

        # Determine risk level
        risk_level = self._determine_risk_level(gap_classification, overall_strength)

        volume_ratio = volume_data.get("volume_ratio", Decimal("1.0"))

        strength_metrics = GapStrengthMetrics(
            asset=gap_classification.asset,
            timestamp=datetime.now(),
            volume_ratio=volume_ratio,
            volume_confirmation=(volume_ratio >= Decimal("2.0")),
            premarket_volume_surge=(volume_ratio >= Decimal("3.0")),
            technical_breakout=market_context.get("technical_breakout", False),
            trend_alignment=market_context.get("trend_alignment", False),
            support_resistance_break=market_context.get(
                "support_resistance_break", False
            ),
            news_catalyst_present=market_context.get("news_catalyst", False),
            catalyst_quality_score=Decimal(
                str(
                    self._calculate_strength_score(
                        volume_strength, technical_strength, catalyst_strength
                    ) / 100.0
                )
            ),
            market_alignment=market_context.get("market_alignment", False),
            sector_momentum=market_context.get("sector_momentum", False),
            overall_strength=overall_strength,
            strength_score=Decimal(
                str(
                    self._calculate_strength_score(
                        volume_strength, technical_strength, catalyst_strength
                    ) / 100.0
                )
            ),
        )

        logger.info(
            f"Gap strength analysis: {overall_strength.value} "
            f"(score: {strength_metrics.strength_score:.1f})"
        )

        return strength_metrics

    def assess_tradability(
        self,
        gap_classification: GapClassification,
        strength_metrics: GapStrengthMetrics,
        risk_parameters: Optional[Dict[str, any]] = None,
    ) -> GapTradabilityAssessment:
        """
        Final assessment of gap trading opportunity

        Args:
            gap_classification: Gap type classification
            strength_metrics: Gap strength analysis
            risk_parameters: Optional risk management overrides

        Returns:
            GapTradabilityAssessment with trading recommendations
        """
        logger.debug(
            f"Assessing tradability for {gap_classification.gap_type.value} gap"
        )

        # Determine if gap is tradeable based on type and strength
        is_tradeable = self._determine_tradability(gap_classification, strength_metrics)

        # Generate trading strategy recommendation
        strategy = self._recommend_strategy(gap_classification, strength_metrics)

        # Calculate position sizing recommendation
        position_sizing = self._recommend_position_sizing(
            gap_classification, strength_metrics, risk_parameters
        )

        # Determine entry timing
        entry_timing = self._recommend_entry_timing(
            gap_classification, strength_metrics
        )

        # Generate key success factors
        success_factors = self._identify_success_factors(
            gap_classification, strength_metrics
        )

        # Generate risk warnings
        risk_warnings = self._generate_risk_warnings(
            gap_classification, strength_metrics
        )

        # Determine recommended trade side
        recommended_side = (
            TradeSide.LONG if gap_classification.gap_percent > 0 else TradeSide.SHORT
        )

        # Map strength to risk level
        risk_level = (
            GapRiskLevel.LOW
            if strength_metrics.overall_strength == GapStrength.VERY_STRONG
            else (
                GapRiskLevel.MEDIUM
                if strength_metrics.overall_strength == GapStrength.STRONG
                else GapRiskLevel.HIGH
            )
        )

        assessment = GapTradabilityAssessment(
            asset=gap_classification.asset,
            timestamp=datetime.now(),
            gap_classification=gap_classification,
            strength_metrics=strength_metrics,
            is_tradeable=is_tradeable,
            recommended_strategy=strategy,
            recommended_side=recommended_side,
            risk_level=risk_level,
            optimal_entry_timing=entry_timing,
            suggested_hold_time="intraday",
            max_hold_hours=4,
            suggested_position_size_percent=Decimal(str(position_sizing)),
            stop_loss_percent=Decimal("2.0"),  # 2% stop loss from research
            take_profit_percent=Decimal("3.0"),  # 1.5:1 risk/reward minimum
            trading_rationale=f"{strategy} strategy based on {gap_classification.gap_type.value} gap pattern",
            key_success_factors=success_factors,
            primary_risks=risk_warnings,
        )

        logger.info(
            f"Tradability assessment: {'TRADEABLE' if is_tradeable else 'NOT TRADEABLE'} "
            f"({strategy}, quality: {assessment.trade_quality_score:.1f})"
        )

        return assessment

    def batch_analyze_candidates(
        self, candidates: List[MarketQuote]
    ) -> List[GapTradabilityAssessment]:
        """
        Analyze multiple gap candidates efficiently

        Args:
            candidates: List of market quotes with potential gaps

        Returns:
            List of assessments sorted by trade quality score
        """
        logger.info(f"Batch analyzing {len(candidates)} gap candidates")

        assessments = []

        for quote in candidates:
            try:
                # Create minimal extended hours data if not provided
                extended_data = ExtendedHoursData(
                    asset=quote.asset,
                    session_type=MarketStatus.PRE_MARKET,  # Use proper enum
                    price_data=quote.price_data,
                    regular_session_close=quote.previous_close
                    or Decimal("100.0"),  # Fallback if missing
                )

                # Classify gap type
                classification = self.classify_gap_type(quote, extended_data)

                # Analyze strength (with minimal data)
                volume_data = {
                    "volume_ratio": getattr(quote, "volume_ratio", Decimal("1.0")),
                    "volume_surge": Decimal("1.0"),
                }
                market_context = {"catalyst_present": False}

                strength_metrics = self.analyze_gap_strength(
                    classification, volume_data, market_context
                )

                # Assess tradability
                assessment = self.assess_tradability(classification, strength_metrics)
                assessments.append(assessment)

            except Exception as e:
                logger.error(f"Error analyzing candidate {quote.asset.symbol}: {e}")
                continue

        # Sort by quality score (highest first)
        assessments.sort(key=lambda x: x.trade_quality_score, reverse=True)

        tradeable_count = sum(1 for a in assessments if a.is_tradeable)
        logger.info(
            f"Batch analysis complete: {tradeable_count}/{len(assessments)} tradeable"
        )

        return assessments

    def get_gap_statistics(self, lookback_days: int = 30) -> Dict[str, any]:
        """
        Get historical gap classification and performance statistics

        Args:
            lookback_days: Days of history to analyze

        Returns:
            Dictionary with comprehensive gap trading statistics
        """
        # This would require historical tracking implementation
        # For now, return academic research statistics as baseline

        return {
            "academic_research_baseline": {
                "common_gaps": {
                    "frequency": "60%",
                    "continuation_rate": "25%",
                    "size_range": "<1.5%",
                    "recommendation": "Generally avoid",
                },
                "breakaway_gaps": {
                    "frequency": "20%",
                    "continuation_rate": "70%",
                    "size_range": "2-5%",
                    "recommendation": "High priority targets",
                },
                "continuation_gaps": {
                    "frequency": "15%",
                    "continuation_rate": "80%",
                    "size_range": "2-7%",
                    "recommendation": "Highest priority targets",
                },
                "exhaustion_gaps": {
                    "frequency": "5%",
                    "continuation_rate": "20%",
                    "size_range": ">5%",
                    "recommendation": "Avoid or trade reversal",
                },
            },
            "lookback_period": f"{lookback_days} days",
            "note": "Historical tracking not yet implemented - showing academic baselines",
        }

    def _classify_by_size(self, gap_size: Decimal) -> GapType:
        """Classify gap type based purely on size"""
        if gap_size < self.common_gap_max:
            return GapType.COMMON
        elif self.breakaway_gap_min <= gap_size <= self.breakaway_gap_max:
            return GapType.BREAKAWAY
        elif self.continuation_gap_min <= gap_size <= self.continuation_gap_max:
            # This could be either breakaway or continuation - need context
            return GapType.CONTINUATION
        elif gap_size >= self.exhaustion_gap_min:
            return GapType.EXHAUSTION
        else:
            return GapType.UNKNOWN

    def _refine_classification(
        self,
        primary_type: GapType,
        quote: MarketQuote,
        extended_data: ExtendedHoursData,
        historical_context: Optional[Dict[str, any]],
    ) -> tuple[GapType, float]:
        """Refine classification using volume and context"""

        confidence = 75.0  # Base confidence
        final_type = primary_type

        # Increase confidence with volume confirmation
        volume_ratio = getattr(quote, "volume_ratio", Decimal(1))
        if volume_ratio >= self.min_volume_ratio:
            confidence += 10.0
        if volume_ratio >= self.high_volume_ratio:
            confidence += 10.0

        # Adjust for gap size clarity
        gap_size = getattr(
            quote, "gap_size", abs(quote.price_change_percent or Decimal(0))
        )

        # Clear size classifications get higher confidence
        if gap_size < 1.5:  # Clearly common
            confidence += 5.0
        elif 2.0 <= gap_size <= 3.0:  # Clear breakaway range
            final_type = GapType.BREAKAWAY
            confidence += 10.0
        elif gap_size >= 6.0:  # Clearly exhaustion
            final_type = GapType.EXHAUSTION
            confidence += 10.0

        return final_type, min(95.0, confidence)

    def _determine_confidence_level(self, confidence_score: float) -> ConfidenceLevel:
        """Convert confidence score to confidence level"""
        if confidence_score >= 85:
            return ConfidenceLevel.VERY_HIGH
        elif confidence_score >= 70:
            return ConfidenceLevel.HIGH
        elif confidence_score >= 50:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW

    def _assess_volume_confirmation(self, quote: MarketQuote) -> bool:
        """Check if volume confirms the gap"""
        volume_ratio = getattr(quote, "volume_ratio", Decimal(1))
        return volume_ratio >= self.min_volume_ratio

    def _generate_classification_reasons(
        self, gap_type: GapType, gap_size: Decimal, quote: MarketQuote
    ) -> List[str]:
        """Generate human-readable classification reasons"""
        reasons = []

        reasons.append(f"Gap size {gap_size:.2f}% fits {gap_type.value} pattern")

        volume_ratio = getattr(quote, "volume_ratio", None)
        if volume_ratio:
            if volume_ratio >= self.high_volume_ratio:
                reasons.append(f"High volume confirmation ({volume_ratio:.1f}x)")
            elif volume_ratio >= self.min_volume_ratio:
                reasons.append(f"Volume confirmation present ({volume_ratio:.1f}x)")
            else:
                reasons.append(f"Limited volume confirmation ({volume_ratio:.1f}x)")

        return reasons

    def _get_research_basis(self, gap_type: GapType) -> str:
        """Get academic research basis for gap type"""
        research_basis = {
            GapType.COMMON: "Plastun et al. (2019): Noise trading, 25% continuation",
            GapType.BREAKAWAY: "Academic research: Trend initiation, 70% continuation",
            GapType.CONTINUATION: "Academic research: Trend acceleration, 80% continuation",
            GapType.EXHAUSTION: "Academic research: Trend termination, 20% continuation",
            GapType.UNKNOWN: "Insufficient data for classification",
        }
        return research_basis.get(gap_type, "No specific research basis")

    def _assess_volume_strength(self, volume_data: Dict[str, Decimal]) -> GapStrength:
        """Assess volume strength component"""
        volume_ratio = volume_data.get("volume_ratio", Decimal(1))

        if volume_ratio >= Decimal("4.0"):
            return GapStrength.VERY_STRONG
        elif volume_ratio >= Decimal("3.0"):
            return GapStrength.STRONG
        elif volume_ratio >= Decimal("2.0"):
            return GapStrength.MODERATE
        else:
            return GapStrength.WEAK

    def _assess_technical_strength(self, market_context: Dict[str, any]) -> GapStrength:
        """Assess technical strength (placeholder)"""
        # This would analyze trend, support/resistance, etc.
        return GapStrength.MODERATE  # Default for now

    def _assess_catalyst_strength(self, market_context: Dict[str, any]) -> GapStrength:
        """Assess catalyst strength"""
        has_catalyst = market_context.get("catalyst_present", False)
        if has_catalyst:
            return GapStrength.STRONG
        else:
            return GapStrength.WEAK

    def _calculate_overall_strength(
        self,
        gap_classification: GapClassification,
        volume_strength: GapStrength,
        technical_strength: GapStrength,
        catalyst_strength: GapStrength,
    ) -> GapStrength:
        """Calculate overall gap strength"""

        # Weight different factors
        strength_scores = {
            GapStrength.WEAK: 1,
            GapStrength.MODERATE: 2,
            GapStrength.STRONG: 3,
            GapStrength.VERY_STRONG: 4,
        }

        volume_score = strength_scores[volume_strength] * 0.4  # 40% weight
        technical_score = strength_scores[technical_strength] * 0.3  # 30% weight
        catalyst_score = strength_scores[catalyst_strength] * 0.3  # 30% weight

        total_score = volume_score + technical_score + catalyst_score

        # Convert back to strength enum
        if total_score >= 3.5:
            return GapStrength.VERY_STRONG
        elif total_score >= 2.5:
            return GapStrength.STRONG
        elif total_score >= 1.5:
            return GapStrength.MODERATE
        else:
            return GapStrength.WEAK

    def _determine_risk_level(
        self, gap_classification: GapClassification, overall_strength: GapStrength
    ) -> GapRiskLevel:
        """Determine risk level for the gap"""

        # High-strength, continuation-type gaps are lower risk
        if gap_classification.gap_type in [
            GapType.BREAKAWAY,
            GapType.CONTINUATION,
        ] and overall_strength in [GapStrength.STRONG, GapStrength.VERY_STRONG]:
            return GapRiskLevel.LOW

        # Exhaustion gaps are higher risk
        if gap_classification.gap_type == GapType.EXHAUSTION:
            return GapRiskLevel.HIGH

        # Common gaps are medium risk (generally avoid)
        if gap_classification.gap_type == GapType.COMMON:
            return GapRiskLevel.MEDIUM

        return GapRiskLevel.MEDIUM

    def _calculate_strength_score(
        self,
        volume_strength: GapStrength,
        technical_strength: GapStrength,
        catalyst_strength: GapStrength,
    ) -> float:
        """Calculate numerical strength score (0-100)"""
        strength_values = {
            GapStrength.WEAK: 20,
            GapStrength.MODERATE: 50,
            GapStrength.STRONG: 75,
            GapStrength.VERY_STRONG: 95,
        }

        volume_score = strength_values[volume_strength] * 0.4
        technical_score = strength_values[technical_strength] * 0.3
        catalyst_score = strength_values[catalyst_strength] * 0.3

        return volume_score + technical_score + catalyst_score

    def _identify_key_strength_factors(
        self,
        gap_classification: GapClassification,
        volume_data: Dict[str, Decimal],
        market_context: Dict[str, any],
    ) -> List[str]:
        """Identify key factors supporting the gap"""
        factors = []

        # Volume factors
        volume_ratio = volume_data.get("volume_ratio", Decimal(1))
        if volume_ratio >= Decimal("3.0"):
            factors.append(f"Exceptional volume confirmation ({volume_ratio:.1f}x)")
        elif volume_ratio >= Decimal("2.0"):
            factors.append(f"Strong volume confirmation ({volume_ratio:.1f}x)")

        # Gap type factors
        if gap_classification.gap_type == GapType.CONTINUATION:
            factors.append("Continuation gap: 80% historical success rate")
        elif gap_classification.gap_type == GapType.BREAKAWAY:
            factors.append("Breakaway gap: 70% historical success rate")

        # Catalyst factors
        if market_context.get("catalyst_present"):
            factors.append("News catalyst supporting price movement")

        return factors

    def _identify_risk_factors(
        self,
        gap_classification: GapClassification,
        volume_data: Dict[str, Decimal],
        market_context: Dict[str, any],
    ) -> List[str]:
        """Identify key risk factors"""
        risks = []

        # Gap type risks
        if gap_classification.gap_type == GapType.EXHAUSTION:
            risks.append("Exhaustion gap: Only 20% continuation rate")
        elif gap_classification.gap_type == GapType.COMMON:
            risks.append("Common gap: Only 25% continuation rate")

        # Volume risks
        volume_ratio = volume_data.get("volume_ratio", Decimal(1))
        if volume_ratio < Decimal("2.0"):
            risks.append(f"Insufficient volume confirmation ({volume_ratio:.1f}x)")

        # General market risks
        risks.append("Intraday holding required - no overnight positions")
        risks.append("Gap fill risk - potential return to previous close")

        return risks

    def _determine_tradability(
        self,
        gap_classification: GapClassification,
        strength_metrics: GapStrengthMetrics,
    ) -> bool:
        """Determine if gap is worth trading"""

        # Never trade common gaps (low success rate)
        if gap_classification.gap_type == GapType.COMMON:
            return False

        # Avoid exhaustion gaps unless very high confidence reversal setup
        if gap_classification.gap_type == GapType.EXHAUSTION:
            return False  # Conservative approach

        # Trade breakaway and continuation gaps with sufficient strength
        if gap_classification.gap_type in [GapType.BREAKAWAY, GapType.CONTINUATION]:
            return strength_metrics.overall_strength != GapStrength.WEAK

        return False

    def _recommend_strategy(
        self,
        gap_classification: GapClassification,
        strength_metrics: GapStrengthMetrics,
    ) -> str:
        """Recommend trading strategy"""

        if gap_classification.gap_type == GapType.BREAKAWAY:
            return "momentum_continuation"
        elif gap_classification.gap_type == GapType.CONTINUATION:
            return "trend_acceleration"
        elif gap_classification.gap_type == GapType.EXHAUSTION:
            return "reversal_anticipation"
        else:
            return "avoid"

    def _recommend_position_sizing(
        self,
        gap_classification: GapClassification,
        strength_metrics: GapStrengthMetrics,
        risk_parameters: Optional[Dict[str, any]],
    ) -> float:
        """Recommend position sizing percentage"""

        base_size = 1.0  # 1% base position

        # Adjust for gap strength
        if strength_metrics.overall_strength == GapStrength.VERY_STRONG:
            base_size *= 1.5
        elif strength_metrics.overall_strength == GapStrength.STRONG:
            base_size *= 1.2
        elif strength_metrics.overall_strength == GapStrength.WEAK:
            base_size *= 0.5

        # Adjust for gap type success rates
        if gap_classification.gap_type == GapType.CONTINUATION:
            base_size *= 1.2  # 80% success rate
        elif gap_classification.gap_type == GapType.BREAKAWAY:
            base_size *= 1.1  # 70% success rate

        return min(2.0, base_size)  # Max 2% position size

    def _recommend_entry_timing(
        self,
        gap_classification: GapClassification,
        strength_metrics: GapStrengthMetrics,
    ) -> str:
        """Recommend entry timing"""

        if strength_metrics.overall_strength == GapStrength.VERY_STRONG:
            return "market_open_immediate"
        else:
            return "wait_5_minutes_for_confirmation"

    def _identify_success_factors(
        self,
        gap_classification: GapClassification,
        strength_metrics: GapStrengthMetrics,
    ) -> List[str]:
        """Identify key factors for trade success"""

        factors = [
            "Volume maintains above 2x average",
            "Price holds above gap-up level or below gap-down level",
            "No adverse news developments during trading day",
        ]

        if gap_classification.gap_type == GapType.CONTINUATION:
            factors.append("Trend momentum continues throughout day")
        elif gap_classification.gap_type == GapType.BREAKAWAY:
            factors.append("Price breaks through resistance/support levels")

        return factors

    def _generate_risk_warnings(
        self,
        gap_classification: GapClassification,
        strength_metrics: GapStrengthMetrics,
    ) -> List[str]:
        """Generate risk warnings for the trade"""

        warnings = [
            "Mandatory exit by market close - no overnight holds",
            "Set stop loss immediately upon entry",
            "Monitor volume - exit if volume drops below 1.5x average",
        ]

        if strength_metrics.overall_strength == GapStrength.WEAK:
            warnings.append("HIGH RISK: Consider reduced position size")

        if gap_classification.gap_percent >= Decimal("5.0"):
            warnings.append("Large gap: Higher volatility and reversal risk")

        return warnings

    def _calculate_overall_quality_score(
        self,
        gap_classification: GapClassification,
        strength_metrics: GapStrengthMetrics,
    ) -> float:
        """Calculate overall trade quality score (0-100)"""

        base_score = float(gap_classification.expected_continuation_probability * Decimal("100"))

        # Adjust for strength
        strength_multiplier = {
            GapStrength.WEAK: 0.7,
            GapStrength.MODERATE: 1.0,
            GapStrength.STRONG: 1.3,
            GapStrength.VERY_STRONG: 1.5,
        }

        multiplier = strength_multiplier[strength_metrics.overall_strength]
        final_score = base_score * multiplier

        return min(100.0, final_score)

    def _categorize_gap_size(self, gap_size: Decimal) -> str:
        """Categorize gap size for classification"""
        if gap_size < Decimal("2"):
            return "small"
        elif gap_size < Decimal("4"):
            return "medium"
        elif gap_size < Decimal("7"):
            return "large"
        else:
            return "extreme"

    def _identify_warning_flags(
        self, quote: MarketQuote, gap_size: Decimal
    ) -> List[str]:
        """Identify potential warning flags for gap classification"""
        flags = []

        if gap_size > Decimal("7"):
            flags.append("Extreme gap size - potential manipulation risk")

        volume_ratio = getattr(quote, "volume_ratio", Decimal("1.0"))
        if volume_ratio < Decimal("1.5"):
            flags.append("Low volume confirmation")

        if (
            hasattr(quote.asset, "market_cap")
            and quote.asset.market_cap
            and quote.asset.market_cap < 1_000_000_000
        ):
            flags.append("Small market cap - higher volatility risk")

        return flags
