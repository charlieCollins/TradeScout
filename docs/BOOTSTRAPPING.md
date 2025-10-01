# TradeScout Bootstrapping Guide

**Last Updated**: 2025-09-30
**Architecture Version**: Manager/Provider Pattern (New)

## Overview

Bootstrapping is the process of populating TradeScout's database with initial reference data from external sources (primarily Polygon.io). This document outlines the bootstrap sequence, dependencies, and implementation in the new Manager/Provider architecture.

## Bootstrap Dependency Chain

The bootstrap process must follow this strict dependency order:

```
1. Providers (no dependencies)
   ↓
2. Markets (no dependencies)
   ↓
3. Assets/Tickers (depends on: Providers + Markets)
   ↓
4. Fundamentals (depends on: Assets)
   ↓
5. Universes (depends on: Assets + Fundamentals)
```

**Critical**: Each step must complete successfully before proceeding to the next step, as later steps require data created by earlier steps.

---

## Bootstrap Operations

### 1. Providers Bootstrap

**Purpose**: Initialize data provider configuration (Polygon.io)

**DataService Method**: `bootstrap_providers() -> int`

**What It Does**:
- Stores hardcoded Polygon provider configuration to `providers` table
- Sets provider as active
- Records metadata timestamp

**Dependencies**: None

**Example**:
```python
data_service = DataService(db_manager, update_tracker, polygon_api_key)
count = data_service.bootstrap_providers()
# Returns: 1 (one provider stored)
```

**Database Tables Updated**:
- `providers`: Polygon configuration record
- `data_update_metadata`: PROVIDERS operation timestamp

---

### 2. Markets Bootstrap

**Purpose**: Fetch and store exchange/market reference data

**DataService Method**: `bootstrap_markets(asset_class="stocks", locale="us") -> int`

**What It Does**:
- Fetches exchanges from Polygon `/v3/reference/exchanges` API
- Filters by asset_class (stocks, options, crypto, etc.) and locale (us, gb, ca, etc.)
- Stores to `markets` table with trading hours and metadata
- Records metadata timestamp

**Dependencies**: None (API-driven, no database dependencies)

**Example**:
```python
count = data_service.bootstrap_markets(asset_class="stocks", locale="us")
# Returns: number of markets stored (e.g., 7-12 for US stock exchanges)
```

**Database Tables Updated**:
- `markets`: Exchange records (XNYS, XNAS, ARCX, BATS, etc.)
- `data_update_metadata`: MARKETS operation timestamp

**TTL**: 1 year (markets rarely change)

---

### 3. Assets/Tickers Bootstrap

**Purpose**: Fetch all available tickers and store as assets

**DataService Method**: `bootstrap_assets(market="stocks", active=True) -> int`

**What It Does**:
- Fetches ALL tickers from Polygon `/v3/reference/tickers` API (paginated)
- Maps ticker data to Asset model
- Looks up market_id from primary_exchange → `markets` table
- Stores to `assets` table
- Records metadata timestamp

**Dependencies**:
- **Providers**: Need provider_id for asset records
- **Markets**: Need market_id lookup for primary_exchange mapping

**Example**:
```python
count = data_service.bootstrap_assets(market="stocks", active=True)
# Returns: number of assets stored (e.g., 10,000+ active stocks)
```

**Database Tables Updated**:
- `assets`: Ticker records with symbol, name, market_id, provider_id, currency, is_active
- `data_update_metadata`: TICKERS operation timestamp

**TTL**: 3 days (new listings/delistings are infrequent)

---

### 4. Fundamentals Bootstrap

**Purpose**: Fetch company fundamentals for each asset

**DataService Method**: `bootstrap_fundamentals(limit=None) -> int`

**What It Does**:
- Iterates through all assets in `assets` table
- For each asset, calls `/v3/reference/tickers/{symbol}` API
- Extracts fundamentals: market_cap, sector, industry, shares_outstanding, beta, pe_ratio, etc.
- Stores to `asset_fundamentals` table
- Records metadata timestamp

