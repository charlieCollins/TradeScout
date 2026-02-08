# TradeScout Architecture

**Purpose:** Technical architecture reference for TradeScout's repository-based architecture
**Last Updated:** 2025-10-12

---

## High-Level Architecture

TradeScout uses a **layered repository architecture** with clean separation of concerns:

```
┌──────────────────────────────────────────────────────┐
│             CLI Layer (src/cli/)                     │
│         User commands → Service calls                │
└─────────────────────┬────────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────────┐
│        Service Layer (src/services/)                 │
│     Business logic, orchestration, workflows         │
│     - DataServiceV2 (main orchestrator)              │
│     - MarketContextService (market state)            │
│     - CacheService (cache-aside pattern)             │
└──────────┬─────────────────────┬─────────────────────┘
           │                     │
    ┌──────▼────────┐     ┌──────▼────────────┐
    │  Repositories │     │  API Providers     │
    │  (src/        │     │  (src/api/         │
    │  repositories/)│    │  providers/)       │
    │               │     │                    │
    │  Business     │     │  HTTP/JSON         │
    │  Queries      │     │  transformations   │
    └──────┬───────┘      └──────┬─────────────┘
           │                     │
   ┌───────▼──────┐      ┌──────▼──────────┐
   │ SQLModel ORM │      │ External APIs   │
   │ (models/     │      │ (yfinance, etc) │
   │ sqlmodel/)   │      │                 │
   │              │      │                 │
   │ Table defs   │      │                 │
   └──────┬───────┘      └─────────────────┘
          │
   ┌──────▼──────┐
   │ SQLite DB   │
   │ (data/*.db) │
   └─────────────┘
```

---

## Dual Model System

TradeScout maintains **two parallel model systems** for clean separation:

### Domain Models (Dataclasses)
**Location:** `src/models/dataclass/`

**Purpose:** Lightweight, immutable business entities for data transfer

**Characteristics:**
```python
@dataclass(frozen=True)  # Immutable
class Asset:
    id: int
    symbol: str
    name: str
    asset_type: AssetType  # Enum
    market_id: int
    is_active: bool
    created_at: datetime
```

**Used By:**
- API Providers (return domain models)
- Services (business logic operations)
- Analysis modules
- CLI display logic

**Key Models:**
- `Asset` - Stock/ticker details
- `Market` - Exchange/market info
- `AssetFundamentals` - Company fundamentals
- `Provider` - Data provider metadata
- `MarketHoliday` - Holiday calendar
- `FedData` - Economic indicators
- `SentimentEvent` - News/sentiment
- `AssetPrice` - Price snapshots
- `GapCandidate` - Gap trading opportunities
- `MarketContext` - Market session state

### ORM Models (SQLModel)
**Location:** `src/models/sqlmodel/`

**Purpose:** Database table definitions with ORM features

**Characteristics:**
```python
class AssetSQLModel(SQLModel, table=True):
    __tablename__ = "assets"

    id: Optional[int] = Field(default=None, primary_key=True)
    symbol: str = Field(unique=True, index=True)
    name: Optional[str] = None
    asset_type: str  # Stored as string
    market_id: int = Field(foreign_key="markets.id")
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
```

**Used By:**
- Repositories (database operations only)
- Database migrations
- SQLModel metadata operations

**Key Models:**
- `AssetSQLModel` - assets table
- `MarketSQLModel` - markets table
- `FundamentalsSQLModel` - fundamentals table
- `ProviderSQLModel` - providers table
- `UniverseSQLModel` - universes table
- `AssetPriceSQLModel` - asset_prices table
- `DataUpdateMetadataSQLModel` - TTL tracking
- `SentimentEventSQLModel` - sentiment_events table
- `FedDataSQLModel` - fed_data table
- `MarketHolidaySQLModel` - market_holidays table

### Model Import Conventions

```python
# Domain models - for business logic
from models.dataclass.asset import Asset, AssetType, AssetClass

# ORM models - for database operations
from models.sqlmodel.asset_sqlmodel import AssetSQLModel

# Backward compatibility - exports domain models from root
from models import Asset, AssetType, AssetClass
```

---

## Layer 1: API Providers

**Location:** `src/api/providers/`

**Purpose:** Fetch data from external APIs, return domain models

**Base Class:**
```python
class BaseAPIProvider(ABC):
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url

    @abstractmethod
    def _add_authentication(self, params: Dict) -> Dict:
        """Add API key/auth to request params"""

    def _make_request(self, endpoint: str, params: Dict) -> Dict:
        """Make HTTP request with retry logic, rate limiting"""
```

**Active Providers (Free by Default):**

| Provider | Purpose | Returns |
|----------|---------|---------|
| `YFinanceSnapshotAdapter` | Real-time snapshots | `TickerSnapshot` domain models |
| `YFinanceAggregatesAdapter` | Historical OHLC | `AssetPrice` domain models |
| `FreeReferenceAdapter` | Ticker listing + details | `Asset` domain models |
| `FinnhubNewsAdapter` | News/sentiment | `SentimentEvent` domain models |
| `PandasMarketCalendarAdapter` | Market status/holidays | `MarketHoliday` domain models |
| `FREDEconomicAdapter` | Economic data | `FedData` domain models |

**Provider Responsibilities:**
- ✅ HTTP communication with external APIs
- ✅ Authentication (API keys, OAuth)
- ✅ Rate limit handling (HTTP 429 backoff)
- ✅ JSON parsing → Domain model transformation
- ✅ Retry logic with exponential backoff
- ❌ NO database writes
- ❌ NO caching/TTL logic
- ❌ NO business logic

---

## Layer 2: Repositories

**Location:** `src/repositories/`

