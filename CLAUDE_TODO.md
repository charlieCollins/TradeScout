# TradeScout - TODO List

*Last updated: 2025-10-15 08:35*

## Active TODOs

**Testing (High Priority - NEXT SESSION):**
- [ ] **Test gap analyze end-to-end** - Verify complete workflow with database save works after fixes
- [ ] **Test gap backtest command** - Verify historical performance tracking works
- [ ] **Test bootstrap commands after refactoring** - Verify BootstrapService works correctly for all 6 bootstrap operations
- [ ] **Explore Web API** - Try out endpoints at http://localhost:8000/docs with Swagger UI

**Testing (Low Priority):**
- [ ] Test context-aware screeners during regular trading session (9:30-4:00 PM) - Optional validation

**Code Quality (Optional):**
- [ ] Create unit tests for business logic files (gap_analyzer.py, gap_performance_calculator.py, sentiment_analyzer.py, screener_engine.py) - Would be significant work due to complex dependencies
- [ ] Audit CacheService - explain and document the cache-aside pattern implementation
- [ ] Audit force/force_refresh parameter support across all DataServiceV2 methods - ensure consistency
- [ ] **Reconcile date handling inconsistencies** - We have `market backfill <date>` command AND `--date` options in screener/gap commands, using inconsistent date formats and approaches

**Nice-to-Have Features:**
- [ ] Validate MarketContext dates are correct and used universally (display in both CLI and Web output)
- [ ] Add `--date` option to market update commands for backfilling historical data for specific dates
- [ ] Add POST endpoints to Web API for bootstrap operations (currently all GET)
- [ ] Follow Polygon API next_url for paginated news results
- [ ] **Web adapters need JSON output adapters** - Currently web layer has hardcoded/extracted output (not using presentation adapters)
- [ ] Add JSONOutputAdapter when Web API work begins
- [ ] Add WebSocketProgressReporter for real-time web UI updates
- [ ] Implement full strategy backtest with entry/exit rules per GAP_TRADING_STRATEGY.md
- [ ] Implement gap_candidate database schema enhancements (Phase 1 from GAP_RESULTS.md)

---

## 📝 Key Architecture Rules

- **Services:** DataServiceV2 (runtime operations) + BootstrapService (initialization/seeding)
- Repository (business queries) + SQLModel (ORM) + Provider (API)
- Cache-aside pattern with TTL management via CacheService
- Dual model system: Domain models (dataclasses) for business logic, SQLModel for database
- Template-based context-aware screeners (gainers_combined model)
- Volume fields: Only min has v+av, prevDay/day only have v
- Reference: `docs/ARCHITECTURE.md`, `docs/DATABASE.md`, `docs/POLYGON.md`

## ✅ Recently Completed

**2025-10-13 Bootstrap Service Refactoring:**
- Created BootstrapService (780 lines) - separates initialization from runtime operations
- Moved 6 bootstrap methods + 4 helpers from DataServiceV2 (removed 734 lines, 29% reduction)
- Updated all CLI commands to use BootstrapService
- Cache-aware fundamentals bootstrap: 99.2% cache hit rate (6,793 assets in 21s)
- Added sentiment types bootstrap command (seeds 4 standard types)
- Created WEB_PLANNING.md documentation for FastAPI server

**2025-10-13 Test Suite Cleanup:**
- Deleted 13 integration/complex test files (88% reduction: 25,620 → 2,944 lines)
- Updated all provider tests to work with dataclass models (NewsArticle, MarketStatusSnapshot, PriceBar)
- Verified repository tests are well-structured unit tests
- Final state: 8 test files (5 provider, 3 repository), all good unit tests
