# TradeScout Database Schema

**Last Updated:** 2025-09-28
**Database:** SQLite
**Location:** `data/tradescout.db`
**Schema Version:** 001

## Overview

TradeScout uses SQLite with **11 core tables** for market data management, asset filtering, and operation tracking. The system supports typed models throughout and includes aggressive file-based caching for fundamentals data.

## Table Summary

| Table | Purpose | Status | Records (Typical) |
|-------|---------|--------|-------------------|
| **Core Data** | | | |
| assets | Stock universe from Polygon API | ✅ Active | 11,765 |
| asset_fundamentals | Company fundamentals (SIC, sector, market cap) | ✅ Active | 2 |
| asset_prices | Live/historical price data with sessions | ✅ Active | ~50,000+ |
| **Configuration** | | | |
| providers | Data source configuration | ✅ Active | 1 |
| markets | Exchange information | ✅ Active | 7 |
| **Universe Management** | | | |
| universes | Asset grouping definitions (default, tech, small_cap) | ✅ Active | 3 |
| universe_memberships | Asset membership in universes | ✅ Active | 7,521 |
| **Operation Tracking** | | | |
| data_update_metadata | All bootstrap/update operation tracking | ✅ Active | Variable |
| **Future Features** | | | |
| sentiment_types | Sentiment analysis categories | 📋 Schema Only | 0 |
| sentiment_events | Sentiment event tracking | 📋 Schema Only | 0 |
| **Versioning** | | | |
| schema_versions | Database schema version tracking | ✅ Active | 1 |

---

## Core Tables Detail

### 1. assets
Complete stock universe from Polygon API.

```sql
CREATE TABLE assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL UNIQUE,         -- 'AAPL', 'MSFT'
    name TEXT NOT NULL,                   -- 'Apple Inc.'
    market_id INTEGER NOT NULL,

    -- Asset classification
    asset_type TEXT CHECK(asset_type IN ('stock', 'etf', 'crypto', 'option', 'forex')) DEFAULT 'stock',
    asset_class TEXT CHECK(asset_class IN ('equity', 'commodity', 'currency', 'crypto', 'derivative')) DEFAULT 'equity',

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
```

**Data Source**: Polygon `/v3/reference/tickers` API
**Bootstrap**: `./tradescout database bootstrap-tickers`

### 2. asset_fundamentals
Company fundamentals data for sector classification and screening.

```sql
CREATE TABLE asset_fundamentals (
    asset_id INTEGER PRIMARY KEY,        -- One-to-one with assets table

    -- Company identification
    company_name TEXT,                   -- 'Apple Inc.' (for display)

    -- Business classification
    sector TEXT,                         -- 'Technology' (derived from SIC)
    industry TEXT,                       -- 'Consumer Electronics'
    sic_code TEXT,                       -- Standard Industrial Classification

    -- Key financials
    market_cap BIGINT,                   -- Market capitalization in cents
    shares_outstanding BIGINT,           -- Outstanding shares

    -- Additional metrics for screening
    avg_volume_30d BIGINT,               -- 30-day average volume
    beta DECIMAL(6,3),                   -- Beta coefficient
    pe_ratio DECIMAL(8,2),               -- Price to earnings ratio
    dividend_yield DECIMAL(6,4),         -- Annual dividend yield

    -- Data tracking
    provider_id INTEGER,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (asset_id) REFERENCES assets (id),
    FOREIGN KEY (provider_id) REFERENCES providers (id)
);
```

**Data Source**: Polygon `/v3/reference/tickers/{symbol}` API
**Bootstrap**: `./tradescout database bootstrap-fundamentals`
**Sector Mapping**: SIC code → GICS-like sectors via `src/config/sic_sector_mapping.py`

### 3. asset_prices
Live and historical price data with session awareness.

```sql
CREATE TABLE asset_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,                    -- Redundant but useful for queries

    -- Provider tracking
    provider_id INTEGER NOT NULL,
    provider_updated_at BIGINT,              -- Provider's 'updated' field (nanoseconds for Polygon)

    -- Trading date (derived from provider_updated)
    trade_date DATE NOT NULL,

    -- Previous Day Data (prevDay.* from snapshot)
    prevday_open DECIMAL(12,4),
    prevday_high DECIMAL(12,4),
    prevday_low DECIMAL(12,4),
    prevday_close DECIMAL(12,4),             -- THE reference price
    prevday_volume BIGINT,
    prevday_vwap DECIMAL(12,4),

    -- Current Day Regular Session (day.* from snapshot)
    day_open DECIMAL(12,4),
    day_high DECIMAL(12,4),
    day_low DECIMAL(12,4),
    day_close DECIMAL(12,4),                 -- Regular session close (4:00 PM)
    day_volume BIGINT,
    day_vwap DECIMAL(12,4),

    -- Last Minute Bar Data (min.* from snapshot)
    min_timestamp BIGINT,                    -- Timestamp (milliseconds)
    min_open DECIMAL(12,4),
    min_high DECIMAL(12,4),
    min_low DECIMAL(12,4),
    min_close DECIMAL(12,4),                 -- Last traded price (any session)
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
```

**Data Source**: Polygon `/v2/snapshot/locale/us/markets/stocks/tickers` API
**Update**: Market snapshot operations via screener commands

### 4. universes
Asset grouping definitions for different trading strategies.

