# TradeScout - TODO List

*Last updated: 2025-10-01*

## 🎯 Current Focus: CLI Migration to New Architecture

### Architecture Refactor Status ✅
**Manager/Provider/DataService architecture COMPLETE** for all core entities:
- ✅ Ticker/Market snapshots (Phase 1)
- ✅ Assets, Markets, Fundamentals, Universes, Sentiment (Phase 2)
- ✅ Market holidays and market context (Phase 2)
- ✅ 238 tests passing (87 provider + 133 manager + 18 service)

### CLI Migration - READY TO EXECUTE

**Reference:** `docs/MIGRATION_PLAN.md`

**Phase 1: Add Missing DataService Methods** (PRIORITY)
- [ ] Snapshot operations (get_ticker_snapshot, refresh_market_data)
- [ ] Asset price operations (get_latest_asset_price, save_asset_price_data, transform methods)
- [ ] Snapshot metadata (get_market_snapshot_metadata, start/complete_snapshot_run)
- [ ] Universe operations (get_active_universe_symbols, get_universe_stats, create/delete_universe)
- [ ] Market operations (get_market_by_code, get_active_markets_by_codes, get_current_market_session)
- [ ] Screener support (execute_screener_query)

**Phase 2: Update CLI Files** (7 files)
- [ ] src/cli/main.py - Config class
- [ ] src/cli/asset_commands.py
- [ ] src/cli/market_commands.py
- [ ] src/cli/gap_commands.py
- [ ] src/cli/screener_commands.py
- [ ] src/cli/universe_commands.py
- [ ] src/cli/database_commands.py

**Phase 3: Update Supporting Services**
- [ ] src/services/market_context_service.py
- [ ] src/screener/screener_engine.py

**Phase 4: Testing & Validation**
- [ ] Test all asset commands (local, info)
- [ ] Test all market commands (info, update, context, session)
- [ ] Test screener commands (--list, gainers, losers)
- [ ] Test universe commands (list, info, activate)
- [ ] Test gap commands (analyze)
- [ ] Test database commands (info)

### Known Issues to Address
- [ ] Fundamentals bulk TTL issue: get_or_fetch needs fallback for new tickers added after bootstrap

---

## 📝 Key Architecture Rules

- Manager (storage/TTL) + Provider (API) + DataService (orchestration)
- Legacy code in `backup/` - DO NOT TOUCH without permission
- Reference: `docs/ARCHITECTURE_MANAGERS.md`, `docs/ARCHITECTURE_API_PROVIDERS.md`, `docs/MIGRATION_PLAN.md`
