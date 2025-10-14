# TradeScout Database Architecture

**Last Updated**: 2025-10-12
**Database**: SQLite
**Location**: `data/tradescout.db`
**Schema Version**: 004
**Architecture**: Repository + SQLModel + Cache-Aside Pattern

---

## Overview

TradeScout uses **SQLite with 16 tables** for market data management, sentiment tracking, gap analysis, and operation metadata. The system follows a **layered repository architecture** where:

- **Repositories** handle business-focused database queries
- **SQLModel** provides type-safe ORM mapping
- **Providers** handle external API calls
- **DataServiceV2** orchestrates between them
- **CacheService** implements cache-aside pattern with TTL

All data uses **dual model system**:
- **Domain models** (dataclasses) - lightweight, immutable business entities
- **SQLModel** (ORM) - type-safe database table representations

---

## Table Summary

| Table                      | Purpose | Repository | Provider | Status |
|----------------------------|---------|------------|----------|--------|
| **Reference Data**         |||||
| `providers`                | API provider configuration | ✅ ProviderRepository | - | ✅ Active |
| `markets`                  | Exchange information | ✅ MarketRepository | ✅ PolygonMarketsProvider | ✅ Active |
| `assets`                   | Stock ticker universe | ✅ AssetRepository | ✅ PolygonTickersProvider | ✅ Active |
| `asset_fundamentals`       | Company fundamentals | ✅ FundamentalsRepository | ✅ PolygonTickersProvider | ✅ Active |
| **Price Data**             |||||
| `asset_prices`             | Historical/live prices | ✅ AssetPriceRepository | ✅ PolygonSnapshotProvider<br>✅ PolygonAggregatesProvider | ✅ Active |
| **Universe Management**    |||||
| `universes`                | Asset groupings | ✅ UniverseRepository | - | ✅ Active |
| `universe_memberships`     | Membership tracking | ✅ UniverseRepository | - | ✅ Active |
| **Sentiment**              |||||
| `sentiment_types`          | Event type definitions | ✅ SentimentTypeRepository | - | ✅ Active |
| `sentiment_events`         | Detected events | ✅ SentimentEventRepository | ✅ PolygonNewsProvider | ✅ Active |
| **Gap Analysis**           |||||
| `gap_candidate`              | Gap candidate results | ✅ GapCandidateRepository | - | ✅ Active |
| `gap_candidate_result` | Gap performance metrics | ✅ GapCandidateResultRepository | ✅ PolygonAggregatesProvider | ✅ Active |
| `gap_result_news`          | Gap-related news | ✅ GapResultNewsRepository | ✅ PolygonNewsProvider | ✅ Active |
| **Economic Data**          |||||
| `fed_data`                 | Federal Reserve data | ✅ FedDataRepository | ✅ PolygonFedProvider | ✅ Active |
| **Market Status**          |||||
| `market_holidays`          | Holiday calendar | ✅ MarketHolidayRepository | ✅ PolygonMarketStatusProvider | ✅ Active |
| **Metadata**               |||||
| `data_update_metadata`     | Operation tracking | ✅ DataUpdateMetadataRepository | - | ✅ Active |
| **System**                 |||||
| `schema_versions`          | Schema migrations | ✅ System | - | ✅ Active |

**Total**: 16 tables

---

## Architecture: Repository + SQLModel Pattern

### Data Flow

```
User Request (CLI or FastAPI)
    ↓
DataServiceV2 (orchestration)
    ↓
┌──────────────────────────────────────────┐
│  CacheService (cache-aside)              │
│  - TTL freshness checks                  │
│  - Metadata tracking                     │
└──────────────────────────────────────────┘
    ↓                     ↓
Repository              Provider
(business queries)      (API calls)
    ↓                     ↓
SQLModel                Response parsing
(ORM mapping)           Rate limiting
    ↓                     ↓
SQLite ←─────────────────┘
Database          (store fresh data)
```

### Example: Get Asset Information

