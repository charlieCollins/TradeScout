# TradeScout Database Architecture

**Last Updated**: 2025-10-11
**Database**: SQLite
**Location**: `data/tradescout.db`
**Schema Version**: 004
**Architecture**: Manager/Provider Pattern

---

## Overview

TradeScout uses **SQLite with 16 tables** for market data management, sentiment tracking, gap analysis, and operation metadata. The system follows a clean **Manager/Provider architecture** where:

- **Managers** handle database CRUD operations
- **Providers** handle external API calls
- **DataService** orchestrates between them

All data types use **immutable model objects** (dataclasses) - no raw dicts or tuples passed around.

---

## Table Summary

| Table | Purpose | Manager | Provider | Status |
|-------|---------|---------|----------|--------|
| **Reference Data** |||||
| `providers` | API provider configuration | ✅ ProviderManager | - | ✅ Active |
| `markets` | Exchange information | ✅ MarketsManager | ✅ PolygonMarketsProvider | ✅ Active |
| `assets` | Stock ticker universe | ✅ AssetManager | ✅ PolygonTickersProvider | ✅ Active |
| `asset_fundamentals` | Company fundamentals | ✅ FundamentalsManager | ✅ PolygonTickersProvider | ✅ Active |
| **Price Data** |||||
| `asset_prices` | Historical/live prices | ✅ TickerSnapshotManager<br>✅ MarketSnapshotManager | ✅ PolygonSnapshotProvider | ✅ Active |
| **Universe Management** |||||
| `universes` | Asset groupings | ✅ UniverseManager | - | ✅ Active |
| `universe_memberships` | Membership tracking | ✅ UniverseManager | - | ✅ Active |
| **Sentiment** |||||
| `sentiment_types` | Event type definitions | ✅ SentimentTypesManager | - | ✅ Active |
| `sentiment_events` | Detected events | ✅ SentimentEventsManager | ✅ PolygonNewsProvider | ✅ Active |
| **Gap Analysis** |||||
| `gap_results` | Gap candidate results | ✅ GapResultsManager | - | ✅ Active |
| `gap_performance_tracking` | Gap performance metrics | ✅ GapPerformanceManager | ✅ PolygonAggregatesProvider | ✅ Active |
| **Economic Data** |||||
| `fed_data` | Federal Reserve data | ✅ FedDataManager | ✅ PolygonFedProvider | ✅ Active |
| **Market Status** |||||
| `market_holidays` | Holiday calendar | ✅ MarketHolidaysManager | ✅ PolygonMarketStatusProvider | ✅ Active |
| `market_context_cache` | Market status/session | ✅ MarketContextManager | ✅ PolygonMarketStatusProvider | ✅ Active |
| **Metadata** |||||
| `data_update_metadata` | Operation tracking | ✅ DataUpdateMetadataManager | - | ✅ Active |
| **System** |||||
| `schema_versions` | Schema migrations | ✅ System | - | ✅ Active |

**Legend**: ✅ Complete | 🚧 In Progress | 🔍 Under Review | ❌ Legacy

---

## Architecture: Manager/Provider Pattern

### Data Flow

```
User Request
    ↓
DataService (orchestration)
    ↓
┌──────────────────────────────┐
│  Manager (database)          │  ←→  Provider (API)
│  - CRUD operations           │      - External calls
│  - TTL validation            │      - Response parsing
│  - Model conversion          │      - Rate limiting
└──────────────────────────────┘
    ↓
SQLite Database
```

### Example: Get Market Data

```python
# User calls DataService
snapshot = data_service.get_ticker_snapshot("AAPL", force_refresh=False)

# DataService coordinates:
# 1. Check if data is stale (TTL validation in manager)
# 2. If stale: Fetch from API (provider)
# 3. Store to database (manager)
# 4. Return model object

# Manager handles database:
manager = TickerSnapshotManager(db_manager, update_tracker, metadata_manager)
cached_snapshot = manager.get_entity_from_database("AAPL")

# Provider handles API:
provider = PolygonSnapshotProvider(api_key)
fresh_snapshot = provider.fetch_single_ticker("AAPL")
```

### When to Use Metadata Tracking

**USE `data_update_metadata` for**:
- ✅ **Bulk operations**: Market snapshots (7k tickers at once)
- ✅ **Bootstrap operations**: Markets, assets, fundamentals (batch from API)
- ✅ **Scheduled batches**: Universe refresh, fundamentals update