**Purpose:** Business-focused data access wrapping ORM layer

### What is a Repository?

A **repository** is a business-focused data access layer that translates domain questions into database queries. It sits between the service layer (DataServiceV2) and the database (SQLModel).

### Why Repositories Exist

#### 1. SQLModel is TOO LOW-LEVEL for Business Logic

SQLModel directly maps to database tables:

```python
# models/sqlmodel/asset_sqlmodel.py - This is JUST a table representation
class AssetSQLModel(SQLModel, table=True):
    __tablename__ = "assets"
    id: Optional[int] = Field(default=None, primary_key=True)
    symbol: str
    name: str
    # ... just fields, no behavior
```

This gives you basic CRUD operations:
- `session.get(AssetSQLModel, id)` - get by primary key
- `session.add(asset)` - insert
- `session.query(AssetSQLModel).all()` - select all

But your business logic needs to ask questions like:
- **"Give me all ACTIVE assets"**
- **"Find assets by market"**
- **"Get an asset WITH its market data (join)"**
- **"Search by symbol prefix"**

These are **domain operations**, not just table operations.

#### 2. Repositories Translate Business Questions to SQL

Example from `repositories/asset_repository.py`:

```python
def find_all_active(self, limit: Optional[int] = None) -> List[AssetSQLModel]:
    """Get all active assets from database.

    Business query: Core operation for trading systems.
    """
    statement = select(AssetSQLModel).where(
        AssetSQLModel.is_active == True
    ).order_by(AssetSQLModel.symbol)

    if limit:
        statement = statement.limit(limit)

    return list(self.session.exec(statement).all())
```

**Business question:** "Give me active assets"
**Repository translates to:** `SELECT * FROM assets WHERE is_active = true ORDER BY symbol`

#### 3. Joins and Complex Queries

Example join query from `asset_repository.py`:

```python
def get_by_symbol_with_market(
    self, symbol: str
) -> Optional[tuple[AssetSQLModel, MarketSQLModel]]:
    """Get asset with its associated market (join query).

    Business query: Need asset + market data together.
    """
    from models.sqlmodel.market_sqlmodel import MarketSQLModel

    statement = select(AssetSQLModel, MarketSQLModel).join(
        MarketSQLModel,
        AssetSQLModel.market_id == MarketSQLModel.id
    ).where(
        AssetSQLModel.symbol == symbol.upper(),
        AssetSQLModel.is_active == True
    )

    result = self.session.exec(statement).first()
    return result if result else None
```

**Business question:** "Give me AAPL with its exchange info"
**Repository translates to:** `SELECT * FROM assets JOIN markets ON assets.market_id = markets.id WHERE symbol = 'AAPL'`

**Without repository**, DataServiceV2 would have to write this SQL logic directly. That's messy and error-prone.

#### 4. Aggregations and Statistics

Example from `asset_repository.py`:

```python
def get_stats(self) -> dict:
    """Get asset repository statistics.

    Business query: Dashboard/monitoring needs.
    """
    from sqlmodel import func

    total_assets = self.count_active()

    # Count by asset type
    statement = select(
        AssetSQLModel.asset_type,
        func.count(AssetSQLModel.id).label('count')
    ).where(
        AssetSQLModel.is_active == True
    ).group_by(AssetSQLModel.asset_type)

    results = self.session.exec(statement).all()
    by_type = {asset_type: count for asset_type, count in results}

    return {
        "total_assets": total_assets,
        "by_type": by_type
    }
```

**Business question:** "Show me asset statistics"
**Repository aggregates:** Multiple queries + calculations + formatting

SQLModel doesn't have a `get_stats()` method - that's **domain logic**, not table logic.

### Repository Principles

#### ✅ Repository Speaks Domain Language

```python
# BAD - Service layer doing SQL directly
assets = session.exec(
    select(AssetSQLModel).where(AssetSQLModel.is_active == True)
).all()

# GOOD - Repository speaks business language
assets = asset_repository.find_all_active()
```

The service layer should never write raw SQL queries. It should ask repositories for what it needs in business terms.

#### ✅ Repository Has Single Responsibility

Each repository manages ONE entity:
- `AssetRepository` → assets table business operations
- `MarketRepository` → markets table business operations
- `FundamentalsRepository` → fundamentals table business operations
- `UniverseRepository` → universes + memberships tables

But they can **join** with other tables when needed for business queries.

#### ✅ Repository Enables Testing

```python
# You can mock repositories in tests
mock_repo = Mock(AssetRepository)
mock_repo.find_all_active.return_value = [test_asset1, test_asset2]

# Can't easily mock raw SQLModel session queries
```

#### ✅ Repository Promotes Reuse

Complex query from `universe_repository.py`:

```python
def get_assets_with_fundamentals(self) -> List[Dict[str, Any]]:
    """Complex join query used by universe filtering.

    Business query: "Give me all assets WITH their fundamental data"
    """
    statement = select(
        AssetSQLModel.id,
        AssetSQLModel.symbol,
        AssetSQLModel.name,
        AssetSQLModel.asset_type,
        FundamentalsSQLModel.sector,
        FundamentalsSQLModel.market_cap,
        MarketSQLModel.code.label("market_code")
    ).join(
        FundamentalsSQLModel,
        # complex join logic
    ).join(
        MarketSQLModel,
        # more join logic
    )

    # Returns dict format for filtering
    return [dict(row._mapping) for row in results]
```

This **complex multi-table join** is used by:
- `bootstrap_universes()` - universe filtering
- Potentially other operations needing enriched asset data

**Without repository:** This SQL would be duplicated everywhere you need it.

### Repository Structure

#### Standard Methods

Every repository should have:

