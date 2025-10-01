# Database Managers Architecture

## Overview

TradeScout uses a three-layer architecture to separate concerns between business logic, data storage, and external API calls:

```
┌─────────────────────────────────────────────────────────────┐
│                      DataService Layer                       │
│              (Orchestration & Business Logic)                │
└──────────────────┬────────────────────┬─────────────────────┘
                   │                    │
         ┌─────────▼────────┐  ┌────────▼─────────┐
         │  Database Layer  │  │   API Layer      │
         │   (Managers)     │  │  (Providers)     │
         └─────────┬────────┘  └────────┬─────────┘
                   │                    │
         ┌─────────▼────────┐  ┌────────▼─────────┐
         │  SQLite Database │  │  External APIs   │
         │  (asset_prices,  │  │  (Polygon, etc)  │
         │   data_update_   │  │                  │
         │   metadata)      │  │                  │
         └──────────────────┘  └──────────────────┘
```

## Core Concepts

### Models (Business Entities)

Models are **immutable dataclasses** that represent business entities:
- `TickerSnapshot` - Real-time snapshot of a single stock
- `MarketSnapshot` - Collection of multiple ticker snapshots
- `MinuteBar` - One-minute price bar data
- `DataUpdateMetadataType` - Enum for operation types

**Location**: `src/models/`

**Characteristics**:
- Immutable (`@dataclass(frozen=True)`)
- Type-safe (all fields typed with Python type hints)
- Business logic only (no database or API awareness)
- Used throughout all layers

### Database Managers

Managers handle **persistence, retrieval, and TTL-based staleness checking**:

**Responsibilities**:
- Store entities to database tables
- Retrieve entities from database tables
- Check if cached data is stale (TTL validation)
- Record metadata timestamps for staleness tracking
- Coordinate with DataService for cache-or-fetch decisions

**What managers do NOT do**:
- Make API calls (that's the provider's job)
- Contain business logic (that's the service layer's job)
- Handle authentication or rate limiting (that's the provider's job)

**Location**: `src/database/managers/`

**Key Components**:
- `BaseManager` - Abstract base class with TTL logic
- `TickerSnapshotManager` - Manages ticker snapshots in `asset_prices` table
- `MarketSnapshotManager` - **SPECIAL**: Metadata-only tracking (see below)
- `DataUpdateMetadataManager` - Tracks operation timestamps for TTL validation

### API Providers

Providers handle **external API communication**:

**Responsibilities**:
- Make HTTP requests to external APIs
- Handle authentication (API keys, tokens)
- Handle rate limiting and retries
- Parse API responses into model objects
- Handle API errors gracefully

