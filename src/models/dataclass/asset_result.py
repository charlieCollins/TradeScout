"""Result models for asset command outputs."""

from dataclasses import dataclass
from typing import Optional, List, Tuple, TYPE_CHECKING
from datetime import datetime

from models.dataclass.asset import Asset
from models.dataclass.market import Market
from models.dataclass.price import AssetPrice

if TYPE_CHECKING:
    from analysis.sentiment_analyzer import SentimentScore


@dataclass
class MarketContextResult:
    """Result for market context display (list of markets with status)."""
    markets: List[Tuple[str, str, str, str, str]]  # (code, session, status, trading_day, extended_hours)


@dataclass
class AssetInfoResult:
    """Result for asset information display."""
    asset: Asset  # Compose existing Asset model
    market: Optional[Market]  # Compose existing Market model
    universes: List[str]  # Universe memberships


@dataclass
class PriceDataResult:
    """Result for price data display."""
    asset_price: AssetPrice  # Compose existing AssetPrice model
    is_new_data: bool = True
    forced_fetch: bool = False


@dataclass
class SentimentEventsResult:
    """Result for sentiment events display."""
    symbol: str
    sentiment_events: List  # List of sentiment event objects
    type_id_to_name: dict  # Mapping of sentiment type IDs to names
    sentiment_score: Optional['SentimentScore']  # Overall sentiment score (composed)
    time_window_days: int  # Time window for sentiment calculation
