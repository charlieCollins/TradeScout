# TradeScout - TODO List

*Last updated: 2025-09-16*

## 🎯 Current Priority Tasks

### 1. CRITICAL: Implement proper extended hours gap identification (NOT total displacement)
- **Goal**: Build the core extended hours gap discovery functionality (THE ENTIRE POINT OF THIS PROJECT)
- **Status**: Currently disabled - gap candidates method returns empty list with warning
- **Priority**: HIGHEST - This is the fundamental purpose of TradeScout

### 2. Implement gainers-extended-hours command
- **Goal**: Show stocks that gained ONLY during extended hours (after close or before open)
- **Implementation**: Compare previous regular session close to current extended hours price
- **Priority**: HIGH - Foundation for gap analysis

### 3. Implement losers-extended-hours command
- **Goal**: Show stocks that lost ONLY during extended hours (after close or before open)
- **Implementation**: Compare previous regular session close to current extended hours price
- **Priority**: HIGH - Foundation for gap analysis

### 4. Implement gainers-extended-hours-candidates command
- **Goal**: Extended hours gainers filtered by gap analysis criteria
- **Implementation**: Use gainers-extended-hours + apply gap criteria filtering
- **Priority**: HIGH - Gap trading candidate identification

### 5. Implement losers-extended-hours-candidates command
- **Goal**: Extended hours losers filtered by gap analysis criteria
- **Implementation**: Use losers-extended-hours + apply gap criteria filtering
- **Priority**: HIGH - Gap trading candidate identification

### 6. Update gap candidates identification to use extended hours candidates
- **Goal**: Fix get_gap_suggestions() to use extended hours candidates instead of total displacement
- **Implementation**: Use gainers-extended-hours-candidates and losers-extended-hours-candidates
- **Priority**: HIGH - Complete the gap analysis workflow

### 7. MAJOR: Implement new database schema and screener architecture
- **Goal**: Implement the comprehensive 8-table database schema designed in docs/REFACTOR_SCREENER_APPROACH.md
- **Implementation**: Create migration scripts, update models, build screener query system
- **Priority**: HIGH - Foundation for all extended hours functionality

### 8. Build custom bars API integration for real-time data
- **Goal**: Replace snapshot API with custom bars API for asset_prices_current table
- **Implementation**: Individual ticker calls using Polygon custom bars API
- **Priority**: HIGH - Real-time data foundation

### 9. Implement extended hours aggregates data collection
- **Goal**: Use aggregates API to collect pre-market (4:00-9:30 AM) and after-hours (4:01-8:00 PM) session data
- **Implementation**: Time-based aggregates calls for extended hours analysis
- **Priority**: HIGH - Core extended hours functionality

### 10. Complete codebase audit for dead code
- **Goal**: Use agents to audit all modules for unused imports, classes, methods
- **Implementation**: Systematic review and cleanup of deprecated code
- **Priority**: MEDIUM - Code quality maintenance

### 11. Implement market cap filtering in gap analysis
- **Goal**: Add fundamentals API calls for proper market cap filtering
- **Status**: Currently fake filtering (returns True always) - needs real implementation
- **Priority**: MEDIUM - Academic strategy compliance

### 12. Extract display logic from engine
- **Goal**: Move Rich formatting to display handler pattern
- **Implementation**: Create presentation layer separate from business logic
- **Priority**: MEDIUM - Architecture improvement

---

*This file tracks active development priorities for next session work.*