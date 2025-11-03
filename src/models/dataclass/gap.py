"""Gap trading model objects.

Model objects for gap analysis workflow:
- Gap candidates and their properties
- Gap classification enums
- Quality scoring results
"""

from dataclasses import dataclass
from typing import Optional
from enum import Enum


class GapDirection(Enum):
    """Gap direction enumeration."""
    UP = "up"
    DOWN = "down"


class GapSignificance(Enum):
    """Gap significance levels based on percentage thresholds."""
    MINOR = "minor"          # 1-2%
    MODERATE = "moderate"    # 2-5%
    SIGNIFICANT = "significant"  # 5-10%
    MAJOR = "major"         # >10%


class RiskLevel(Enum):
    """Risk level classification for gap candidates."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class GapCandidate:
    """A potential gap trading candidate.

    Represents a stock with a significant price gap from active universe,
    meeting basic quality filters (market cap, gap size).

    Workflow stages:
    1. Initial creation: symbol, prices, gap metrics, fundamentals
    2. Volume validation: volume_ratio, extended_hours_volume
    3. News analysis: catalyst_score, sentiment_score, news_count
    4. Quality scoring: quality_score, risk_level
    5. Database storage: status, rejection_reason, filter flags
    """

    # Basic identification
    symbol: str
    name: str

    # Price data
    current_price: float
    reference_price: float  # prevDay.c for premarket, day.c for after-hours
    gap_amount: float
    gap_percent: float

    # Gap classification
    direction: GapDirection
    significance: GapSignificance
    session: str  # "premarket" or "afterhours"

    # Fundamentals
    market_cap: float
    prevday_volume: int
    day_volume: Optional[int] = None  # Today's regular hours volume (for after-hours gaps)

    # Stage 2: Volume validation (populated by calculate_volume_ratio)
    volume_ratio: Optional[float] = None
    extended_hours_volume: Optional[int] = None

    # Stage 3: News/Catalyst analysis (populated by news analyzer)
    catalyst_score: Optional[int] = None
    sentiment_score: Optional[float] = None
    news_count: Optional[int] = None

    # Stage 4: Quality scoring (populated by calculate_quality_score)
    quality_score: Optional[int] = None
    risk_level: Optional[RiskLevel] = None

    # Database storage fields (populated during analysis workflow)
    asset_id: Optional[int] = None
    session_type: Optional[str] = None  # Maps to session
    trading_date: Optional[str] = None
    gap_percentage: Optional[float] = None  # Maps to gap_percent
    gap_type: Optional[str] = None  # 'full', 'partial', or None (for gap fill tracking)
    academic_gap_type: Optional[str] = None  # 'common', 'breakaway_continuation', 'exhaustion_candidate'
    day_open: Optional[float] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    day_close: Optional[float] = None
    prevday_close: Optional[float] = None
    prevday_high: Optional[float] = None
    prevday_low: Optional[float] = None
    previous_day_volume: Optional[int] = None  # Maps to prevday_volume
    sector: Optional[str] = None
    quality_tier: Optional[str] = None  # 'excellent', 'good', 'fair', 'poor'
    volume_score: Optional[float] = None
    gap_size_score: Optional[float] = None
    sector_alignment_score: Optional[float] = None
    market_alignment_score: Optional[float] = None
    passed_gap_filter: Optional[bool] = None
    passed_volume_filter: Optional[bool] = None
    passed_market_cap_filter: Optional[bool] = None
    passed_exhaustion_filter: Optional[bool] = None
    is_friday_gap: Optional[bool] = None
    status: Optional[str] = None  # 'passed', 'rejected', 'warning'
    rejection_reason: Optional[str] = None
    has_tier1_catalyst: Optional[bool] = None
    catalyst_description: Optional[str] = None
    min_timestamp: Optional[int] = None
    data_freshness_hours: Optional[float] = None

    @property
    def gap_size_dollars(self) -> float:
        """Gap size in dollars."""
        return abs(self.gap_amount)

    @property
    def gap_size_percent(self) -> float:
        """Gap size as percentage."""
        return abs(self.gap_percent)

    @property
    def is_validated(self) -> bool:
        """Check if candidate has completed volume validation."""
        return self.volume_ratio is not None

    @property
    def has_catalyst(self) -> bool:
        """Check if candidate has catalyst/news analysis."""
        return self.catalyst_score is not None and self.catalyst_score > 0

    @property
    def is_scored(self) -> bool:
        """Check if candidate has quality score."""
        return self.quality_score is not None
