# TradeScout Architecture

**Purpose:** Technical architecture reference for TradeScout's codebase
**Last Updated:** 2025-10-10

---

## High-Level Architecture

TradeScout uses a **three-layer architecture** to separate concerns:

```
┌──────────────────────────────────────────────────────┐
│             CLI Layer (src/cli/)                     │
│         User commands → DataService calls            │
└─────────────────────┬────────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────────┐
│          DataService Layer (src/services/)           │
│     Business logic, orchestration, TTL checks        │
└──────────┬─────────────────────┬─────────────────────┘
           │                     │
    ┌──────▼────────┐     ┌──────▼────────────┐
    │  Database     │     │  API Providers    │
    │  Managers     │     │  (Polygon, etc.)  │
    │  (src/       │     │  (src/api/        │
    │  database/   │     │  providers/)       │
    │  managers/)  │     │                    │
    └──────┬───────┘     └──────┬─────────────┘
           │                     │
   ┌───────▼──────┐      ┌──────▼──────────┐
   │ SQLite DB    │      │ External APIs   │
   │ (data/*.db)  │      │ (polygon.io)    │
   └──────────────┘      └─────────────────┘
```

---

## Layer 1: Models (Business Entities)

**Location:** `src/models/`

**Purpose:** Immutable dataclasses representing business entities

**Key Models:**
- `Asset` - Stock/ticker details (symbol, name, type)
- `Fundamentals` - Company fundamentals (market cap, sector, SIC)
- `AssetPrice` - Current price snapshot (close, open, high, low, volume)
- `TickerSnapshot` - Real-time market data (minute bars, session data)
- `MarketSnapshot` - Collection of ticker snapshots
- `SentimentEvent` - News/sentiment data point
- `FedData` - Federal Reserve economic data
- `GapCandidate` - Identified gap trading opportunity
- `MarketContext` - Current market state (session, date, status)

**Characteristics:**
```python
@dataclass(frozen=True)  # Immutable
class Asset:
    id: int
    symbol: str
    name: str
    asset_type: str
    market_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
```

**Rules:**
- ✅ Frozen (immutable)
- ✅ Type hints on all fields
- ✅ No database/API awareness
- ✅ Business logic only (helpers, validators)
- ❌ No external dependencies

---

## Layer 2a: API Providers

**Location:** `src/api/providers/`

**Purpose:** Fetch data from external APIs (Polygon, etc.)

**Base Class:** `BaseAPIProvider`
```python
class BaseAPIProvider(ABC):
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url

    @abstractmethod
    def _add_authentication(self, params: Dict) -> Dict:
        """Add API key/auth to request params"""

    @abstractmethod
    def _get_health_endpoint(self) -> str:
        """Health check endpoint"""

    def _make_request(self, endpoint: str, params: Dict) -> Dict:
        """Make HTTP request with retry logic, rate limiting"""
```

**Existing Providers:**

| Provider | Purpose | Endpoints |
|----------|---------|-----------|
| `PolygonSnapshotProvider` | Real-time snapshot data | `/v2/snapshot/locale/us/markets/stocks/tickers` |
| `PolygonTickersProvider` | Ticker details/metadata | `/v3/reference/tickers/{symbol}` |
| `PolygonAggregatesProvider` | Historical OHLC bars | `/v2/aggs/ticker/{symbol}/range/{timespan}` |
| `PolygonNewsProvider` | News/sentiment | `/v2/reference/news` |
| `PolygonMarketStatusProvider` | Market hours/status | `/v1/marketstatus/now` |
| `PolygonMarketsProvider` | Market/exchange data | `/v3/reference/exchanges` |
| `PolygonFedProvider` | Fed economic data | `/fed/v1/inflation`, `/fed/v1/treasury-yields` |

**Provider Responsibilities:**
- ✅ HTTP communication
- ✅ Authentication (API keys)
- ✅ Rate limit handling (HTTP 429)
- ✅ Response parsing (JSON → Model objects)
- ✅ Retry logic (exponential backoff)
- ❌ NO database writes
- ❌ NO caching/TTL logic
- ❌ NO business logic

---

## Layer 2b: Database Managers

