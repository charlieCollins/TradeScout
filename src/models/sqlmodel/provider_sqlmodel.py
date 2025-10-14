"""SQLModel version of Provider - Repository/DAO pattern implementation.

This file contains the SQLModel version used by repositories for database operations.
The dataclass version (provider.py) is used by providers and business logic.
"""

from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel


class ProviderSQLModel(SQLModel, table=True):
    """SQLModel representation of Provider - serves as both ORM model and schema.

    This model maps to the existing 'providers' table in the database.
    Providers represent API data sources (Polygon, YFinance, etc.).
    """

    __tablename__ = "providers"

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
        max_length=50,
        description="Provider identifier (e.g., 'polygon', 'yfinance')"
    )

    display_name: str = Field(
        description="Human-readable name (e.g., 'Polygon.io', 'Yahoo Finance')"
    )

    # ============================================================================
    # CONFIGURATION
    # ============================================================================

    base_url: Optional[str] = Field(
        default=None,
        description="Base API URL for the provider"
    )

    api_key_required: bool = Field(
        default=True,
        description="Whether this provider requires an API key"
    )

    # ============================================================================
    # STATUS
    # ============================================================================

    is_active: bool = Field(
        default=True,
        index=True,
        description="Whether provider is currently active"
    )

    # ============================================================================
    # METADATA
    # ============================================================================

    created_at: datetime = Field(
        default_factory=datetime.now,
        description="Record creation timestamp"
    )

    # ============================================================================
    # COMPUTED PROPERTIES
    # ============================================================================

    @property
    def name_display(self) -> str:
        """Get display name for the provider."""
        return self.display_name or self.name.title()

    @property
    def requires_api_key(self) -> bool:
        """Check if provider requires API key."""
        return self.api_key_required

    # ============================================================================
    # MODEL CONFIGURATION
    # ============================================================================

    class Config:
        """SQLModel configuration."""
        json_schema_extra = {
            "example": {
                "id": 1,
                "name": "polygon",
                "display_name": "Polygon.io",
                "base_url": "https://api.polygon.io",
                "api_key_required": True,
                "is_active": True
            }
        }
