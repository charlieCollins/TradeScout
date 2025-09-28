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

    @classmethod
    def from_db_row(cls, row: tuple) -> 'Universe':
        """Create Universe from database row."""
        return cls(
            id=row[0],
            name=row[1],
            description=row[2],
            is_active=bool(row[3]),
            min_market_cap=row[4],
            min_volume=row[5],
            max_assets=row[6],
            last_updated=datetime.fromisoformat(row[7]) if row[7] else None,
            created_at=datetime.fromisoformat(row[8]),
            updated_at=datetime.fromisoformat(row[9])
        )


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

    @classmethod
    def from_db_row(cls, row: tuple) -> 'UniverseMembership':
        """Create UniverseMembership from database row."""
        return cls(
            id=row[0],
            universe_id=row[1],
            asset_id=row[2],
            added_date=datetime.fromisoformat(row[3]),
            removed_date=datetime.fromisoformat(row[4]) if row[4] else None,
            reason=row[5],
            is_active=bool(row[6])
        )


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