**Query Methods:**
```python
def get_by_id(self, id: int) -> Optional[T]          # Single record by ID
def get_by_[field](self, value) -> Optional[T]       # Single record by field
def find_all() -> List[T]                             # All records
def find_by_[criteria]() -> List[T]                   # Filtered records
```

**Persistence Methods:**
```python
def save(self, entity: T) -> T                        # Insert/update single
def bulk_save(self, entities: List[T]) -> int         # Insert/update many
def delete(self, entity: T) -> None                   # Delete single
```

**Statistics Methods:**
```python
def count_all() -> int                                # Total count
def count_by_[criteria]() -> int                      # Conditional count
def get_stats() -> dict                               # Aggregated statistics
```

### Existing Repositories

| Repository | Entity | Business Queries |
|------------|--------|------------------|
| `AssetRepository` | `AssetSQLModel` | get_by_symbol, find_all_active, search |
| `MarketRepository` | `MarketSQLModel` | get_by_code, find_all_active |
| `FundamentalsRepository` | `FundamentalsSQLModel` | get_by_asset_id, bulk_upsert |
| `ProviderRepository` | `ProviderSQLModel` | get_by_name, get_active_provider |
| `UniverseRepository` | `UniverseSQLModel` | get_by_name, bulk_add_memberships, get_statistics |
| `AssetPriceRepository` | `AssetPriceSQLModel` | get_latest_by_asset_id, bulk_save |
| `DataUpdateMetadataRepository` | `DataUpdateMetadataSQLModel` | get_latest_by_operation, record_update |
| `SentimentEventRepository` | `SentimentEventSQLModel` | find_recent_by_asset, bulk_save |
| `SentimentTypeRepository` | `SentimentTypeSQLModel` | get_by_name, find_all_active |
| `FedDataRepository` | `FedDataSQLModel` | get_latest_by_type, find_by_date_range |
| `MarketHolidayRepository` | `MarketHolidaySQLModel` | find_upcoming, clear_all |

**Repository Responsibilities:**
- ✅ Business-focused query methods
- ✅ CRUD operations on SQLModel entities
- ✅ Type-safe SQLModel queries
- ✅ Bulk operations for efficiency
- ✅ Transaction management
- ❌ NO API calls
- ❌ NO business logic (workflows, validation)
- ❌ NO TTL/caching logic

---

## Layer 3: Cache Service

**Location:** `src/services/cache_service.py`

**Purpose:** Generic cache-aside pattern with TTL tracking

**Pattern:**
```python
class CacheService[T]:
    """Cache-aside pattern for any entity type."""

    def __init__(
        self,
        repository: Any,  # Repository with get/save methods
        metadata_repository: DataUpdateMetadataRepository,
        metadata_type: DataUpdateMetadataType,
        ttl_seconds: int
    ):
        self.repository = repository
        self.metadata_repository = metadata_repository
        self.metadata_type = metadata_type
        self.ttl_seconds = ttl_seconds

    def get_or_fetch(
        self,
        key: str,
        fetch_fn: Callable[[], Optional[T]],
        force_refresh: bool = False
    ) -> Optional[T]:
        """Cache-aside: Get from DB if fresh, else fetch and store."""

        # Check freshness
        if not force_refresh and self._is_fresh():
            cached = self.repository.get(key)
            if cached:
                return cached

        # Fetch fresh data
        fresh_data = fetch_fn()
        if fresh_data:
            # Store to cache
            self.repository.save(fresh_data)
            # Update TTL metadata
            self.metadata_repository.record_update(
                self.metadata_type.value
            )

        return fresh_data
```

**TTL Configuration:**
**File:** `configs/database_ttl.yaml`

```yaml
# Asset metadata (rarely changes)
asset_ttl_days: 7
fundamentals_ttl_days: 7

# Market data (changes frequently)
snapshot_ttl_minutes: 5
asset_price_ttl_minutes: 5

# News & sentiment
news_ttl_minutes: 30

# Economic data
fed_data_ttl_hours: 12

# Reference data (very stable)
markets_ttl_days: 7
market_holidays_ttl_days: 30
```

**Cache Service Benefits:**
- Generic (works with any entity type)
- Configurable TTL per entity
- Automatic metadata tracking
- Reduces API calls 90%+
- No external cache needed (Redis, etc.)

---

## Layer 4: Data Service V2 (Orchestration)

**Location:** `src/services/data_service_v2.py`

**Purpose:** Orchestrate repositories + providers + caches for business workflows

**Architecture:**
```python
class DataServiceV2:
    """Main orchestration service using repository pattern."""

    def __init__(self, session: Session):
        # Initialize repositories
        self.asset_repository = AssetRepository(session)
        self.market_repository = MarketRepository(session)
        self.fundamentals_repository = FundamentalsRepository(session)
        self.metadata_repository = DataUpdateMetadataRepository(session)
        # ... more repositories

        # Initialize providers via factory (reads configs/providers.yaml)
        self.snapshot_provider = ProviderFactory.create_snapshot_provider()
        self.aggregates_provider = ProviderFactory.create_aggregates_provider()
        # ... more providers

        # Initialize caches
        self.asset_cache = CacheService[AssetSQLModel](
            repository=self.asset_repository,
            metadata_repository=self.metadata_repository,
            metadata_type=DataUpdateMetadataType.TICKERS,
            ttl_seconds=CacheConfig.ASSETS_TTL
        )
        # ... more caches
```

