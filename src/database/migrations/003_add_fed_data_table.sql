-- Migration 003: Add fed_data table for Federal Reserve economic data
-- Created: 2025-10-10

CREATE TABLE IF NOT EXISTS fed_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_type TEXT NOT NULL,  -- 'inflation', 'inflation_expectations', 'treasury_yields'
    observation_date TEXT NOT NULL,  -- ISO format date (YYYY-MM-DD)
    value REAL NOT NULL,  -- The actual data value (rate, yield, index, etc.)
    details TEXT NOT NULL,  -- JSON blob with additional metadata
    created_at TEXT NOT NULL,  -- ISO format datetime
    updated_at TEXT NOT NULL,  -- ISO format datetime

    -- Unique constraint: one record per data type per observation date
    UNIQUE(data_type, observation_date)
);

-- Index for efficient queries by data type
CREATE INDEX IF NOT EXISTS idx_fed_data_type ON fed_data(data_type);

-- Index for efficient queries by observation date
CREATE INDEX IF NOT EXISTS idx_fed_data_date ON fed_data(observation_date);

-- Index for finding latest data by type
CREATE INDEX IF NOT EXISTS idx_fed_data_type_date ON fed_data(data_type, observation_date DESC);