**Location:** `src/database/managers/`

**Purpose:** Persist and retrieve data with TTL-based staleness checking

**Base Class:** `BaseManager`
```python
class BaseManager(ABC):
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    @abstractmethod
    def get_operation_type(self) -> str:
        """Return operation type for TTL tracking"""

    @abstractmethod
    def get_ttl_seconds(self) -> int:
        """Return TTL in seconds for this data type"""
```

**Existing Managers:**

| Manager | Entity | Table | TTL Logic |
|---------|--------|-------|-----------|
| `AssetManager` | `Asset` | `assets` | Per-ticker (7 days) |
| `AssetPriceManager` | `AssetPrice` | `asset_prices` | Per-ticker (5 min) |
| `FundamentalsManager` | `Fundamentals` | `fundamentals` | Per-ticker (7 days) |
| `TickerSnapshotManager` | `TickerSnapshot` | `ticker_snapshots` | Per-ticker (5 min) |
| `MarketSnapshotManager` | `MarketSnapshot` | N/A (in-memory) | Bulk operation (5 min) |
| `SentimentEventsManager` | `SentimentEvent` | `sentiment_events` | Per-ticker (30 min) |
| `FedDataManager` | `FedData` | `fed_data` | Bulk operation (12 hours) |
| `MarketsManager` | `Market` | `markets` | Global (7 days) |
| `MarketHolidaysManager` | `MarketHoliday` | `market_holidays` | Global (30 days) |
| `MarketContextManager` | `MarketContext` | N/A (computed) | Session-based |

**Manager Responsibilities:**
- ✅ CRUD operations (Create, Read, Update, Delete)
- ✅ TTL staleness checking
- ✅ Bulk upserts
- ✅ Query helpers
- ❌ NO API calls
- ❌ NO business logic

**Pattern: get_or_fetch()**
```python
def get_or_fetch(
    self,
    key: str,
    fetch_fn: Callable,
    force_refresh: bool = False
) -> Optional[T]:
    """Get from DB if fresh, otherwise fetch and store.

    1. Check if data exists and is fresh (TTL)
    2. If yes, return from database
    3. If no, call fetch_fn() to get from API
    4. Store fetched data to database
    5. Return data
    """
```

---

## Layer 3: DataService (Orchestration)

**Location:** `src/services/data_service.py`

**Purpose:** Orchestrate managers + providers to fulfill business requirements

**Key Methods:**
```python
class DataService:
    def __init__(self, db_manager: DatabaseManager, api_key: str):
        # Initialize all managers
        self.asset_manager = AssetManager(db_manager)
        self.asset_price_manager = AssetPriceManager(db_manager)
        self.fundamentals_manager = FundamentalsManager(db_manager)
        # ...

        # Initialize all providers
        self.polygon_snapshot_provider = PolygonSnapshotProvider(api_key)
        self.polygon_tickers_provider = PolygonTickersProvider(api_key)
        # ...

    def get_asset(self, symbol: str, force_refresh: bool = False) -> Optional[Asset]:
        """Get asset with TTL-based caching"""
        return self.asset_manager.get_or_fetch(
            key=symbol,
            fetch_fn=lambda: self.polygon_tickers_provider.fetch_ticker_details(symbol),
            force_refresh=force_refresh
        )

    def get_latest_price(self, symbol: str, force_refresh: bool = False) -> Optional[AssetPrice]:
        """Get latest price with TTL-based caching"""
        # Complex orchestration: snapshot → parse → store → return
```

**DataService Responsibilities:**
- ✅ Orchestrate managers + providers
- ✅ Implement business workflows
- ✅ TTL-based refresh decisions
- ✅ Error handling for end users
- ✅ Logging

---

## TTL (Time-To-Live) System

### Purpose

Prevent excessive API calls by caching data with configurable freshness thresholds.

### Configuration

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

### TTL Tracking

**Table:** `data_update_metadata`

