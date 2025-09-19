-- TradeScout Complete Database Schema
-- Based on REFACTOR_SCREENER_APPROACH.md unified design
-- Date: 2025-09-18

-- ==========================================
-- 1. MARKETS & EXCHANGES
-- ==========================================

CREATE TABLE IF NOT EXISTS markets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,           -- 'XNYS', 'XNAS'
    name TEXT NOT NULL,                  -- 'New York Stock Exchange'
    country TEXT NOT NULL,               -- 'US'
    timezone TEXT NOT NULL,              -- 'America/New_York'
    currency TEXT NOT NULL,              -- 'USD'

    -- Trading hours (in market timezone)
    premarket_start_time TIME,           -- '04:00:00'
    premarket_end_time TIME,             -- '09:30:00'
    regular_open_time TIME NOT NULL,     -- '09:30:00'
    regular_close_time TIME NOT NULL,    -- '16:00:00'
    afterhours_start_time TIME,          -- '16:00:00'
    afterhours_end_time TIME,            -- '20:00:00'

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_markets_code ON markets(code);
CREATE INDEX idx_markets_active ON markets(is_active);


-- ==========================================
-- 2. ASSETS (TRADEABLE INSTRUMENTS)
-- ==========================================

CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,                -- 'AAPL'
    name TEXT,                           -- 'Apple Inc.' or 'SPDR S&P 500 ETF'
    market_id INTEGER NOT NULL,          -- Which exchange trades this

    -- Asset classification
    asset_type TEXT NOT NULL,            -- 'stock', 'etf', 'reit'
    asset_class TEXT NOT NULL,           -- 'equity', 'fixed_income', 'commodity'

    -- Trading details
    currency TEXT NOT NULL,              -- 'USD'
    lot_size INTEGER DEFAULT 1,          -- Minimum trading unit
    tick_size DECIMAL(10,6),             -- Minimum price movement

    -- Status and metadata
    is_active BOOLEAN DEFAULT TRUE,      -- Currently trading
    is_delisted BOOLEAN DEFAULT FALSE,   -- Delisted but may have historical data
    listing_date DATE,                   -- When asset started trading
    delisting_date DATE,                 -- When asset stopped trading (if applicable)

    -- Data tracking
    data_source TEXT,                    -- 'polygon', 'manual'
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (market_id) REFERENCES markets (id),
    UNIQUE(symbol, market_id)            -- Same symbol can exist on different markets
);

CREATE INDEX idx_assets_symbol ON assets(symbol);
CREATE INDEX idx_assets_market ON assets(market_id);
CREATE INDEX idx_assets_type ON assets(asset_type);
CREATE INDEX idx_assets_active ON assets(is_active);


-- ==========================================
-- 3. ASSET FUNDAMENTALS
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
    data_source TEXT,                    -- 'polygon', 'manual'
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (asset_id) REFERENCES assets (id)
);

CREATE INDEX idx_fundamentals_sector ON asset_fundamentals(sector);
CREATE INDEX idx_fundamentals_industry ON asset_fundamentals(industry);
CREATE INDEX idx_fundamentals_market_cap ON asset_fundamentals(market_cap);
CREATE INDEX idx_fundamentals_updated ON asset_fundamentals(last_updated);


-- ==========================================
-- 4. UNIFIED ASSET PRICING (Snapshot-Based)
-- ==========================================

CREATE TABLE IF NOT EXISTS asset_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    market_id INTEGER NOT NULL,
    trade_date DATE NOT NULL,

    -- Regular session data (from snapshot day.* fields)
    day_open DECIMAL(12,4),              -- day.o - Regular session open
    day_high DECIMAL(12,4),              -- day.h - Regular session high
    day_low DECIMAL(12,4),               -- day.l - Regular session low
    day_close DECIMAL(12,4),             -- day.c - Regular session close (4:00 PM)
    day_volume BIGINT,                   -- day.v - Regular session volume
    day_vwap DECIMAL(12,4),              -- day.vw - Regular session VWAP

    -- Current/Extended hours data (from snapshot min.* fields)
    current_price DECIMAL(12,4),         -- min.c - Current price (any session)
    current_timestamp BIGINT,            -- min.t - When current price occurred
    current_session TEXT,                -- Derived: 'premarket', 'regular', 'afterhours', 'closed'
    current_volume INTEGER,              -- min.v - Current minute volume

    -- Previous day reference (from snapshot prevDay.* fields)
    prev_close DECIMAL(12,4),            -- prevDay.c - Previous trading day close

    -- Metadata
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
    data_source TEXT DEFAULT 'polygon_snapshot',

    FOREIGN KEY (asset_id) REFERENCES assets (id),
    FOREIGN KEY (market_id) REFERENCES markets (id),

    -- One record per asset per trading day (UPSERT on each snapshot call)
    UNIQUE(asset_id, trade_date)
);

