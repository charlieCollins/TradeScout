# TradeScout - TODO List

*Last updated: 2025-10-11*

## 🎯 Current Focus: Gap Analysis Enhancement & Web Frontend Preparation

### Recent Completions (2025-10-11 - Gap Display & Academic Classification)
- ✅ **Gap display refactoring**: Extracted all display logic into dedicated classes
  - Created src/output/gap_display.py (GapAnalysisDisplay, GapPerformanceDisplay)
  - Reduced gap_commands.py by 245 lines (19% reduction)
  - Follows ScreenerDisplay pattern - ready for JSON adapters
- ✅ **Academic gap type classification**: Full implementation
  - Database migration 005: added academic_gap_type field
  - classify_academic_gap_type() in gap_analyzer.py
  - Classification: common (<2%), breakaway_continuation (2-5%), exhaustion_candidate (≥5%)
  - Integrated into analysis workflow and backtest statistics
  - Backfilled 36 existing records
- ✅ **Command rename**: gap performance → gap backtest
  - Clarified this is strategy validation, not trade tracking
  - Updated all help text, display headers, examples
- ✅ **Documentation updates**: docs/GAP_BACKTEST.md (renamed from GAP_PERFORMANCE.md)
  - Added section explaining simplified vs full strategy backtest
  - Updated implementation status (phases 1-3 complete)

