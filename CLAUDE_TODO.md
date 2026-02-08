# TradeScout - TODO List

*Last updated: 2026-02-08*

## Active TODOs

**Testing (High Priority):**
- [ ] **Test gap analyze during premarket/afterhours** - Verify complete workflow with database save works
- [ ] **Test screener commands during regular session** - Validate context-aware templates work correctly

**Code Quality (Optional):**
- [ ] Create unit tests for business logic files (gap_analyzer.py, gap_performance_calculator.py, sentiment_analyzer.py, screener_engine.py)
- [ ] Audit CacheService - explain and document the cache-aside pattern implementation
- [ ] Audit force/force_refresh parameter support across all DataServiceV2 methods - ensure consistency

**Nice-to-Have Features:**
- [ ] Add WebSocketProgressReporter for real-time web UI updates

---

## Key Architecture Rules

- **Services:** DataServiceV2 (runtime operations) + BootstrapService (initialization/seeding)
- Repository (business queries) + SQLModel (ORM) + Provider (API)
- Cache-aside pattern with TTL management via CacheService
- Dual model system: Domain models (dataclasses) for business logic, SQLModel for database
- Template-based context-aware screeners (gainers_combined model)
- Volume fields: Only min has v+av, prevDay/day only have v
- Reference: `docs/ARCHITECTURE.md`, `docs/DATABASE.md`

## Recently Completed

**2026-02-08 SEC EDGAR Fundamentals Bootstrap:**
- Replaced per-ticker yfinance fundamentals (11K calls, 60-100 min) with SEC EDGAR bulk approach (~13 min)
- Created EdgarFundamentalsAdapter: bulk CIK mapping + XBRL shares + parallel SIC codes + batched yfinance prices
- Added from_edgar_data() to AssetFundamentals dataclass
- bootstrap-all now includes fundamentals (with interactive prompt) before universes
- bootstrap_providers registers all 6 active providers (nasdaq_trader, yfinance, finnhub, fred, pandas_market_calendars, edgar)

**2026-02 Provider Migration:**
- All 6 capabilities migrated from Polygon to free providers ($0/month)
- Full code + docs audit completed, all active Polygon refs cleaned