```sql
CREATE TABLE data_update_metadata (
    operation_type TEXT PRIMARY KEY,  -- e.g., 'ticker_snapshot', 'fed_data'
    last_update TEXT NOT NULL,        -- ISO timestamp of last update
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

**Purpose:** Track last update time for bulk operations (all tickers, all indices, etc.)

**Example:**
```sql
-- Last time we fetched market snapshot for all tickers
INSERT INTO data_update_metadata VALUES ('market_snapshot', '2025-10-10 14:30:00', ...);

-- Last time we fetched all Fed data
INSERT INTO data_update_metadata VALUES ('fed_data', '2025-10-10 06:00:00', ...);
```

### TTL Patterns

**Pattern 1: Per-Ticker TTL**
```python
# Each ticker has its own timestamp
asset = asset_manager.get(symbol="AAPL")
if asset and asset.is_stale(ttl_seconds=604800):  # 7 days
    # Fetch fresh data for AAPL only
```

**Pattern 2: Bulk Operation TTL**
```python
# All tickers share one timestamp
metadata = metadata_manager.get_metadata("market_snapshot")
if metadata.is_stale(ttl_seconds=300):  # 5 minutes
    # Fetch fresh data for ALL tickers
```

---

## Key Design Patterns

### 1. Immutable Models

**Why:** Thread-safe, predictable, prevents accidental mutations

```python
@dataclass(frozen=True)
class Asset:
    id: int
    symbol: str
    # ... fields are immutable after creation
```

### 2. Separation of Concerns

| Layer | Does | Doesn't Do |
|-------|------|------------|
| **Models** | Define structure, business helpers | Database, API, I/O |
| **Providers** | Fetch from APIs, parse responses | Store to DB, business logic |
| **Managers** | CRUD, TTL checks | API calls, business logic |
| **DataService** | Orchestrate, business workflows | Direct SQL, HTTP requests |
| **CLI** | User interaction, display | Business logic, data access |

### 3. Dependency Injection

**Service Layer:**
```python
class DataService:
    def __init__(self, db_manager: DatabaseManager, api_key: str):
        # Inject dependencies
        self.asset_manager = AssetManager(db_manager)
        self.polygon_provider = PolygonSnapshotProvider(api_key)
```

**Benefits:**
- Testable (inject mocks)
- Flexible (swap implementations)
- Clear dependencies

### 4. Factory Pattern for Providers

**Why:** Multiple API providers may exist for same data (Polygon, Alpha Vantage, Finnhub)

```python
def create_snapshot_provider(provider_name: str, api_key: str) -> BaseSnapshotProvider:
    if provider_name == "polygon":
        return PolygonSnapshotProvider(api_key)
    elif provider_name == "alpha_vantage":
        return AlphaVantageSnapshotProvider(api_key)
    else:
        raise ValueError(f"Unknown provider: {provider_name}")
```

### 5. Bulk Operations

**Why:** API efficiency (1 call for 100 symbols vs 100 calls)

**Example: Market Snapshot**
```python
# Fetch all tracked tickers in one API call
def fetch_market_snapshot() -> List[TickerSnapshot]:
    # GET /v2/snapshot/locale/us/markets/stocks/tickers
    # Returns: 100+ ticker snapshots in single response
```

**TTL Strategy:**
- Single `data_update_metadata` entry for "market_snapshot"
- All tickers refreshed together (not individually)

---

## Directory Structure

```
src/
├── models/              # Immutable business entities
│   ├── snapshot.py      # TickerSnapshot, MarketSnapshot
│   ├── fundamentals.py  # Fundamentals
│   ├── price.py         # AssetPrice
│   ├── market_context.py# MarketContext
│   ├── gap.py           # GapCandidate
│   └── fed_data.py      # FedData
│
├── api/
│   ├── config/
│   │   └── api_keys.py  # API key configuration
│   └── providers/       # External API clients
│       ├── base_provider.py
│       ├── polygon_snapshot_provider.py
│       ├── polygon_tickers_provider.py
│       ├── polygon_aggregates_provider.py
│       ├── polygon_news_provider.py
│       ├── polygon_fed_provider.py
│       └── ...
│
├── database/
│   ├── database_manager.py         # SQLite connection manager
│   ├── migrations/                 # SQL migration files
│   └── managers/                   # Data access layer
│       ├── base_manager.py
│       ├── asset_manager.py
│       ├── asset_price_manager.py
│       ├── fundamentals_manager.py
│       ├── ticker_snapshot_manager.py
│       ├── market_snapshot_manager.py
│       ├── sentiment_events_manager.py
│       ├── fed_data_manager.py
│       ├── data_update_metadata_manager.py
│       └── ...
│
├── services/
│   ├── data_service.py            # Main orchestration layer
│   └── market_context_service.py  # Market state service
│
├── analysis/
│   ├── gap_analyzer.py            # Gap trading analysis
│   └── sentiment_analyzer.py      # Sentiment scoring
│
├── screener/
│   ├── screener_engine.py         # Screener execution
│   └── screener_display.py        # Results formatting
│
├── cli/
│   ├── main.py                    # CLI entry point
│   ├── asset_commands.py
│   ├── market_commands.py
│   ├── screener_commands.py
│   ├── gap_commands.py
│   ├── fed_commands.py
│   └── ...
│
└── utils/
    ├── config_loader.py           # YAML config loading
    └── ...
