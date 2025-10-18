"""Asset fundamentals data model for TradeScout."""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class AssetFundamentals:
    """Represents fundamental data for an asset."""

    # Primary key - matches asset ID
    asset_id: int

    # Company identification
    company_name: Optional[str]

    # Business classification
    sector: Optional[str]
    industry: Optional[str]
    sic_code: Optional[str]

    # Key financials
    market_cap: Optional[int]  # Market capitalization in cents
    shares_outstanding: Optional[int]  # Outstanding shares

    # Data tracking (required fields)
    provider_id: int
    last_updated: datetime

    # Additional metrics for screening (optional fields with defaults)
    avg_volume_30d: Optional[int] = None
    beta: Optional[Decimal] = None
    pe_ratio: Optional[Decimal] = None
    dividend_yield: Optional[Decimal] = None

    @property
    def market_cap_display(self) -> str:
        """Get human-readable market cap."""
        if not self.market_cap:
            return "N/A"

        # Convert from cents to dollars
        market_cap_dollars = self.market_cap / 100

        if market_cap_dollars >= 1_000_000_000:
            return f"${market_cap_dollars / 1_000_000_000:.1f}B"
        elif market_cap_dollars >= 1_000_000:
            return f"${market_cap_dollars / 1_000_000:.1f}M"
        else:
            return f"${market_cap_dollars:,.0f}"

    @property
    def shares_outstanding_display(self) -> str:
        """Get human-readable shares outstanding."""
        if not self.shares_outstanding:
            return "N/A"

        if self.shares_outstanding >= 1_000_000_000:
            return f"{self.shares_outstanding / 1_000_000_000:.1f}B"
        elif self.shares_outstanding >= 1_000_000:
            return f"{self.shares_outstanding / 1_000_000:.1f}M"
        else:
            return f"{self.shares_outstanding:,}"

    def to_dict(self) -> dict:
        """Convert to dictionary for database operations."""
        return {
            "asset_id": self.asset_id,
            "company_name": self.company_name,
            "sector": self.sector,
            "industry": self.industry,
            "sic_code": self.sic_code,
            "market_cap": self.market_cap,
            "shares_outstanding": self.shares_outstanding,
            "avg_volume_30d": self.avg_volume_30d,
            "beta": self.beta,
            "pe_ratio": self.pe_ratio,
            "dividend_yield": self.dividend_yield,
            "provider_id": self.provider_id,
            "last_updated": self.last_updated.isoformat()
        }

    @classmethod
    def from_polygon_data(cls, asset_id: int, provider_id: int, polygon_data: dict) -> 'AssetFundamentals':
        """Create AssetFundamentals from Polygon API ticker overview data."""
        from utils.config_loader import get_sector_from_sic

        sic_code = polygon_data.get("sic_code", "")
        sector = get_sector_from_sic(sic_code) if sic_code else None

        return cls(
            asset_id=asset_id,
            company_name=polygon_data.get("name"),
            sector=sector,
            industry=polygon_data.get("sic_description"),
            sic_code=sic_code or None,
            market_cap=polygon_data.get("market_cap"),
            shares_outstanding=(
                polygon_data.get("weighted_shares_outstanding") or
                polygon_data.get("share_class_shares_outstanding")
            ),
            provider_id=provider_id,
            last_updated=datetime.now()
        )