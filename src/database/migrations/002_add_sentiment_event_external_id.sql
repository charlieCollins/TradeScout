-- ==========================================
-- Migration: Add external_id to sentiment_events
-- Version: 002
-- Description: Add external_id column and unique constraint to prevent duplicate sentiment events
-- ==========================================

-- Add external_id column for tracking external references (article_id, analyst_report_id, etc.)
ALTER TABLE sentiment_events ADD COLUMN external_id TEXT;

-- Create unique constraint on (asset_id, sentiment_type_id, external_id)
-- This prevents storing the same news article/event multiple times for the same asset
CREATE UNIQUE INDEX idx_sentiment_events_unique_external
ON sentiment_events(asset_id, sentiment_type_id, external_id)
WHERE external_id IS NOT NULL;

-- Update schema version
INSERT INTO schema_versions (version, description)
VALUES ('002', 'Add external_id to sentiment_events with unique constraint');
