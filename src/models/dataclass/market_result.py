"""Result models for market command outputs."""

from dataclasses import dataclass
from typing import Optional, List, Tuple
from datetime import datetime, date

from models.dataclass.market_context import MarketContext


@dataclass
class MarketUpdateResult:
    """Result for market update command."""
    data_was_fresh: bool
    total_tickers: int
    matched_symbols: int
    unmatched_symbols: int
    transformed: int
    saved: int
    duplicates: int
    invalid: int
    duration_seconds: float
    completed_at: datetime
    last_snapshot_time: Optional[datetime] = None
    age_minutes: Optional[float] = None
    ttl_minutes: Optional[float] = None
    total_historical_records: Optional[int] = None


@dataclass
class MarketBackfillResult:
    """Result for market backfill command."""
    target_date: date
    force_refresh: bool
    total_tickers: int
    matched_symbols: int
    unmatched_symbols: int
    transformed: int
    saved: int
    duplicates: int
    invalid: int
    duration_seconds: float
    completed_at: datetime
    total_historical_records: Optional[int] = None


@dataclass
class MarketContextResult:
    """Result for market context command."""
    universe_name: str
    universe_markets: List[Tuple[str, str, int]]  # (code, name, count)
    total_universe: int
    market_context: MarketContext  # Compose existing MarketContext model

    # Last snapshot metadata (display-specific)
    last_snapshot_status: Optional[str] = None
    last_snapshot_time: Optional[datetime] = None
    last_snapshot_age_str: Optional[str] = None