```python
# User calls DataServiceV2
asset = data_service.get_asset("AAPL", force_refresh=False)

# DataServiceV2 uses CacheService:
asset_sql = self.asset_cache.get_or_fetch(
    key="AAPL",
    fetch_fn=lambda: self._fetch_and_convert_asset("AAPL"),
    force_refresh=False
)

# CacheService coordinates:
# 1. Check metadata: Is data fresh? (< 7 days TTL)
# 2. If fresh: Repository.get_by_symbol("AAPL") → return cached
# 3. If stale:
#    a. Call fetch_fn() → Provider fetches from API
#    b. Convert domain model → SQLModel
#    c. Repository.save(asset_sql)
#    d. MetadataRepository.record_update("tickers")
# 4. Return AssetSQLModel

# Repository handles database queries:
repository = AssetRepository(session)
cached_asset = repository.get_by_symbol("AAPL")

# Provider handles API:
provider = PolygonTickersProvider(api_key)
fresh_asset = provider.fetch_ticker_details("AAPL")  # Returns Asset domain model
```

### When to Use Metadata Tracking

**USE `data_update_metadata` for**:
- ✅ **Bulk operations**: Bootstrap operations (7k+ tickers at once)
- ✅ **TTL-based caching**: Check if data category is stale
- ✅ **Operation tracking**: Monitor long-running processes
- ✅ **Statistics**: Track API calls, success/failure rates