**DON'T use for**:
- ❌ **Individual CRUD**: Single asset lookups
- ❌ **Records with `updated_at`**: Check freshness from record itself
- ❌ **Continuous operations**: Sentiment events created on-demand

**Why?** Metadata tracks "when did we last run this expensive batch operation?" to avoid re-running unnecessarily. Without metadata, we'd scan thousands of rows to check staleness. With metadata, we check ONE row.

---

## Table Schemas

### 1. providers

**Purpose**: API provider configuration
**Manager**: `ProviderManager` (no metadata tracking)
**Data Source**: Hardcoded (single Polygon.io entry)

```sql
CREATE TABLE providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,              -- 'polygon'
    display_name TEXT NOT NULL,              -- 'Polygon.io'
    base_url TEXT,                           -- 'https://api.polygon.io'
    api_key_required BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Bootstrap**: `data_service.bootstrap_providers()` - Hardcoded Polygon config

---

### 2. markets

**Purpose**: Exchange/market reference data
**Manager**: `MarketsManager` (with metadata tracking, TTL: 1 year)
**Provider**: `PolygonMarketsProvider` → `/v3/reference/exchanges`

```sql
CREATE TABLE markets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,               -- 'XNYS', 'XNAS', 'ARCX'
    name TEXT NOT NULL,                       -- 'New York Stock Exchange'
    country TEXT DEFAULT 'US',
    timezone TEXT DEFAULT 'America/New_York',
    currency TEXT DEFAULT 'USD',

    -- Trading hours (in market timezone)
    premarket_start_time TIME,               -- '04:00:00'
    premarket_end_time TIME,                  -- '09:30:00'
    regular_open_time TIME,                   -- '09:30:00'
    regular_close_time TIME,                  -- '16:00:00'
    afterhours_start_time TIME,               -- '16:00:00'
    afterhours_end_time TIME,                 -- '20:00:00'

    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Typical Data**: 7-12 US exchanges (XNYS, XNAS, ARCX, BATS, etc.)
**Bootstrap**: `data_service.bootstrap_markets(asset_class="stocks", locale="us")`

---

### 3. assets

**Purpose**: Complete ticker universe
**Manager**: `AssetManager` (with metadata tracking, TTL: 3 days)
**Provider**: `PolygonTickersProvider` → `/v3/reference/tickers`

```sql
CREATE TABLE assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL UNIQUE,             -- 'AAPL', 'MSFT'
    name TEXT NOT NULL,                       -- 'Apple Inc.'
    market_id INTEGER NOT NULL,

    -- Classification
    asset_type TEXT CHECK(asset_type IN ('stock', 'etf', 'crypto', 'option', 'forex')) DEFAULT 'stock',

    -- Trading details
    currency TEXT DEFAULT 'USD',

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    is_delisted BOOLEAN DEFAULT FALSE,

    -- Provider reference
    provider_id INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (market_id) REFERENCES markets (id),
    FOREIGN KEY (provider_id) REFERENCES providers (id)
);
```

**Typical Data**: ~10,000+ active tickers
**Bootstrap**: `data_service.bootstrap_assets(market="stocks", active=True)`
**Index**: `idx_assets_symbol`, `idx_assets_market`, `idx_assets_active`

---

### 4. asset_fundamentals

**Purpose**: Company fundamentals for screening
**Manager**: `FundamentalsManager` (with metadata tracking, TTL: 1 week)
**Provider**: `PolygonTickersProvider.fetch_ticker_details_raw()` → `/v3/reference/tickers/{symbol}`

**Note**: Same API endpoint as `assets` - single call provides BOTH ticker reference data AND fundamentals.

```sql
CREATE TABLE asset_fundamentals (
    asset_id INTEGER PRIMARY KEY,            -- One-to-one with assets

    -- Company identification
    company_name TEXT,

    -- Classification
    sector TEXT,                             -- 'Technology', 'Healthcare'
    industry TEXT,                           -- 'Consumer Electronics'
    sic_code TEXT,                           -- Standard Industrial Classification

    -- Key metrics
    market_cap BIGINT,                       -- Market cap in cents
    shares_outstanding BIGINT,
    avg_volume_30d BIGINT,                   -- 30-day avg volume
    beta DECIMAL(6,3),
    pe_ratio DECIMAL(8,2),
    dividend_yield DECIMAL(6,4),

    -- Tracking
    provider_id INTEGER,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (asset_id) REFERENCES assets (id),
    FOREIGN KEY (provider_id) REFERENCES providers (id)
);
```

