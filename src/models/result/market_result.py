"""Result models for market command outputs."""

from dataclasses import dataclass
from typing import Optional, List, Tuple
from datetime import datetime, date

from models.dataclass.market_context import MarketContext


@dataclass
class MarketSnapshotUpdateStats:
    """Internal statistics for market snapshot update operations.

    Used by data_service_v2 to return stats from update/backfill operations.
    CLI/Web convert this to MarketUpdateResult or MarketBackfillResult for display.
    """
    total_tickers: int
    matched_symbols: int
    unmatched_symbols: int
    transformed: int
    invalid: int
    invalid_no_timestamp: int = 0
    invalid_exception: int = 0
    saved: int = 0
    duplicates: int = 0
    data_was_fresh: bool = False


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
    invalid_no_timestamp: int = 0  # Invalid: missing provider_updated_at timestamp
    invalid_exception: int = 0  # Invalid: exception during transformation
    duration_seconds: float = 0.0
    completed_at: Optional[datetime] = None
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
    invalid_no_timestamp: int = 0  # Invalid: missing provider_updated_at timestamp
    invalid_exception: int = 0  # Invalid: exception during transformation
    duration_seconds: float = 0.0
    completed_at: Optional[datetime] = None
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
