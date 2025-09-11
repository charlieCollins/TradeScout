-- Migration: Create Schema Aligned with Current Models
-- Version: 001
-- Date: 2025-09-09
-- Description: Create database schema that matches our current domain models

-- Markets table (represents Market model)
CREATE TABLE IF NOT EXISTS markets (
    id VARCHAR(20) PRIMARY KEY,  -- e.g., "NYSE", "NASDAQ", "CME"
    name VARCHAR(255) NOT NULL,  -- e.g., "New York Stock Exchange"
    market_type VARCHAR(20) NOT NULL,  -- "stock", "options", "futures", etc.
    timezone VARCHAR(50),
    country VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Assets table (represents Asset model)
CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol VARCHAR(20) NOT NULL UNIQUE,  -- Primary identifier
    name VARCHAR(255) NOT NULL,  -- Full company/asset name
    asset_type VARCHAR(30) NOT NULL,  -- snake_case enum values
    market_id VARCHAR(20) NOT NULL,  -- Foreign key to markets
    currency VARCHAR(10) NOT NULL,  -- Trading currency
    
    -- Optional identifiers
    isin VARCHAR(12),  -- International Securities ID
    cusip VARCHAR(10),  -- US securities ID
    
    -- Trading characteristics
    is_active BOOLEAN DEFAULT 1,
    min_order_size DECIMAL(15,6) DEFAULT 1.0,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (market_id) REFERENCES markets(id)
);

-- Market segments table (for Asset.segments relationship)
CREATE TABLE IF NOT EXISTS market_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE,  -- e.g., "large_cap", "tech_sector"
    description TEXT,
    segment_type VARCHAR(50),  -- "cap_size", "sector", "industry", etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Asset-segment relationship (many-to-many)
CREATE TABLE IF NOT EXISTS asset_segments (
    asset_id INTEGER NOT NULL,
    segment_id INTEGER NOT NULL,
    PRIMARY KEY (asset_id, segment_id),
    FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE,
    FOREIGN KEY (segment_id) REFERENCES market_segments(id) ON DELETE CASCADE
);

-- Price data table (represents PriceData model)
CREATE TABLE IF NOT EXISTS price_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    price DECIMAL(15,6) NOT NULL,
    volume BIGINT,
    
    -- Optional OHLC data
    open_price DECIMAL(15,6),
    high_price DECIMAL(15,6),
    low_price DECIMAL(15,6),
    
    -- Data source tracking
    source VARCHAR(50),  -- "polygon", "yfinance", etc.
    data_type VARCHAR(20),  -- "real_time", "historical", "delayed"
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (asset_id) REFERENCES assets(id),
    UNIQUE(asset_id, timestamp, source)  -- Prevent duplicate data points
);

-- Market quotes table (represents MarketQuote model - current/latest quotes)
CREATE TABLE IF NOT EXISTS market_quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    price_data_id INTEGER NOT NULL,
    market_status VARCHAR(20),  -- "open", "pre_market", "after_hours", etc.
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (asset_id) REFERENCES assets(id),
    FOREIGN KEY (price_data_id) REFERENCES price_data(id),
    UNIQUE(asset_id)  -- Only one current quote per asset
);

-- Fundamentals table (represents Fundamentals model)
CREATE TABLE IF NOT EXISTS fundamentals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    report_date DATE NOT NULL,
    
    -- Basic metrics
    market_cap DECIMAL(20,2),
    shares_outstanding BIGINT,
    
    -- Valuation ratios
    pe_ratio DECIMAL(8,2),
    pb_ratio DECIMAL(8,2),
    price_to_sales DECIMAL(8,2),
    
    -- Financial health
    debt_to_equity DECIMAL(8,2),
    current_ratio DECIMAL(8,2),
    
    -- Profitability
    roe DECIMAL(6,4),  -- Return on Equity
    roa DECIMAL(6,4),  -- Return on Assets
    gross_margin DECIMAL(6,4),
    operating_margin DECIMAL(6,4),
    net_margin DECIMAL(6,4),
    
    -- Growth metrics
    revenue_growth DECIMAL(6,4),
    earnings_growth DECIMAL(6,4),
    
    -- Per-share metrics
    earnings_per_share DECIMAL(10,4),
    book_value_per_share DECIMAL(10,4),
    dividend_per_share DECIMAL(10,4),
    dividend_yield DECIMAL(6,4),
    
    -- Risk metrics
    beta DECIMAL(6,4),
    
    data_source VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (asset_id) REFERENCES assets(id),
    UNIQUE(asset_id, report_date)
);