**Typical Data**: Fundamentals for all active assets
**Bootstrap**: `data_service.bootstrap_fundamentals(limit=None)` - Can take time (one API call per asset)
**Index**: `idx_fundamentals_sector`, `idx_fundamentals_market_cap`

---

### 5. asset_prices

**Purpose**: Live and historical price snapshots
**Managers**: `TickerSnapshotManager` (single ticker), `MarketSnapshotManager` (bulk)
**Provider**: `PolygonSnapshotProvider` → `/v2/snapshot/locale/us/markets/stocks/tickers`

```sql
CREATE TABLE asset_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,

    -- Provider tracking
    provider_id INTEGER NOT NULL,
    provider_updated_at BIGINT,              -- Provider's timestamp (nanoseconds)
    trade_date DATE NOT NULL,

    -- Previous Day Data (reference price)
    prevday_close DECIMAL(12,4),             -- THE reference price for % change
    prevday_volume BIGINT,
    prevday_vwap DECIMAL(12,4),

    -- Current Day Regular Session
    day_open DECIMAL(12,4),
    day_high DECIMAL(12,4),
    day_low DECIMAL(12,4),
    day_close DECIMAL(12,4),                 -- Regular session close
    day_volume BIGINT,
    day_vwap DECIMAL(12,4),

    -- Last Minute Bar (real-time)
    min_timestamp BIGINT,
    min_close DECIMAL(12,4),                 -- Last traded price (any session)
    min_volume BIGINT,
    min_vwap DECIMAL(12,4),

    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (asset_id) REFERENCES assets (id),
    FOREIGN KEY (provider_id) REFERENCES providers (id),
    UNIQUE(asset_id, provider_id, provider_updated_at)
);
```

**Typical Data**: 50,000+ snapshots (grows over time)
**Update**: `data_service.refresh_market_data(symbols, force_refresh=False)`
**Index**: `idx_asset_prices_symbol`, `idx_asset_prices_asset`, `idx_asset_prices_date`

---

### 6. universes

**Purpose**: Asset grouping definitions
**Manager**: `UniverseManager` (with metadata tracking, TTL: 24 hours)
**Data Source**: Internal filtering (no API)

```sql
CREATE TABLE universes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,               -- 'default_universe', 'tech'
    description TEXT,

    -- Criteria (JSON)
    criteria TEXT,                           -- Filtering parameters

    -- Status
    is_active BOOLEAN DEFAULT TRUE,          -- Currently selected
    last_updated DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Typical Data**: 1-5 universe definitions
**Configuration**: `src/config/universe_config.py`
**Bootstrap**: `data_service.bootstrap_universes(universe_name="default_universe")`

---

### 7. universe_memberships

**Purpose**: Asset membership tracking
**Manager**: `UniverseManager`
**Data Source**: Internal (created during universe bootstrap)

```sql
CREATE TABLE universe_memberships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    universe_id INTEGER NOT NULL,
    asset_id INTEGER NOT NULL,

    -- Membership metadata
    added_date DATE NOT NULL,
    removed_date DATE,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,

    FOREIGN KEY (universe_id) REFERENCES universes (id),
    FOREIGN KEY (asset_id) REFERENCES assets (id),
    UNIQUE(universe_id, asset_id, added_date)
);
```

**Typical Data**: 7,000+ memberships for default_universe
**Index**: `idx_universe_memberships_universe`, `idx_universe_memberships_asset`

---

### 8. sentiment_types

**Purpose**: Sentiment event type definitions
**Manager**: `SentimentTypesManager` (no metadata tracking - static config)
**Data Source**: Hardcoded types

```sql
CREATE TABLE sentiment_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,               -- 'news_positive', 'news_negative'
    description TEXT,
    category TEXT,                           -- 'news', 'analyst', 'earnings'
    parameters TEXT,                         -- JSON: {"min_confidence": 0.7}
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Typical Data**: 3-10 predefined types
**Phase 1**: News sentiment only (news_positive, news_negative, news_neutral)
**Future**: Earnings events, analyst ratings
**Bootstrap**: `data_service.bootstrap_sentiment_types()`

---

### 9. sentiment_events

**Purpose**: Detected sentiment events
**Manager**: `SentimentEventsManager` (no metadata tracking - continuous creation)
**Provider**: `PolygonNewsProvider` → `/v2/reference/news`