**DON'T USE for**:
- ❌ Single entity updates (use updated_at column on entity table)
- ❌ Real-time queries (check entity's updated_at directly)

---

## Core Tables

### Reference Data

#### `providers`

API provider configuration and tracking.

```sql
CREATE TABLE providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,           -- Provider identifier
    display_name TEXT NOT NULL,           -- Human-readable name
    base_url TEXT,
    api_key_required BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Domain Model**: `Provider` (dataclass)
**SQLModel**: `ProviderSQLModel`
**Repository**: `ProviderRepository`

**Key Methods**:
- `get_by_name(name: str)` - Get provider by identifier
- `get_active_provider()` - Get first active provider (typically Polygon)
- `save(provider: ProviderSQLModel)` - Persist provider

**Current Providers**:
- `polygon` - Polygon.io (primary provider)

---

#### `markets`

Exchange and trading venue information.

```sql
CREATE TABLE markets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,            -- 'XNAS', 'XNYS', 'CRYPTO'
    name TEXT NOT NULL,                    -- 'NASDAQ', 'NYSE'
    country TEXT DEFAULT 'US',
    timezone TEXT DEFAULT 'America/New_York',
    currency TEXT DEFAULT 'USD',

    -- Trading hours (in local timezone)
    premarket_start_time TIME,             -- '04:00:00'
    premarket_end_time TIME,                -- '09:30:00'
    regular_open_time TIME,                 -- '09:30:00'
    regular_close_time TIME,                -- '16:00:00'
    afterhours_start_time TIME,             -- '16:00:00'
    afterhours_end_time TIME,               -- '20:00:00'

    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Domain Model**: `Market` (dataclass)
**SQLModel**: `MarketSQLModel`
**Repository**: `MarketRepository`
**Provider**: `PolygonMarketsProvider`

**Key Methods**:
- `get_by_code(code: str)` - Get market by MIC code (e.g., 'XNAS')
- `find_all_active()` - Get all active markets
- `save(market: MarketSQLModel)` - Persist market
- `bulk_save(markets: List[MarketSQLModel])` - Bulk persist

**Bootstrap**: `./tradescout database bootstrap-markets`

---

#### `assets`

Stock ticker universe with classification and status tracking.

```sql
CREATE TABLE assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL UNIQUE,          -- 'AAPL', 'MSFT'
    name TEXT NOT NULL,                    -- 'Apple Inc.'
    market_id INTEGER NOT NULL,

    -- Asset classification
    asset_type TEXT CHECK(asset_type IN (
        'stock', 'etf', 'reit', 'fund', 'warrant',
        'right', 'unit', 'bond', 'adr', 'other'
    )) DEFAULT 'stock',
    asset_class TEXT CHECK(asset_class IN (
        'equity', 'fixed_income', 'commodity'
    )) DEFAULT 'equity',

    -- Trading details
    currency TEXT DEFAULT 'USD',
    lot_size INTEGER DEFAULT 1,
    tick_size DECIMAL(10,6),

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    is_delisted BOOLEAN DEFAULT FALSE,
    listing_date DATE,
    delisting_date DATE,

    -- Provider reference
    provider_id INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (market_id) REFERENCES markets (id),
    FOREIGN KEY (provider_id) REFERENCES providers (id)
);

CREATE INDEX idx_assets_symbol ON assets(symbol);
CREATE INDEX idx_assets_market ON assets(market_id);
CREATE INDEX idx_assets_type ON assets(asset_type);
CREATE INDEX idx_assets_active ON assets(is_active);
```

**Domain Model**: `Asset` (dataclass)
**SQLModel**: `AssetSQLModel`
**Repository**: `AssetRepository`
**Provider**: `PolygonTickersProvider`

**Key Methods**:
- `get_by_id(id: int)` - Get asset by database ID
- `get_by_symbol(symbol: str)` - Get asset by ticker symbol
- `find_all_active(limit: Optional[int])` - Get active assets
- `find_by_market(market_id: int)` - Get assets for exchange
- `bulk_save(assets: List[AssetSQLModel])` - Bulk persist
- `count_active()` - Count active assets
- `get_stats()` - Get asset statistics (by type, etc.)

**Bootstrap**: `./tradescout database bootstrap-assets`
**Typical Count**: ~11,000 active US stocks/ETFs

---

#### `asset_fundamentals`

Company fundamental data for screening and analysis.

```sql
CREATE TABLE asset_fundamentals (
    asset_id INTEGER PRIMARY KEY,         -- One-to-one with assets table

    -- Company identification
    company_name TEXT,                     -- 'Apple Inc.' (for display)

    -- Business classification
    sector TEXT,                           -- 'Technology'
    industry TEXT,                         -- 'Consumer Electronics'
    sic_code TEXT,                         -- Standard Industrial Classification

    -- Key financials
    market_cap BIGINT,                     -- Market capitalization in cents
    shares_outstanding BIGINT,             -- Outstanding shares

    -- Additional metrics for screening
    avg_volume_30d BIGINT,                 -- 30-day average volume
    beta DECIMAL(6,3),                     -- Beta coefficient
    pe_ratio DECIMAL(8,2),                 -- Price to earnings ratio
    dividend_yield DECIMAL(6,4),           -- Annual dividend yield

    -- Data tracking
    provider_id INTEGER,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (asset_id) REFERENCES assets (id),
    FOREIGN KEY (provider_id) REFERENCES providers (id)
);

CREATE INDEX idx_fundamentals_sector ON asset_fundamentals(sector);
CREATE INDEX idx_fundamentals_industry ON asset_fundamentals(industry);
CREATE INDEX idx_fundamentals_market_cap ON asset_fundamentals(market_cap);
```

**Domain Model**: `AssetFundamentals` (dataclass)
**SQLModel**: `FundamentalsSQLModel`
**Repository**: `FundamentalsRepository`
**Provider**: `PolygonTickersProvider` (from ticker details endpoint)

**Key Methods**:
- `get_by_asset_id(asset_id: int)` - Get fundamentals for asset
- `bulk_upsert(fundamentals: List[FundamentalsSQLModel])` - Bulk insert/update
- `find_by_sector(sector: str)` - Get assets in sector
- `count_total()` - Count total fundamentals records

**Bootstrap**: `./tradescout database bootstrap-fundamentals`
**Typical Count**: ~7,000 (not all assets have fundamentals)

---

### Price Data

#### `asset_prices`

Historical and real-time price snapshots from Polygon.

```sql
CREATE TABLE asset_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,                  -- Redundant but useful for queries

    -- Provider tracking
    provider_id INTEGER NOT NULL,
    provider_updated_at BIGINT,            -- Provider's 'updated' field (nanoseconds)

    -- Trading date (derived from provider_updated)
    trade_date DATE NOT NULL,

    -- Previous Day Data (prevDay.* from snapshot)
    prevday_open DECIMAL(12,4),
    prevday_high DECIMAL(12,4),
    prevday_low DECIMAL(12,4),
    prevday_close DECIMAL(12,4),           -- THE reference price
    prevday_volume BIGINT,
    prevday_vwap DECIMAL(12,4),

    -- Current Day Regular Session (day.* from snapshot)
    day_open DECIMAL(12,4),
    day_high DECIMAL(12,4),
    day_low DECIMAL(12,4),
    day_close DECIMAL(12,4),               -- Regular session close (4:00 PM)
    day_volume BIGINT,
    day_vwap DECIMAL(12,4),

    -- Last Minute Bar Data (min.* from snapshot)
    min_timestamp BIGINT,                  -- Timestamp (milliseconds)
    min_open DECIMAL(12,4),
    min_high DECIMAL(12,4),
    min_low DECIMAL(12,4),
    min_close DECIMAL(12,4),               -- Last traded price (any session)
    min_volume BIGINT,
    min_vwap DECIMAL(12,4),
    min_accumulated_volume BIGINT,
    min_num_trades INTEGER,

    -- Metadata
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (asset_id) REFERENCES assets (id),
    FOREIGN KEY (provider_id) REFERENCES providers (id),

    -- One record per asset per provider per fetch
    UNIQUE(asset_id, provider_id, provider_updated_at)
);

CREATE INDEX idx_asset_prices_symbol ON asset_prices(symbol);
CREATE INDEX idx_asset_prices_asset ON asset_prices(asset_id);
CREATE INDEX idx_asset_prices_date ON asset_prices(trade_date);
CREATE INDEX idx_asset_prices_updated ON asset_prices(updated_at);
```

**Domain Model**: `AssetPrice` (dataclass)
**SQLModel**: `AssetPriceSQLModel`
**Repository**: `AssetPriceRepository`
**Provider**: `PolygonSnapshotProvider`, `PolygonAggregatesProvider`

**Key Methods**:
- `get_latest_by_asset_id(asset_id: int)` - Get most recent price
- `get_latest_by_symbol(symbol: str)` - Get most recent price by symbol
- `bulk_save(prices: List[AssetPriceSQLModel])` - Bulk persist prices
- `find_by_date_range(start_date, end_date)` - Get prices in range

**Usage**: Gap analysis, screening, portfolio tracking

---

### Universe Management

#### `universes`

Asset groupings based on criteria (momentum, value, growth, etc.).

```sql
CREATE TABLE universes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,             -- 'momentum', 'value', 'growth'
    description TEXT,

    -- Universe parameters
    min_market_cap BIGINT,
    min_volume BIGINT,
    max_assets INTEGER,                     -- Maximum number of assets in universe

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    last_updated DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### `universe_memberships`

Tracks which assets belong to which universes.

```sql
CREATE TABLE universe_memberships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    universe_id INTEGER NOT NULL,
    asset_id INTEGER NOT NULL,

    FOREIGN KEY (universe_id) REFERENCES universes (id),
    FOREIGN KEY (asset_id) REFERENCES assets (id),
    UNIQUE(universe_id, asset_id)          -- Each asset once per universe
);

