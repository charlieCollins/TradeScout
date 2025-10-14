"""SQLModel version of Market - Repository/DAO pattern implementation.

This file contains the SQLModel version used by repositories for database operations.
The dataclass version (market.py) is used by providers and business logic.
"""

from datetime import datetime, time
from typing import Optional
from sqlmodel import Field, SQLModel


class MarketSQLModel(SQLModel, table=True):
    """SQLModel representation of Market - serves as both ORM model and schema.

    This model maps to the existing 'markets' table in the database.
    It serves as the DAO (Data Access Object) layer, providing:
    - Database table definition
    - Pydantic validation
    - Type-safe queries
    - Automatic CRUD operations

    The Repository layer will wrap this model with business operations.
    """

    __tablename__ = "markets"

    # ============================================================================
    # PRIMARY IDENTIFICATION
    # ============================================================================

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
        description="Auto-incrementing primary key"
    )

    code: str = Field(
        index=True,
        unique=True,
        max_length=20,
        description="Market/exchange code (e.g., 'XNYS', 'XNAS', 'NYSE')"
    )

    name: str = Field(
        description="Human-readable market name (e.g., 'New York Stock Exchange')"
    )

    # ============================================================================
    # LOCATION DETAILS
    # ============================================================================

    country: str = Field(
        default="US",
        max_length=2,
        description="Country code (ISO 3166-1 alpha-2)"
    )

    timezone: str = Field(
        default="America/New_York",
        description="Market timezone (tz database format)"
    )

    currency: str = Field(
        default="USD",
        max_length=3,
        description="Primary currency traded (ISO 4217)"
    )

    # ============================================================================
    # TRADING HOURS (in market timezone)
    # ============================================================================

    premarket_start_time: Optional[time] = Field(
        default=None,
        description="Pre-market session start time (e.g., 04:00:00)"
    )

    premarket_end_time: Optional[time] = Field(
        default=None,
        description="Pre-market session end time (e.g., 09:30:00)"
    )

    regular_open_time: Optional[time] = Field(
        default=time(9, 30),
        description="Regular session open time (e.g., 09:30:00)"
    )

    regular_close_time: Optional[time] = Field(
        default=time(16, 0),
        description="Regular session close time (e.g., 16:00:00)"
    )

    afterhours_start_time: Optional[time] = Field(
        default=None,
        description="After-hours session start time (e.g., 16:00:00)"
    )

    afterhours_end_time: Optional[time] = Field(
        default=None,
        description="After-hours session end time (e.g., 20:00:00)"
    )

    # ============================================================================
    # STATUS
    # ============================================================================

    is_active: bool = Field(
        default=True,
        index=True,
        description="Whether market is currently active"
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
        description="Record last update timestamp"
    )

    # ============================================================================
    # COMPUTED PROPERTIES (Domain Logic)
    # ============================================================================

    @property
    def has_extended_hours(self) -> bool:
        """Check if market supports extended hours trading."""
        return (self.premarket_start_time is not None or
                self.afterhours_end_time is not None)

    @property
    def display_name(self) -> str:
        """Get display name for the market."""
        return f"{self.name} ({self.code})"

    @property
    def is_us_market(self) -> bool:
        """Check if this is a US market."""
        return self.country == "US"

    @property
    def has_premarket(self) -> bool:
        """Check if market has pre-market session."""
        return (self.premarket_start_time is not None and
                self.premarket_end_time is not None)

    @property
    def has_afterhours(self) -> bool:
        """Check if market has after-hours session."""
        return (self.afterhours_start_time is not None and
                self.afterhours_end_time is not None)

    # ============================================================================
    # MODEL CONFIGURATION
    # ============================================================================

    class Config:
        """SQLModel configuration."""
        # Allow arbitrary types (for time, datetime, etc.)
        arbitrary_types_allowed = True

        # JSON schema extra
        json_schema_extra = {
            "example": {
                "id": 1,
                "code": "XNYS",
                "name": "New York Stock Exchange",
                "country": "US",
                "timezone": "America/New_York",
                "currency": "USD",
                "regular_open_time": "09:30:00",
                "regular_close_time": "16:00:00",
                "is_active": True
            }
        }
