# Gap Trading Volume Ratio Calculation

**Purpose:** Explains how TradeScout calculates volume ratios for gap trading candidates during extended hours sessions (premarket and after-hours).

---

## Overview

The volume ratio determines if a gap has sufficient trading activity to be tradeable. Academic research shows that gaps need **unusual volume relative to normal trading activity** to have edge.

**Key Formula:**
```
Volume Ratio = Actual Extended Hours Volume / Expected Volume
Expected Volume = Hourly Average × Elapsed Session Hours
```

---

## Session-Aware Baseline Selection

TradeScout uses **different volume baselines** depending on the session, ensuring the most relevant comparison:

### Premarket Gaps (4:00-9:30 AM)
- **Baseline**: Yesterday's regular hours volume (`prevday_volume`)
- **Why**: Today hasn't started trading yet, so yesterday is the most recent data
- **Hourly Average**: `prevday_volume / 6.5 hours`

### After-Hours Gaps (4:00-8:00 PM)
- **Baseline**: Today's regular hours volume (`day_volume`)
- **Why**: Today's trading just finished - most recent and relevant pace
- **Hourly Average**: `day_volume / 6.5 hours`

**Critical Insight**: After-hours uses today's pace, not yesterday's. This accounts for stocks that had unusual volume today.

---

## Elapsed Time Calculation

TradeScout uses **ELAPSED session time**, not the full session length.

**Example: After-hours at 5:30 PM**
```
Session start:    4:00 PM
Current time:     5:30 PM
Elapsed time:     1.5 hours  (NOT the full 4-hour session!)
```

**Why this matters:**
- At 5:30 PM, only 1.5 hours have passed
- Using full 4 hours would dramatically understate the volume ratio
- Earlier in the session = smaller denominator = higher ratio

---

## Complete Calculation Example

**CORZ at 5:30 PM (After-Hours)**

### Step 1: Get Baseline Volume
```
Today's regular hours volume: 11,469,296 shares
(Obtained from day_volume field in asset_prices)
```

### Step 2: Calculate Hourly Average
```
Regular hours: 9:30 AM - 4:00 PM = 6.5 hours
Hourly average: 11,469,296 / 6.5 = 1,764,507 shares/hour
```

### Step 3: Calculate Elapsed Time
```
Session start: 4:00 PM
Analysis time: 5:30 PM
Elapsed: 1.5 hours
```

### Step 4: Calculate Expected Volume
```
Expected = Hourly Average × Elapsed Hours
Expected = 1,764,507 × 1.5 = 2,646,761 shares
```

### Step 5: Calculate Volume Ratio
```
Actual extended hours volume: 751,726 shares
Volume ratio = 751,726 / 2,646,761 = 0.28x (28%)
```

**Result**: CORZ is trading at 28% of its normal pace - **below the 1.5x threshold**.

---

## Threshold Interpretation

**Default threshold: 1.5x**

| Ratio | Interpretation | Trade? |
|-------|---------------|--------|
| ≥2.0x | Very strong volume - high conviction | ✓ Yes |
| 1.5-2.0x | Good volume - meets threshold | ✓ Yes |
| 1.0-1.5x | Normal pace - no edge | ✗ No |
| <1.0x | Below average - weak | ✗ No |

---

## Why This Approach Works

### 1. **Relative, Not Absolute**
- 1M shares is huge for a low-volume stock
- 1M shares is tiny for a high-volume stock
- Using hourly average normalizes across stocks

### 2. **Most Recent Data**
- After-hours uses today's pace (not yesterday's)
- Accounts for stocks with unusual volume today
- More accurate context for current conditions

### 3. **Time-Aware**
- Early in session (4:15 PM): small expected volume, easier to exceed
- Later in session (7:30 PM): large expected volume, harder to exceed
- Ratio naturally adjusts as session progresses

### 4. **Academic Validation**
- Research shows volume confirms gap validity
- Gaps without volume tend to reverse
- 1.5x threshold balances opportunity vs risk

---

## Example Scenarios

### Scenario 1: High-Volume Stock (AAPL-like)
```
Regular hours volume: 50,000,000 shares
After-hours at 5:00 PM (1 hour elapsed)
Actual volume: 10,000,000 shares

Hourly avg: 50M / 6.5 = 7,692,308/hr
Expected: 7,692,308 × 1 = 7,692,308 shares
Ratio: 10M / 7.7M = 1.30x ✗ (below threshold)
```

### Scenario 2: Low-Volume Stock
```
Regular hours volume: 500,000 shares
After-hours at 6:00 PM (2 hours elapsed)
Actual volume: 250,000 shares

Hourly avg: 500K / 6.5 = 76,923/hr
Expected: 76,923 × 2 = 153,846 shares
Ratio: 250K / 154K = 1.62x ✓ (passes threshold!)
```

**Key Insight**: The low-volume stock needs far less absolute volume to pass the filter because it's normalized to its typical activity.

---

## Implementation Details

### Database Fields
- `day_volume` (INTEGER): Today's regular hours volume for after-hours baseline
- `previous_day_volume` (INTEGER): Yesterday's volume for premarket baseline
- `extended_hours_volume` (INTEGER): Actual extended hours volume from Aggregates API
- `volume_ratio` (FLOAT): Calculated ratio

### Code Location
- **Volume Ratio Calculation**: `src/analysis/gap_analyzer.py::calculate_volume_ratio()`
- **Elapsed Time Logic**: Lines 275-304 in gap_analyzer.py
- **Baseline Selection**: Lines 257-263 in gap_analyzer.py
- **CLI Integration**: `src/cli/gap_commands.py::analyze()` line 150-154

### Config
- **Session hours**: `configs/gap_trading.yaml::session_hours`
- **Default threshold**: CLI parameter `--min-volume-ratio` (default: 1.5)

---

## Troubleshooting

### "Why is my volume ratio so low?"
1. Check if stock had unusually high volume today (uses today's pace for after-hours)
2. Early in session? Less elapsed time = lower expected volume
3. Low absolute volume but high ratio? That's normal for low-volume stocks

### "Volume ratio seems wrong"
1. Verify `day_volume` is populated (should be for after-hours)
2. Check analysis timestamp - ratio changes as session progresses
3. Enable debug logging: `logging.getLogger('analysis.gap_analyzer').setLevel(logging.DEBUG)`

### "I want to see debug output"
Remove this line from gap_commands.py:
```python
logging.getLogger('analysis.gap_analyzer').setLevel(logging.ERROR)
```

---

## Related Documentation
- **Gap Analysis Workflow**: `docs/GAP_ANALYSIS_MANUAL_WORKFLOW.md`
- **Gap Trading Strategy**: `configs/gap_trading.yaml`
- **API Reference**: `docs/API_REFERENCE_GAP_ANALYZER.md`

---

**Last Updated**: 2025-10-20
**Version**: 1.0