CREATE INDEX idx_universe_memberships_universe ON universe_memberships(universe_id);
CREATE INDEX idx_universe_memberships_asset ON universe_memberships(asset_id);
```

**Domain Models**: `Universe`, `UniverseMembership` (dataclasses)
**SQLModel**: `UniverseSQLModel`, `UniverseMembershipSQLModel`
**Repository**: `UniverseRepository`

**Key Methods**:
- `get_by_name(name: str)` - Get universe by name
- `find_all_active()` - Get all active universes
- `get_memberships(universe_id: int)` - Get assets in universe
- `bulk_add_memberships(memberships: List[UniverseMembershipSQLModel])` - Bulk add
- `clear_memberships(universe_id: int)` - Clear all memberships
- `get_statistics(universe_id: int)` - Get universe stats

**Bootstrap**: `./tradescout database bootstrap-universes`

---

### Sentiment Tracking

#### `sentiment_types`

Event type definitions for sentiment tracking.

```sql
CREATE TABLE sentiment_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,             -- 'gap_up', 'gap_down', 'momentum_spike'
    description TEXT,
    category TEXT,                          -- 'price_action', 'volume', 'technical'

    -- Calculation parameters (JSON)
    parameters TEXT,                        -- '{"threshold": 0.02, "min_volume": 1000000}'

    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### `sentiment_events`

Detected sentiment events with measurements.

```sql
CREATE TABLE sentiment_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    sentiment_type_id INTEGER NOT NULL,

    -- Event details
    event_date DATE NOT NULL,
    event_time TIME,
    session TEXT CHECK(session IN ('premarket', 'regular', 'afterhours')),

    -- Event measurements
    value DECIMAL(12,4),                   -- Gap percentage, volume spike multiplier
    magnitude TEXT CHECK(magnitude IN ('small', 'medium', 'large', 'extreme')),

    -- Additional data (JSON)
    details TEXT,                           -- '{"prev_close": 100.50, "open": 103.75}'
    external_id TEXT,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (asset_id) REFERENCES assets (id),
    FOREIGN KEY (sentiment_type_id) REFERENCES sentiment_types (id)
);

CREATE INDEX idx_sentiment_events_asset ON sentiment_events(asset_id);
CREATE INDEX idx_sentiment_events_type ON sentiment_events(sentiment_type_id);
CREATE INDEX idx_sentiment_events_date ON sentiment_events(event_date);
CREATE UNIQUE INDEX idx_sentiment_events_unique_external
  ON sentiment_events(asset_id, sentiment_type_id, external_id)
  WHERE external_id IS NOT NULL;
```

