"""FedData SQLModel for database operations.

This model represents Federal Reserve economic data in the database using SQLModel ORM.
"""

from datetime import datetime, date
from typing import Optional
from sqlmodel import Field, SQLModel


class FedDataSQLModel(SQLModel, table=True):
    """SQLModel for fed_data table.

    Represents Federal Reserve economic data points (inflation, treasury yields, etc.)
    """

    __tablename__ = "fed_data"

    # Primary key
    id: Optional[int] = Field(default=None, primary_key=True)

    # Data identification
    data_type: str = Field(index=True)  # 'inflation', 'inflation_expectations', 'treasury_yields'
    observation_date: date = Field(index=True)

    # Data value
    value: float  # The actual data value (rate, yield, index, etc.)

    # Additional metadata (stored as JSON text)
    details: str  # JSON string: '{"series_name": "CPI", "maturity": "10Y"}'

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
