# TradeScout - TODO List

*Last updated: 2025-09-27*

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

### 4. Optimize market update with batch inserts
- **Goal**: Improve performance of bulk market snapshot processing
- **Implementation**: Replace individual inserts with batch operations
- **Priority**: MEDIUM - Performance optimization

---

*This file tracks active development priorities for next session work.*