### Recent Completions (2025-10-10 Evening - Documentation Cleanup)
- ✅ Deleted obsolete docs/GAP_TRADING_PLANNING.md (work is complete)
- ✅ Deleted docs/GAP_CANDIDATES_IDENTIFIED.md (migrated to GAP_RESULTS.md)
- ✅ Created docs/planning/GAP_RESULTS.md - Complete database architecture for gap results
- ✅ Added historical gap candidates to GAP_RESULTS.md (62 candidates, 3 sessions)
- ✅ **GETTING_STARTED.md completely rewritten** - Accurate, concise, current
  - Removed deleted screener references (only gainers/losers_combined remain)
  - Updated config to YAML (configs/universes/*.yaml)
  - Added gap analyze documentation
  - Removed deleted doc references
  - Reduced from 610 to 457 lines (25% shorter)

### Recent Completions (2025-10-10 Morning - Config Migration & Gap Analyzer Refactor)
- ✅ **Premarket volume validation completed**: Confirmed min.av works during premarket (0-97% variance)
- ✅ Updated POLYGON_VOLUME_FIELDS.md with Oct 10 premarket confirmation test
- ✅ Enhanced gap analyze output - Added sentiment score and news count columns
- ✅ **Database TTL config migrated to YAML**: configs/database_ttl.yaml
  - Updated 10 manager files to use config loader
  - Deleted src/database/config/ directory
- ✅ **Gap trading config created**: configs/gap_trading.yaml with all strategy settings
- ✅ **Gap analyzer fully refactored**: All magic numbers removed, config-driven
- ✅ **Gap models properly structured**: Created src/models/gap.py
  - GapCandidate, GapDirection, GapSignificance, RiskLevel
  - Helper properties: is_validated, has_catalyst, is_scored
- ✅ Gap trading strategy now fully tunable via YAML

### Recent Completions (2025-10-09 Afternoon - Config Migration & After-Hours Testing)
- ✅ **CRITICAL DISCOVERY**: Polygon snapshot min.av FREEZES at day.v during after-hours (100% confirmation, 15 symbols tested)
- ✅ **After-hours testing completed**: Ran gap analyze (50 candidates, 0 passed) and validate volume (all showed 0 vs Aggregates showing actual volume)
- ✅ Updated POLYGON_VOLUME_FIELDS.md with Oct 9 after-hours test evidence
- ✅ E*TRADE API evaluated - Not suitable for market data (documented in ETRADE.md)
- ✅ Enhanced validate volume command - Shows "N/A" for after-hours snapshot (was misleading "0")
- ✅ **MAJOR CONFIG MIGRATION**: Converted all Python configs to YAML in top-level configs/
  - Created configs/universes/*.yaml (4 universe configs)
  - Created configs/sic_sector_mapping.yaml
  - Created configs/market_context_rules.yaml with corrected volume mappings
  - Implemented src/utils/config_loader.py with singleton and helper functions
  - Updated 6 files to use YAML loader (data_service, CLI, models)
  - Deleted src/config/ directory
  - All imports tested successfully ✅

### Recent Completions (2025-10-09 Morning - Gap Trading Automation & Screener Cleanup)
- ✅ **MAJOR REFACTOR**: Rebuilt gap_analyzer.py with new architecture (find_gap_candidates, calculate_volume_ratio, calculate_quality_score)
- ✅ Created automated `gap analyze` command - Implements complete manual workflow
- ✅ Tested gap analyze with premarket data - 377 candidates, 0 passed volume filter (correct)
- ✅ Verified manual workflow vs automated command produce identical results
- ✅ **SCREENER CLEANUP**: Deleted 10 non-context-aware screeners
- ✅ Created losers_combined.yaml (context-aware across all sessions)
- ✅ Verified gainers_combined correctly excludes volume from Stage 1 filtering
- ✅ **NEW ARCHITECTURE**: 2 context-aware screeners replace 10+ session-specific screeners

### Recent Completions (2025-10-08 - Volume Validation Architecture Refactor)
- ✅ **MAJOR DISCOVERY**: Identified Polygon snapshot vs aggregates volume discrepancy root cause (trade eligibility rules)
- ✅ **MAJOR REFACTOR**: Implemented two-stage screening architecture (price → volume validation)
- ✅ Created SCREENER_VOLUME_VALIDATION.md planning document
- ✅ Refactored gainers_premarket.yaml to use volume_validation section
- ✅ Implemented ScreenerEngine._validate_volume() method using Aggregates API
- ✅ Updated POLYGON_VOLUME_FIELDS.md with trade eligibility explanation
- ✅ **TESTED SUCCESSFULLY**: Ran gainers_premarket during live session (50 candidates → 11 validated)
- ✅ Validated premarket min.av reliability (6-38% variance vs Aggregates API - acceptable for screening)
- ✅ Clarified after-hours formula: `min.av - day.v` (JUST after-hours session volume)
- ✅ Implemented `tradescout validate volume` command with proper architecture
- ✅ Added PolygonAggregatesProvider to DataService (fetch_minute_bars, calculate_extended_hours_volume)

### Recent Completions (2025-10-07 Evening - Context-Aware Screeners)
- ✅ Created TemplateResolver class with template parsing and resolution
- ✅ Implemented gainers_combined.yaml - First context-aware screener
- ✅ Updated ScreenerEngine to accept market_context and resolve templates
- ✅ Updated ScreenerDisplay for context-specific columns
- ✅ Fixed volume field mappings (min_accumulated_volume for premarket)
- ✅ Documented volume fields in POLYGON_VOLUME_FIELDS.md
- ✅ Renamed Polygon docs to POLYGON_* prefix
- ✅ Reorganized POLYGON.md (API ref) and POLYGON_IMPLEMENTATION.md (usage)

### Recent Completions (2025-10-07 Afternoon - After-Hours Gap Analysis)
- ✅ Implemented PolygonAggregatesProvider for accurate extended hours volume
- ✅ Fixed CRITICAL gap calculation error (after-hours uses day.c, not prevday.c)
- ✅ Completed corrected after-hours analysis (28 candidates, all failed volume test)
- ✅ Documented min.av field limitation (unreliable during after-hours)

### Recent Completions (2025-10-06 - News & Sentiment)
- ✅ Implemented `asset news <symbol>` command
- ✅ Created SentimentAnalyzer with score calculation
- ✅ Completed gap candidate validation using sentiment + volume

### Active TODOs

**Gap Results Database Implementation:**
- [ ] Create database migration for gap_results tables
- [ ] Create src/database/managers/gap_results_manager.py
- [ ] Integrate gap analyze command with database storage
- [ ] Migrate historical gap candidates (62 from GAP_RESULTS.md) to database
- [ ] Create `tradescout gap results` query command

**Testing & Validation:**
- [x] Run `gap analyze` during after-hours (4-8 PM) - COMPLETED (50 candidates, 0 passed volume)
- [x] Run `validate volume` during after-hours (4-8 PM) - COMPLETED (discovered min.av freeze issue)
- [x] Run `validate volume` during premarket - COMPLETED (confirmed min.av works, 0-97% variance)
- [ ] Test context-aware screeners during regular session (9:30-4:00 PM)
- [ ] Test context-aware screeners during closed session (outside market hours)

**Future Screeners (Use Context-Aware Template):**
- [ ] Create momentum_combined.yaml - Session-aware momentum detection
- [ ] Create volume_combined.yaml - Session-aware volume spikes
- [ ] All new screeners must use gainers_combined.yaml template approach

**Architecture & Cleanup:**
- [ ] Follow Polygon API next_url for paginated news results
- [x] Move config files from src/config to top-level configs/ - COMPLETED (all configs now YAML)
- [x] Database TTL config migration - COMPLETED (configs/database_ttl.yaml)
- [x] Gap trading config creation - COMPLETED (configs/gap_trading.yaml)
- [x] Gap analyzer refactor - COMPLETED (no magic numbers, models in src/models/gap.py)
- [x] E*TRADE API evaluation - COMPLETED (not suitable for market data, see ETRADE.md)
- [x] Documentation cleanup - COMPLETED (deleted obsolete docs, rewrote GETTING_STARTED.md)

### Future/Optional
- [ ] Add JSONOutputAdapter when Web API work begins
- [ ] Add ReportOutputAdapter for CSV/PDF generation
- [ ] Add WebSocketProgressReporter for real-time web UI updates

---

## 📝 Key Architecture Rules

- Manager (storage/TTL) + Provider (API) + DataService (orchestration)
- Template-based context-aware screeners (gainers_combined model)
- Volume fields: Only min has v+av, prevDay/day only have v
- Reference: `docs/POLYGON.md`, `docs/POLYGON_IMPLEMENTATION.md`, `docs/POLYGON_VOLUME_FIELDS.md`