**Domain Models**: `SentimentType`, `SentimentEvent` (dataclasses)
**SQLModel**: `SentimentTypeSQLModel`, `SentimentEventSQLModel`
**Repositories**: `SentimentTypeRepository`, `SentimentEventRepository`
**Provider**: `PolygonNewsProvider`

---

### Gap Analysis

#### `gap_candidate`

Gap candidate analysis results with quality scores and filtering.

```sql
CREATE TABLE gap_candidate (
    -- Primary identification
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    analysis_timestamp TIMESTAMP NOT NULL,
    session_type TEXT NOT NULL,            -- 'premarket' or 'afterhours'
    trading_date DATE NOT NULL,

    -- Gap characteristics
    gap_percentage REAL NOT NULL,
    gap_direction TEXT NOT NULL,           -- 'up' or 'down'
    gap_type TEXT,                          -- 'full', 'partial', NULL

    -- Price snapshot at analysis time
    reference_price REAL NOT NULL,         -- prevday.c or day.c
    current_price REAL NOT NULL,           -- min.c at analysis time
    day_open REAL,                          -- NULL if premarket
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
    min_timestamp BIGINT,                  -- Polygon min.t
    data_freshness_hours REAL,
    academic_gap_type TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (asset_id) REFERENCES assets(id)
);

CREATE INDEX idx_gap_candidate_analysis_timestamp ON gap_candidate(analysis_timestamp);
CREATE INDEX idx_gap_candidate_trading_date ON gap_candidate(trading_date);
CREATE INDEX idx_gap_candidate_session ON gap_candidate(session_type);
CREATE INDEX idx_gap_candidate_status ON gap_candidate(status);
CREATE INDEX idx_gap_candidate_quality ON gap_candidate(quality_tier);
CREATE INDEX idx_gap_candidate_asset_id ON gap_candidate(asset_id);
```

**Domain Model**: `GapCandidate` (dataclass)
**SQLModel**: `GapResultSQLModel`
**Repository**: `GapCandidateRepository`

**Key Methods**:
- `find_by_session(session_type: str, trading_date: date)` - Get gaps for session
- `find_passed_gaps(trading_date: date)` - Get all passed gaps
- `bulk_save(gaps: List[GapResultSQLModel])` - Bulk persist
- `get_statistics(trading_date: date)` - Get gap analysis stats

**Usage**: `./tradescout gap analyze`, `./tradescout gap report`

---

#### `gap_candidate_result`

Performance tracking for gap trades (intraday and multi-day).

```sql
CREATE TABLE gap_candidate_result (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gap_candidate_id INTEGER NOT NULL UNIQUE,

    -- Intraday performance (same day)
    entry_price REAL,
    entry_timestamp TIMESTAMP,
    exit_price REAL,
    exit_timestamp TIMESTAMP,
    max_intraday_price REAL,
    min_intraday_price REAL,

    -- Performance metrics
    realized_return_pct REAL,
    max_drawdown_pct REAL,
    max_upside_pct REAL,
    gap_filled BOOLEAN,                    -- Did price return to reference?
    gap_fill_timestamp TIMESTAMP,

    -- Outcome classification
    outcome TEXT,                           -- 'winner', 'loser', 'breakeven', 'not_traded'
    trade_taken BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (gap_candidate_id) REFERENCES gap_candidate(id) ON DELETE CASCADE
);

CREATE INDEX idx_gap_candidate_result_gap_candidate_id ON gap_candidate_result(gap_candidate_id);
CREATE INDEX idx_gap_candidate_result_outcome ON gap_candidate_result(outcome);
```

**Domain Model**: `GapPerformance` (dataclass)
**SQLModel**: `GapPerformanceTrackingSQLModel`
**Repository**: `GapCandidateResultRepository`
**Provider**: `PolygonAggregatesProvider` (for performance data)

