# Cache and API Separation Pattern

**Status:** Work in Progress - Currently implemented for TickerSnapshot only
**Date:** 2025-09-29

## Overview

This document outlines the separation of concerns between cache managers and the data provider for API calls and database operations.

## Design Principles

### DataProvider Responsibilities
- **API Calls**: Makes external API requests to fetch fresh data from Polygon, etc.
- **Data Transformation**: Minimal - just calls appropriate model constructors
- **Orchestration**: Coordinates between cache managers for complex operations
- **Business Logic**: High-level data operations and workflows

### Cache Manager Responsibilities
- **Database Operations**: All read/write operations for their specific entity type
- **TTL Logic**: Decides when to use cached data vs request fresh data
- **Data Storage Strategy**: How and where to store the entity data
- **Cache Statistics**: Provides metrics about cache performance

## Current Implementation: TickerSnapshot

### Flow Example
```python
# DataProvider
def get_single_ticker_snapshot(self, symbol: str, force: bool = False) -> Optional[TickerSnapshot]:
    return self.ticker_snapshot_cache.get_or_fetch(
        symbol,
        lambda: self._fetch_single_ticker_snapshot(symbol),  # API call provided to cache
        force_refresh=force  # Pass --force down to cache layer
    )

# TickerSnapshotCache decides:
# - If force=True: ALWAYS call provided fetch_fn() → API call, then set_entity_to_database()
# - If cache fresh: call get_entity_from_database() → read from asset_prices table
# - If cache stale: call provided fetch_fn() → API call, then set_entity_to_database()
```

### TickerSnapshotCache Implementation
- **Database Read**: `get_entity_from_database()` reads from asset_prices table, constructs TickerSnapshot
- **Database Write**: `set_entity_to_database()` transforms TickerSnapshot and stores to asset_prices table
- **TTL Validation**: Uses DataUpdateMetadataType.TICKER_SNAPSHOTS with 15-minute TTL
- **Storage Table**: asset_prices (shared with other price data)

### DataProvider Implementation
- **API Call**: `_fetch_single_ticker_snapshot()` calls Polygon API, returns TickerSnapshot
- **Coordination**: Provides API calling capability to cache manager
- **No Direct DB Operations**: Cache handles all database operations for ticker snapshots

## Work Status

### ✅ Completed: TickerSnapshot
- BaseCacheManager abstract interface with get_or_fetch() logic
- TickerSnapshotCache implements get/set_entity_to_database() methods
- DataProvider provides API calling capability via lambda
- Fixes critical bug where fresh data wasn't being stored

### 🚧 In Progress
- Documenting the pattern for future entity implementations
- Testing and validation of TickerSnapshot implementation

### ⏳ Pending: Other Entities
- AssetPricesCache - individual asset price operations
- MarketSnapshotCache - bulk market snapshot operations
- MarketContextCache - market status and context
- MarketHolidaysCache - market holiday data

### ⏳ Future Refactoring
- Break up monolithic data_provider.py into separate modules by data type
- Standardize all cache managers to follow this pattern
- Remove legacy caching approaches
- **Rename provider/cache → database/manager**: The "cache" naming is misleading - these are actually storage/database managers with TTL-based refresh logic, not traditional caches

## Target Architecture

The goal is to break the monolithic `data_provider.py` into clean, separate layers:

### Database Layer
```
database/manager/
├── base_database_manager.py      # Abstract base for all database operations
├── ticker_snapshot_manager.py    # TickerSnapshot database operations
├── market_context_manager.py     # MarketContext database operations
├── asset_prices_manager.py       # AssetPrice database operations
└── fundamentals_manager.py       # Fundamentals database operations
```

### API Provider Layer
```
api/provider/
├── base_api_provider.py          # Abstract base for all API operations
├── polygon_snapshot_provider.py  # Polygon snapshot API calls
├── polygon_context_provider.py   # Polygon market status API calls
├── polygon_fundamentals_provider.py # Polygon fundamentals API calls
└── yfinance_provider.py          # YFinance API calls (backup)
```

### Orchestration Layer
```
data_service.py                   # Top-level coordinator
├── Wires together database managers and API providers
├── Handles complex multi-entity operations
├── Manages cross-cutting concerns (logging, errors, etc.)
└── Provides clean interface to business logic
```

### Flow Example (Target State)
```python
# data_service.py
class DataService:
    def __init__(self):
        # Database managers
        self.ticker_db = TickerSnapshotManager(db_manager, update_tracker)

        # API providers
        self.polygon_api = PolygonSnapshotProvider(api_key)

    def get_ticker_snapshot(self, symbol: str, force: bool = False):
        return self.ticker_db.get_or_fetch(
            symbol,
            lambda: self.polygon_api.fetch_ticker_snapshot(symbol),
            force_refresh=force
        )
```

This separates:
- **Database operations** (storage, TTL, metadata)
- **API operations** (authentication, requests, parsing)
- **Orchestration** (coordination between layers)

## Force Refresh Handling

The `--force` parameter must be respected throughout the cache/API layer:

### DataProvider Level
- Accepts `force: bool = False` parameter from CLI or calling code
- Passes `force_refresh=force` to cache manager's `get_or_fetch()` method
- Example: `get_single_ticker_snapshot(symbol, force=True)`

### Cache Manager Level
- `get_or_fetch()` accepts `force_refresh: bool = False` parameter
- When `force_refresh=True`: ALWAYS bypass cache and call API, regardless of TTL
- When `force_refresh=False`: Use normal TTL-based cache logic
- Still stores fresh data to database after forced API call

### Implementation Priority
- Force refresh bypasses ALL cache logic - always makes API call
- Cache invalidation is achieved by forcing fresh API calls, not deleting data
- Database stores new data alongside existing data (no deletion)

## Key Benefits

1. **Separation of Concerns**: API calling vs data storage are cleanly separated
2. **Unified TTL Logic**: All caches use same operation-level TTL validation
3. **Consistent Interface**: BaseCacheManager provides standard get_or_fetch() behavior
4. **Force Refresh Support**: `--force` parameter properly cascades through all layers
5. **Easier Testing**: Cache and API operations can be tested independently
6. **Better Maintainability**: Changes to storage strategy don't affect API calling logic

## Design Notes

- Cache managers are NOT responsible for API authentication or rate limiting
- DataProvider maintains API key management and request logic
- Cache managers focus purely on database operations and TTL decisions
- The "big ugly data_provider" will be refactored into separate modules once pattern is proven

## Naming Considerations

The current `provider/cache` naming is misleading:

- **Current**: `TickerSnapshotCache`, `MarketContextCache`, etc.
- **Reality**: These are database/storage managers with TTL-based refresh logic
- **Better Names**: `TickerSnapshotManager`, `MarketContextManager`, or `TickerSnapshotStorage`
- **Better Location**: `database/manager/` instead of `provider/cache/`

These aren't traditional "caches" (like Redis or in-memory stores). They're database managers that:
- Store data persistently in SQLite tables
- Use metadata-based TTL logic to decide when to refresh
- Handle all database operations for their specific entity type
- Coordinate with DataProvider for fresh data when needed

The database IS our cache, but calling these classes "cache managers" confuses their actual role as persistent storage layers.

## Current Limitations

- Only TickerSnapshot follows this pattern so far
- DataProvider is still monolithic and needs modularization
- Some cache managers may still use legacy approaches
- Pattern needs validation through actual usage before broader implementation