```

---

## Data Flow Examples

### Example 1: Get Latest Price for AAPL

```
1. CLI Command:
   ./tradescout asset info AAPL

2. CLI Layer (asset_commands.py):
   data_service.get_latest_price("AAPL")

3. DataService:
   - Check: Is AAPL snapshot fresh? (< 5 min old)
   - If NO:
     a. Call: polygon_snapshot_provider.fetch_ticker_snapshot("AAPL")
     b. Store: ticker_snapshot_manager.upsert(snapshot)
     c. Update: metadata_manager.record_update("ticker_snapshot")
   - If YES:
     a. Get: ticker_snapshot_manager.get("AAPL")

4. Provider (if needed):
   - HTTP GET: /v2/snapshot/locale/us/markets/stocks/tickers/AAPL
   - Parse JSON → TickerSnapshot model
   - Return to DataService

5. Manager (if fetch occurred):
   - INSERT/UPDATE ticker_snapshots table
   - Return TickerSnapshot to DataService

6. DataService → CLI → User:
   Display price, change%, volume, etc.
```

### Example 2: Run Gap Analysis

```
1. CLI Command:
   ./tradescout gap analyze

2. CLI Layer (gap_commands.py):
   - Get market context (session, date)
   - Fetch all ticker snapshots (bulk)
   - Filter for gap candidates

3. DataService:
   - Check: Is market_snapshot fresh? (< 5 min)
   - If NO:
     a. Fetch: polygon_snapshot_provider.fetch_all_tickers()
     b. Store: market_snapshot_manager.bulk_upsert(snapshots)
   - Return: List[TickerSnapshot]

4. GapAnalyzer:
   - Calculate gaps (current vs previous close)
   - Filter by volume, market cap
   - Score quality (0-100)
   - Detect exhaustion patterns

5. CLI Display:
   - Show gap candidates
   - Show quality scores
   - Generate report file