-- Optimized indexes for gap analysis
CREATE INDEX idx_asset_prices_asset_date ON asset_prices(asset_id, trade_date);
CREATE INDEX idx_asset_prices_session ON asset_prices(current_session);
CREATE INDEX idx_asset_prices_updated ON asset_prices(last_updated);


-- ==========================================
-- 5. UNIVERSES (ASSET GROUPINGS)
-- ==========================================

CREATE TABLE IF NOT EXISTS universes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,           -- 'default_universe', 'sp500', 'nasdaq100'
    description TEXT,                    -- 'Primary universe for gap analysis'

    -- Universe criteria (for documentation)
    criteria_description TEXT,           -- 'Large cap US equities, >$1B market cap'
    min_market_cap BIGINT,              -- Minimum market cap for inclusion
    max_market_cap BIGINT,              -- Maximum market cap (nullable)
    required_exchanges TEXT,             -- JSON array: ['XNYS', 'XNAS']
    required_asset_types TEXT,           -- JSON array: ['stock', 'etf', 'reit']

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    auto_update BOOLEAN DEFAULT FALSE,   -- Automatically update membership
    last_updated DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Universe membership (many-to-many: assets can be in multiple universes)
CREATE TABLE IF NOT EXISTS universe_memberships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    universe_id INTEGER NOT NULL,
    asset_id INTEGER NOT NULL,

    -- Membership metadata
    added_date DATE NOT NULL,            -- When asset was added to universe
    removed_date DATE,                   -- When asset was removed (nullable)
    reason TEXT,                         -- 'initial_load', 'market_cap_growth', 'delisted'

    -- Status
    is_active BOOLEAN DEFAULT TRUE,      -- Currently in universe

    FOREIGN KEY (universe_id) REFERENCES universes (id),
    FOREIGN KEY (asset_id) REFERENCES assets (id),
    UNIQUE(universe_id, asset_id, added_date)
);

CREATE INDEX idx_universe_memberships_universe ON universe_memberships(universe_id);
CREATE INDEX idx_universe_memberships_asset ON universe_memberships(asset_id);
CREATE INDEX idx_universe_memberships_active ON universe_memberships(is_active);


-- ==========================================
-- 6. SENTIMENT TRACKING
-- ==========================================

CREATE TABLE IF NOT EXISTS sentiment_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,           -- 'earnings_announcement', 'analyst_upgrade'
    category TEXT NOT NULL,              -- 'fundamental', 'technical', 'social'
    description TEXT,                    -- Human readable description

    -- Sentiment scoring
    default_weight DECIMAL(4,2) DEFAULT 1.0,  -- Default weight for this type
    impact_duration_hours INTEGER DEFAULT 24,  -- How long sentiment typically lasts

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sentiment_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    sentiment_type_id INTEGER NOT NULL,

    -- Event details
    event_date DATETIME NOT NULL,        -- When the event occurred
    event_source TEXT,                   -- 'reuters', 'twitter', 'sec_filing'
    event_title TEXT,                    -- 'Apple announces Q4 earnings beat'
    event_description TEXT,              -- Full text or summary
    event_url TEXT,                      -- Link to original source

    -- Sentiment scoring
    sentiment_score DECIMAL(4,2),        -- -1.0 (very negative) to +1.0 (very positive)
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (asset_id) REFERENCES assets (id),
    FOREIGN KEY (sentiment_type_id) REFERENCES sentiment_types (id)
);

CREATE INDEX idx_sentiment_events_asset_date ON sentiment_events(asset_id, event_date);
CREATE INDEX idx_sentiment_events_type ON sentiment_events(sentiment_type_id);
CREATE INDEX idx_sentiment_events_date ON sentiment_events(event_date);
CREATE INDEX idx_sentiment_events_score ON sentiment_events(sentiment_score);


-- ==========================================
-- 7. VERSIONING & DATA LINEAGE
-- ==========================================

