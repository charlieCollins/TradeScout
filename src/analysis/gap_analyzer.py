"""Gap analysis for TradeScout trading system."""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import datetime, date
from enum import Enum

from models.asset import Asset
from models.price import AssetPrice


class GapDirection(Enum):
    """Gap direction enumeration."""
    UP = "up"
    DOWN = "down"


class GapSignificance(Enum):
    """Gap significance levels."""
    MINOR = "minor"          # 1-2%
    MODERATE = "moderate"    # 2-5%
    SIGNIFICANT = "significant"  # 5-10%
    MAJOR = "major"         # >10%


@dataclass(frozen=True)
class GapCandidate:
    """A potential gap trading candidate."""

    symbol: str
    asset: Asset
    current_price: Decimal
    previous_close: Decimal
    gap_amount: Decimal
    gap_percent: Decimal
    direction: GapDirection
    significance: GapSignificance
    volume: Optional[int] = None
    market_cap: Optional[int] = None

    @property
    def gap_size_dollars(self) -> Decimal:
        """Gap size in dollars."""
        return abs(self.gap_amount)

    @property
    def gap_size_percent(self) -> Decimal:
        """Gap size as percentage."""
        return abs(self.gap_percent)


@dataclass(frozen=True)
class GapAssessment:
    """Assessment of gap trading opportunity."""

    candidate: GapCandidate
    score: int  # 0-100
    risk_level: str  # "low", "medium", "high"
    target_price: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    reasoning: List[str] = None
    catalyst_info: Optional[Dict[str, Any]] = None  # Optional catalyst information from catalyst_analyzer

    def __post_init__(self):
        if self.reasoning is None:
            object.__setattr__(self, 'reasoning', [])


class GapAnalyzer:
    """Analyzes gaps for trading opportunities."""

    def __init__(self, min_gap_percent: float = 2.0):
        """Initialize gap analyzer.

        Args:
            min_gap_percent: Minimum gap percentage to consider significant
        """
        self.min_gap_percent = min_gap_percent

    def analyze_gaps(self, assets_with_prices: List[tuple[Asset, AssetPrice]]) -> List[GapCandidate]:
        """Analyze assets for gap opportunities.

        Args:
            assets_with_prices: List of (Asset, AssetPrice) tuples

        Returns:
            List of gap candidates sorted by significance
        """
        candidates = []

        for asset, price in assets_with_prices:
            candidate = self._analyze_single_gap(asset, price)
            if candidate and candidate.gap_size_percent >= self.min_gap_percent:
                candidates.append(candidate)

        # Sort by gap significance (largest gaps first)
        return sorted(candidates, key=lambda c: c.gap_size_percent, reverse=True)

    def _analyze_single_gap(self, asset: Asset, price: AssetPrice) -> Optional[GapCandidate]:
        """Analyze a single asset for gap opportunity."""
        if not price.prevday_close or not price.day_open:
            return None

        gap_amount = price.day_open - price.prevday_close
        gap_percent = (gap_amount / price.prevday_close) * 100

        if abs(gap_percent) < self.min_gap_percent:
            return None

        direction = GapDirection.UP if gap_amount > 0 else GapDirection.DOWN
        significance = self._determine_significance(abs(gap_percent))

        return GapCandidate(
            symbol=asset.symbol,
            asset=asset,
            current_price=price.day_open,
            previous_close=price.prevday_close,
            gap_amount=gap_amount,
            gap_percent=gap_percent,
            direction=direction,
            significance=significance,
            volume=price.day_volume
        )

    def _determine_significance(self, gap_percent: float) -> GapSignificance:
        """Determine gap significance level."""
        if gap_percent > 10:
            return GapSignificance.MAJOR
        elif gap_percent > 5:
            return GapSignificance.SIGNIFICANT
        elif gap_percent > 2:
            return GapSignificance.MODERATE
        else:
            return GapSignificance.MINOR

    def assess_opportunity(self, candidate: GapCandidate) -> GapAssessment:
        """Assess a gap candidate for trading opportunity.

        Args:
            candidate: Gap candidate to assess

        Returns:
            Gap assessment with score and recommendations
        """
        score = 50  # Base score
        risk_level = "medium"
        reasoning = []

        # Adjust score based on gap size
        if candidate.significance == GapSignificance.MAJOR:
            score += 20
            risk_level = "high"
            reasoning.append("Major gap size increases opportunity but also risk")
        elif candidate.significance == GapSignificance.SIGNIFICANT:
            score += 15
            reasoning.append("Significant gap size provides good opportunity")
        elif candidate.significance == GapSignificance.MODERATE:
            score += 10
            reasoning.append("Moderate gap size with reasonable risk")

        # Adjust score based on direction (gap ups generally more favorable)
        if candidate.direction == GapDirection.UP:
            score += 5
            reasoning.append("Gap up typically has better success rate")

        # Adjust based on volume if available
        if candidate.volume and candidate.volume > 1000000:  # High volume
            score += 10
            reasoning.append("High volume confirms gap significance")
        elif candidate.volume and candidate.volume < 100000:  # Low volume
            score -= 10
            risk_level = "high"
            reasoning.append("Low volume increases risk")

        # Calculate targets (simple approach)
        target_price = None
        stop_loss = None

        if candidate.direction == GapDirection.UP:
            # For gap ups, target is fill (previous close) with some buffer
            target_price = candidate.previous_close * Decimal('0.95')  # 95% of gap fill
            stop_loss = candidate.current_price * Decimal('0.97')     # 3% stop loss
        else:
            # For gap downs, target is partial fill
            target_price = candidate.previous_close * Decimal('1.05')  # 105% of gap fill
            stop_loss = candidate.current_price * Decimal('1.03')     # 3% stop loss

        # Ensure score is within bounds
        score = max(0, min(100, score))

        return GapAssessment(
            candidate=candidate,
            score=score,
            risk_level=risk_level,
            target_price=target_price,
            stop_loss=stop_loss,
            reasoning=reasoning
        )