```sql
CREATE TABLE sentiment_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    sentiment_type_id INTEGER NOT NULL,

    -- Event timing
    event_date DATE NOT NULL,
    event_time TIME,
    session TEXT CHECK(session IN ('premarket', 'regular', 'afterhours')),

    -- Event measurements
    value DECIMAL(12,4),                     -- Sentiment score, confidence
    magnitude TEXT CHECK(magnitude IN ('small', 'medium', 'large', 'extreme')),

    -- Additional context (JSON)
    details TEXT,                            -- {"title": "...", "source": "polygon"}

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (asset_id) REFERENCES assets (id),
    FOREIGN KEY (sentiment_type_id) REFERENCES sentiment_types (id)
);
```

**Typical Data**: Grows continuously as news/events detected
**Retention**: 90 days (cleanup, not TTL)
**Index**: `idx_sentiment_events_asset`, `idx_sentiment_events_type`, `idx_sentiment_events_date`

---

### 10. data_update_metadata

**Purpose**: Track bulk operation timestamps for TTL validation
**Manager**: `DataUpdateMetadataManager`

```sql
CREATE TABLE data_update_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Operation identification
    operation_type TEXT NOT NULL,            -- 'markets', 'fundamentals', 'market_snapshots'
    operation_subtype TEXT,                  -- 'bootstrap', 'refresh'

    -- Run metadata
    started_at DATETIME NOT NULL,
    completed_at DATETIME,

    -- Status
    status TEXT CHECK(status IN ('running', 'completed', 'failed', 'partial')),

    -- Statistics (JSON)
    stats TEXT,                              -- {"inserted": 1234, "updated": 456}

    -- Details
    total_items INTEGER,
    processed_items INTEGER DEFAULT 0,
    failed_items INTEGER DEFAULT 0,
    api_calls_made INTEGER DEFAULT 0,

    -- Context
    operation_params TEXT,                   -- JSON: {"symbol": "AAPL"}
    error_message TEXT,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Purpose**: Enables "did we already fetch all markets this week?" checks without scanning table
**Index**: `idx_data_update_operation`, `idx_data_update_completed`

---

### 11. market_holidays

**Purpose**: Market holiday calendar
**Manager**: `MarketHolidaysManager` (with metadata tracking, TTL: 30 days)
**Provider**: `PolygonMarketStatusProvider` → `/v1/marketstatus/upcoming`

```sql
CREATE TABLE market_holidays (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,            -- YYYY-MM-DD format
    name TEXT,                            -- Holiday name
    status TEXT NOT NULL                  -- 'closed' or 'early_close'
);
```

**Typical Data**: 12-15 upcoming holidays
**Update**: `data_service.get_market_holidays(force_refresh=False)` - Auto-refreshes when stale
**Query**: `data_service.get_upcoming_holidays(from_date=None)` - Get upcoming holidays only
**Index**: `idx_market_holidays_date`

**Note**: Polygon returns one holiday per exchange (NYSE, NASDAQ, etc.). We deduplicate by date since all US exchanges share the same holiday schedule.

---

### 12. market_context_cache

**Purpose**: Current market state/session context
**Manager**: `MarketContextManager` (with metadata tracking, TTL: 5 minutes)
**Provider**: `PolygonMarketStatusProvider` → `/v1/marketstatus/now`

```sql
CREATE TABLE market_context_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_code TEXT NOT NULL UNIQUE,     -- 'XNYS', 'XNAS', etc.
    context_data TEXT NOT NULL            -- Serialized MarketContext object (JSON)
);
```

**Typical Data**: 1-3 market contexts (NYSE, NASDAQ, etc.)
**Update**: `data_service.get_market_context(market_code, force_refresh=False)`
**Model**: `MarketContext` - Combines market info with current status (session, trading day, etc.)
**Index**: `idx_market_context_code`

**Note**: MarketContext requires coordination with `market_holidays` table to determine `is_trading_day`.

---

### 13. gap_results

**Purpose**: Store gap analysis results for historical review and strategy validation
**Manager**: `GapResultsManager` (no metadata tracking - discrete analysis runs)
**Data Source**: Internal gap analyzer

```sql
CREATE TABLE gap_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    analysis_timestamp TIMESTAMP NOT NULL,
    session_type TEXT NOT NULL,            -- 'premarket' or 'afterhours'
    trading_date DATE NOT NULL,

    -- Gap characteristics
    gap_percentage REAL NOT NULL,
    gap_direction TEXT NOT NULL,           -- 'up' or 'down'
    gap_type TEXT,                         -- 'full', 'partial', NULL

    -- Price snapshot at analysis time
    reference_price REAL NOT NULL,         -- prevday.c or day.c
    current_price REAL NOT NULL,           -- min.c at analysis time
    day_open REAL,
    day_high REAL,
    day_low REAL,
    day_close REAL,
    prevday_close REAL NOT NULL,
    prevday_high REAL,
    prevday_low REAL,

    -- Volume analysis
    extended_hours_volume INTEGER,
    previous_day_volume INTEGER,
    volume_ratio REAL,

    -- Market context
    market_cap REAL,
    sector TEXT,

    -- Quality assessment
    quality_score REAL,
    quality_tier TEXT,                     -- 'excellent', 'good', 'fair', 'poor'
    catalyst_score REAL,
    volume_score REAL,
    gap_size_score REAL,
    sector_alignment_score REAL,
    market_alignment_score REAL,

    -- Filter results
    passed_gap_filter BOOLEAN NOT NULL,
    passed_volume_filter BOOLEAN NOT NULL,
    passed_market_cap_filter BOOLEAN NOT NULL,
    passed_exhaustion_filter BOOLEAN NOT NULL,
    is_friday_gap BOOLEAN NOT NULL,

    -- Rejection details
    status TEXT NOT NULL,                  -- 'passed', 'rejected', 'warning'
    rejection_reason TEXT,

    -- News & sentiment
    news_count INTEGER,
    sentiment_score REAL,
    has_tier1_catalyst BOOLEAN,
    catalyst_description TEXT,

    -- Metadata
    min_timestamp BIGINT,
    data_freshness_hours REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (asset_id) REFERENCES assets(id)
);
```

**Typical Data**: Grows continuously with each `gap analyze` run (optional save)
**Query**: `./tradescout gap results --num-days=7 --status=passed`
**Index**: `idx_gap_results_analysis_timestamp`, `idx_gap_results_trading_date`, `idx_gap_results_session`, `idx_gap_results_status`, `idx_gap_results_quality`, `idx_gap_results_asset_id`

**Use Cases**:
- Historical gap review: "What gaps were found last week?"
- Strategy validation: "Do volume filters prevent bad setups?"
- Pattern analysis: "How often do Friday gaps get flagged?"

See [GAP_RESULTS.md](GAP_RESULTS.md) for query examples and use cases.

---

### 14. gap_performance_tracking

**Purpose**: Track actual intraday performance for gap candidates
**Manager**: `GapPerformanceManager` (no metadata tracking - historical snapshots)
**Provider**: `PolygonAggregatesProvider` → `/v2/aggs/ticker/{symbol}/range`

```sql
CREATE TABLE gap_performance_tracking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gap_result_id INTEGER NOT NULL UNIQUE,

    -- Intraday performance (9:30 AM - 4:00 PM ET)
    entry_price REAL,                      -- Open at 9:30 AM
    entry_timestamp TIMESTAMP,
    exit_price REAL,                       -- Close at 4:00 PM
    exit_timestamp TIMESTAMP,
    max_intraday_price REAL,               -- Day's high
    min_intraday_price REAL,               -- Day's low

    -- Performance metrics
    realized_return_pct REAL,              -- (exit - entry) / entry * 100
    max_drawdown_pct REAL,                 -- (min - entry) / entry * 100
    max_upside_pct REAL,                   -- (max - entry) / entry * 100
    gap_filled BOOLEAN,                    -- Price touched reference price?
    gap_fill_timestamp TIMESTAMP,

    -- Outcome classification
    outcome TEXT,                          -- 'winner', 'loser', 'breakeven'
    trade_taken BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (gap_result_id) REFERENCES gap_results(id) ON DELETE CASCADE
);
```

**Typical Data**: One record per gap result (after trading day completes)
**Update**: `./tradescout gap performance --date=2025-10-09` (on-demand)
**Index**: `idx_gap_performance_tracking_gap_result_id`, `idx_gap_performance_tracking_outcome`

**Session-Aware Date Logic**:
- **Premarket gap** (8:30 AM Oct 9) → Track Oct 9 regular hours (9:30-4:00 PM)
- **Afterhours gap** (5:00 PM Oct 9) → Track Oct 10 regular hours (9:30-4:00 PM)

**Outcome Classification**:
- **Winner**: realized_return_pct ≥ 2.0%
- **Loser**: realized_return_pct ≤ -1.0%
- **Breakeven**: Between -1.0% and 2.0%

See [GAP_PERFORMANCE.md](GAP_PERFORMANCE.md) for detailed design and examples.

---

### 15. fed_data

**Purpose**: Federal Reserve economic indicators for market context
**Manager**: `FedDataManager` (with metadata tracking, TTL: varies by data type)
**Provider**: `PolygonFedProvider` → `/v1/indicators/sma/{ticker}`

```sql
CREATE TABLE fed_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_type TEXT NOT NULL,               -- 'inflation', 'inflation_expectations', 'treasury_yields'
    observation_date TEXT NOT NULL,        -- YYYY-MM-DD format
    value REAL NOT NULL,                   -- Rate, yield, index, etc.
    details TEXT NOT NULL,                 -- JSON metadata
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    UNIQUE(data_type, observation_date)
);
```

**Typical Data**: Economic indicators updated periodically
**Update**: `./tradescout fed update --type=inflation`
**Index**: `idx_fed_data_type`, `idx_fed_data_date`, `idx_fed_data_type_date`

**Data Types**:
- **inflation**: CPI, PCE data
- **inflation_expectations**: Market-based expectations
- **treasury_yields**: 2Y, 10Y Treasury yields

**Use Cases**:
- Macro context for gap trading decisions
- Rate environment awareness
- Market regime classification

---

### 16. schema_versions

**Purpose**: Database migration tracking
**Managed by**: `database_initializer.py`

```sql
CREATE TABLE schema_versions (
    version TEXT PRIMARY KEY,
    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## Bootstrap Operations

### Dependency Chain

```
1. Providers (hardcoded)
   ↓
2. Markets (API fetch)
   ↓
3. Assets (API fetch, needs Markets + Providers)
   ↓
4. Fundamentals (API fetch, needs Assets)
   ↓
5. Universes (internal filtering, needs Assets + Fundamentals)
   ↓
6. Sentiment Types (hardcoded)
   ↓
7. Market Holidays (API fetch, independent)
```

### Bootstrap Commands

```python
from services.data_service import DataService

# Initialize
data_service = DataService(db_manager, update_tracker, polygon_api_key)

# 1. Providers (1 record)
data_service.bootstrap_providers()

# 2. Markets (7-12 exchanges)
data_service.bootstrap_markets(asset_class="stocks", locale="us")

# 3. Assets (~10,000 tickers)
data_service.bootstrap_assets(market="stocks", active=True)

# 4. Fundamentals (one API call per asset - can be slow)
data_service.bootstrap_fundamentals(limit=100)  # Or limit=None for all

# 5. Universes (filters existing assets)
data_service.bootstrap_universes(universe_name="default_universe")

# 6. Sentiment types (3 types for Phase 1)
data_service.bootstrap_sentiment_types()

# 7. Market Holidays (12-15 upcoming holidays)
data_service.get_market_holidays(force_refresh=True)
```

### TTL Configuration

**File**: `src/database/config/ttl_config.py`

```python
# Bootstrap operations
MARKETS_TTL_HOURS = 8760        # 1 year - markets rarely change
ASSETS_TTL_HOURS = 72           # 3 days - new listings happen
FUNDAMENTALS_TTL_HOURS = 168    # 1 week - fundamentals change periodically
UNIVERSES_TTL_HOURS = 24        # 1 day - membership can shift

# Snapshot operations
TICKER_SNAPSHOT_TTL_MINUTES = 15
MARKET_SNAPSHOT_TTL_MINUTES = 15

# Market status operations
MARKET_HOLIDAYS_TTL_DAYS = 30       # 30 days - holidays rarely change
MARKET_CONTEXT_TTL_MINUTES = 5      # 5 minutes - market state changes throughout day
```

---

## Performance & Indexing

### Critical Indexes

All critical indexes are created during schema initialization:

**Asset Lookups**:
- `idx_assets_symbol` - Fast symbol → asset resolution
- `idx_assets_market` - Filter by exchange
- `idx_assets_active` - Filter active tickers only

**Price Queries**:
- `idx_asset_prices_symbol` - Price lookups by ticker
- `idx_asset_prices_asset` - Price history for asset
- `idx_asset_prices_date` - Historical date queries

**Universe Filtering**:
- `idx_universe_memberships_universe` - Get all assets in universe
- `idx_universe_memberships_asset` - Find universe for asset
- `idx_fundamentals_sector` - Sector-based screening
- `idx_fundamentals_market_cap` - Market cap filtering

**Sentiment Queries**:
- `idx_sentiment_events_asset` - Events for specific ticker
- `idx_sentiment_events_type` - Events by type (news_positive, etc.)
- `idx_sentiment_events_date` - Events in date range

**Metadata Tracking**:
- `idx_data_update_operation` - Find last operation by type
- `idx_data_update_completed` - Sort by completion time

---

## Model Objects

All database operations use **immutable dataclasses** - no raw dicts or tuples.

**Models Location**: `src/models/`

**Available Models**:
- `Asset` - Stock ticker data
- `AssetFundamentals` - Company fundamentals
- `Market` - Exchange information
- `MarketHoliday` - Holiday calendar entries
- `MarketContext` - Current market state/session
- `Universe`, `UniverseMembership` - Universe management
- `TickerSnapshot`, `MarketSnapshot` - Price data
- `SentimentType`, `SentimentEvent` - Sentiment tracking
- `DataUpdateMetadata` - Operation metadata

**Example**:
```python
# Manager returns model object, not raw tuple
asset = asset_manager.get_entity_from_database("AAPL")
# asset is an Asset dataclass with: id, symbol, name, market_id, etc.

# Can check fields
if asset.is_active and asset.market_id == 1:
    # ...

# Immutable - can't accidentally mutate
# asset.symbol = "MSFT"  # Error: frozen dataclass
```

---

## Data Service Interface

**File**: `src/services/data_service.py`

The `DataService` class provides the public interface for all data operations:

```python
class DataService:
    """Orchestrates data access between managers and providers."""

    # Bootstrap operations
    def bootstrap_providers() -> int
    def bootstrap_markets(asset_class, locale) -> int
    def bootstrap_assets(market, active) -> int
    def bootstrap_fundamentals(limit) -> int
    def bootstrap_universes(universe_name) -> Dict[str, int]
    def bootstrap_sentiment_types() -> int

    # Get operations
    def get_asset(symbol, force_refresh) -> Optional[Asset]
    def get_fundamentals(symbol, force_refresh) -> Optional[AssetFundamentals]
    def get_market(market_code) -> Optional[Market]
    def get_ticker_snapshot(symbol, force_refresh) -> Optional[TickerSnapshot]
    def refresh_market_data(symbols, force_refresh) -> int
    def get_market_holidays(force_refresh) -> List[MarketHoliday]
    def get_upcoming_holidays(from_date) -> List[MarketHoliday]
    def get_market_context(market_code, force_refresh) -> Optional[MarketContext]
    def get_sentiment_events(asset_id, sentiment_type_id, start_date, end_date) -> List[SentimentEvent]

    # Statistics
    def get_asset_stats() -> dict
    def get_fundamentals_stats() -> dict
    def get_markets_stats() -> dict
    def get_market_holidays_stats() -> dict
    def get_market_context_stats() -> dict
    def get_sentiment_types_stats() -> dict
    def get_sentiment_events_stats() -> dict
```

---

## Summary

**Architecture**: Clean Manager/Provider separation
**Data Types**: Immutable model objects throughout
**Metadata Tracking**: Only for bulk/bootstrap operations
**Current Status**: 16 tables, 15 active managers, 7 API providers
**Market Status**: Market holidays and context fully integrated with Manager/Provider pattern
**Sentiment**: Phase 1 complete - infrastructure, managers, and PolygonNewsProvider all active
**Gap Analysis**: Complete gap results tracking and performance validation system

**Directory Structure**:
- **Managers**: `src/database/managers/` - Database CRUD operations
- **Providers**: `src/api/providers/` - External API integrations
- **Models**: `src/models/` - Immutable dataclasses
- **Service**: `src/services/data_service.py` - Public orchestration layer

**See Also**:
- `docs/BOOTSTRAPPING.md` - Bootstrap operations guide
- `docs/SENTIMENT.md` - Sentiment detection system
- `docs/ARCHITECTURE_MANAGERS.md` - Manager pattern details (future)
- `docs/ARCHITECTURE_API_PROVIDERS.md` - Provider pattern details (future)
