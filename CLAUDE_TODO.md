# TradeScout - TODO List

*Last updated: 2025-09-22*

## 🎯 Current Priority Tasks

### 1. Test snapshot API behavior during regular trading hours
- **Goal**: Continue verification of Polygon API field behavior during market hours
- **Implementation**: Test snapshot API during 9:30-4:00 PM ET trading session
- **Status**: Premarket confirmed, regular hours pending
- **Priority**: HIGH - API understanding completion

### 2. Test if day.* fields update in real-time or only at market close
- **Goal**: Understand when day.open/high/low/close/volume fields get updated
- **Implementation**: Monitor day.* fields throughout trading session
- **Priority**: HIGH - Critical for gap analysis logic

### 3. Verify updated timestamp always corresponds to day.* session date
- **Goal**: Confirm relationship between updated timestamp and day.* data
- **Implementation**: Cross-check updated field with day.* trading date
- **Priority**: HIGH - Data integrity verification

### 4. Implement screener query engine
- **Goal**: Build unified screener system for gap candidates
- **Implementation**: SQL-based screener with configurable criteria
- **Priority**: HIGH - Core functionality

### 5. Build CLI with screener commands
- **Goal**: Create main TradeScout CLI with gap analysis commands
- **Implementation**: Click-based CLI with gainers/losers/gaps commands
- **Priority**: HIGH - User interface

### 6. Implement extended hours gap identification
- **Goal**: Core gap discovery using confirmed API approach
- **Implementation**: Use prevDay.c vs min.c comparison for gaps
- **Priority**: HIGH - Primary project purpose

---

## ✅ Recently Completed (September 22, 2025)

- **Fixed markets bootstrapping** - Added bootstrap_markets() method with US exchanges (XNYS, XNAS, ARCX, etc.)
- **Fixed provider_id foreign key issue** - Dynamic lookup instead of hardcoded ID=1
- **Successfully populated database** - 11,745 tickers loaded from Polygon API
- **Validated Monday premarket snapshot behavior** - Confirmed day.* fields NULL, prevDay.c has Friday close
- **Documented live test results** - Added Monday Sept 22 premarket validation

---

*This file tracks active development priorities for next session work.*