---

#### `gap_result_news`

News articles associated with gap results.

```sql
CREATE TABLE gap_result_news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gap_candidate_id INTEGER NOT NULL,
    news_headline TEXT NOT NULL,
    news_source TEXT,
    news_published_at TIMESTAMP,
    news_sentiment REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (gap_candidate_id) REFERENCES gap_candidate(id) ON DELETE CASCADE
);

CREATE INDEX idx_gap_result_news_gap_candidate_id ON gap_result_news(gap_candidate_id);
```

**SQLModel**: `GapResultNewsSQLModel`
**Repository**: `GapResultNewsRepository`
**Provider**: `PolygonNewsProvider`

---

### Economic Data

#### `fed_data`

Federal Reserve economic indicators (inflation, yields, etc.).

```sql
CREATE TABLE fed_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_type TEXT NOT NULL,               -- 'inflation', 'inflation_expectations', 'treasury_yields'
    observation_date TEXT NOT NULL,        -- ISO format date (YYYY-MM-DD)
    value REAL NOT NULL,                    -- The actual data value (rate, yield, index)
    details TEXT NOT NULL,                  -- JSON blob with additional metadata
    created_at TEXT NOT NULL,               -- ISO format datetime
    updated_at TEXT NOT NULL,               -- ISO format datetime

    -- Unique constraint: one record per data type per observation date
    UNIQUE(data_type, observation_date)
);

CREATE INDEX idx_fed_data_type ON fed_data(data_type);
CREATE INDEX idx_fed_data_date ON fed_data(observation_date);
CREATE INDEX idx_fed_data_type_date ON fed_data(data_type, observation_date DESC);
```

**Domain Model**: `FedData` (dataclass)
**SQLModel**: `FedDataSQLModel`
**Repository**: `FedDataRepository`
**Provider**: `PolygonFedProvider`

**Key Methods**:
- `get_latest_by_type(data_type: str)` - Get most recent observation
- `find_by_date_range(data_type: str, start_date, end_date)` - Get time series
- `bulk_upsert(fed_data: List[FedDataSQLModel])` - Bulk insert/update

**Bootstrap**: `./tradescout fed update`

---

### Market Status

#### `market_holidays`

Market holiday calendar for determining trading days.

```sql
CREATE TABLE market_holidays (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,             -- YYYY-MM-DD format
    name TEXT,                              -- Holiday name
    status TEXT NOT NULL                    -- 'closed' or 'early-close'
);

CREATE INDEX idx_market_holidays_date ON market_holidays(date);
```

**Domain Model**: `MarketHoliday` (dataclass)
**SQLModel**: `MarketHolidaySQLModel`
**Repository**: `MarketHolidayRepository`
**Provider**: `PolygonMarketStatusProvider`

**Key Methods**:
- `find_upcoming(limit: int)` - Get upcoming holidays
- `is_holiday(date: date)` - Check if date is holiday
- `clear_all()` - Clear all holidays (before refresh)
- `bulk_save(holidays: List[MarketHolidaySQLModel])` - Bulk persist

**Bootstrap**: `./tradescout database bootstrap-market-holidays`

---

### Metadata

#### `data_update_metadata`

Operation tracking for bootstrap/refresh operations with statistics.

```sql
CREATE TABLE data_update_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Operation identification
    operation_type TEXT NOT NULL,          -- 'fundamentals', 'tickers', 'snapshot', 'universe'
    operation_subtype TEXT,                -- 'bootstrap', 'refresh', 'single_symbol'

    -- Run metadata
    started_at DATETIME NOT NULL,
    completed_at DATETIME,

    -- Status tracking
    status TEXT CHECK(status IN ('running', 'completed', 'failed', 'partial')) DEFAULT 'running',

    -- Statistics (JSON for flexibility)
    stats TEXT,                             -- JSON: '{"inserted": 1234, "updated": 456, "errors": 2}'

    -- Operation details
    total_items INTEGER,                    -- symbols, assets, etc.
    processed_items INTEGER DEFAULT 0,
    failed_items INTEGER DEFAULT 0,
    api_calls_made INTEGER DEFAULT 0,

    -- Additional context
    operation_params TEXT,                  -- JSON: '{"symbol": "AAPL", "force": true, "limit": 100}'
    error_message TEXT,

    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_data_update_operation ON data_update_metadata(operation_type);
CREATE INDEX idx_data_update_completed ON data_update_metadata(completed_at);
CREATE INDEX idx_data_update_status ON data_update_metadata(status);
```

