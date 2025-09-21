-- ==========================================
-- MARKET SNAPSHOT METADATA TABLE
-- ==========================================
-- Tracks market-wide snapshot update operations

CREATE TABLE IF NOT EXISTS market_snapshot_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Run metadata
    started_at DATETIME NOT NULL,
    completed_at DATETIME,

    -- Statistics
    total_symbols INTEGER NOT NULL,      -- Number of symbols attempted
    successful_updates INTEGER DEFAULT 0, -- Successfully updated
    failed_updates INTEGER DEFAULT 0,     -- Failed updates

    -- Status
    status TEXT CHECK(status IN ('running', 'completed', 'failed', 'partial')) DEFAULT 'running',

    -- Error tracking
    error_message TEXT,                   -- Error if failed

    -- API details
    api_calls_made INTEGER DEFAULT 0,     -- Number of API calls

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_snapshot_runs_completed ON market_snapshot_runs(completed_at);
CREATE INDEX idx_snapshot_runs_status ON market_snapshot_runs(status);