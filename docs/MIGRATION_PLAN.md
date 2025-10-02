# CLI Architecture Migration Plan: Old data_provider.py → New data_service.py

**Last Updated:** 2025-10-01
**Status:** Planning Phase

## Overview

Migrate all CLI commands from legacy `PolygonDataProvider` (backup/provider/data_provider.py) to new `DataService` architecture (src/services/data_service.py). Maintain identical CLI command interface - users should see no breaking changes.

---

## Files to Modify (7 CLI files + 2 supporting services)

### Core CLI Files:
1. **src/cli/main.py** - Config class data provider initialization
2. **src/cli/asset_commands.py** - Asset info and local commands
3. **src/cli/market_commands.py** - Market updates and info
4. **src/cli/gap_commands.py** - Gap analysis
5. **src/cli/screener_commands.py** - Screener execution
6. **src/cli/universe_commands.py** - Universe management
7. **src/cli/database_commands.py** - Database operations

### Supporting Services (need compatibility updates):
8. **src/services/market_context_service.py** - Market context logic
9. **src/screener/screener_engine.py** - Screener query execution

---

## Method Mapping: Old → New

### ✅ Already Implemented in DataService:

- `get_asset()` → Already exists (force_refresh param)
- `get_fundamentals()` → Already exists
- `get_market()` → Already exists
- `get_all_markets()` → Already exists
- `get_market_holidays()` → Already exists
- `get_upcoming_holidays()` → Already exists
- `get_market_context()` → Already exists
- `get_all_universes()` → Already exists (via universe_manager)
- `get_active_universe()` → Already exists
- `set_active_universe()` → Already exists
- `bootstrap_*()` methods → All exist

### ❌ Missing in DataService (NEED TO ADD):

#### Snapshot Operations:
- `get_market_snapshot()` - Bulk snapshot fetching with progress callback
- `get_single_ticker_snapshot()` - Single ticker snapshot
- `get_ticker_snapshot()` - Alias or similar method
- `refresh_market_data()` - Market data update orchestration

#### Asset Price Operations:
- `get_latest_asset_price(asset_id)` - Get most recent price from DB
- `get_asset_price_data(asset_id)` - Get price with possible refresh
- `save_asset_price_data(asset_price)` - Save price to DB
- `transform_ticker_snapshot_to_asset_price()` - Convert snapshot to price model

#### Snapshot Metadata:
- `get_market_snapshot_metadata()` - Last snapshot run info
- `start_market_snapshot_run()` - Begin tracking snapshot operation
- `complete_market_snapshot_run()` - Finish tracking snapshot operation

#### Universe Operations:
- `get_active_universe_symbols()` - Get symbols in active universe
- `get_universe_stats(name)` - Universe statistics
- `get_universe_market_breakdown(name)` - Assets by market
- `create_universe()` - Create new universe
- `delete_universe()` - Delete universe

#### Market Operations:
- `get_market_by_code(code)` - Get market by exchange code
- `get_active_markets_by_codes(codes)` - Get multiple markets
- `get_current_market_session()` - Current session name

#### Screener Operations:
- `execute_screener_query(sql)` - Run raw SQL screener query

#### Market Context Cache:
- `get_cached_market_context()` - Cached context retrieval
- `store_market_context()` - Store context to cache

---

## Migration Steps

### Phase 1: Add Missing Methods to DataService (PRIORITY)

#### Step 1.1: Snapshot Operations

Add to DataService:

```python
def get_ticker_snapshot(self, symbol: str, force_refresh: bool = False) -> Optional[TickerSnapshot]:
    """Get single ticker snapshot (maps to old get_single_ticker_snapshot)."""
    # Delegate to ticker_snapshot_manager + polygon_snapshot_provider

def refresh_market_data(self, symbols: List[str], progress_callback=None) -> MarketSnapshot:
    """Bulk market data refresh (maps to old get_market_snapshot)."""
    # Delegate to market_snapshot_manager + polygon_snapshot_provider
```

#### Step 1.2: Asset Price Operations

Add to DataService (or delegate to managers):

```python
def get_latest_asset_price(self, asset_id: int) -> Optional[AssetPrice]:
    """Get most recent asset price from database."""
    # Delegate to appropriate manager

def save_asset_price_data(self, asset_price: AssetPrice) -> bool:
    """Save asset price to database."""
    # Delegate to appropriate manager

def transform_ticker_snapshot_to_asset_price(...) -> Optional[AssetPrice]:
    """Transform TickerSnapshot model to AssetPrice model."""
    # Utility method for data transformation
```

#### Step 1.3: Snapshot Metadata

Add to DataService (delegate to metadata_manager):

```python
def get_market_snapshot_metadata(self) -> Optional[Dict]:
    """Get metadata about last market snapshot run."""

def start_market_snapshot_run(self, total: int) -> str:
    """Start tracking a market snapshot operation."""

def complete_market_snapshot_run(self, op_id: str, successful: int, failed: int, ...):
    """Complete tracking a market snapshot operation."""
```

#### Step 1.4: Universe Operations

Add to DataService (delegate to universe_manager):

