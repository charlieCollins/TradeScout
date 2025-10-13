"""SQLModel version of Asset - Repository/DAO pattern implementation.

This file contains the SQLModel version of Asset for the new architecture,
including AssetType and AssetClass enums.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from sqlmodel import Field, SQLModel


class AssetType(Enum):
    """Asset type classification."""
    STOCK = "stock"
    ETF = "etf"
    REIT = "reit"
    FUND = "fund"
    WARRANT = "warrant"
    RIGHT = "right"
    UNIT = "unit"
    BOND = "bond"
    ADR = "adr"
    OTHER = "other"


class AssetClass(Enum):
    """Asset class classification."""
    EQUITY = "equity"
    FIXED_INCOME = "fixed_income"
    COMMODITY = "commodity"


class AssetSQLModel(SQLModel, table=True):
    """SQLModel representation of Asset - serves as both ORM model and schema.

    This model maps to the existing 'assets' table in the database.
    It serves as the DAO (Data Access Object) layer, providing:
    - Database table definition
    - Pydantic validation
    - Type-safe queries
    - Automatic CRUD operations

    The Repository layer will wrap this model with business operations.
    """

    __tablename__ = "assets"

    # ============================================================================
    # PRIMARY IDENTIFICATION
    # ============================================================================

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
        description="Auto-incrementing primary key"
    )

    symbol: str = Field(
        index=True,
        unique=True,
        max_length=20,
        description="Ticker symbol (e.g., 'AAPL', 'MSFT')"
    )

    name: str = Field(
        description="Company/asset name (e.g., 'Apple Inc.')"
    )

    # ============================================================================
    # CLASSIFICATION
    # ============================================================================

    asset_type: str = Field(
        default="stock",
        description="Asset type classification"
    )

    asset_class: str = Field(
        default="equity",
        description="Asset class classification"
    )

    market_id: int = Field(
        foreign_key="markets.id",
        index=True,
        description="Foreign key to markets table"
    )

    # ============================================================================
    # TRADING DETAILS
    # ============================================================================

    currency: str = Field(
        default="USD",
        max_length=3,
        description="Trading currency"
    )

    lot_size: int = Field(
        default=1,
        description="Standard trading lot size"
    )

    tick_size: Optional[Decimal] = Field(
        default=None,
        max_digits=10,
        decimal_places=6,
        description="Minimum price increment"
    )

    # ============================================================================
    # STATUS
    # ============================================================================

    is_active: bool = Field(
        default=True,
        index=True,
        description="Whether asset is currently active"
    )

    is_delisted: bool = Field(
        default=False,
        description="Whether asset has been delisted"
    )

    listing_date: Optional[datetime] = Field(
        default=None,
        description="Date asset was listed"
    )

    delisting_date: Optional[datetime] = Field(
        default=None,
        description="Date asset was delisted (if applicable)"
    )

    # ============================================================================
    # METADATA
    # ============================================================================

    provider_id: int = Field(
        foreign_key="providers.id",
        description="Foreign key to providers table"
    )

    created_at: datetime = Field(
        default_factory=datetime.now,
        description="Record creation timestamp"
    )

    updated_at: datetime = Field(
        default_factory=datetime.now,
        description="Record last update timestamp"
    )

    # ============================================================================
    # COMPUTED PROPERTIES (Domain Logic)
    # ============================================================================

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

    @property
    def asset_type_enum(self) -> AssetType:
        """Get AssetType enum from string value."""
        return AssetType(self.asset_type)

    @property
    def asset_class_enum(self) -> AssetClass:
        """Get AssetClass enum from string value."""
        return AssetClass(self.asset_class)

    @property
    def is_tradeable(self) -> bool:
        """Check if asset can be traded (active and not delisted)."""
        return self.is_active and not self.is_delisted

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
                "id": 1,
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "asset_type": "stock",
                "asset_class": "equity",
                "market_id": 1,
                "currency": "USD",
                "lot_size": 1,
                "tick_size": "0.01",
                "is_active": True,
                "is_delisted": False,
                "provider_id": 1
            }
        }
