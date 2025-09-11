-- Migration: Create Market Snapshot Metadata Table
-- Version: 002
-- Date: 2025-09-09
-- Description: Add table to track when market snapshots were last retrieved for database caching

-- Market snapshot metadata table (tracks when full snapshots were last retrieved)
CREATE TABLE IF NOT EXISTS market_snapshot_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_type VARCHAR(50) NOT NULL, -- 'full_market', 'sector', etc.
    last_retrieved_at TIMESTAMP NOT NULL,
    symbols_count INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'success', -- 'success', 'partial', 'failed'
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(snapshot_type)
);

-- Index for performance
CREATE INDEX IF NOT EXISTS idx_snapshot_metadata_type ON market_snapshot_metadata(snapshot_type);
CREATE INDEX IF NOT EXISTS idx_snapshot_metadata_retrieved ON market_snapshot_metadata(last_retrieved_at);