```python
def get_active_universe_symbols(self) -> List[str]:
    """Get all symbols in active universe."""

def get_universe_stats(self, name: str) -> UniverseStats:
    """Get statistics for a universe."""

def get_universe_market_breakdown(self, name: str) -> List[Tuple[str, str, int]]:
    """Get asset distribution by market for a universe."""

def create_universe(self, name: str, description: str = None, ...) -> bool:
    """Create a new universe."""

def delete_universe(self, name: str) -> Tuple[bool, int]:
    """Delete a universe and return success status and deleted count."""
```

#### Step 1.5: Market Operations

Add to DataService:

```python
def get_market_by_code(self, code: str) -> Optional[Market]:
    """Get market by exchange code (e.g., 'XNYS')."""

def get_active_markets_by_codes(self, codes: List[str]) -> List[Tuple[str, str]]:
    """Get multiple markets by codes, return (code, name) tuples."""

def get_current_market_session(self) -> str:
    """Get current market session name."""
    # Return: 'premarket', 'regular', 'afterhours', or 'closed'
```

#### Step 1.6: Screener Support

Add to DataService:

```python
def execute_screener_query(self, sql: str) -> List[Dict]:
    """Execute raw SQL query for screeners."""
    # Execute SQL and return results as list of dicts
```

---

### Phase 2: Update CLI Files (ALL IN PARALLEL)

For **EACH** CLI file, make identical changes:

#### Step 2.1: Update imports

```python
# OLD:
from provider.data_provider import PolygonDataProvider

# NEW:
from services.data_service import DataService
from api.config.api_keys import POLYGON_API_KEY
```

#### Step 2.2: Update initialization

```python
# OLD:
data_provider = PolygonDataProvider(db_manager)

# NEW:
data_service = DataService(db_manager, POLYGON_API_KEY)
```

#### Step 2.3: Rename all variable references

Change ALL occurrences:
```python
data_provider → data_service
```

#### Files to update:

- [ ] **main.py** - Config class methods (`get_data_provider()`, `get_market_context_service()`)
- [ ] **asset_commands.py** - All command functions (`local`, `info`)
- [ ] **market_commands.py** - All command functions (`info`, `update`, `context`, `session`)
- [ ] **gap_commands.py** - All command functions (`analyze`, etc.)
- [ ] **screener_commands.py** - `screener()` command
- [ ] **universe_commands.py** - All command functions (`list`, `info`, `activate`, etc.)
- [ ] **database_commands.py** - Database bootstrap operations

---

### Phase 3: Update Supporting Services

#### Step 3.1: MarketContextService

- Already designed to accept any data_provider via dependency injection
- Just pass DataService instance instead of PolygonDataProvider
- Verify method signatures match:
  - `get_market_status()`
  - `get_market_holidays()`
  - `get_cached_market_context()` (if using cache)

#### Step 3.2: ScreenerEngine

- Already designed to accept any data_provider via dependency injection
- Just pass DataService instance instead of PolygonDataProvider
- Verify these methods work:
  - `execute_screener_query(sql)`
  - `get_current_market_session()`

---

### Phase 4: Testing & Validation

Test each command group:

#### Asset Commands
```bash
tradescout asset local AAPL
tradescout asset info AAPL
```

#### Market Commands
```bash
tradescout market info
tradescout market update
tradescout market context
tradescout market session
```

#### Screener Commands
```bash
tradescout screener --list
tradescout screener gainers
tradescout screener losers
```

#### Universe Commands
```bash
tradescout universe list
tradescout universe info
tradescout universe current
tradescout universe activate default_universe
```

#### Gap Commands
```bash
tradescout gap analyze AAPL MSFT
tradescout gap candidates --direction up
```

#### Database Commands
```bash
tradescout database info
tradescout database init
```

---

## Implementation Order

1. **First:** Add all missing methods to DataService (Phase 1) - this is the foundation
2. **Second:** Update main.py Config class (critical for all other commands)
3. **Third:** Update all CLI command files in parallel (Phase 2)
4. **Fourth:** Update MarketContextService and ScreenerEngine (Phase 3)
5. **Finally:** Run full test suite and validate all commands work (Phase 4)

---

## Rollback Plan

If issues arise:

- Old provider is preserved in `backup/provider/data_provider.py`
- Can revert imports to point back to backup temporarily
- No data loss risk - only changing code, not database
- Git commit before migration allows easy rollback

---

## Success Criteria

- [ ] All CLI commands work identically to before
- [ ] No references to `provider.data_provider` or `PolygonDataProvider` in CLI code
- [ ] All references use `services.data_service` and `DataService`
- [ ] All tests pass
- [ ] No breaking changes for end users
- [ ] Legacy code remains in backup/ for reference

---

## Notes

- **Do NOT touch backup/** directory files - these are for reference only
- CLI command INTERFACE stays identical (no breaking changes for users)
- All business logic moves from old PolygonDataProvider → new DataService
- MarketContextService and ScreenerEngine are adapter-pattern compatible
- Database schema unchanged - only code layer migration
- New architecture uses Manager/Provider pattern with TTL-based caching
