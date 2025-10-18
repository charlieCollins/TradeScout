"""Universe data models for TradeScout."""

from dataclasses import dataclass
from typing import List, Optional, Dict
from datetime import datetime


@dataclass(frozen=True)
class Universe:
    """Represents an asset universe configuration."""

    id: int
    name: str
    description: Optional[str]
    is_active: bool
    min_market_cap: Optional[int]
    min_volume: Optional[int]
    max_assets: Optional[int]
    last_updated: Optional[datetime]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class UniverseMembership:
    """Represents an asset's membership in a universe."""

    id: int
    universe_id: int
    asset_id: int
    added_date: datetime
    removed_date: Optional[datetime]
    reason: Optional[str]
    is_active: bool


@dataclass(frozen=True)
class UniverseStats:
    """Statistics for a universe."""

    universe_name: str
    total_members: int
    active_members: int
    inactive_members: int
    by_asset_type: Dict[str, int]
    by_market: Dict[str, int]
    last_updated: Optional[str]

    @property
    def activity_rate(self) -> float:
        """Percentage of active members."""
        if self.total_members == 0:
            return 0.0
        return (self.active_members / self.total_members) * 100