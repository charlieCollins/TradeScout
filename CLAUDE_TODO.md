# TradeScout - TODO List

*Last updated: 2025-09-30*

## 🎯 Current Focus: Architecture Refactor - Phase 2

### Phase 1 Complete ✅
Ticker/Market snapshots migrated to Manager/Provider/DataService architecture. 74 tests passing.

### Phase 2: Migrate Remaining Entities

**Entities Still Using OLD Architecture:**
- [ ] Fundamentals data (company info, financials, etc.)
- [ ] News data
- [ ] Historical price data
- [ ] Earnings data
- [ ] Market holidays/context data
- [ ] Any other data types in old `data_provider.py`

**Migration Pattern** (follow for each entity):
1. **Create Manager** - Extend `BaseManager` in `src/database/managers/`
   - Implement `get_entity_from_database()` - read from DB
   - Implement `set_entity_to_database()` - write to DB
   - Define `get_ttl_seconds()` - return TTL for this data type
   - Define `get_data_update_metadata_type()` - return metadata enum
2. **Add Provider Methods** - Add to appropriate API provider
   - e.g., `PolygonFundamentalsProvider.fetch_company_info()`
   - Parse API JSON → Model objects
3. **Add to DataService** - Wire manager + provider
   - e.g., `get_company_fundamentals(symbol, force_refresh=False)`
   - Coordinate cache-or-fetch logic
4. **Write Tests**
   - Unit tests for manager (mock DB)
   - Unit tests for provider (mock HTTP)
   - Integration tests via DataService
5. **Update Business Logic** - Migrate old code to use DataService

**Old Code Cleanup:**
- [ ] Audit what's still using old `data_provider.py`
- [ ] Migrate CLI commands to new DataService methods
- [ ] Remove deprecated classes once migration complete

### 📋 Additional Providers (Future)
- [ ] Alpha Vantage provider (market movers, sector performance)
- [ ] Finnhub provider (fundamentals, news sentiment)
- [ ] YFinance provider (fallback for free data)

---

## 📝 Key Architecture Rules

- Manager (storage/TTL) + Provider (API) + DataService (orchestration)
- Don't mix old and new architecture
- Reference: `docs/ARCHITECTURE_MANAGERS.md`, `docs/ARCHITECTURE_API_PROVIDERS.md`
- Template: `TickerSnapshotManager` (standard entity manager)