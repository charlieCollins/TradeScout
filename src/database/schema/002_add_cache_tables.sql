-- ==========================================
-- TradeScout Database Schema Update
-- Version: 002 - Add Cache Tables
-- ==========================================

-- ==========================================
-- MARKET CONTEXT CACHE
-- ==========================================
CREATE TABLE IF NOT EXISTS market_context_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_code TEXT NOT NULL UNIQUE,     -- 'XNYS', 'XNAS', etc.
    context_data TEXT NOT NULL            -- Serialized MarketContext object (JSON)
);

-- ==========================================
-- MARKET HOLIDAYS
-- ==========================================
CREATE TABLE IF NOT EXISTS market_holidays (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,            -- YYYY-MM-DD format
    name TEXT,                            -- Holiday name
    status TEXT NOT NULL                  -- 'closed' or 'early-close'
);

-- Create indexes for performance
CREATE INDEX idx_market_context_code ON market_context_cache(market_code);
CREATE INDEX idx_market_holidays_date ON market_holidays(date);

-- Insert schema version
INSERT INTO schema_versions (version, description)
VALUES ('002', 'Add cache tables for market context and holidays');