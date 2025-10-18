"""TradeScout data models - Typed data structures for consistent API.

Domain Models (Dataclasses):
- Used by providers, services, business logic
- Lightweight, immutable transfer objects
- Import from models.dataclass.* (e.g., from models.dataclass.asset import Asset)

ORM Models (SQLModel):
- Used by repositories for database operations
- Import from models.sqlmodel.* (e.g., from models.sqlmodel.asset_sqlmodel import AssetSQLModel)

Backward Compatibility:
- For convenience, domain models are also exported from models.* root
"""

# Domain models - for business logic
from .dataclass.asset import Asset, AssetType, AssetClass
from .dataclass.market import Market
from .dataclass.market_holiday import MarketHoliday, HolidayStatus
from .dataclass.provider import Provider
from .dataclass.fundamentals import AssetFundamentals
from .dataclass.price import AssetPrice
from .dataclass.snapshot import TickerSnapshot, MarketSnapshot
from .result.database_result import DatabaseStats
from .dataclass.universe import Universe, UniverseMembership, UniverseStats

__all__ = [
    # Domain models
    'Asset',
    'AssetType',
    'AssetClass',
    'Market',
    'MarketHoliday',
    'HolidayStatus',
    'Provider',
    'AssetFundamentals',
    'AssetPrice',
    'TickerSnapshot',
    'MarketSnapshot',
    'DatabaseStats',
    'Universe',
    'UniverseMembership',
    'UniverseStats',
]
