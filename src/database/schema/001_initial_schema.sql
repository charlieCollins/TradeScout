-- ==========================================
-- TradeScout Database Schema
-- Version: 1.0
-- ==========================================

-- ==========================================
-- 1. PROVIDERS
-- ==========================================
CREATE TABLE IF NOT EXISTS providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,          -- Provider identifier
    display_name TEXT NOT NULL,          -- Human-readable name
    base_url TEXT,
    api_key_required BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================
-- 2. MARKETS
-- ==========================================
CREATE TABLE IF NOT EXISTS markets (
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

-- ==========================================
-- 3. ASSETS
-- ==========================================
CREATE TABLE IF NOT EXISTS assets (
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

CREATE INDEX idx_assets_symbol ON assets(symbol);
CREATE INDEX idx_assets_market ON assets(market_id);
CREATE INDEX idx_assets_type ON assets(asset_type);
CREATE INDEX idx_assets_active ON assets(is_active);

-- ==========================================
-- 4. ASSET FUNDAMENTALS
-- ==========================================
CREATE TABLE IF NOT EXISTS asset_fundamentals (
    asset_id INTEGER PRIMARY KEY,        -- One-to-one with assets table

    -- Company identification
    company_name TEXT,                   -- 'Apple Inc.' (for display)

    -- Business classification
    sector TEXT,                         -- 'Technology'
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

CREATE INDEX idx_fundamentals_sector ON asset_fundamentals(sector);
CREATE INDEX idx_fundamentals_industry ON asset_fundamentals(industry);
CREATE INDEX idx_fundamentals_market_cap ON asset_fundamentals(market_cap);

-- ==========================================
-- 5. ASSET PRICES (Snapshot-Based)
-- ==========================================
CREATE TABLE IF NOT EXISTS asset_prices (
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

CREATE INDEX idx_asset_prices_symbol ON asset_prices(symbol);
CREATE INDEX idx_asset_prices_asset ON asset_prices(asset_id);
CREATE INDEX idx_asset_prices_date ON asset_prices(trade_date);
CREATE INDEX idx_asset_prices_updated ON asset_prices(updated_at);

-- ==========================================
-- 6. UNIVERSES
-- ==========================================
CREATE TABLE IF NOT EXISTS universes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,           -- 'momentum', 'value', 'growth'
    description TEXT,

    -- Universe parameters
    min_market_cap BIGINT,
    min_volume BIGINT,
    max_assets INTEGER,                   -- Maximum number of assets in universe

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    last_updated DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================
-- 7. UNIVERSE MEMBERSHIPS
-- ==========================================
CREATE TABLE IF NOT EXISTS universe_memberships (
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

CREATE INDEX idx_universe_memberships_universe ON universe_memberships(universe_id);
CREATE INDEX idx_universe_memberships_asset ON universe_memberships(asset_id);
CREATE INDEX idx_universe_memberships_active ON universe_memberships(is_active);

-- ==========================================
-- 8. SENTIMENT TYPES
-- ==========================================
CREATE TABLE IF NOT EXISTS sentiment_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,           -- 'gap_up', 'gap_down', 'momentum_spike'
    description TEXT,
    category TEXT,                        -- 'price_action', 'volume', 'technical'

    -- Calculation parameters (JSON)
    parameters TEXT,                      -- '{"threshold": 0.02, "min_volume": 1000000}'

    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================
-- 9. SENTIMENT EVENTS
-- ==========================================
CREATE TABLE IF NOT EXISTS sentiment_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    sentiment_type_id INTEGER NOT NULL,

    -- Event details
    event_date DATE NOT NULL,
    event_time TIME,
    session TEXT CHECK(session IN ('premarket', 'regular', 'afterhours')),

    -- Event measurements
    value DECIMAL(12,4),                 -- Gap percentage, volume spike multiplier
    magnitude TEXT CHECK(magnitude IN ('small', 'medium', 'large', 'extreme')),

    -- Additional data (JSON)
    details TEXT,                         -- '{"prev_close": 100.50, "open": 103.75}'

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (asset_id) REFERENCES assets (id),
    FOREIGN KEY (sentiment_type_id) REFERENCES sentiment_types (id)
);

CREATE INDEX idx_sentiment_events_asset ON sentiment_events(asset_id);
CREATE INDEX idx_sentiment_events_type ON sentiment_events(sentiment_type_id);
CREATE INDEX idx_sentiment_events_date ON sentiment_events(event_date);

-- ==========================================
-- 10. DATA UPDATE METADATA
-- ==========================================
CREATE TABLE IF NOT EXISTS data_update_metadata (
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

CREATE INDEX idx_data_update_operation ON data_update_metadata(operation_type);
CREATE INDEX idx_data_update_completed ON data_update_metadata(completed_at);
CREATE INDEX idx_data_update_status ON data_update_metadata(status);

-- ==========================================
-- 11. SCHEMA VERSIONS
-- ==========================================
CREATE TABLE IF NOT EXISTS schema_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT NOT NULL UNIQUE,
    description TEXT,
    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================
-- CLEANUP: Remove any unused tables
-- ==========================================
DROP TABLE IF EXISTS data_lineage;
DROP TABLE IF EXISTS data_sources;
DROP TABLE IF EXISTS data_versions;
DROP TABLE IF EXISTS system_config;
DROP TABLE IF EXISTS system_metrics;
DROP TABLE IF EXISTS market_snapshot_runs;
DROP TABLE IF EXISTS market_snapshot_metadata;

-- Insert initial schema version
INSERT INTO schema_versions (version, description)
VALUES ('001', 'Complete schema with all core tables');


