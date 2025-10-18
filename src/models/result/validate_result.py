"""Result models for validate command outputs."""

from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime, date


@dataclass
class VolumeValidationRow:
    """Single row in volume validation results."""
    symbol: str
    snapshot_volume: Optional[int]
    snapshot_time: Optional[datetime]
    aggregates_volume: Optional[int]
    aggregates_time: Optional[datetime]
    diff_percent: Optional[float]
    status: Optional[str]  # "good", "ok", "high", "snap_na"


@dataclass
class VolumeValidationResult:
    """Result for volume validation command."""
    session: str  # "premarket", "regular", "afterhours", "closed"
    trading_date: date
    is_extended_hours: bool
    rows: List[VolumeValidationRow]
