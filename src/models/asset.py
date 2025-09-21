"""Asset data model for TradeScout."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
from datetime import datetime
from decimal import Decimal


class AssetType(Enum):
    """Asset type classification."""
    STOCK = "stock"
    ETF = "etf"
    REIT = "reit"


class AssetClass(Enum):
    """Asset class classification."""
    EQUITY = "equity"
    FIXED_INCOME = "fixed_income"
    COMMODITY = "commodity"


@dataclass(frozen=True)
class Asset:
    """Represents a tradeable asset/security."""

    # Primary identification (required fields)
    id: int
    symbol: str
    name: Optional[str]

    # Classification (required fields)
    asset_type: AssetType
    asset_class: AssetClass
    market_id: int

    # Trading details (required fields)
    currency: str

    # Metadata (required fields)
    provider_id: int
    created_at: datetime
    updated_at: datetime

    # Trading details (optional fields with defaults)
    lot_size: int = 1
    tick_size: Optional[Decimal] = None

    # Status (optional fields with defaults)
    is_active: bool = True
    is_delisted: bool = False
    listing_date: Optional[datetime] = None
    delisting_date: Optional[datetime] = None

    @property
    def display_name(self) -> str:
        """Get display name (name if available, otherwise symbol)."""
        return self.name or self.symbol

    @property
    def status_text(self) -> str:
        """Get human-readable status."""
        if self.is_delisted:
            return "Delisted"
        return "Active" if self.is_active else "Inactive"