**What providers do NOT do**:
- Store data to database (that's the manager's job)
- Make caching decisions (that's the manager/service job)
- Implement TTL logic (that's the manager's job)

**Location**: `src/api/provider/`

**Key Components**:
- `BaseAPIProvider` - Abstract base with HTTP request handling
- `PolygonSnapshotProvider` - Polygon.io snapshot API implementation

### DataService (Orchestration)

The service layer **coordinates between managers and providers**:

**Responsibilities**:
- Initialize managers and providers with dependencies
- Provide clean public API for business logic
- Coordinate cache-or-fetch decisions
- Handle bulk operations (e.g., store individual tickers from bulk fetch)
- Expose statistics and health check methods

**Location**: `src/services/data_service.py`

## Data Flow Example

### Single Ticker Fetch

```
1. User calls: data_service.get_ticker_snapshot("AAPL")

2. DataService delegates to TickerSnapshotManager.get_or_fetch()

3. Manager checks metadata: Is cached data stale?

   IF FRESH (within TTL):
   → Manager reads from asset_prices table
   → Returns cached TickerSnapshot

   IF STALE (beyond TTL):
   → Manager calls fetch_fn (provided by DataService)
   → DataService calls PolygonSnapshotProvider.fetch_single_ticker_snapshot()
   → Provider makes API call to Polygon
   → Provider parses response into TickerSnapshot model
   → Manager stores TickerSnapshot to asset_prices table
   → Manager records metadata timestamp
   → Returns fresh TickerSnapshot

4. DataService returns TickerSnapshot to user
```

### Force Refresh

```
1. User calls: data_service.get_ticker_snapshot("AAPL", force_refresh=True)

2. Manager SKIPS TTL check entirely

3. Manager always calls fetch_fn → API call → Store → Return fresh data
```

## TTL (Time-To-Live) Management

### How TTL Works

Each data type has a configured TTL (e.g., 15 minutes for snapshots):

```python
# src/database/config/ttl_config.py
TICKER_SNAPSHOT_TTL_MINUTES = 15
MARKET_SNAPSHOT_TTL_MINUTES = 15
```

**Metadata Tracking**:
- `DataUpdateMetadataManager` stores timestamps in `data_update_metadata` table
- Each operation type (e.g., `TICKER_SNAPSHOTS`, `MARKET_SNAPSHOTS`) has its own timestamp
- Managers check: `current_time - last_update_time > TTL ?`

**Benefits**:
- Reduces API calls (respect rate limits)
- Improves performance (serve from cache when fresh)
- Configurable per data type
- Force refresh available when needed

## Standard Manager Pattern

Most managers follow this pattern:

```python
class TickerSnapshotManager(BaseManager):
    """Standard entity manager - stores and retrieves entities."""

    def get_entity_from_database(self, key: str) -> Optional[TickerSnapshot]:
        """Read entity from database table."""
        # SELECT from asset_prices WHERE symbol = key
        # Parse row into TickerSnapshot model
        return ticker_snapshot

    def set_entity_to_database(self, key: str, entity: TickerSnapshot) -> bool:
        """Write entity to database table."""
        # INSERT OR REPLACE into asset_prices
        return success

    def get_or_fetch(self, key: str, fetch_fn, force_refresh: bool):
        """Inherited from BaseManager - handles TTL logic."""
        # Check TTL → Read from DB OR Call fetch_fn → Store → Return
```

**Standard managers**:
1. Store entities to database
2. Retrieve entities from database
3. Use TTL to decide when to refresh
4. Return actual entity data to caller

---

## ⚠️ SPECIAL CASE: MarketSnapshotManager

### Why MarketSnapshotManager is Different

`MarketSnapshotManager` is **NOT a standard entity manager**. It is a **metadata-only manager** used to track bulk refresh operations.

### What Makes It Special

**It does NOT**:
- Store `MarketSnapshot` entities to the database
- Retrieve `MarketSnapshot` entities from the database
- Cache snapshot data anywhere

**It ONLY**:
- Tracks WHEN bulk market data refreshes occur (metadata timestamps)
- Controls refresh frequency via TTL (prevents excessive bulk API calls)
- Coordinates data flow from API → Individual entity storage

### Why This Design?

**Problem**: Bulk market snapshots contain thousands of tickers. We need to:
1. Fetch all tickers efficiently (single bulk API call)
2. Store each ticker individually (for single-ticker queries)
3. Prevent excessive bulk API calls (TTL-based refresh control)
4. Support both bulk refresh AND individual ticker access

**Solution**: Separate concerns:
- **Bulk refresh cadence** (tracked by MarketSnapshotManager metadata)
- **Individual ticker storage** (handled by TickerSnapshotManager)
- **Individual ticker TTL** (each ticker has its own freshness)

### Data Flow: Bulk Market Refresh

```
1. User calls: data_service.refresh_market_data(symbols=["AAPL", "MSFT", ...])

2. DataService delegates to MarketSnapshotManager.get_or_fetch()

3. Manager checks metadata: Was bulk refresh done recently?

   IF RECENTLY REFRESHED (within 15min TTL):
   → Manager returns None (skips API call to respect rate limits)
   → User should read individual tickers via get_ticker_snapshot()

   IF STALE (beyond 15min TTL):
   → Manager calls fetch_fn
   → Provider fetches bulk snapshot (thousands of tickers in one API call)
   → Provider returns MarketSnapshot object
   → Manager records metadata timestamp (bulk refresh occurred at X time)
   → Manager returns MarketSnapshot to DataService
   → DataService iterates through all tickers in snapshot
   → DataService stores EACH ticker to asset_prices via TickerSnapshotManager
   → Returns MarketSnapshot to user

4. Result:
   - Bulk refresh metadata updated (prevents another bulk call for 15min)
   - All individual tickers stored to asset_prices (available for single queries)
   - Each individual ticker now has its own TTL (15min from this refresh)
```

### Code Example

```python
# MarketSnapshotManager - Metadata only
def get_entity_from_database(self, key: str) -> Optional[MarketSnapshot]:
    """Always returns None - entities are not stored."""
    return None

def set_entity_to_database(self, key: str, entity: MarketSnapshot) -> bool:
    """Does NOT store entity - just logs metadata."""
    logger.debug(f"Bulk refresh completed with {entity.total_symbols} symbols")
    return True  # Metadata tracking only

def get_or_fetch(self, key: str, fetch_fn, force_refresh: bool):
    """Override: Returns None if data is fresh (within TTL)."""
    if not force_refresh and not self._is_data_stale():
        logger.info("Bulk refresh done recently, skipping API call")
        return None  # Skip refresh

    # TTL expired - fetch and record metadata
    market_snapshot = fetch_fn()
    self._record_update()  # Record bulk refresh timestamp
    return market_snapshot
```

### Usage Recommendations

**For bulk refresh operations**:
```python
# Refresh all market data (respects TTL)
market_snapshot = data_service.refresh_market_data()

if market_snapshot:
    # Refresh happened - data was stale
    print(f"Refreshed {market_snapshot.total_symbols} tickers")
else:
    # Refresh skipped - data is fresh (bulk refresh done recently)
    print("Market data is fresh, skipping refresh")
```

**For reading individual ticker data**:
```python
# Always use get_ticker_snapshot() to read individual tickers
ticker = data_service.get_ticker_snapshot("AAPL")

# This reads from asset_prices table (populated by bulk refresh)
# Each ticker has its own TTL independent of bulk refresh timing
```

### Key Takeaway

`MarketSnapshotManager` is a **coordination manager**, not an entity manager:
- Coordinates bulk API operations (timing control)
- Tracks metadata only (timestamps, not data)
- Enables separation between bulk refresh cadence and individual ticker access patterns

This pattern allows:
- Efficient bulk API calls (fetch thousands at once)
- Individual ticker caching (each has its own TTL)
- Rate limit protection (prevent excessive bulk calls)
- Flexible access patterns (bulk refresh + individual queries)

---

## Summary

| Component | Responsibility | Example |
|-----------|---------------|---------|
| **Models** | Immutable business entities | `TickerSnapshot`, `MarketSnapshot` |
| **Managers** | Database persistence + TTL logic | `TickerSnapshotManager` |
| **Providers** | External API communication | `PolygonSnapshotProvider` |
| **DataService** | Orchestration & coordination | `data_service.get_ticker_snapshot()` |

**Special Case**: `MarketSnapshotManager` tracks metadata only, does not persist/retrieve entities like other managers.