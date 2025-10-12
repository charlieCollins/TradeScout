-- Migration: Add gap results tracking tables
-- Created: 2025-10-11
-- Purpose: Store gap analysis results for performance tracking and strategy validation

-- Primary table: gap_results
-- Stores every gap candidate evaluation from each analysis run
CREATE TABLE IF NOT EXISTS gap_results (
    -- Primary identification
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    analysis_timestamp TIMESTAMP NOT NULL,
    session_type TEXT NOT NULL,  -- 'premarket' or 'afterhours'
    trading_date DATE NOT NULL,

    -- Gap characteristics
    gap_percentage REAL NOT NULL,
    gap_direction TEXT NOT NULL,  -- 'up' or 'down'
    gap_type TEXT,  -- 'full', 'partial', NULL if not classified

    -- Price snapshot at analysis time
    reference_price REAL NOT NULL,  -- prevday.c or day.c depending on session
    current_price REAL NOT NULL,    -- min.c at analysis time
    day_open REAL,                   -- NULL if premarket
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
    quality_tier TEXT,  -- 'excellent', 'good', 'fair', 'poor'
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
    status TEXT NOT NULL,  -- 'passed', 'rejected', 'warning'
    rejection_reason TEXT,  -- NULL if passed, detailed reason if rejected

    -- News & sentiment
    news_count INTEGER,
    sentiment_score REAL,
    has_tier1_catalyst BOOLEAN,
    catalyst_description TEXT,  -- Brief summary of catalyst if any

    -- Metadata
    min_timestamp BIGINT,  -- Original Polygon min.t for data freshness tracking
    data_freshness_hours REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign keys
    FOREIGN KEY (asset_id) REFERENCES assets(id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_gap_results_analysis_timestamp ON gap_results(analysis_timestamp);
CREATE INDEX IF NOT EXISTS idx_gap_results_trading_date ON gap_results(trading_date);
CREATE INDEX IF NOT EXISTS idx_gap_results_session ON gap_results(session_type);
CREATE INDEX IF NOT EXISTS idx_gap_results_status ON gap_results(status);
CREATE INDEX IF NOT EXISTS idx_gap_results_quality ON gap_results(quality_tier);
CREATE INDEX IF NOT EXISTS idx_gap_results_asset_id ON gap_results(asset_id);

-- Supporting table: gap_result_news
-- Links gap results to news articles that influenced catalyst scoring
CREATE TABLE IF NOT EXISTS gap_result_news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gap_result_id INTEGER NOT NULL,
    news_headline TEXT NOT NULL,
    news_source TEXT,
    news_published_at TIMESTAMP,
    news_sentiment REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (gap_result_id) REFERENCES gap_results(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_gap_result_news_gap_result_id ON gap_result_news(gap_result_id);

-- Supporting table: gap_performance_tracking
-- Tracks actual performance after gap was identified (future enhancement)
CREATE TABLE IF NOT EXISTS gap_performance_tracking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gap_result_id INTEGER NOT NULL UNIQUE,

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
    gap_filled BOOLEAN,  -- Did price return to reference price?
    gap_fill_timestamp TIMESTAMP,

    -- Outcome classification
    outcome TEXT,  -- 'winner', 'loser', 'breakeven', 'not_traded'
    trade_taken BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (gap_result_id) REFERENCES gap_results(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_gap_performance_tracking_gap_result_id ON gap_performance_tracking(gap_result_id);
CREATE INDEX IF NOT EXISTS idx_gap_performance_tracking_outcome ON gap_performance_tracking(outcome);