```

---

## Database Schema (Key Tables)

### assets
```sql
CREATE TABLE assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT UNIQUE NOT NULL,
    name TEXT,
    asset_type TEXT,  -- 'stock', 'etf', 'index'
    market_id INTEGER,
    is_active BOOLEAN DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (market_id) REFERENCES markets(id)
);
```

### asset_prices
```sql
CREATE TABLE asset_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    timestamp INTEGER NOT NULL,
    close REAL,
    high REAL,
    low REAL,
    open REAL,
    volume INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (asset_id) REFERENCES assets(id),
    UNIQUE(asset_id, timestamp)
);
```

### fundamentals
```sql
CREATE TABLE fundamentals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER UNIQUE NOT NULL,
    market_cap REAL,
    shares_outstanding REAL,
    sector TEXT,
    sic_code TEXT,
    description TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (asset_id) REFERENCES assets(id)
);
```

### sentiment_events
```sql
CREATE TABLE sentiment_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    sentiment_type_id INTEGER NOT NULL,
    event_timestamp INTEGER NOT NULL,
    title TEXT,
    description TEXT,
    url TEXT,
    sentiment_score TEXT,  -- 'positive', 'negative', 'neutral', 'mixed'
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (asset_id) REFERENCES assets(id),
    FOREIGN KEY (sentiment_type_id) REFERENCES sentiment_types(id)
);
```

### fed_data
```sql
CREATE TABLE fed_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_type TEXT NOT NULL,  -- 'inflation', 'inflation_expectations', 'treasury_yields'
    observation_date TEXT NOT NULL,
    value REAL NOT NULL,
    details TEXT NOT NULL,  -- JSON blob
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(data_type, observation_date)
);
```

### data_update_metadata
```sql
CREATE TABLE data_update_metadata (
    operation_type TEXT PRIMARY KEY,
    last_update TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

---

## Configuration System

### YAML Configuration Files

**Location:** `configs/`

**Files:**
- `database_ttl.yaml` - TTL settings for all data types
- `gap_trading.yaml` - Gap analysis configuration
- `market_context_rules.yaml` - Market session rules
- `sic_sector_mapping.yaml` - SIC code → sector mapping
- `universes/*.yaml` - Universe definitions
- `screeners/*.yaml` - Screener definitions

**Loading:**
```python
from utils.config_loader import get_config_loader

config = get_config_loader()
ttl_config = config.load_database_ttl_config()
gap_config = config.load_gap_trading_config()
```

---

## Testing Strategy

### Unit Tests
- **Models:** Validation, helpers, transformations
- **Providers:** Response parsing (mock HTTP)
- **Managers:** CRUD operations (in-memory SQLite)
- **Services:** Business logic (mock providers + managers)

### Integration Tests
- **End-to-end workflows** with real database
- **API provider** smoke tests (optional, rate limit friendly)
- **CLI commands** with test fixtures

**Location:** `tests/`

---

## Error Handling

### Provider Layer
```python
try:
    response = self._make_request(endpoint, params)
except requests.exceptions.Timeout:
    logger.error(f"Timeout fetching {endpoint}")
    return None
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 429:
        logger.warning("Rate limit hit, implement backoff")
    raise
```

### Manager Layer
```python
try:
    with self.db_manager.get_connection() as conn:
        cursor.execute(query, params)
except sqlite3.IntegrityError as e:
    logger.error(f"Duplicate entry: {e}")
    return None
```

### Service Layer
```python
try:
    asset = self.get_asset(symbol)
    if not asset:
        logger.warning(f"Asset {symbol} not found")
        return None
except Exception as e:
    logger.error(f"Unexpected error fetching {symbol}: {e}")
    raise
```

---

## Performance Considerations

### 1. Bulk Operations
- Fetch 100+ tickers in single API call (market snapshot)
- Bulk INSERT with `executemany()`
- Single TTL check for entire bulk operation

### 2. Database Indexing
```sql
CREATE INDEX idx_asset_prices_symbol ON asset_prices(asset_id, timestamp DESC);
CREATE INDEX idx_sentiment_events_asset ON sentiment_events(asset_id, event_timestamp DESC);
```

### 3. Connection Pooling
- Single `DatabaseManager` instance per CLI command
- Context manager pattern for connections
- Automatic cleanup on exit

### 4. Caching Strategy
- TTL-based caching reduces API calls 90%+
- In-memory caching in CLI session (e.g., market context)
- No external cache (Redis, etc.) - keep it simple

---

## Summary

**Architecture Philosophy:**
- **Separation of concerns** - Each layer has one job
- **Immutability** - Models are frozen dataclasses
- **Dependency injection** - Testable, flexible
- **TTL-based caching** - Reduce API calls, configurable freshness
- **Bulk operations** - API efficiency
- **Type safety** - Python type hints throughout

**Key Strengths:**
- ✅ Clean layer separation
- ✅ Easy to test
- ✅ Easy to add new providers
- ✅ Easy to add new data types
- ✅ Configurable TTL system
- ✅ Type-safe throughout

**Trade-offs:**
- More files/classes than monolithic approach
- Some duplication (managers have similar patterns)
- Learning curve for new contributors

**Next Steps:**
- See planning docs for upcoming features (indicators, indices)
- See database migration files for schema evolution
- See CLI commands for user-facing functionality
