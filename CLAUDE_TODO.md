# TradeScout - TODO List

*Last updated: 2025-09-19*

## 🎯 Current Priority Tasks

### 1. Check markets and providers bootstrapping
- **Goal**: Verify bootstrap commands populate data correctly from APIs with clean schema
- **Implementation**: Test existing bootstrap commands after removing default data insertions
- **Status**: NEW - needed after schema cleanup
- **Priority**: HIGH - Core system functionality

### 2. Test snapshot API behavior during regular trading hours
- **Goal**: Continue verification of Polygon API field behavior during market hours
- **Implementation**: Test snapshot API during 9:30-4:00 PM ET trading session
- **Status**: Premarket confirmed, regular hours pending
- **Priority**: HIGH - API understanding completion

### 3. Test if day.* fields update in real-time or only at market close
- **Goal**: Understand when day.open/high/low/close/volume fields get updated
- **Implementation**: Monitor day.* fields throughout trading session
- **Priority**: HIGH - Critical for gap analysis logic

### 4. Verify updated timestamp always corresponds to day.* session date
- **Goal**: Confirm relationship between updated timestamp and day.* data
- **Implementation**: Cross-check updated field with day.* trading date
- **Priority**: HIGH - Data integrity verification

### 5. Implement screener query engine
- **Goal**: Build unified screener system for gap candidates
- **Implementation**: SQL-based screener with configurable criteria
- **Priority**: HIGH - Core functionality

### 6. Build CLI with screener commands
- **Goal**: Create main TradeScout CLI with gap analysis commands
- **Implementation**: Click-based CLI with gainers/losers/gaps commands
- **Priority**: HIGH - User interface

### 7. Implement extended hours gap identification
- **Goal**: Core gap discovery using confirmed API approach
- **Implementation**: Use prevDay.c vs min.c comparison for gaps
- **Priority**: HIGH - Primary project purpose

---

## ✅ Recently Completed

- **Data models implementation** (src/models directory with Asset, Market, AssetPrice, Provider)
- **Typed AssetAnalyzer** (returns typed models instead of dictionaries)
- **Fixed foreign key constraint** (INSERT OR REPLACE → INSERT OR IGNORE for ticker bootstrap)
- **Updated CLI for typed models** (analyze asset command works with new data structures)
- **Unified tradescout CLI** (single entry point with bootstrap and analyze commands)
- **Ticker bootstrapping implementation** (11,743 assets from Polygon API)
- **Universe bootstrapping implementation** (11,248 filtered assets)
- **Batch processing optimization** (1000 assets per batch, no hanging)
- **API key configuration** (moved to src/config/api_keys.py)
- **Subcommand CLI structure** (tickers init/info, universe init/info)
- **Database schema integration** (proper universes/universe_memberships tables)
- Database schema implementation (all 14 tables)
- Database bootstrap idempotency fixes
- Bootstrap CLI conversion to Click
- Premarket snapshot behavior confirmation
- Extended hours gap formula documentation
- Project structure cleanup (data/ directory)

---

*This file tracks active development priorities for next session work.*