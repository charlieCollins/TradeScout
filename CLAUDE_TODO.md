# TradeScout - TODO List

*Last updated: 2025-10-12*

## Active TODOs

**Testing (Low Priority):**
- [ ] Test context-aware screeners during regular trading session (9:30-4:00 PM) - Optional validation

**Documentation & Code Quality:**
- [ ] Audit CacheService - explain and document the cache-aside pattern implementation
- [ ] Audit force/force_refresh parameter support across all DataServiceV2 methods - ensure consistency

**Nice-to-Have Features:**
- [ ] Follow Polygon API next_url for paginated news results
- [ ] Add JSONOutputAdapter when Web API work begins
- [ ] Add WebSocketProgressReporter for real-time web UI updates
- [ ] Implement full strategy backtest with entry/exit rules per GAP_TRADING_STRATEGY.md

---

## 📝 Key Architecture Rules

- Repository (business queries) + SQLModel (ORM) + Provider (API) + DataServiceV2 (orchestration)
- Cache-aside pattern with TTL management via CacheService
- Dual model system: Domain models (dataclasses) for business logic, SQLModel for database
- Template-based context-aware screeners (gainers_combined model)
- Volume fields: Only min has v+av, prevDay/day only have v
- Reference: `docs/ARCHITECTURE.md`, `docs/DATABASE.md`, `docs/POLYGON.md`
