"""GapCandidate SQLModel for database operations.

This model represents gap candidate analysis in the database using SQLModel ORM.
"""

from datetime import date, datetime
from typing import Optional
from sqlmodel import Field, SQLModel


class GapCandidateSQLModel(SQLModel, table=True):
    """SQLModel for gap_candidate table.

    Represents gap trading candidates with quality scoring and filtering.
    """

    __tablename__ = "gap_candidate"

    # Primary identification
    id: Optional[int] = Field(default=None, primary_key=True)
    asset_id: int = Field(index=True)
    analysis_timestamp: datetime = Field(index=True)
    session_type: str = Field(index=True)  # 'premarket' or 'afterhours'
    trading_date: date = Field(index=True)

    # Gap characteristics
    gap_percentage: float
    gap_direction: str  # 'up' or 'down'
    gap_type: Optional[str] = None  # 'full', 'partial', NULL

    # Price snapshot at analysis time
    reference_price: float  # prevday.c or day.c depending on session
    current_price: float    # min.c at analysis time
    day_open: Optional[float] = None  # NULL if premarket
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    day_close: Optional[float] = None
    prevday_close: float
    prevday_high: Optional[float] = None
    prevday_low: Optional[float] = None

    # Volume analysis
    extended_hours_volume: Optional[int] = None
    previous_day_volume: Optional[int] = None
    day_volume: Optional[int] = None  # Today's regular hours volume (for after-hours)
    volume_ratio: Optional[float] = None

    # Market context
    market_cap: Optional[float] = None
    sector: Optional[str] = None

    # Quality assessment
    quality_score: Optional[float] = None
    quality_tier: Optional[str] = None  # 'excellent', 'good', 'fair', 'poor'
    catalyst_score: Optional[float] = None
    volume_score: Optional[float] = None
    gap_size_score: Optional[float] = None
    sector_alignment_score: Optional[float] = None
    market_alignment_score: Optional[float] = None

    # Filter results
    passed_gap_filter: bool
    passed_volume_filter: bool
    passed_market_cap_filter: bool
    passed_exhaustion_filter: bool
    is_friday_gap: bool

    # Rejection details
    status: str = Field(index=True)  # 'passed', 'rejected', 'warning'
    rejection_reason: Optional[str] = None

    # News & sentiment
    news_count: Optional[int] = None
    sentiment_score: Optional[float] = None
    has_tier1_catalyst: Optional[bool] = None
    catalyst_description: Optional[str] = None

    # Metadata
    min_timestamp: Optional[int] = None  # Last minute bar timestamp
    data_freshness_hours: Optional[float] = None
    created_at: Optional[datetime] = None
    academic_gap_type: Optional[str] = None
