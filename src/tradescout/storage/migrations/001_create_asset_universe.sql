-- Migration: Create Asset Universe Tables
-- Version: 001
-- Date: 2025-09-07
-- Description: Create tables for dynamic asset universe management

-- Asset metadata table
CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol VARCHAR(10) NOT NULL UNIQUE,
    name VARCHAR(255),
    asset_type VARCHAR(50) DEFAULT 'COMMON_STOCK',
    exchange VARCHAR(50),
    sector VARCHAR(100),
    industry VARCHAR(100),
    market_cap_millions REAL,
    avg_daily_volume INTEGER,
    is_active BOOLEAN DEFAULT 1,
    is_tradeable BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Asset universe membership table (which assets are in which universes)
CREATE TABLE IF NOT EXISTS universe_membership (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    universe_name VARCHAR(100) NOT NULL,
    added_date DATE DEFAULT CURRENT_DATE,
    removed_date DATE,
    is_active BOOLEAN DEFAULT 1,
    reason VARCHAR(255),
    FOREIGN KEY (asset_id) REFERENCES assets(id),
    UNIQUE(asset_id, universe_name)
);

-- Asset performance tracking table
CREATE TABLE IF NOT EXISTS asset_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    date DATE NOT NULL,
    gap_count INTEGER DEFAULT 0,
    successful_gaps INTEGER DEFAULT 0,
    total_gap_return REAL DEFAULT 0,
    avg_gap_size REAL,
    last_gap_date DATE,
    notes TEXT,
    FOREIGN KEY (asset_id) REFERENCES assets(id),
    UNIQUE(asset_id, date)
);

-- Universes configuration table
CREATE TABLE IF NOT EXISTS universes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    min_market_cap_millions REAL,
    min_avg_volume INTEGER,
    max_assets INTEGER,
    selection_criteria TEXT,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default universes
INSERT OR IGNORE INTO universes (name, description, min_market_cap_millions, min_avg_volume, max_assets) VALUES
    ('liquid_universe', 'High-volume liquid stocks for reliable market screening', 10000, 1000000, 1000),
    ('gap_trading', 'Stocks suitable for gap trading strategies', 1000, 500000, 500),
    ('small_cap', 'Small cap growth stocks', 100, 100000, 200),
    ('mega_cap', 'Mega cap stable stocks', 50000, 5000000, 100);

-- Historical price data table
CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    date DATE NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume BIGINT,
    vwap REAL,
    premarket_open REAL,
    premarket_close REAL,
    premarket_volume BIGINT,
    afterhours_open REAL,
    afterhours_close REAL,
    afterhours_volume BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (asset_id) REFERENCES assets(id),
    UNIQUE(asset_id, date)
);

-- Gap history table
CREATE TABLE IF NOT EXISTS gap_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    gap_date DATE NOT NULL,
    gap_type VARCHAR(20), -- 'up' or 'down'
    gap_size_percent REAL NOT NULL,
    gap_size_dollars REAL,
    previous_close REAL,
    open_price REAL,
    session_type VARCHAR(20), -- 'premarket', 'regular', 'afterhours'
    volume_at_open BIGINT,
    filled BOOLEAN DEFAULT 0,
    fill_time TIME,
    fill_price REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (asset_id) REFERENCES assets(id)
);

-- Market snapshot history table (for full market data snapshots)
CREATE TABLE IF NOT EXISTS market_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_time TIMESTAMP NOT NULL,
    asset_id INTEGER NOT NULL,
    price REAL,
    change_percent REAL,
    change_dollars REAL,
    volume BIGINT,
    day_open REAL,
    day_high REAL,
    day_low REAL,
    previous_close REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (asset_id) REFERENCES assets(id),
    UNIQUE(snapshot_time, asset_id)
);

-- Fundamental data history table
CREATE TABLE IF NOT EXISTS fundamental_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    report_date DATE NOT NULL,
    market_cap BIGINT,
    pe_ratio REAL,
    earnings_per_share REAL,
    dividend_yield REAL,
    beta REAL,
    shares_outstanding BIGINT,
    revenue_ttm BIGINT,
    profit_margin REAL,
    operating_margin REAL,
    return_on_equity REAL,
    debt_to_equity REAL,
    current_ratio REAL,
    book_value REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (asset_id) REFERENCES assets(id),
    UNIQUE(asset_id, report_date)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_assets_symbol ON assets(symbol);
CREATE INDEX IF NOT EXISTS idx_assets_active ON assets(is_active);
CREATE INDEX IF NOT EXISTS idx_universe_membership_active ON universe_membership(universe_name, is_active);
CREATE INDEX IF NOT EXISTS idx_asset_performance_date ON asset_performance(date);
CREATE INDEX IF NOT EXISTS idx_asset_performance_asset ON asset_performance(asset_id);
CREATE INDEX IF NOT EXISTS idx_price_history_date ON price_history(asset_id, date);
CREATE INDEX IF NOT EXISTS idx_gap_history_date ON gap_history(gap_date, asset_id);
CREATE INDEX IF NOT EXISTS idx_market_snapshots_time ON market_snapshots(snapshot_time);
CREATE INDEX IF NOT EXISTS idx_fundamental_history_date ON fundamental_history(asset_id, report_date);