-- Market snapshots table (for bulk market data caching)
CREATE TABLE IF NOT EXISTS market_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_time TIMESTAMP NOT NULL,
    asset_id INTEGER NOT NULL,
    
    -- Current price info
    current_price DECIMAL(15,6),
    previous_close DECIMAL(15,6),
    change_amount DECIMAL(15,6),
    change_percent DECIMAL(8,4),
    
    -- Volume
    volume BIGINT,
    avg_volume BIGINT,
    
    -- Daily range
    day_open DECIMAL(15,6),
    day_high DECIMAL(15,6),
    day_low DECIMAL(15,6),
    
    -- Extended hours (if available)
    premarket_price DECIMAL(15,6),
    afterhours_price DECIMAL(15,6),
    
    -- Real-time minute bar (if available)
    minute_price DECIMAL(15,6),
    minute_timestamp BIGINT,
    minute_volume BIGINT,
    
    data_source VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (asset_id) REFERENCES assets(id),
    UNIQUE(snapshot_time, asset_id)
);

-- Insert default markets
INSERT OR IGNORE INTO markets (id, name, market_type, timezone, country) VALUES 
    ('NYSE', 'New York Stock Exchange', 'stock', 'America/New_York', 'US'),
    ('NASDAQ', 'NASDAQ Global Market', 'stock', 'America/New_York', 'US'),
    ('AMEX', 'American Stock Exchange', 'stock', 'America/New_York', 'US'),
    ('LSE', 'London Stock Exchange', 'stock', 'Europe/London', 'UK'),
    ('TSE', 'Tokyo Stock Exchange', 'stock', 'Asia/Tokyo', 'JP');

-- Insert default market segments
INSERT OR IGNORE INTO market_segments (name, description, segment_type) VALUES
    ('large_cap', 'Large capitalization stocks (>$10B market cap)', 'cap_size'),
    ('mid_cap', 'Mid capitalization stocks ($2B-$10B market cap)', 'cap_size'),
    ('small_cap', 'Small capitalization stocks (<$2B market cap)', 'cap_size'),
    ('technology', 'Technology sector stocks', 'sector'),
    ('healthcare', 'Healthcare sector stocks', 'sector'),
    ('financials', 'Financial sector stocks', 'sector'),
    ('energy', 'Energy sector stocks', 'sector'),
    ('consumer_discretionary', 'Consumer discretionary sector', 'sector'),
    ('industrials', 'Industrial sector stocks', 'sector'),
    ('materials', 'Materials sector stocks', 'sector'),
    ('utilities', 'Utilities sector stocks', 'sector'),
    ('real_estate', 'Real estate sector stocks', 'sector'),
    ('communication', 'Communication services sector', 'sector');

-- Universe tables for asset universe management
CREATE TABLE IF NOT EXISTS universes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Asset-Universe membership (many-to-many with proper foreign keys)
CREATE TABLE IF NOT EXISTS universe_memberships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    universe_id INTEGER NOT NULL,
    added_date DATE DEFAULT CURRENT_DATE,
    removed_date DATE NULL,
    reason TEXT,
    is_active BOOLEAN DEFAULT 1,
    FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE,
    FOREIGN KEY (universe_id) REFERENCES universes(id) ON DELETE CASCADE,
    UNIQUE(asset_id, universe_id)
);

-- Insert default universe
INSERT OR IGNORE INTO universes (name, description) VALUES 
    ('default_universe', 'US Common Stocks from major exchanges with standard filtering criteria');

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_assets_symbol ON assets(symbol);
CREATE INDEX IF NOT EXISTS idx_assets_market ON assets(market_id);
CREATE INDEX IF NOT EXISTS idx_assets_active ON assets(is_active);
CREATE INDEX IF NOT EXISTS idx_price_data_asset_time ON price_data(asset_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_price_data_timestamp ON price_data(timestamp);
CREATE INDEX IF NOT EXISTS idx_market_quotes_updated ON market_quotes(last_updated);
CREATE INDEX IF NOT EXISTS idx_fundamentals_asset_date ON fundamentals(asset_id, report_date);
CREATE INDEX IF NOT EXISTS idx_market_snapshots_time ON market_snapshots(snapshot_time);
CREATE INDEX IF NOT EXISTS idx_market_snapshots_asset ON market_snapshots(asset_id);

-- Universe table indexes
CREATE INDEX IF NOT EXISTS idx_universe_memberships_asset ON universe_memberships(asset_id);
CREATE INDEX IF NOT EXISTS idx_universe_memberships_universe ON universe_memberships(universe_id);
CREATE INDEX IF NOT EXISTS idx_universe_memberships_active ON universe_memberships(is_active);