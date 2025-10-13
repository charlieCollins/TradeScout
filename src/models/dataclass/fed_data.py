"""Federal Reserve economic data model for TradeScout."""

from dataclasses import dataclass
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Dict, Any


@dataclass(frozen=True)
class FedData:
    """Represents Federal Reserve economic data point.

    This model handles multiple types of Fed data:
    - Inflation (CPI, PCE, etc.)
    - Inflation expectations
    - Treasury yields (various maturities)
    """

    # Primary identification
    id: int
    data_type: str  # 'inflation', 'inflation_expectations', 'treasury_yields'

    # Data point
    observation_date: date  # Date of the observation
    value: Decimal  # The actual data value (rate, yield, index, etc.)

    # Additional metadata (JSON)
    details: Dict[str, Any]  # {"series_name": "CPI", "maturity": "10Y", etc.}

    # Timestamps
    created_at: datetime
    updated_at: datetime

    @property
    def is_inflation(self) -> bool:
        """Check if this is inflation data."""
        return self.data_type == "inflation"

    @property
    def is_inflation_expectation(self) -> bool:
        """Check if this is inflation expectations data."""
        return self.data_type == "inflation_expectations"

    @property
    def is_treasury_yield(self) -> bool:
        """Check if this is treasury yield data."""
        return self.data_type == "treasury_yields"

    def get_detail(self, key: str, default: Any = None) -> Any:
        """Get specific detail from details dict."""
        return self.details.get(key, default)

    @property
    def display_value(self) -> str:
        """Format value for display (typically as percentage)."""
        if self.is_treasury_yield or self.is_inflation:
            return f"{float(self.value):.2f}%"
        else:
            return f"{float(self.value):.2f}"

    @classmethod
    def from_polygon_data(
        cls,
        data_type: str,
        polygon_data: Dict[str, Any],
        observation_date: date,
    ) -> "FedData":
        """Create FedData from Polygon API response.

        Args:
            data_type: Type of fed data
            polygon_data: Raw data from Polygon API
            observation_date: Date of observation

        Returns:
            FedData instance
        """
        # Extract representative value based on data type
        if data_type == "treasury_yields":
            # Use 10-year yield as representative value
            value = polygon_data.get("yield_10_year", 0)
        else:
            # For inflation and inflation_expectations, use direct value
            value = polygon_data.get("value", 0)

        return cls(
            id=0,  # Will be assigned by database
            data_type=data_type,
            observation_date=observation_date,
            value=Decimal(str(value)),
            details=polygon_data,  # Store entire response for reference
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
