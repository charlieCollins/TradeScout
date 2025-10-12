-- Migration: Add academic gap type classification
-- Created: 2025-10-11
-- Purpose: Store academic gap type classification (Common, Breakaway/Continuation, Exhaustion)

-- Add academic_gap_type field to gap_results
ALTER TABLE gap_results ADD COLUMN academic_gap_type TEXT;

-- Possible values:
-- 'common' - <2.0% gaps (noise, should be filtered out)
-- 'breakaway_continuation' - 2.0-4.9% gaps (can't differentiate without trend analysis)
-- 'exhaustion_candidate' - ≥5.0% gaps (possible exhaustion, requires trend confirmation)

-- Note: Full academic classification requires:
--   - Breakaway: Gap at end of consolidation period
--   - Continuation: Gap within established trend
--   - Exhaustion: Gap at end of extended trend (≥20 days)
-- These require historical price trend analysis not yet implemented.