**Domain Model**: `DataUpdateMetadata` (dataclass)
**SQLModel**: `DataUpdateMetadataSQLModel`
**Repository**: `DataUpdateMetadataRepository`

**Key Methods**:
- `get_latest_by_operation(operation_type: str)` - Get last update time (for TTL)
- `record_update(operation_type: str, subtype: str)` - Record operation completion
- `find_recent(limit: int)` - Get recent operations
- `get_running_operations()` - Get currently running operations

**Usage**: TTL validation, operation tracking, statistics

---

## Table Relationships

```
providers (1) ──< (many) assets
markets (1) ──< (many) assets
assets (1) ──< (many) asset_prices
assets (1) ──── (1) asset_fundamentals
assets (many) >──< (many) universes  [via universe_memberships]
assets (1) ──< (many) sentiment_events
sentiment_types (1) ──< (many) sentiment_events
assets (1) ──< (many) gap_candidate
gap_candidate (1) ──── (1) gap_candidate_result
gap_candidate (1) ──< (many) gap_result_news
```

---

## Data Flow Example: Gap Analysis

1. **User runs**: `./tradescout gap analyze premarket`

2. **DataServiceV2.analyze_gaps()**:
   - Get active universe assets: `UniverseRepository.get_memberships()`
   - Fetch market snapshots: `PolygonSnapshotProvider.fetch_market_snapshot()`
   - Store prices: `AssetPriceRepository.bulk_save()`

3. **GapAnalyzer**:
   - Calculate gaps
   - Score quality
   - Apply filters

4. **Save results**: `GapCandidateRepository.bulk_save()`

5. **Display**: CLI shows gap candidates with quality scores

---

## Performance Considerations

### Indexes

All key query paths have indexes:
- Symbol lookups: `idx_assets_symbol`
- Active asset filtering: `idx_assets_active`
- Date range queries: `idx_asset_prices_date`
- Gap analysis: `idx_gap_candidate_trading_date`, `idx_gap_candidate_session`

### Bulk Operations

Repositories support bulk operations for efficiency:
- `bulk_save()` - Bulk insert/update
- `bulk_upsert()` - Bulk insert with conflict resolution
- Batch size: Typically 100-1000 records

### TTL-Based Caching

Cache-aside pattern reduces API calls:
- Assets: 7-day TTL
- Fundamentals: 7-day TTL
- Market holidays: 30-day TTL
- Snapshots: 5-minute TTL (real-time data)

---

## Schema Evolution

### Migration Strategy

TradeScout uses incremental schema migrations:

**Location**: `database/migrations/`

**Tracking**: `schema_versions` table

**Process**:
1. Write migration SQL script
2. Update `schema_versions`
3. Run migration via `DatabaseManager.run_migrations()`

**Current Version**: 004

**Migration History**:
- v001: Initial schema
- v002: Add gap analysis tables
- v003: Add sentiment tracking
- v004: Add gap performance tracking + news

---

## Backup and Recovery

### Backup Strategy

```bash
# Daily backup
cp data/tradescout.db data/backups/tradescout_$(date +%Y%m%d).db

# Compress older backups
gzip data/backups/tradescout_*.db
```

### Recovery

```bash
# Restore from backup
cp data/backups/tradescout_20251012.db data/tradescout.db
```

### Data Freshness

Check last update times:
```bash
./tradescout database stats
```

Shows:
- Assets count + last update
- Fundamentals count + last update
- Universe memberships
- Recent operations

---

## Summary

**Architecture**: Repository + SQLModel + Cache-Aside Pattern
**Tables**: 16 tables covering reference, price, sentiment, gap analysis, and metadata
**Repositories**: 16 repositories with business-focused queries
**Providers**: 7 Polygon API providers
**Domain Models**: Dual model system (dataclass + SQLModel)
**Caching**: TTL-based cache-aside pattern
**Migration**: Incremental schema evolution with versioning

**Key Strengths**:
- Type-safe throughout (SQLModel + Python type hints)
- Business-focused queries (repositories speak domain language)
- Generic caching (works for any entity)
- Clean separation (providers don't touch database, repositories don't call APIs)
- Comprehensive tracking (metadata for all operations)
