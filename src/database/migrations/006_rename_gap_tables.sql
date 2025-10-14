-- Migration 006: Rename gap tables for semantic clarity
-- Date: 2025-10-13
-- Description: Rename gap_results → gap_candidate and gap_performance_tracking → gap_candidate_result
--              to better reflect domain concepts (candidate = identified opportunity, result = performance outcome)

-- Rename gap_results table to gap_candidate
ALTER TABLE gap_results RENAME TO gap_candidate;

-- Rename gap_performance_tracking table to gap_candidate_result
ALTER TABLE gap_performance_tracking RENAME TO gap_candidate_result;

-- Update foreign key column name in gap_candidate_result for consistency
-- SQLite doesn't support ALTER COLUMN RENAME directly, but since we're just renaming the table
-- the foreign key column gap_result_id now logically references gap_candidate.id
-- The column will be renamed in the SQLModel definition and application code

-- Note: SQLite renames are atomic and preserve all indexes, constraints, and triggers
