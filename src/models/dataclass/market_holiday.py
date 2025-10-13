"""Market holiday model for TradeScout."""

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Dict, Any


class HolidayStatus(Enum):
    """Market holiday status types."""
    CLOSED = "closed"           # Market fully closed
    EARLY_CLOSE = "early_close" # Market closes early


@dataclass(frozen=True)
class MarketHoliday:
    """Represents a market holiday or early close day.

    Attributes:
        date: Holiday date
        name: Holiday name (e.g., "New Year's Day", "Thanksgiving")
        status: Whether market is closed or closes early
        exchange: Optional exchange code (e.g., "XNYS") - None means all US markets
    """

    date: date
    name: str
    status: HolidayStatus
    exchange: str = "US"  # Default to US markets

    @property
    def is_full_closure(self) -> bool:
        """Check if this is a full market closure."""
        return self.status == HolidayStatus.CLOSED

    @property
    def is_early_close(self) -> bool:
        """Check if this is an early close day."""
        return self.status == HolidayStatus.EARLY_CLOSE

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation
        """
        return {
            'date': self.date.isoformat(),
            'name': self.name,
            'status': self.status.value,
            'exchange': self.exchange
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MarketHoliday':
        """Create MarketHoliday from dictionary.

        Args:
            data: Dictionary with holiday data

        Returns:
            MarketHoliday instance
        """
        return cls(
            date=date.fromisoformat(data['date']) if isinstance(data['date'], str) else data['date'],
            name=data['name'],
            status=HolidayStatus(data['status']) if isinstance(data['status'], str) else data['status'],
            exchange=data.get('exchange', 'US')
        )

    @classmethod
    def from_polygon_data(cls, polygon_data: Dict[str, Any]) -> 'MarketHoliday':
        """Create MarketHoliday from Polygon API response.

        Polygon API returns holidays in format:
        {
            "date": "2024-01-01",
            "exchange": "NYSE",
            "name": "New Year's Day",
            "status": "closed"
        }

        Args:
            polygon_data: Raw Polygon API holiday data

        Returns:
            MarketHoliday instance
        """
        # Parse date string to date object
        date_str = polygon_data.get('date', '')
        holiday_date = date.fromisoformat(date_str) if date_str else date.today()

        # Map Polygon status to our enum
        status_str = polygon_data.get('status', 'closed').lower()
        if 'early' in status_str:
            status = HolidayStatus.EARLY_CLOSE
        else:
            status = HolidayStatus.CLOSED

        # Map exchange (Polygon might use "NYSE", we standardize to MIC codes)
        exchange = polygon_data.get('exchange', 'US')

        return cls(
            date=holiday_date,
            name=polygon_data.get('name', 'Holiday'),
            status=status,
            exchange=exchange
        )

    def __str__(self) -> str:
        """Human-readable representation."""
        return f"{self.date.isoformat()}: {self.name} ({self.status.value})"