**Dependencies**:
- **Assets**: Need asset_id for each ticker to fetch fundamentals

**Example**:
```python
# Bootstrap all assets (can take a while!)
count = data_service.bootstrap_fundamentals()

# Bootstrap first 100 assets (for testing)
count = data_service.bootstrap_fundamentals(limit=100)

# Returns: number of fundamentals records stored
```

**Database Tables Updated**:
- `asset_fundamentals`: Company data linked to asset_id
- `data_update_metadata`: FUNDAMENTALS operation timestamp

**TTL**: 1 week (fundamentals change infrequently)

**Performance Note**: This can make thousands of API calls (one per asset). Consider using `limit` parameter for testing or processing in batches.

---

### 5. Universes Bootstrap

**Purpose**: Create filtered asset universes based on criteria

**DataService Method**: `bootstrap_universes()` *(NOT YET IMPLEMENTED)*

**What It Will Do**:
- Read universe configuration from `config/universe_config.py`
- Fetch all assets + fundamentals from database
- Apply filtering criteria:
  - Asset types (stocks, ETFs, REITs)
  - Exchanges (XNYS, XNAS)
  - Symbol patterns (alphabetic, length)
  - Market cap ranges
  - Sectors
  - Volume thresholds
- Exclude unwanted assets (preferred stocks, OTC, special characters)
- Create/update `universes` table record
- Populate `universe_memberships` table
- Records metadata timestamp

**Dependencies**:
- **Assets**: Need ticker data
- **Fundamentals**: Need market_cap, sector for filtering

**Database Tables Updated**:
- `universes`: Universe configuration record
- `universe_memberships`: Asset membership records
- `data_update_metadata`: UNIVERSES operation timestamp

**TTL**: 24 hours (membership can change with market cap shifts)

**Status**: Legacy implementation exists in `src/bootstrapping/bootstrapper_universe.py` - needs migration to new architecture

---

## New Architecture Pattern

### Location: DataService vs Managers

In the new Manager/Provider architecture:

**Bootstrap Methods Live in DataService** (`src/services/data_service.py`):
- Orchestrates the 3-step bootstrap process:
  1. Fetch from API Provider
  2. Store via Manager
  3. Record metadata timestamp

**Bootstrap Methods DO NOT Live in Managers**:
- Managers only handle database CRUD operations
- Managers don't know about API providers or orchestration

### Why This Pattern?

Bootstrap is an **orchestration operation** that requires coordination between multiple components:

```python
def bootstrap_X(self, ...):
    """Bootstrap X from Polygon API."""
    # Step 1: Fetch from API provider
    data = self.polygon_X_provider.fetch_all_X(...)

    # Step 2: Store via manager (one by one or batch)
    stored_count = 0
    for item in data:
        if self.X_manager.set_entity_to_database(key, item):
            stored_count += 1

    # Step 3: Record metadata timestamp for TTL tracking
    self.X_manager._record_update()

    return stored_count
```

All three components (provider, manager, metadata) are wired together in **DataService**, so bootstrap orchestration lives there.

---

## TTL-Based Refresh

Each bootstrap operation records a timestamp in `data_update_metadata` table. Future bootstrap calls check this timestamp against the configured TTL:

| Operation | TTL | Auto-Refresh Logic |
|-----------|-----|-------------------|
| Providers | 1 year | Essentially static - rarely refreshed |
| Markets | 1 year | Exchanges added infrequently |
| Assets | 3 days | New listings/delistings happen regularly |
| Fundamentals | 1 week | Company data changes periodically |
| Universes | 24 hours | Membership can shift with market conditions |

**Force Refresh**: All bootstrap methods support a `force_refresh` parameter to bypass TTL checks.

---

## Migration from Legacy Bootstrappers

### Old Approach (src/bootstrapping/)

