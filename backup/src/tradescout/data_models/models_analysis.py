"""
Analysis Domain Models for TradeScout

Models representing trading analysis, strategies, and suggestions.
These models are used by the GapAnalysisInterface operations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from .models_asset import Asset, PriceData
from .models_market import MarketStatus


# ==================== ENUMS ====================


class RiskLevel(Enum):
    """Risk levels for trades"""

    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class ConfidenceLevel(Enum):
    """Confidence levels for trade suggestions"""

    LOW = "low"  # 50-70%
    MEDIUM = "medium"  # 70-85%
    HIGH = "high"  # 85-95%
    VERY_HIGH = "very_high"  # 95%+


class GapType(Enum):
    """Gap classification based on characteristics"""

    COMMON = "common"  # <2% size, likely to fill
    BREAKAWAY = "breakaway"  # 2-5% size, trend initiation
    CONTINUATION = "continuation"  # 2-7% size, trend acceleration
    EXHAUSTION = "exhaustion"  # >5% size, trend termination


# ==================== DATACLASSES ====================


@dataclass
class GapRules:
    """Configuration for gap candidate identification"""

    # Gap size criteria
    min_gap_percent: float
    max_gap_percent: float

    # Volume criteria
    min_volume: int
    min_volume_ratio: float

    # Price criteria
    min_price: float
    max_spread_percent: float

    # Session filtering
    session_types: List[str]

    # Quality filters
    exclude_penny_stocks: bool
    exclude_low_volume: bool

    # Academic research thresholds
    exhaustion_threshold: float
    breakaway_min: float

    # Optional fields with defaults
    max_price: Optional[float] = None
    min_market_cap: Optional[int] = None


@dataclass
class GapCandidate:
    """Gap candidate identified from price screening"""

    asset: Asset
    analysis_time: datetime
    session_type: MarketStatus  # PRE_MARKET or AFTER_HOURS

    # Gap metrics
    previous_close: Decimal
    current_price: Decimal
    gap_size: Decimal  # Absolute dollar amount
    gap_percent: Decimal  # Percentage

    # Gap characteristics
    gap_type: GapType
    gap_direction: str  # "up" or "down"

    # Volume analysis
    volume: int


@dataclass
class GapAssessment:
    """Risk assessment for a gap trading opportunity"""

    gap_candidate: GapCandidate

    # Risk metrics
    fill_probability: Decimal  # 0.0 to 1.0
    continuation_probability: Decimal  # 0.0 to 1.0
    risk_level: RiskLevel
    confidence: ConfidenceLevel

    # Trade parameters
    suggested_entry: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    max_position_size: Decimal  # Dollar amount
    risk_reward_ratio: Decimal
