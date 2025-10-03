# TradeScout - TODO List

*Last updated: 2025-10-03*

## 🎯 Current Focus: CLI Migration to New Architecture

### Architecture Refactor Status ✅
**Manager/Provider/DataService architecture COMPLETE** for all core entities:
- ✅ Ticker/Market snapshots (Phase 1)
- ✅ Assets, Markets, Fundamentals, Universes, Sentiment (Phase 2)
- ✅ Market holidays table added, market_context_cache removed (Phase 2)
- ✅ 238 tests passing (87 provider + 133 manager + 18 service)

### CLI Migration - IN PROGRESS

**Reference:** `docs/MIGRATION_PLAN.md`

**Recent Completions (2025-10-03)**
- ✅ Fixed market_context_service.py import paths
- ✅ Removed market_context_cache (data records ARE the cache)
- ✅ Optimized bootstrap-fundamentals (2-phase: API fetch → DB batch insert)
- ✅ Cleaned up market commands (removed info/session, enhanced context)
- ✅ Renamed universe → universes, removed create/delete
- ✅ Fixed market update tracking (direct DB operations)

**Phase 1: Add Missing DataService Methods**
- [x] Snapshot metadata (get_market_snapshot_metadata, start/complete_snapshot_run) - DONE
- [ ] Snapshot operations (get_ticker_snapshot, refresh_market_data)
- [ ] Asset price operations (get_latest_asset_price, save_asset_price_data, transform methods)
- [ ] Universe operations (get_active_universe_symbols, get_universe_stats) - partially done
- [ ] Market operations (get_market_by_code, get_active_markets_by_codes, get_current_market_session) - partially done
- [ ] Screener support (execute_screener_query)

**Phase 2: Update CLI Files** (7 files)
- [ ] src/cli/main.py - Config class
- [ ] src/cli/asset_commands.py
- [~] src/cli/market_commands.py - partially updated
- [ ] src/cli/gap_commands.py
- [ ] src/cli/screener_commands.py
- [~] src/cli/universe_commands.py - renamed, cleaned up
- [ ] src/cli/database_commands.py

**Phase 3: Update Supporting Services**
- [~] src/services/market_context_service.py - import fixed, cache removed
- [ ] src/screener/screener_engine.py

**Phase 4: Testing & Validation**
- [ ] Test market update command end-to-end (ready to test)
- [ ] Test all asset commands (local, info)
- [ ] Test screener commands (--list, gainers, losers)
- [ ] Test universes commands (list, info, activate, current)
- [ ] Test gap commands (analyze)
- [ ] Test database commands (info, bootstrap-fundamentals)

### Known Issues to Address
- [ ] Fundamentals bulk TTL issue: get_or_fetch needs fallback for new tickers added after bootstrap

### Future Architecture Improvements
- [ ] Separate display/output from DataService - DataService should return data structures, not format output (Rich progress bars, etc.). This allows DataService to serve CLI, web API, reports, etc. with different formatters/outputters handling display per context.

---

## 📝 Key Architecture Rules

- Manager (storage/TTL) + Provider (API) + DataService (orchestration)
- Legacy code in `backup/` - DO NOT TOUCH without permission
- Reference: `docs/ARCHITECTURE_MANAGERS.md`, `docs/ARCHITECTURE_API_PROVIDERS.md`, `docs/MIGRATION_PLAN.md`