**Business Workflows:**
```python
def get_asset(self, symbol: str, force_refresh: bool = False) -> Optional[Asset]:
    """Get asset with TTL-based caching.

    Returns domain model, not ORM model.
    """
    # Use cache service
    asset_sql = self.asset_cache.get_or_fetch(
        key=symbol,
        fetch_fn=lambda: self._fetch_and_convert_asset(symbol),
        force_refresh=force_refresh
    )

    if not asset_sql:
        return None

    # Convert SQLModel → Domain model
    return Asset(
        id=asset_sql.id,
        symbol=asset_sql.symbol,
        name=asset_sql.name,
        asset_type=AssetType(asset_sql.asset_type),
        market_id=asset_sql.market_id,
        is_active=asset_sql.is_active,
        created_at=asset_sql.created_at,
        updated_at=asset_sql.updated_at
    )

def _fetch_and_convert_asset(self, symbol: str) -> Optional[AssetSQLModel]:
    """Fetch from provider, convert to SQLModel."""
    # Provider returns domain model
    asset_domain = self.reference_provider.fetch_ticker_details(symbol)
    if not asset_domain:
        return None

    # Convert domain model → SQLModel for storage
    return AssetSQLModel(
        symbol=asset_domain.symbol,
        name=asset_domain.name,
        asset_type=asset_domain.asset_type.value,
        market_id=asset_domain.market_id,
        is_active=asset_domain.is_active,
        created_at=asset_domain.created_at,
        updated_at=asset_domain.updated_at
    )
```

**Service Responsibilities:**
- ✅ Orchestrate repositories + providers + caches
- ✅ Implement business workflows
- ✅ Convert between domain models ↔ SQLModels
- ✅ Error handling for end users
- ✅ Logging
- ✅ Transaction coordination

---

## Data Flow Examples

### Example 1: Get Asset Information

```
1. CLI Command:
   ./tradescout asset info AAPL

2. CLI Layer:
   asset = data_service.get_asset("AAPL")

3. DataServiceV2:
   - Uses CacheService.get_or_fetch()

4. CacheService:
   - Checks metadata: Is AAPL data fresh? (< 7 days)
   - If YES: AssetRepository.get_by_symbol("AAPL") → AssetSQLModel
   - If NO:
     a. Call fetch_fn() → Provider
     b. Provider returns Asset (domain)
     c. Convert Asset → AssetSQLModel
     d. AssetRepository.save(asset_sql)
     e. MetadataRepository.record_update("tickers")

5. ReferenceDataProvider (if fetched):
   - Fetch ticker details via yfinance
   - Parse response → Asset domain model
   - Return to CacheService

6. DataServiceV2:
   - Convert AssetSQLModel → Asset domain model
   - Return to CLI

7. CLI Display:
   - Show symbol, name, type, market, status
```

### Example 2: Bootstrap All Assets

```
1. CLI Command:
   ./tradescout database bootstrap-assets

2. CLI Layer:
   result = data_service.bootstrap_assets()

3. DataServiceV2:
   - Check prerequisites (providers, markets exist)
   - Build market_code_to_id mapping
   - Call provider for all tickers

4. FreeReferenceAdapter:
   - Download NASDAQ Trader bulk ticker file
   - Parse pipe-delimited data (~12,000 securities)
   - Map each ticker → Asset domain model
   - Return List[Asset]

5. DataServiceV2:
   - Convert each Asset → AssetSQLModel
   - AssetRepository.bulk_save(asset_sql_list)
   - MetadataRepository.record_update("tickers", "bootstrap")
   - Return BootstrapResult

6. CLI Display:
   - Show count, duration, statistics
```

---

## What Goes Where: Layer Responsibilities

This section defines **exactly** what code belongs in each layer to maintain clean separation of concerns.

### Repository Layer (Data Access)

**Responsibilities:**
- ✅ SQL queries (SELECT, INSERT, UPDATE, DELETE)
- ✅ Joins across tables
- ✅ Aggregations (COUNT, SUM, GROUP BY)
- ✅ Filtering by database fields
- ✅ Sorting, pagination, limits
- ✅ Database transactions
- ✅ Type-safe query building

**Examples:**
```python
def get_by_symbol(self, symbol: str) -> Optional[AssetSQLModel]
def find_all_active(self, limit: Optional[int] = None) -> List[AssetSQLModel]
def bulk_save(self, assets: List[AssetSQLModel]) -> int
def count_active(self) -> int
```

**Does NOT Belong Here:**
- ❌ API calls to external services
- ❌ Business rules ("if market cap > X then do Y")
- ❌ Data transformations (API response → domain model)
- ❌ TTL/caching decisions

### Service Layer (Business Logic)

**Responsibilities:**
- ✅ Orchestration (call multiple repositories)
- ✅ Business rules (if this then that)
- ✅ API calls (fetch from providers)
- ✅ Data transformation (API response → database model)
- ✅ Caching decisions (when to refresh)
- ✅ Error handling & retries
- ✅ Progress tracking
- ✅ Validation of business constraints

**Examples:**
```python
def bootstrap_assets(self, market: str, active: bool)
def calculate_asset_sentiment(self, symbol: str)
def update_market_snapshot(self, force_refresh: bool = False)
```

**Does NOT Belong Here:**
- ❌ Raw SQL queries
- ❌ Direct database connections
- ❌ HTTP request/response handling (belongs in FastAPI)
- ❌ User interface logic (belongs in CLI)

### Provider Layer (External APIs)

**Responsibilities:**
- ✅ HTTP communication with external APIs
- ✅ Authentication (API keys, OAuth)
- ✅ Rate limit handling (HTTP 429 backoff)
- ✅ JSON parsing → Domain model transformation
- ✅ Retry logic with exponential backoff
- ✅ Provider-specific error handling

**Examples:**
```python
def fetch_ticker_details(self, symbol: str) -> Optional[Asset]
def fetch_all_tickers(self, market: str) -> List[Asset]
def fetch_market_status(self) -> Optional[Dict[str, Any]]
```