CREATE TABLE IF NOT EXISTS data_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_number TEXT NOT NULL UNIQUE, -- 'v1.0.0', 'v1.1.0'
    description TEXT NOT NULL,           -- 'Initial schema', 'Added sentiment tracking'

    -- Schema changes
    schema_version TEXT NOT NULL,        -- 'schema_v1', 'schema_v2'
    migration_script TEXT,               -- SQL script that created this version

    -- Data changes
    data_sources_changed TEXT,           -- JSON array of affected data sources
    tables_affected TEXT,                -- JSON array of tables modified

    -- Deployment info
    deployed_at DATETIME NOT NULL,
    deployed_by TEXT,                    -- 'system', 'admin', 'migration_script'

    -- Validation
    validation_passed BOOLEAN DEFAULT FALSE,
    validation_notes TEXT,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS data_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,           -- 'polygon_api', 'yahoo_finance', 'manual_entry'
    description TEXT,                    -- Human readable description

    -- Source details
    source_type TEXT NOT NULL,           -- 'api', 'file', 'manual', 'calculated'
    base_url TEXT,                       -- For APIs
    api_version TEXT,                    -- API version if applicable
    rate_limit_per_minute INTEGER,       -- Rate limiting info

    -- Data quality
    reliability_score DECIMAL(4,2) DEFAULT 1.0,  -- 0.0 to 1.0
    latency_minutes INTEGER,             -- Typical data delay
    coverage_description TEXT,           -- What data this source provides

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    last_successful_update DATETIME,
    last_error_at DATETIME,
    last_error_message TEXT,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS data_lineage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,            -- 'asset_prices', 'sentiment_events'
    record_id INTEGER NOT NULL,          -- ID of the record in that table
    data_source_id INTEGER NOT NULL,     -- Which data source provided this

    -- Lineage details
    source_reference TEXT,               -- External ID, URL, or reference
    extraction_timestamp DATETIME NOT NULL, -- When we got the data
    processing_timestamp DATETIME NOT NULL, -- When we processed/stored it

    -- Processing info
    processing_method TEXT,              -- 'direct_api', 'batch_import', 'calculation'
    confidence_score DECIMAL(4,2) DEFAULT 1.0,  -- How confident we are in this data

    FOREIGN KEY (data_source_id) REFERENCES data_sources (id)
);

CREATE INDEX idx_data_lineage_table_record ON data_lineage(table_name, record_id);
CREATE INDEX idx_data_lineage_source ON data_lineage(data_source_id);
CREATE INDEX idx_data_lineage_timestamp ON data_lineage(extraction_timestamp);


-- ==========================================
-- 8. SYSTEM METADATA
-- ==========================================

CREATE TABLE IF NOT EXISTS system_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_key TEXT NOT NULL UNIQUE,     -- 'default_universe', 'gap_analysis_version'
    config_value TEXT NOT NULL,          -- Value (can be JSON)
    config_type TEXT NOT NULL,           -- 'string', 'integer', 'json', 'boolean'
    description TEXT,                    -- Human readable description

    -- Change tracking
    previous_value TEXT,                 -- Previous value before last change
    changed_at DATETIME,                 -- When it was last changed
    changed_by TEXT,                     -- Who changed it

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS system_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_date DATE NOT NULL,

    -- Database metrics
    total_assets INTEGER,                -- Number of assets in system
    total_price_records INTEGER,         -- Number of price records
    total_sentiment_events INTEGER,      -- Number of sentiment events

    -- Data freshness
    latest_price_data_date DATE,         -- Most recent price data
    price_data_staleness_hours INTEGER,  -- Hours since latest price data
    sentiment_data_staleness_hours INTEGER,

    -- Performance metrics
    avg_screener_query_ms INTEGER,       -- Average screener performance
    data_load_time_ms INTEGER,           -- Time to load reference data

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(metric_date)
);


-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT NOT NULL UNIQUE,        -- '001', '002', etc.
    description TEXT NOT NULL,           -- 'Initial schema', 'Added sentiment tracking'
    migration_file TEXT NOT NULL,        -- '001_initial_schema.sql'
    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Insert initial schema version
INSERT OR IGNORE INTO schema_versions (version, description, migration_file)
VALUES ('001', 'Complete schema - markets, assets, fundamentals, pricing, universes, sentiment, data lineage', '001_initial_schema.sql');