Legacy bootstrap code exists in standalone classes:
- `bootstrapper_provider.py` - ProviderBootstrapper
- `bootstrapper_market.py` - MarketBootstrapper
- `bootstrapper_ticker.py` - TickerBootstrapper
- `bootstrapper_fundamentals.py` - FundamentalsBootstrapper
- `bootstrapper_universe.py` - UniverseBootstrapper

These classes directly accessed the old `PolygonDataProvider` monolith and handled their own database operations.

### New Approach (services/data_service.py)

Bootstrap operations now follow clean architecture separation:
- **API Providers**: Handle external API calls only
  - `PolygonMarketsProvider`
  - `PolygonTickersProvider`
  - (Fundamentals use `PolygonTickersProvider.fetch_ticker_details_raw()`)
- **Managers**: Handle database CRUD + TTL validation only
  - `ProviderManager`
  - `MarketsManager`
  - `AssetManager`
  - `FundamentalsManager`
  - `UniverseManager` *(exists but bootstrap not yet implemented)*
- **DataService**: Orchestrates bootstrap operations

**Benefits of New Approach**:
- Clear separation of concerns
- Testable components in isolation
- Consistent patterns across all data types
- Centralized orchestration logic

---

## CLI Integration

**Status**: CLI commands will be wired to DataService bootstrap methods in a future update.

**Planned Commands**:
```bash
# Individual bootstrap operations
tradescout database bootstrap-providers
tradescout database bootstrap-markets
tradescout database bootstrap-assets [--limit N]
tradescout database bootstrap-fundamentals [--limit N]
tradescout database bootstrap-universes

# Full bootstrap sequence (respects dependencies)
tradescout database bootstrap-all
```

**Current Status**:
- Old CLI commands exist in `src/cli/database_commands.py`
- Old commands call legacy bootstrapper classes
- Need migration to call DataService methods instead

---

## Complete Bootstrap Example

```python
from database.database_manager import DatabaseManager
from services.data_update_tracker import DataUpdateTracker
from services.data_service import DataService
import os

# Initialize components
db_manager = DatabaseManager("tradescout.db")
update_tracker = DataUpdateTracker(None)  # Will be initialized by DataService
polygon_api_key = os.getenv("POLYGON_API_KEY")

data_service = DataService(db_manager, update_tracker, polygon_api_key)

# Bootstrap sequence (respects dependencies)
print("1. Bootstrapping providers...")
providers_count = data_service.bootstrap_providers()
print(f"   ✓ {providers_count} provider(s) configured")

print("2. Bootstrapping markets...")
markets_count = data_service.bootstrap_markets(asset_class="stocks", locale="us")
print(f"   ✓ {markets_count} market(s) stored")

print("3. Bootstrapping assets...")
assets_count = data_service.bootstrap_assets(market="stocks", active=True)
print(f"   ✓ {assets_count} asset(s) stored")

print("4. Bootstrapping fundamentals (first 100)...")
fundamentals_count = data_service.bootstrap_fundamentals(limit=100)
print(f"   ✓ {fundamentals_count} fundamentals record(s) stored")

print("5. Bootstrapping universes...")
# universes_count = data_service.bootstrap_universes()  # NOT YET IMPLEMENTED
# print(f"   ✓ {universes_count} universe(s) created")

print("\nBootstrap complete!")
```

---

## Next Steps

1. **Implement Universe Bootstrap**: Migrate `UniverseBootstrapper` logic to `DataService.bootstrap_universes()`
2. **Update CLI Commands**: Wire database commands to call DataService methods
3. **Add Progress Callbacks**: Support progress reporting for long-running operations
4. **Add Force Refresh**: Implement `force_refresh` parameter to bypass TTL checks
5. **Error Handling**: Improve error messages and recovery strategies

---

## Reference

- **Architecture Docs**: `docs/ARCHITECTURE_MANAGERS.md`, `docs/ARCHITECTURE_API_PROVIDERS.md`
- **DataService**: `src/services/data_service.py`
- **Managers**: `src/database/managers/`
- **Providers**: `src/api/provider/`
- **Legacy Bootstrappers**: `src/bootstrapping/` *(to be deprecated)*