```sql
CREATE TABLE universes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,           -- 'default_universe', 'tech', 'small_cap'
    description TEXT,

    -- Universe parameters
    min_market_cap BIGINT,
    min_volume BIGINT,
    max_assets INTEGER,                   -- Maximum number of assets in universe

    -- Status
    is_active BOOLEAN DEFAULT TRUE,       -- Currently selected universe
    last_updated DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Configuration**: `src/config/universe_config.py`
**Management**: `./tradescout universe` commands
**Bootstrap**: `./tradescout database bootstrap-universes`

### 5. universe_memberships
Asset membership tracking with historical data.

```sql
CREATE TABLE universe_memberships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    universe_id INTEGER NOT NULL,
    asset_id INTEGER NOT NULL,

    -- Membership metadata
    added_date DATE NOT NULL,
    removed_date DATE,
    reason TEXT,                         -- 'initial_load', 'market_cap_growth', 'delisted'

    -- Status
    is_active BOOLEAN DEFAULT TRUE,

    FOREIGN KEY (universe_id) REFERENCES universes (id),
    FOREIGN KEY (asset_id) REFERENCES assets (id),
    UNIQUE(universe_id, asset_id, added_date)
);
```

**Filtering Logic**: `src/bootstrapping/bootstrapper_universe.py`

### 6. data_update_metadata
Comprehensive tracking of all data operations.

```sql
CREATE TABLE data_update_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Operation identification
    operation_type TEXT NOT NULL,           -- 'fundamentals', 'tickers', 'snapshot', 'universe'
    operation_subtype TEXT,                 -- 'bootstrap', 'refresh', 'single_symbol'

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
```

**Purpose**: Track all bootstrap operations, API usage, success rates, and enable cache decisions
**Service**: `src/services/data_update_tracker.py`

### 7. providers
Data source configuration and API management.

```sql
CREATE TABLE providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,          -- Provider identifier
    display_name TEXT NOT NULL,          -- Human-readable name
    base_url TEXT,
    api_key_required BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Current Data**: Single Polygon.io provider entry

### 8. markets
Exchange and market information.

```sql
CREATE TABLE markets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,           -- 'NYSE', 'NASDAQ', 'CRYPTO'
    name TEXT NOT NULL,                   -- 'New York Stock Exchange'
    country TEXT DEFAULT 'US',
    timezone TEXT DEFAULT 'America/New_York',
    currency TEXT DEFAULT 'USD',

    -- Trading hours (in local timezone)
    premarket_start_time TIME,           -- '04:00:00'
    premarket_end_time TIME,              -- '09:30:00'
    regular_open_time TIME,               -- '09:30:00'
    regular_close_time TIME,              -- '16:00:00'
    afterhours_start_time TIME,           -- '16:00:00'
    afterhours_end_time TIME,             -- '20:00:00'

    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Current Data**: 7 major US exchanges from Polygon API

### 9-11. Future Tables
- **sentiment_types**: Sentiment analysis categories (schema only)
- **sentiment_events**: Sentiment event tracking (schema only)
- **schema_versions**: Database version tracking

---

## Data Flow & Operations

### Bootstrap Sequence
```bash
# 1. Initialize database
./tradescout database init

# 2. Bootstrap providers
./tradescout database bootstrap-providers

# 3. Bootstrap tickers (~11,765 assets)
./tradescout database bootstrap-tickers

# 4. Bootstrap fundamentals (~12,000 API calls)
./tradescout database bootstrap-fundamentals

# 5. Create universes (default_universe, tech, small_cap)
./tradescout database bootstrap-universes
```

### Universe Filtering
- **default_universe**: Basic filtering (US exchanges, active, clean symbols) → ~7,500 assets
- **tech**: Technology sector (SIC 35, 36, 38, 73) + min market cap → Hundreds of assets
- **small_cap**: Market cap $300M-$2B + min volume → ~200 assets

### Sector Classification
- **Source**: SIC codes from Polygon ticker overview
- **Mapping**: First 2 digits of SIC code → Broad sectors
- **Implementation**: `src/config/sic_sector_mapping.py`
- **Documentation**: `docs/SECTOR_CLASSIFICATION.md`

### Operation Tracking
- **All operations** logged in `data_update_metadata`
- **Staleness detection**: Automatic cache invalidation after 1 week
- **Progress tracking**: Real-time progress for long operations
- **History**: Complete operation history with success rates

---

## Performance & Indexing

### Critical Indexes
```sql
-- Asset lookups
CREATE INDEX idx_assets_symbol ON assets(symbol);
CREATE INDEX idx_assets_market ON assets(market_id);
CREATE INDEX idx_assets_active ON assets(is_active);

-- Price queries
CREATE INDEX idx_asset_prices_symbol ON asset_prices(symbol);
CREATE INDEX idx_asset_prices_asset ON asset_prices(asset_id);
CREATE INDEX idx_asset_prices_date ON asset_prices(trade_date);

-- Universe filtering
CREATE INDEX idx_universe_memberships_universe ON universe_memberships(universe_id);
CREATE INDEX idx_universe_memberships_asset ON universe_memberships(asset_id);

-- Fundamentals screening
CREATE INDEX idx_fundamentals_sector ON asset_fundamentals(sector);
CREATE INDEX idx_fundamentals_market_cap ON asset_fundamentals(market_cap);

-- Operation tracking
CREATE INDEX idx_data_update_operation ON data_update_metadata(operation_type);
CREATE INDEX idx_data_update_completed ON data_update_metadata(completed_at);
```

---

*This schema reflects the complete implemented system as of September 2025, including fundamentals integration, universe management, and comprehensive operation tracking.*