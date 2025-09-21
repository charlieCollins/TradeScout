-- ==========================================
-- REMOVE UNUSED TABLES
-- ==========================================
-- Remove unused tables that are not being used

DROP TABLE IF EXISTS data_lineage;
DROP TABLE IF EXISTS data_versions;
DROP TABLE IF EXISTS data_sources;
DROP TABLE IF EXISTS system_config;
DROP TABLE IF EXISTS system_metrics;