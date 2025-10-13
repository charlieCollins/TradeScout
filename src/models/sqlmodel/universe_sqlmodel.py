"""SQLModel version of Universe - Repository/DAO pattern implementation.

This file contains the SQLModel versions for the new architecture.
The original dataclass version (universe.py) remains for backward compatibility.

IMPORTANT: Universes are INTERNAL-ONLY entities. They are NOT fetched from external APIs.
Universes are created, updated, and managed entirely within TradeScout's database
through bootstrap operations and manual configuration.
"""

from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel


class UniverseSQLModel(SQLModel, table=True):
    """SQLModel representation of Universe - asset collection configuration.

    This model maps to the existing 'universes' table in the database.
    Universes define groups of assets for screening and analysis based on criteria
    like market cap, volume, and asset count limits.
    """

    __tablename__ = "universes"

    # ============================================================================
    # PRIMARY IDENTIFICATION
    # ============================================================================

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
        description="Auto-incrementing primary key"
    )

    name: str = Field(
        index=True,
        unique=True,
        max_length=100,
        description="Universe name (e.g., 'momentum', 'value', 'growth')"
    )

    description: Optional[str] = Field(
        default=None,
        description="Human-readable description of universe purpose"
    )

    # ============================================================================
    # UNIVERSE CRITERIA
    # ============================================================================

    min_market_cap: Optional[int] = Field(
        default=None,
        description="Minimum market cap in cents (e.g., 30000000000 = $300M)"
    )

    min_volume: Optional[int] = Field(
        default=None,
        description="Minimum 30-day average volume"
    )

    max_assets: Optional[int] = Field(
        default=None,
        description="Maximum number of assets allowed in universe"
    )

    # ============================================================================
    # STATUS
    # ============================================================================

    is_active: bool = Field(
        default=True,
        index=True,
        description="Whether this universe is currently active (only one can be active)"
    )

    last_updated: Optional[datetime] = Field(
        default=None,
        description="When universe memberships were last refreshed"
    )

    # ============================================================================
    # METADATA
    # ============================================================================

    created_at: datetime = Field(
        default_factory=datetime.now,
        description="Record creation timestamp"
    )

    updated_at: datetime = Field(
        default_factory=datetime.now,
        description="Record update timestamp"
    )

    # ============================================================================
    # COMPUTED PROPERTIES
    # ============================================================================

    @property
    def has_market_cap_filter(self) -> bool:
        """Check if universe has market cap filtering."""
        return self.min_market_cap is not None and self.min_market_cap > 0

    @property
    def has_volume_filter(self) -> bool:
        """Check if universe has volume filtering."""
        return self.min_volume is not None and self.min_volume > 0

    @property
    def has_size_limit(self) -> bool:
        """Check if universe has max assets limit."""
        return self.max_assets is not None and self.max_assets > 0

    # ============================================================================
    # MODEL CONFIGURATION
    # ============================================================================

    class Config:
        """SQLModel configuration."""
        json_schema_extra = {
            "example": {
                "id": 1,
                "name": "gap_trading_universe",
                "description": "Assets for gap trading strategy",
                "min_market_cap": 30000000000,  # $300M in cents
                "min_volume": 1000000,
                "max_assets": 500,
                "is_active": True,
                "last_updated": "2025-10-12T10:00:00"
            }
        }


class UniverseMembershipSQLModel(SQLModel, table=True):
    """SQLModel representation of UniverseMembership - M2M relationship.

    This model maps to the existing 'universe_memberships' table.
    It represents the many-to-many relationship between universes and assets.
    """

    __tablename__ = "universe_memberships"

    # ============================================================================
    # PRIMARY IDENTIFICATION
    # ============================================================================

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
        description="Auto-incrementing primary key"
    )

    # ============================================================================
    # RELATIONSHIPS (Foreign Keys)
    # ============================================================================

    universe_id: int = Field(
        foreign_key="universes.id",
        index=True,
        description="Universe this membership belongs to"
    )

    asset_id: int = Field(
        foreign_key="assets.id",
        index=True,
        description="Asset in this universe"
    )

    # ============================================================================
    # COMPUTED PROPERTIES
    # ============================================================================

    @property
    def is_valid(self) -> bool:
        """Check if membership has valid IDs."""
        return self.universe_id > 0 and self.asset_id > 0

    # ============================================================================
    # MODEL CONFIGURATION
    # ============================================================================

    class Config:
        """SQLModel configuration."""
        json_schema_extra = {
            "example": {
                "id": 1,
                "universe_id": 1,
                "asset_id": 42
            }
        }
