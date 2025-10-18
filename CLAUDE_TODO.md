# TradeScout - TODO List

*Last updated: 2025-10-18 10:30*

## Active TODOs

**Testing (High Priority - NEXT SESSION):**
- [ ] **Test gap analyze during premarket/afterhours** - Verify complete workflow with database save works
- [ ] **Test screener commands during regular session** - Validate context-aware templates work correctly

**Testing (Low Priority):**
- [ ] Test context-aware screeners during regular trading session (9:30-4:00 PM) - Optional validation

**Code Quality (Optional):**
- [ ] Create unit tests for business logic files (gap_analyzer.py, gap_performance_calculator.py, sentiment_analyzer.py, screener_engine.py) - Would be significant work due to complex dependencies
- [ ] Audit CacheService - explain and document the cache-aside pattern implementation
- [ ] Audit force/force_refresh parameter support across all DataServiceV2 methods - ensure consistency

**Nice-to-Have Features:**
- [ ] Add WebSocketProgressReporter for real-time web UI updates

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
