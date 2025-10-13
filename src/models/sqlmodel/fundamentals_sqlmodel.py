"""SQLModel version of AssetFundamentals - Repository/DAO pattern implementation.

This file contains the SQLModel version of AssetFundamentals for the new architecture.
The original dataclass version (fundamentals.py) remains for backward compatibility
during the strangler fig migration.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlmodel import Field, SQLModel, Relationship


class FundamentalsSQLModel(SQLModel, table=True):
    """SQLModel representation of AssetFundamentals - serves as both ORM model and schema.

    This model maps to the existing 'asset_fundamentals' table in the database.
    It has a one-to-one relationship with Asset.

    Key features:
    - Database table definition
    - Pydantic validation
    - Type-safe queries
    - Foreign key relationship to assets table
    """

    __tablename__ = "asset_fundamentals"

    # ============================================================================
    # PRIMARY KEY - One-to-one with Assets
    # ============================================================================

    asset_id: int = Field(
        primary_key=True,
        foreign_key="assets.id",
        description="Foreign key to assets table (one-to-one relationship)"
    )

    # ============================================================================
    # COMPANY IDENTIFICATION
    # ============================================================================

    company_name: Optional[str] = Field(
        default=None,
        description="Company name (e.g., 'Apple Inc.')"
    )

    # ============================================================================
    # BUSINESS CLASSIFICATION
    # ============================================================================

    sector: Optional[str] = Field(
        default=None,
        index=True,
        description="Business sector (e.g., 'Technology')"
    )

    industry: Optional[str] = Field(
        default=None,
        index=True,
        description="Industry classification (e.g., 'Consumer Electronics')"
    )

    sic_code: Optional[str] = Field(
        default=None,
        max_length=10,
        description="Standard Industrial Classification code"
    )

    # ============================================================================
    # KEY FINANCIALS
    # ============================================================================

    market_cap: Optional[int] = Field(
        default=None,
        index=True,
        description="Market capitalization in cents (stored as integer for precision)"
    )

    shares_outstanding: Optional[int] = Field(
        default=None,
        description="Total outstanding shares"
    )

    # ============================================================================
    # SCREENING METRICS
    # ============================================================================

    avg_volume_30d: Optional[int] = Field(
        default=None,
        description="30-day average trading volume"
    )

    beta: Optional[Decimal] = Field(
        default=None,
        max_digits=6,
        decimal_places=3,
        description="Beta coefficient (volatility measure)"
    )

    pe_ratio: Optional[Decimal] = Field(
        default=None,
        max_digits=8,
        decimal_places=2,
        description="Price-to-earnings ratio"
    )

    dividend_yield: Optional[Decimal] = Field(
        default=None,
        max_digits=6,
        decimal_places=4,
        description="Annual dividend yield (as decimal, e.g., 0.0250 = 2.5%)"
    )

    # ============================================================================
    # METADATA
    # ============================================================================

    provider_id: int = Field(
        foreign_key="providers.id",
        description="Foreign key to providers table"
    )

    last_updated: datetime = Field(
        default_factory=datetime.now,
        description="Last update timestamp"
    )

    # ============================================================================
    # RELATIONSHIPS (SQLModel relationships for joins)
    # ============================================================================

    # Note: Uncomment when AssetSQLModel is updated with back-reference
    # asset: Optional["AssetSQLModel"] = Relationship(back_populates="fundamentals")

    # ============================================================================
    # COMPUTED PROPERTIES (Domain Logic)
    # ============================================================================

    @property
    def market_cap_display(self) -> str:
        """Get human-readable market cap.

        Returns:
            Formatted market cap string (e.g., "$2.5T", "$150.3B", "$45.2M")
        """
        if not self.market_cap:
            return "N/A"

        # Convert from cents to dollars
        market_cap_dollars = self.market_cap / 100

        if market_cap_dollars >= 1_000_000_000_000:
            return f"${market_cap_dollars / 1_000_000_000_000:.1f}T"
        elif market_cap_dollars >= 1_000_000_000:
            return f"${market_cap_dollars / 1_000_000_000:.1f}B"
        elif market_cap_dollars >= 1_000_000:
            return f"${market_cap_dollars / 1_000_000:.1f}M"
        else:
            return f"${market_cap_dollars:,.0f}"

    @property
    def shares_outstanding_display(self) -> str:
        """Get human-readable shares outstanding.

        Returns:
            Formatted shares string (e.g., "16.3B", "245.7M")
        """
        if not self.shares_outstanding:
            return "N/A"

        if self.shares_outstanding >= 1_000_000_000:
            return f"{self.shares_outstanding / 1_000_000_000:.1f}B"
        elif self.shares_outstanding >= 1_000_000:
            return f"{self.shares_outstanding / 1_000_000:.1f}M"
        else:
            return f"{self.shares_outstanding:,}"

    @property
    def has_market_cap(self) -> bool:
        """Check if market cap data is available."""
        return self.market_cap is not None and self.market_cap > 0

    @property
    def is_large_cap(self) -> bool:
        """Check if this is a large-cap stock (>$10B)."""
        if not self.market_cap:
            return False
        return (self.market_cap / 100) >= 10_000_000_000

    @property
    def is_mid_cap(self) -> bool:
        """Check if this is a mid-cap stock ($2B - $10B)."""
        if not self.market_cap:
            return False
        market_cap_dollars = self.market_cap / 100
        return 2_000_000_000 <= market_cap_dollars < 10_000_000_000

    @property
    def is_small_cap(self) -> bool:
        """Check if this is a small-cap stock ($300M - $2B)."""
        if not self.market_cap:
            return False
        market_cap_dollars = self.market_cap / 100
        return 300_000_000 <= market_cap_dollars < 2_000_000_000

    # ============================================================================
    # MODEL CONFIGURATION
    # ============================================================================

    class Config:
        """SQLModel configuration."""
        # Allow arbitrary types (for Decimal, etc.)
        arbitrary_types_allowed = True

        # JSON schema extra
        json_schema_extra = {
            "example": {
                "asset_id": 27,
                "company_name": "Apple Inc.",
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "sic_code": "3571",
                "market_cap": 285000000000000,  # $2.85T in cents
                "shares_outstanding": 16000000000,
                "avg_volume_30d": 50000000,
                "beta": 1.25,
                "pe_ratio": 28.50,
                "dividend_yield": 0.0052,
                "provider_id": 1
            }
        }