**Does NOT Belong Here:**
- ❌ Database writes
- ❌ Caching/TTL logic
- ❌ Business logic (filtering, validation)
- ❌ References to repositories or services

### Cache Service Layer

**Responsibilities:**
- ✅ Cache-aside pattern implementation
- ✅ TTL freshness checks
- ✅ Metadata timestamp tracking
- ✅ Generic caching logic (works for any entity)

**Does NOT Belong Here:**
- ❌ Entity-specific logic
- ❌ Business rules
- ❌ Direct API calls (passed as fetch_fn)

### Presentation Layer (Output Adapters)

**Responsibilities:**
- ✅ Format result models for specific outputs (CLI, Web, JSON)
- ✅ Terminal formatting (Rich tables, colors, panels)
- ✅ JSON serialization for API responses
- ✅ Handle datetime formatting, number formatting
- ✅ Output-specific styling and layout

**Examples:**
```python
def display_screener_results(self, result: ScreenerResult)
def display_market_context(self, result: MarketContextResult)
def display_gap_analysis(self, result: GapAnalysisResult)
```

**Does NOT Belong Here:**
- ❌ Business logic
- ❌ Database queries
- ❌ Building result models (that's command layer)
- ❌ Data fetching or calculations

### CLI Layer (User Interface)

**Responsibilities:**
- ✅ Parse user commands and arguments
- ✅ Call service layer methods
- ✅ Build result models from service responses
- ✅ Call presentation adapters to display results
- ✅ Handle user errors (invalid input)
- ✅ Progress bars and status updates

**Does NOT Belong Here:**
- ❌ Business logic
- ❌ Database queries
- ❌ API calls
- ❌ Data transformations
- ❌ Direct formatting (use adapters instead)

### Model Layers

**Domain Models (Dataclasses):**
- ✅ Business entity definitions
- ✅ Enums for type safety
- ✅ Helper methods for display
- ✅ Validation logic
- ❌ NO database awareness
- ❌ NO API calls

**SQLModel (ORM):**
- ✅ Table definitions
- ✅ Column types and constraints
- ✅ Relationships (foreign keys)
- ✅ Indexes
- ❌ NO business logic
- ❌ NO complex calculations

---

## Migration Guide: Old vs New Architecture

### Old Pattern (BaseManager)

The old architecture mixed responsibilities in a single class:

```python
# OLD - Mixed responsibilities
class AssetManager(BaseManager):
    def get_or_fetch(self, key, fetch_fn):
        # Cache logic + database logic + TTL logic mixed together
        ...

    def get_entity_from_database(self, key):
        # Raw SQL + manual row mapping
        cursor.execute("SELECT * FROM assets WHERE symbol = ?", (symbol,))
        row = cursor.fetchone()
        return dict(zip(columns, row))
```

**Problems:**
- Mixed concerns (cache + database + business logic)
- Raw SQL strings everywhere
- Manual row-to-dict mapping (error-prone)
- Hard to test (can't mock parts)
- Hard to reuse queries
- No type safety

### New Pattern (Layered)

The new architecture separates responsibilities across layers:

```python
# NEW - Separated responsibilities

# 1. SQLModel - Pure table definition
class AssetSQLModel(SQLModel, table=True):
    __tablename__ = "assets"
    id: Optional[int] = Field(default=None, primary_key=True)
    symbol: str
    # ... type-safe fields

# 2. Repository - Business queries
class AssetRepository:
    def find_all_active(self) -> List[AssetSQLModel]:
        statement = select(AssetSQLModel).where(
            AssetSQLModel.is_active == True
        )
        return list(self.session.exec(statement).all())

# 3. Cache - Cache-aside pattern
class CacheService:
    def get_or_fetch(self, key, fetch_fn, ttl_seconds):
        # Generic caching logic

# 4. Service - Orchestration
class DataServiceV2:
    def get_asset(self, symbol: str) -> Optional[Asset]:
        return self.asset_cache.get_or_fetch(
            key=symbol,
            fetch_fn=lambda: self._fetch_asset(symbol)
        )
```

**Benefits:**
- Separation of concerns - each layer has one job
- Type safety everywhere (SQLModel + Python type hints)
- Easy to test - mock each layer independently
- Reusable queries - define once, use everywhere
- Clear business intent - method names describe operations
- No raw SQL in business logic

### Migration Status: COMPLETE

The migration from the old manager-based pattern to the repository-based architecture is **complete**:

**Completed Migration:**
- ✅ **All SQLModels created** - Asset, Market, Fundamentals, Provider, Universe, AssetPrice, DataUpdateMetadata, SentimentEvent, FedData, MarketHoliday, Gap tracking
- ✅ **All Repositories implemented** - Business queries for all entities
- ✅ **DataServiceV2 fully wired** - All repositories initialized and integrated
- ✅ **FastAPI endpoints created** - HTTP interface with auto-generated docs
- ✅ **CLI migrated** - All commands use DataServiceV2
- ✅ **Old code deleted** - BaseManager pattern removed, old data_service.py removed

**Current Architecture:**
- `DataServiceV2` is the primary orchestration service
- Repository pattern used throughout
- Dual model system (domain dataclasses + ORM SQLModels)
- Cache-aside pattern with TTL management
- Type-safe queries with SQLModel

---

## Database Schema

### Core Tables

**assets**
```sql
CREATE TABLE assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT UNIQUE NOT NULL,
    name TEXT,
    asset_type TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    market_id INTEGER NOT NULL,
    currency TEXT DEFAULT 'USD',
    provider_id INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    is_delisted BOOLEAN DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (market_id) REFERENCES markets(id),
    FOREIGN KEY (provider_id) REFERENCES providers(id)
);
```

**providers**
```sql
CREATE TABLE providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    base_url TEXT,
    api_key_required BOOLEAN DEFAULT 1,
    is_active BOOLEAN DEFAULT 1,
    created_at TEXT NOT NULL
);
```

**markets**
```sql
CREATE TABLE markets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    country TEXT DEFAULT 'US',
    timezone TEXT DEFAULT 'America/New_York',
    currency TEXT DEFAULT 'USD',
    regular_open_time TEXT,
    regular_close_time TEXT,
    is_active BOOLEAN DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

**asset_fundamentals**
```sql
CREATE TABLE asset_fundamentals (
    asset_id INTEGER PRIMARY KEY,         -- One-to-one with assets table
    company_name TEXT,
    sector TEXT,
    industry TEXT,
    sic_code TEXT,
    market_cap BIGINT,
    shares_outstanding BIGINT,
    avg_volume_30d BIGINT,
    beta DECIMAL(6,3),
    pe_ratio DECIMAL(8,2),
    dividend_yield DECIMAL(6,4),
    provider_id INTEGER,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (asset_id) REFERENCES assets(id),
    FOREIGN KEY (provider_id) REFERENCES providers(id)
);
CREATE INDEX idx_fundamentals_sector ON asset_fundamentals(sector);
CREATE INDEX idx_fundamentals_industry ON asset_fundamentals(industry);
CREATE INDEX idx_fundamentals_market_cap ON asset_fundamentals(market_cap);
```

**universes**
```sql
CREATE TABLE universes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT 1,
    min_market_cap INTEGER,
    min_volume INTEGER,
    max_assets INTEGER,
    last_updated TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

**universe_memberships**
```sql
CREATE TABLE universe_memberships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    universe_id INTEGER NOT NULL,
    asset_id INTEGER NOT NULL,
    added_at TEXT NOT NULL,
    FOREIGN KEY (universe_id) REFERENCES universes(id),
    FOREIGN KEY (asset_id) REFERENCES assets(id),
    UNIQUE(universe_id, asset_id)
);
```

**data_update_metadata**
```sql
CREATE TABLE data_update_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_type TEXT NOT NULL,
    operation_subtype TEXT,
    started_at TEXT,
    completed_at TEXT,
    status TEXT DEFAULT 'running',
    total_items INTEGER,
    processed_items INTEGER DEFAULT 0,
    failed_items INTEGER DEFAULT 0,
    api_calls_made INTEGER DEFAULT 0,
    stats TEXT,
    operation_params TEXT,
    error_message TEXT
);
```

---

## Directory Structure

```
src/
├── models/
│   ├── dataclass/          # Domain models for business logic
│   │   ├── asset.py
│   │   ├── market.py
│   │   ├── fundamentals.py
│   │   ├── provider.py
│   │   ├── universe.py
│   │   ├── price.py
│   │   ├── snapshot.py
│   │   ├── gap.py
│   │   ├── market_context.py
│   │   ├── sentiment_event.py
│   │   ├── fed_data.py
│   │   └── ...
│   │
│   ├── result/             # Output-agnostic result models
│   │   ├── asset_result.py      # AssetInfoResult, PriceDataResult, etc.
│   │   ├── market_result.py     # MarketUpdateResult, MarketContextResult
│   │   ├── screener_result.py   # ScreenerResult
│   │   ├── gap_result.py        # GapAnalysisResult, GapPerformanceResult
│   │   ├── fed_result.py        # FedDataResult
│   │   ├── news_result.py       # NewsResult
│   │   ├── universe_result.py   # UniverseListResult, UniverseInfoResult
│   │   ├── validate_result.py   # VolumeValidationResult
│   │   ├── database_result.py   # DatabaseStats
│   │   └── bootstrap_result.py  # BootstrapResult
│   │
│   ├── sqlmodel/           # ORM models for database
│   │   ├── asset_sqlmodel.py
│   │   ├── market_sqlmodel.py
│   │   ├── fundamentals_sqlmodel.py
│   │   ├── provider_sqlmodel.py
│   │   ├── universe_sqlmodel.py
│   │   ├── asset_price_sqlmodel.py
│   │   ├── data_update_metadata_sqlmodel.py
│   │   └── ...
│   │
│   └── __init__.py         # Backward compatibility exports
│
├── repositories/           # Business-focused data access
│   ├── asset_repository.py
│   ├── market_repository.py
│   ├── fundamentals_repository.py
│   ├── provider_repository.py
│   ├── universe_repository.py
│   ├── asset_price_repository.py
│   ├── data_update_metadata_repository.py
│   └── ...
│
├── api/
│   └── providers/          # External API clients
│       ├── base_provider.py
│       ├── protocols/           # Provider interfaces
│       ├── adapters/            # Provider implementations
│       │   ├── yfinance_snapshot_adapter.py
│       │   ├── yfinance_aggregates_adapter.py
│       │   ├── free_reference_adapter.py
│       │   ├── finnhub_news_adapter.py
│       │   ├── pandas_market_calendar_adapter.py
│       │   ├── fred_economic_adapter.py
│       │   └── ...
│       └── provider_factory.py
│
├── services/
│   ├── data_service_v2.py            # Main orchestration
│   ├── cache_service.py              # Generic cache-aside
│   └── market_context_service.py     # Market state
│
├── analysis/
│   ├── gap_analyzer.py
│   └── sentiment_analyzer.py
│
├── screener/
│   ├── screener_engine.py
│   └── screener_display.py
│
├── output/                  # Output adapters (CLI and Web)
│   ├── cli_screener_adapter.py
│   ├── cli_market_adapter.py
│   ├── cli_asset_adapter.py
│   ├── cli_gap_adapter.py       # CLIGapAnalysisAdapter + CLIGapPerformanceAdapter
│   ├── cli_news_adapter.py
│   ├── cli_bootstrap_adapter.py
│   ├── cli_database_adapter.py
│   ├── cli_universe_adapter.py
│   ├── cli_validate_adapter.py
│   ├── cli_fed_adapter.py
│   ├── cli_progress_reporter.py
│   ├── web_screener_adapter.py
│   ├── web_market_adapter.py
│   ├── web_asset_adapter.py
│   ├── web_gap_adapter.py
│   ├── web_news_adapter.py
│   ├── web_universe_adapter.py
│   ├── web_validate_adapter.py
│   ├── web_fed_adapter.py
│   └── __init__.py
│
├── cli/
│   ├── main.py
│   ├── asset_commands.py
│   ├── market_commands.py
│   ├── database_commands.py
│   ├── screener_commands.py
│   ├── gap_commands.py
│   └── ...
│
└── utils/
    ├── config_loader.py
    └── ...
```

---

## Layer 5: Presentation Layer (Output Adapters)

**Location:** `src/output/`

**Purpose:** Format result models for different output contexts (CLI, Web, Reports)

### Result Model → Adapter Pattern

TradeScout separates business logic from presentation using an **output-agnostic architecture**:

```
Business Logic → Result Model → Output Adapter → Display
     (Service)      (Data)        (Format)       (CLI/Web)
```

### Result Models

**Location:** `src/models/result/`

**Purpose:** Output-agnostic data containers that hold all information needed to display results

**Characteristics:**
```python
@dataclass(frozen=True)  # Immutable
class ScreenerResult:
    """Pure data - no display logic."""
    screener_name: str
    results: List[Dict[str, Any]]
    screener_def: Dict[str, Any]
    market_context: MarketContext
    excluded_count: int
    snapshot_time: Optional[str] = None
```

**Benefits:**
- Output-agnostic (can display as CLI, Web, JSON, PDF, etc.)
- Testable (no UI dependencies)
- Serializable (can log, cache, transmit)
- Type-safe (validated structure)

**Result Models:**
- `ScreenerResult` - Screener execution results
- `GapAnalysisResult` - Gap analysis findings
- `GapPerformanceResult` - Gap backtest performance
- `MarketUpdateResult` - Market data update stats
- `MarketContextResult` - Market session state
- `AssetInfoResult` - Asset information
- `PriceDataResult` - Price data
- `NewsResult` - News/sentiment results
- `UniverseListResult` - Universe listings
- `UniverseInfoResult` - Universe details
- `VolumeValidationResult` - Volume validation data
- `DatabaseStats` - Database statistics
- `BootstrapResult` - Bootstrap operation results
- `FedDataResult` - Federal reserve data

### Output Adapters

**CLI Adapters:** `src/output/cli_*_adapter.py`
- Format results using Rich library (tables, colors, panels)
- Display directly to terminal
- Examples: `CLIScreenerOutputAdapter`, `CLIGapAnalysisAdapter`

**Web Adapters:** `src/output/web_*_adapter.py`
- Format results as JSON-serializable dictionaries
- Return Dict[str, Any] for FastAPI responses
- Examples: `WebScreenerOutputAdapter`, `WebMarketOutputAdapter`

**Adapter Pattern:**
```python
class CLIScreenerOutputAdapter:
    """CLI-specific formatting using Rich."""

    def display_screener_results(self, result: ScreenerResult):
        """Takes result model, displays with Rich tables."""
        table = Table(title=result.screener_name)
        for row in result.results:
            table.add_row(...)
        console.print(table)

class WebScreenerOutputAdapter:
    """Web API formatting - returns JSON."""

    def display_screener_results(self, result: ScreenerResult) -> Dict[str, Any]:
        """Takes result model, returns JSON-ready dict."""
        return {
            "screener": result.screener_name,
            "results": result.results,
            "excluded_count": result.excluded_count,
            # ... all fields as JSON
        }
```

### PresentationContext (Dependency Injection)

**Location:** `src/utils/presentation_context.py`

**Purpose:** Inject appropriate output adapters based on context (CLI vs Web)

```python
class PresentationContext:
    """Manages output adapters - separate from application state."""

    def __init__(
        self,
        screener_adapter=None,
        gap_analysis_adapter=None,
        market_adapter=None,
        asset_adapter=None,
        # ... all domain adapters
    ):
        self.screener_adapter = screener_adapter
        self.gap_analysis_adapter = gap_analysis_adapter
        # ...
```

**Injection at CLI:**
```python
# src/cli/main.py
app_context.presentation = PresentationContext(
    screener_adapter=CLIScreenerOutputAdapter(),
    gap_analysis_adapter=CLIGapAnalysisAdapter(),
    market_adapter=CLIMarketOutputAdapter(),
    # ... inject CLI adapters
)
```

**Injection at Web:**
```python
# src/web/web_app.py
def get_presentation_context():
    return PresentationContext(
        screener_adapter=WebScreenerOutputAdapter(),
        gap_adapter=WebGapOutputAdapter(),
        market_adapter=WebMarketOutputAdapter(),
        # ... inject Web adapters
    )
```

### Command Pattern (Output-Agnostic)

Commands build result models and delegate display to injected adapters:

```python
# src/cli/screener_commands.py
def screener(app_context, screener_name: str):
    """Command is output-agnostic - works for CLI and Web."""

    # Execute business logic
    results = screener_engine.execute_screener(...)

    # Build output-agnostic result model
    result = ScreenerResult(
        screener_name=screener_name,
        results=results,
        screener_def=screener_def,
        market_context=market_context,
        excluded_count=excluded_count,
        # ... all display data
    )

    # Display using injected adapter (CLI or Web!)
    app_context.presentation.screener_adapter.display_screener_results(result)
```

**Same command works for:**
- CLI: Displays Rich tables in terminal
- Web: Returns JSON for API responses
- Tests: No display, just validates result model

### Adapter Coverage

**CLI Adapters (11):**
1. `CLIScreenerOutputAdapter` - Screener results
2. `CLIGapAnalysisAdapter` - Gap analysis
3. `CLIGapPerformanceAdapter` - Gap backtest
4. `CLIMarketOutputAdapter` - Market updates
5. `CLIAssetOutputAdapter` - Asset information
6. `CLINewsOutputAdapter` - News/sentiment
7. `CLIUniverseOutputAdapter` - Universe listings
8. `CLIValidateOutputAdapter` - Validation results
9. `CLIFedOutputAdapter` - Federal reserve data
10. `CLIBootstrapOutputAdapter` - Bootstrap operations (CLI-only)
11. `CLIDatabaseOutputAdapter` - Database statistics (CLI-only)

**Web Adapters (8):**
1. `WebScreenerOutputAdapter` - Screener results
2. `WebGapOutputAdapter` - Gap analysis
3. `WebMarketOutputAdapter` - Market updates
4. `WebAssetOutputAdapter` - Asset information
5. `WebNewsOutputAdapter` - News/sentiment
6. `WebUniverseOutputAdapter` - Universe listings
7. `WebValidateOutputAdapter` - Validation results
8. `WebFedOutputAdapter` - Federal reserve data

**Note:** Bootstrap and Database are CLI-only operations (no web adapters)

---

## Key Design Patterns

### 1. Dual Model System

**Why:** Separate concerns - domain logic vs database persistence

**Domain Models (Dataclass):**
- Lightweight, immutable
- Used by: Providers, Services, Analysis
- Import: `from models.dataclass.asset import Asset`

**ORM Models (SQLModel):**
- Database-aware, mutable
- Used by: Repositories only
- Import: `from models.sqlmodel.asset_sqlmodel import AssetSQLModel`

### 2. Repository Pattern

**Why:** Business-focused data access, hide database implementation

```python
# Repository provides business queries
assets = asset_repository.find_all_active(limit=100)

# Not raw SQL
cursor.execute("SELECT * FROM assets WHERE is_active = 1 LIMIT 100")
```

### 3. Cache-Aside Pattern

**Why:** Generic caching with TTL, works for any entity

```python
# CacheService handles: check freshness, fetch if stale, store, update TTL
asset = cache.get_or_fetch(
    key=symbol,
    fetch_fn=lambda: provider.fetch(symbol)
)
```

### 4. Dependency Injection

**Why:** Testable, flexible, clear dependencies

```python
class DataServiceV2:
    def __init__(self, session: Session, api_key: str):
        # Inject session (can mock for tests)
        self.asset_repository = AssetRepository(session)
```

### 5. Separation of Concerns

| Layer | Responsibility | Doesn't Do |
|-------|---------------|------------|
| **Domain Models** | Business entities, helpers | Database, API |
| **SQLModel** | Table definitions, ORM | Business logic, API |
| **Providers** | Fetch from APIs | Database writes, caching |
| **Repositories** | Data access queries | API calls, business logic |
| **CacheService** | TTL-based caching | Entity-specific logic |
| **DataService** | Orchestrate workflows | Direct SQL, HTTP |
| **CLI** | User interaction | Business logic, data access |

---

## Testing Strategy

### Unit Tests
- **Domain Models:** Validation, helpers, transformations
- **Providers:** Response parsing (mock HTTP)
- **Repositories:** CRUD operations (in-memory SQLite)
- **Services:** Business logic (mock repositories)

### Integration Tests
- **End-to-end workflows** with real database
- **Repository queries** with actual SQLModel
- **CLI commands** with test fixtures

**Location:** `tests/`

---

## Configuration System

### YAML Configuration Files

**Location:** `configs/`

**Files:**
- `database_ttl.yaml` - TTL settings for caching
- `gap_trading.yaml` - Gap analysis configuration
- `market_context_rules.yaml` - Market session rules
- `sic_sector_mapping.yaml` - SIC code → sector mapping
- `universes/*.yaml` - Universe definitions
- `screeners/*.yaml` - Screener templates

**Loading:**
```python
from utils.config_loader import get_config_loader

config = get_config_loader()
ttl_config = config.load_database_ttl_config()
```

---

## Summary

**Architecture Philosophy:**
- **Repository pattern** - Business queries, not raw SQL
- **Dual model system** - Domain logic separate from persistence
- **Cache-aside pattern** - Generic caching with TTL
- **Clean layering** - Each layer has one job
- **Type safety** - Python type hints + SQLModel validation
- **Dependency injection** - Testable, flexible

**Key Strengths:**
- ✅ Clean separation of concerns
- ✅ Easy to test (mock repositories)
- ✅ Type-safe throughout (domain + ORM)
- ✅ Generic caching (any entity type)
- ✅ Business-meaningful queries
- ✅ Easy to add new entities
- ✅ SQLModel benefits (migrations, validation)

**Trade-offs:**
- Dual model system requires conversion
- More boilerplate than direct SQL
- Learning curve for repository pattern
- SQLModel adds complexity vs raw SQL

**Next Steps:**
- See `docs/planning/` for upcoming features
- See `database/migrations/` for schema evolution
- See `cli/` for user-facing functionality
- See `GETTING_STARTED.md` for development guide
