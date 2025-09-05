# TradeScout - TODO List

*Last updated: 2025-09-05 17:37 (Claude) - Completed custom bars integration and provider-agnostic architecture*

## About TradeScout

TradeScout is a personal market research assistant for gap trading strategy implementation. The system combines academic research-based trading rules with multi-provider data collection and intelligent market analysis.

## Current Command Structure

```bash
# Individual asset data
./tradescout asset quote AAPL MSFT TSLA
./tradescout asset fundamentals IBM  
./tradescout asset ohlc TSLA

# Market-wide analysis
./tradescout market gainers --limit 10
./tradescout market losers --limit 10
./tradescout market active --limit 10
./tradescout market movers --limit 5
./tradescout market suggest

# System status
./tradescout system status
```

## ✅ Recently Completed (Session 2025-09-05)
- **Custom bars endpoint integrated** ✅ - Successfully replaced failing API with Polygon custom bars for live extended hours pricing
- **Provider-agnostic architecture enforced** ✅ - Eliminated all direct API calls from smart coordinator, moved to provider layer  
- **Major test coverage improvement** ✅ - Added 44 new tests (76% increase) with critical production bug discovered and fixed
- **Cache optimization fixed** ✅ - System now properly uses provider caching eliminating redundant API calls
- **Architecture consistency verified** ✅ - Comprehensive audit confirmed all provider delegation patterns working correctly

## ⚠️ Critical Issue Discovered
- **Market data cache limitation** - Polygon snapshot cache contains only 1 symbol instead of full market data
  - **Impact**: System shows "0 market movers" and "0 gap candidates"  
  - **Status**: Needs immediate investigation next session

## 🎯 Pending Priority Tasks

### 1. **HIGH PRIORITY**: Investigate Polygon market snapshot data issue
- **Goal**: Fix cache showing only 1 symbol ("NEW") instead of full market data
- **Impact**: Currently preventing gap detection from finding candidates
- **Investigation needed**: API response format, caching logic, data processing
- **Priority**: Critical - Blocking core functionality

### 2. Add ASCII spinner progress bar to suggest command showing current ticker being processed
- **Goal**: Show real-time progress during gap analysis with spinner and current ticker name
- **Implementation**: ASCII spinner (like Claude Code uses) updating on same line during processing
- **Benefit**: Better user experience during market analysis
- **Priority**: High - User experience improvement

### 3. Move asset universe from config files to database for better management
- **Goal**: Store ticker symbols and metadata in SQLite database instead of static YAML files
- **Features**: Dynamic ticker management, metadata storage, performance tracking per symbol
- **Implementation**: Database tables for symbols, exchanges, sector classifications
- **Location**: Enhance existing SQLite database schema in data/tradescout.db
- **Priority**: High - Better data management foundation

### 2. Add pre-market activity filter to gap scanner to exclude non-trading symbols
- **Goal**: Filter out symbols with no pre-market activity to focus gap analysis on actively trading stocks
- **Implementation**: Check for pre-market volume or price movement before including in gap candidates
- **Benefit**: Reduces noise and focuses on meaningful gap opportunities
- **Priority**: Medium - Quality improvement for gap detection

### 3. Implement market status API instead of hardcoded hours
- **Goal**: Use Polygon's market status API to determine trading sessions instead of hardcoded time checks
- **Implementation**: Replace time-based session detection with real-time market status checks
- **Benefit**: Accurate session detection including holidays and early market closures
- **Priority**: Medium - Accuracy improvement for session-aware features

### 4. Separate engine from display/CLI output - create separate presentation layer
- **Goal**: Move all Rich formatting and display logic out of engine into dedicated presentation layer
- **Implementation**: Create display/presentation layer that takes engine data and formats for CLI
- **Benefit**: Cleaner separation of concerns, easier to add web interface later
- **Priority**: Medium - Architecture improvement

### 5. Audit entire codebase for magic numbers and config values that should not be hardcoded
- **Goal**: Find all hardcoded values and move them to configuration files where appropriate
- **Scope**: Search for numeric literals, hardcoded URLs, thresholds, timeouts
- **Implementation**: Move found values to appropriate config files with documentation
- **Priority**: Low - Code quality improvement

---

*This file tracks active development priorities for next session work.*