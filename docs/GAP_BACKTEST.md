# Gap Strategy Backtest

**Purpose:** Validate gap identification strategy by backtesting candidates against actual market data

**Status:** Implemented - Currently Active
**Created:** 2025-10-11
**Updated:** 2025-10-11

---

## 🎯 Overview

Gap backtesting validates our gap identification strategy by measuring what **actually happened** to gap candidates during the trading day, enabling data-driven validation of:
- Quality scoring effectiveness
- Filter threshold optimization
- Strategy assumptions (Friday gaps, exhaustion gaps, volume ratios)
- Overall candidate identification accuracy

**Key Design Principle:** Simplified backtest using open-to-close performance, not full strategy execution.

## ⚠️ Important: Simplified vs. Full Strategy Backtest

### What This Backtest Does (Simplified)
- **Entry:** Market open (9:30 AM) price
- **Exit:** Market close (4:00 PM) price
- **Return:** Simple (close - open) / open calculation
- **No strategy rules applied:** Doesn't follow first 2-hour entry window, stop losses, or exit criteria

### What a Full Strategy Backtest Would Do
Per docs/GAP_TRADING_STRATEGY.md rules:
- **Entry:** Within first 2 hours (9:30 AM - 11:30 AM) at optimal point
- **Exit:** Based on strategy conditions (profit targets, stops, time-based exits)
- **Position sizing:** Dynamic based on gap quality, volatility, market regime
- **Risk management:** Stop losses at gap fill level, trailing stops, max loss limits

### Why We Use Simplified Backtest

**Pros:**
- Quick validation of gap identification quality
- Clean, objective metric (every gap gets same treatment)
- Easy to calculate (just daily open/close bars)
- Removes execution variables from analysis

**Cons:**
- Doesn't represent actual strategy performance
- Ignores optimal entry timing within first 2 hours
- No stop-loss protection (full downside exposure)
- No profit-taking or partial exits

**Use Cases:**
- ✅ "Are the gaps we identify actually significant moves?"
- ✅ "Do quality scores correlate with better outcomes?"
- ✅ "Are exhaustion gaps worse performers?"
- ❌ "What would our actual P&L be following the strategy?"
- ❌ "What's the optimal stop-loss placement?"

---

## ⏰ Time Window: Single Trading Day

Backtest tracks intraday movement during **regular trading hours only** (9:30 AM - 4:00 PM ET).

**Critical Logic:** Which trading day's data to use depends on the session type when the gap was identified.

### Premarket Gap
```
Gap identified:    Oct 9, 8:30 AM (session_type = 'premarket')
Database record:   trading_date = 2025-10-09
Backtest data:     Oct 9 regular hours (9:30 AM - 4:00 PM SAME DAY)

Rationale: Premarket gap is for the trading day about to open.
           We backtest using that day's regular hours.
```

### Afterhours Gap
```
Gap identified:    Oct 9, 5:00 PM (session_type = 'afterhours')
Database record:   trading_date = 2025-10-09
Backtest data:     Oct 10 regular hours (9:30 AM - 4:00 PM NEXT DAY)

Rationale: Afterhours gap is after Oct 9 market closed.
           We backtest using NEXT trading day's regular hours.
```

### Algorithm to Determine Backtest Date

```python
def get_performance_trading_date(gap_result):
    """Determine which trading day to use for backtest data."""

    if gap_result.session_type == 'premarket':
        # Premarket gap: use same day's regular hours
        performance_date = gap_result.trading_date

    elif gap_result.session_type == 'afterhours':
        # Afterhours gap: use next trading day's regular hours
        performance_date = get_next_trading_day(gap_result.trading_date)

    return performance_date
```

**Example Scenarios:**

| Gap Identified | Session Type | Trading Date (DB) | Performance Date | Data Needed |
|----------------|--------------|-------------------|------------------|-------------|
| Oct 9, 8:30 AM | premarket | 2025-10-09 | 2025-10-09 | Oct 9 9:30-4:00 |
| Oct 9, 5:00 PM | afterhours | 2025-10-09 | 2025-10-10 | Oct 10 9:30-4:00 |
| Oct 10, 7:00 AM | premarket | 2025-10-10 | 2025-10-10 | Oct 10 9:30-4:00 |
| Oct 10, 6:00 PM | afterhours | 2025-10-10 | 2025-10-11 | Oct 11 9:30-4:00 |

**Not Tracked:**
- Extended hours movement (premarket/afterhours)
- Multi-day performance trends
- Whether user actually took the trade
- Position sizing or exit timing decisions

**Only Tracked:**
- Mechanical buy-at-open, sell-at-close performance
- Intraday high/low opportunities
- Gap fill events

---

## 📊 Performance Metrics

### 1. Entry/Exit Prices

| Metric | Definition | Data Source |
|--------|------------|-------------|
| `entry_price` | Open price at 9:30 AM | Daily aggregate bar `.o` |
| `exit_price` | Close price at 4:00 PM | Daily aggregate bar `.c` |

**Polygon API:**
```
GET /v2/aggs/ticker/{symbol}/range/1/day/{date}/{date}

Response: {
  "o": 10.50,  // entry_price
  "h": 11.20,  // max_intraday_price
  "l": 10.30,  // min_intraday_price
  "c": 10.90,  // exit_price
  "v": 1234567
}
```

### 2. Intraday Range

| Metric | Definition | Data Source |
|--------|------------|-------------|
| `max_intraday_price` | Highest price during 9:30-4:00 | Daily aggregate bar `.h` |
| `min_intraday_price` | Lowest price during 9:30-4:00 | Daily aggregate bar `.l` |

### 3. Gap Fill Detection

| Metric | Definition | Algorithm |
|--------|------------|-----------|
| `gap_filled` | Did price touch reference_price? | Check minute bars for touch |
| `gap_fill_timestamp` | Exact time gap filled | First minute bar where fill occurred |

**Reference Price by Session:**
- **Premarket gap:** `reference_price = prevday_close` (yesterday's 4PM close)
- **Afterhours gap:** `reference_price = day_close` (yesterday's 4PM close)

**Algorithm:**
```python
def detect_gap_fill(minute_bars, reference_price):
    """Check if any intraday bar touched reference price."""
    for bar in minute_bars:
        # Price touched reference if within bar's range
        if bar.low <= reference_price <= bar.high:
            return True, bar.timestamp
    return False, None
```

**Polygon API:**
```
GET /v2/aggs/ticker/{symbol}/range/1/minute/{date}T09:30/{date}T16:00

Response: {
  "results": [
    {"t": 1696848600000, "o": 10.50, "h": 10.55, "l": 10.48, "c": 10.52},
    {"t": 1696848660000, "o": 10.52, "h": 10.58, "l": 10.50, "c": 10.56},
    ...
  ]
}
```

### 4. Calculated Performance Metrics

```python
# Realized return: Open-to-close performance
realized_return_pct = ((exit_price - entry_price) / entry_price) * 100

# Max upside: Best possible intraday return
max_upside_pct = ((max_intraday_price - entry_price) / entry_price) * 100

# Max drawdown: Worst intraday drawdown
max_drawdown_pct = ((min_intraday_price - entry_price) / entry_price) * 100
```

**Example Calculation:**
```
Entry (9:30 AM):  $10.00
High:             $11.50
Low:              $9.80
Close (4:00 PM):  $10.90

realized_return_pct = ((10.90 - 10.00) / 10.00) * 100 = +9.0%
max_upside_pct      = ((11.50 - 10.00) / 10.00) * 100 = +15.0%
max_drawdown_pct    = ((9.80 - 10.00) / 10.00) * 100 = -2.0%
```

**Interpretation:**
- Realized: Made 9% if held open-to-close
- Max upside: Had 15% profit opportunity at the high
- Max drawdown: Faced 2% drawdown risk at the low

### 5. Outcome Classification

```python
if realized_return_pct >= 2.0:
    outcome = 'winner'     # Green trade
elif realized_return_pct <= -1.0:
    outcome = 'loser'      # Red trade
else:
    outcome = 'breakeven'  # Neutral trade
```

**Rationale:**
- Winners: ≥2% return justifies trading costs and risk
- Losers: ≤-1% represents failed setup
- Breakeven: -1% to +2% range is noise/chop

---

## 🗄️ Database Schema

### Table: `gap_candidate_result`

```sql
CREATE TABLE gap_candidate_result (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gap_candidate_id INTEGER NOT NULL UNIQUE,

    -- Entry/Exit (regular hours only)
    entry_price REAL,              -- Open at 9:30 AM
    exit_price REAL,               -- Close at 4:00 PM

    -- Intraday range
    max_intraday_price REAL,       -- High during 9:30-4:00
    min_intraday_price REAL,       -- Low during 9:30-4:00

    -- Gap fill tracking
    gap_filled BOOLEAN,             -- Did price touch reference_price?
    gap_fill_timestamp TIMESTAMP,   -- When gap filled (NULL if didn't fill)

    -- Performance metrics
    realized_return_pct REAL,       -- (exit - entry) / entry * 100
    max_upside_pct REAL,            -- (high - entry) / entry * 100
    max_drawdown_pct REAL,          -- (low - entry) / entry * 100

    -- Outcome classification
    outcome TEXT,                   -- 'winner', 'loser', 'breakeven'

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (gap_candidate_id) REFERENCES gap_candidate(id) ON DELETE CASCADE
);

CREATE INDEX idx_gap_performance_outcome ON gap_candidate_result(outcome);
CREATE INDEX idx_gap_performance_return ON gap_candidate_result(realized_return_pct);
```

**Relationship:**
- One-to-one with `gap_candidate` (each gap has at most one performance record)
- Foreign key on `gap_candidate_id` with CASCADE delete
- Performance is immutable once recorded (single trading day snapshot)

---

## ⚙️ Command Design: `tradescout gap backtest`

### Update Logic

```python
def update_gap_performance(date_filter=None, force=False):
    """Update performance for gap results that need it."""

    # Get gap results to process
    if date_filter:
        gap_candidate = get_gap_candidate_by_date(date_filter)
    else:
        gap_candidate = get_all_gap_candidate()

    for gap in gap_candidate:
        # Check if performance already exists
        existing = get_performance_tracking(gap.id)

        # Determine if we should update
        should_update = False

        if force:
            # Force refresh: reprocess even if exists
            should_update = True
        elif not existing:
            # No performance record exists
            should_update = True
        elif existing.entry_price is None or existing.exit_price is None:
            # Performance record incomplete (partial data)
            should_update = True

        if not should_update:
            continue

        # Determine which trading day to use for performance
        if gap.session_type == 'premarket':
            # Premarket: use same day's regular hours
            performance_date = gap.trading_date
        elif gap.session_type == 'afterhours':
            # Afterhours: use next trading day's regular hours
            performance_date = get_next_trading_day(gap.trading_date)
        else:
            logger.error(f"Unknown session type: {gap.session_type}")
            continue

        # Check if performance trading day is complete
        # (Need data from 4:00 PM ET, available ~5 PM)
        if not is_trading_day_complete(performance_date):
            continue  # Data not available yet, skip

        # Fetch intraday data from Polygon for the correct trading day
        try:
            daily_bar = fetch_daily_bar(gap.symbol, performance_date)
            minute_bars = fetch_minute_bars(gap.symbol, performance_date)
        except APIError as e:
            logger.warning(f"Failed to fetch data for {gap.symbol}: {e}")
            continue

        # Calculate metrics
        gap_filled, fill_time = detect_gap_fill(minute_bars, gap.reference_price)

        performance = {
            'entry_price': daily_bar.open,
            'exit_price': daily_bar.close,
            'max_intraday_price': daily_bar.high,
            'min_intraday_price': daily_bar.low,
            'gap_filled': gap_filled,
            'gap_fill_timestamp': fill_time,
            'realized_return_pct': calculate_return(daily_bar.open, daily_bar.close),
            'max_upside_pct': calculate_return(daily_bar.open, daily_bar.high),
            'max_drawdown_pct': calculate_return(daily_bar.open, daily_bar.low),
            'outcome': classify_outcome(realized_return_pct)
        }

        # Save or update performance
        upsert_performance_tracking(gap.id, performance)
```

### When to Update ("Newer/Relevant" Criteria)

**Update scenarios:**

1. **Missing performance:** Gap result exists but no performance record
   ```sql
   SELECT * FROM gap_candidate gr
   LEFT JOIN gap_candidate_result gpt ON gpt.gap_candidate_id = gr.id
   WHERE gpt.id IS NULL
   ```

2. **Incomplete performance:** Record exists but missing fields
   ```sql
   SELECT * FROM gap_candidate_result
   WHERE entry_price IS NULL OR exit_price IS NULL
   ```

3. **Trading day complete but not processed:** Data became available since last run
   ```python
   if gap.trading_date < today() and not has_performance(gap.id):
       # Historical gap that never got performance data
       should_update = True
   ```

4. **Force refresh:** User runs `--force` flag to reprocess all
   ```bash
   ./tradescout gap backtest --force
   ```

**Not updated:**
- Performance data doesn't change after trading day completes
- Daily bar for Oct 9 is final after Oct 9 4:00 PM close
- No "newer" data for a completed day (exception: force refresh)

### Command Usage

```bash
# Update all gaps that need performance data
./tradescout gap backtest

# Update specific date
./tradescout gap backtest --date 2025-10-09

# Update date range
./tradescout gap backtest --start-date 2025-10-01 --end-date 2025-10-10

# Force reprocess (recompute existing records)
./tradescout gap backtest --force

# Dry run (show what would be updated)
./tradescout gap backtest --dry-run
```

### Example Output

```
╭────────────────────────────────────────────────╮
│ Gap Strategy Backtest                          │
╰────────────────────────────────────────────────╯

Checking gap results for performance updates...

2025-10-09 premarket (19 gaps):
  AKRO: Fetching performance data... ✓
    Entry: $54.80 | Exit: $52.30 | Return: -4.6% (loser)
    High: $55.10 | Low: $51.90
    Gap filled: No

  TLRY: Fetching performance data... ✓
    Entry: $1.98 | Exit: $2.05 | Return: +3.5% (winner)
    High: $2.12 | Low: $1.95
    Gap filled: Yes (at 10:45 AM)

  RACE: Fetching performance data... ✓
    Entry: $422.60 | Exit: $419.80 | Return: -0.7% (breakeven)
    High: $425.20 | Low: $418.50
    Gap filled: Yes (at 2:15 PM)

  ... (16 more)

2025-10-10 afterhours (1 gap):
  ASST: Trading day not complete yet (need data for 2025-10-11)
    Status: Skipped (afterhours gap on Oct 10 → performance on Oct 11, not closed yet)

════════════════════════════════════════════════

Summary:
  Updated: 19 records
  Skipped (incomplete day): 1 record
  Failed (API errors): 0 records

Performance Statistics (19 gaps):
  Winners (≥2%):       7 (36.8%)
  Losers (≤-1%):       8 (42.1%)
  Breakeven (-1-2%):   4 (21.1%)

  Avg return:         -0.8%
  Avg winner:         +4.2%
  Avg loser:          -3.1%

  Gap fill rate:      63.2% (12/19 gaps filled)
```

---

## 📈 Use Cases & Queries

### 1. Validate Quality Scoring Effectiveness

**Question:** Do higher quality scores predict better returns?

```sql
SELECT
    gr.quality_tier,
    COUNT(*) as total_gaps,
    AVG(gpt.realized_return_pct) as avg_return,
    SUM(CASE WHEN gpt.outcome = 'winner' THEN 1 ELSE 0 END) as winners,
    ROUND(100.0 * SUM(CASE WHEN gpt.outcome = 'winner' THEN 1 ELSE 0 END) / COUNT(*), 1) as win_rate_pct
FROM gap_candidate gr
JOIN gap_candidate_result gpt ON gpt.gap_candidate_id = gr.id
WHERE gr.trading_date >= date('now', '-90 days')
GROUP BY gr.quality_tier
ORDER BY avg_return DESC;
```

**Expected Output:**
```
quality_tier | total_gaps | avg_return | winners | win_rate_pct
-------------|------------|------------|---------|-------------
excellent    | 12         | +2.4%      | 8       | 66.7%
good         | 28         | +1.1%      | 14      | 50.0%
fair         | 45         | +0.3%      | 18      | 40.0%
poor         | 156        | -0.8%      | 12      | 7.7%
```

**Validation:** If excellent tier doesn't outperform poor tier, quality scoring is broken.

---

### 2. Test Exhaustion Filter Effectiveness

**Question:** Does rejecting exhaustion gaps prevent losses?

```sql
SELECT
    gr.passed_exhaustion_filter,
    COUNT(*) as total,
    AVG(gpt.realized_return_pct) as avg_return,
    SUM(CASE WHEN gpt.outcome = 'winner' THEN 1 ELSE 0 END) as winners
FROM gap_candidate gr
JOIN gap_candidate_result gpt ON gpt.gap_candidate_id = gr.id
WHERE gr.trading_date >= date('now', '-90 days')
GROUP BY gr.passed_exhaustion_filter;
```

**Expected Output:**
```
passed_exhaustion_filter | total | avg_return | winners
-------------------------|-------|------------|--------
TRUE                     | 42    | +1.8%      | 28
FALSE (rejected)         | 18    | -2.1%      | 3
```

**Validation:** Exhaustion filter should show rejected gaps have worse returns.

---

### 3. Friday Gap Risk Analysis

**Question:** Are Friday gaps truly riskier due to weekend uncertainty?

```sql
SELECT
    gr.is_friday_gap,
    COUNT(*) as total,
    AVG(gpt.realized_return_pct) as avg_return,
    AVG(gpt.max_drawdown_pct) as avg_drawdown,
    SUM(CASE WHEN gpt.gap_filled THEN 1 ELSE 0 END) as gaps_filled,
    ROUND(100.0 * SUM(CASE WHEN gpt.gap_filled THEN 1 ELSE 0 END) / COUNT(*), 1) as fill_rate_pct
FROM gap_candidate gr
JOIN gap_candidate_result gpt ON gpt.gap_candidate_id = gr.id
WHERE gr.status IN ('passed', 'warning')
GROUP BY gr.is_friday_gap;
```

**Expected Output:**
```
is_friday_gap | total | avg_return | avg_drawdown | gaps_filled | fill_rate_pct
--------------|-------|------------|--------------|-------------|---------------
FALSE         | 38    | +1.9%      | -2.1%        | 18          | 47.4%
TRUE          | 8     | -0.5%      | -4.3%        | 6           | 75.0%
```

**Validation:** If Friday gaps show worse returns/higher fill rates, warning is justified.

---

### 4. Volume Ratio Threshold Optimization

**Question:** Should we use 1.5x or 2.0x volume ratio threshold?

```sql
SELECT
    CASE
        WHEN gr.volume_ratio >= 2.0 THEN '≥2.0x'
        WHEN gr.volume_ratio >= 1.5 THEN '1.5x-2.0x'
        WHEN gr.volume_ratio >= 1.0 THEN '1.0x-1.5x'
        ELSE '<1.0x'
    END as volume_bucket,
    COUNT(*) as total,
    AVG(gpt.realized_return_pct) as avg_return,
    SUM(CASE WHEN gpt.outcome = 'winner' THEN 1 ELSE 0 END) as winners,
    ROUND(100.0 * SUM(CASE WHEN gpt.outcome = 'winner' THEN 1 ELSE 0 END) / COUNT(*), 1) as win_rate_pct
FROM gap_candidate gr
JOIN gap_candidate_result gpt ON gpt.gap_candidate_id = gr.id
GROUP BY volume_bucket
ORDER BY gr.volume_ratio DESC;
```

**Expected Output:**
```
volume_bucket | total | avg_return | winners | win_rate_pct
--------------|-------|------------|---------|-------------
≥2.0x         | 14    | +2.8%      | 10      | 71.4%
1.5x-2.0x     | 22    | +1.2%      | 12      | 54.5%
1.0x-1.5x     | 38    | -0.3%      | 14      | 36.8%
<1.0x         | 156   | -1.2%      | 18      | 11.5%
```

**Validation:** Data-driven answer on optimal volume threshold.

---

### 5. Gap Fill Rate Analysis

**Question:** What percentage of gaps fill on the same day?

```sql
SELECT
    gr.gap_direction,
    gr.session_type,
    COUNT(*) as total_gaps,
    SUM(CASE WHEN gpt.gap_filled THEN 1 ELSE 0 END) as gaps_filled,
    ROUND(100.0 * SUM(CASE WHEN gpt.gap_filled THEN 1 ELSE 0 END) / COUNT(*), 1) as fill_rate_pct,
    AVG(CASE WHEN gpt.gap_filled
        THEN gpt.realized_return_pct
        ELSE NULL END) as avg_return_if_filled,
    AVG(CASE WHEN NOT gpt.gap_filled
        THEN gpt.realized_return_pct
        ELSE NULL END) as avg_return_if_not_filled
FROM gap_candidate gr
JOIN gap_candidate_result gpt ON gpt.gap_candidate_id = gr.id
WHERE gr.status = 'passed'
GROUP BY gr.gap_direction, gr.session_type;
```

**Expected Output:**
```
gap_direction | session_type | total_gaps | gaps_filled | fill_rate_pct | avg_return_if_filled | avg_return_if_not_filled
--------------|--------------|------------|-------------|---------------|----------------------|-------------------------
up            | premarket    | 18         | 12          | 66.7%         | -0.8%                | +3.2%
up            | afterhours   | 8          | 5           | 62.5%         | -1.2%                | +2.8%
down          | premarket    | 4          | 3           | 75.0%         | +2.1%                | +0.5%
down          | afterhours   | 2          | 1           | 50.0%         | +1.8%                | +1.2%
```

**Insight:** Gap fills often correlate with failed trades (reversal to reference price).

---

## 🎓 Strategy Validation Framework

### Step 1: Accumulate Data
```bash
# Run gap analysis for 30-90 days
./tradescout gap analyze  # Daily during premarket/afterhours
```

### Step 2: Update Performance
```bash
# Every evening at 5:30 PM (after market close + data available)
./tradescout gap backtest
```

### Step 3: Analyze Results
```bash
# Weekly review
./tradescout gap results stats --last 7d

# Monthly deep dive
./tradescout gap results analyze --last 30d
```

### Step 4: Iterate Strategy
```python
# Example: Test new quality score weighting
results = query_gap_performance(
    quality_tier='excellent',
    min_catalyst_score=80,
    min_volume_ratio=2.0
)

win_rate = calculate_win_rate(results)  # Target: ≥55%
avg_return = calculate_avg_return(results)  # Target: ≥1.5%

if win_rate >= 0.55 and avg_return >= 0.015:
    print("Strategy validated! Deploy with confidence.")
else:
    print("Strategy needs refinement. Adjust filters or scoring.")
```

---

## 🚀 Implementation Status

### ✅ Phase 1: Database & Manager (COMPLETE)
- [x] Update migration to include `gap_candidate_result` table
- [x] Create `GapCandidateResultManager` class
- [x] Implement gap fill detection algorithm
- [x] Add performance metric calculations

### ✅ Phase 2: Data Collection (COMPLETE)
- [x] Integrate Polygon daily aggregate API
- [x] Integrate Polygon minute bars API
- [x] Add trading day completion checks
- [x] Implement update logic (missing/incomplete/force)

### ✅ Phase 3: Command Interface (COMPLETE)
- [x] Create `tradescout gap backtest` command
- [x] Add date filtering (--date)
- [x] Add num-days filtering (--num-days)
- [x] Add force refresh (--force)
- [x] Add dry-run mode (--dry-run)
- [x] Display backtest results with statistics
- [x] Academic gap type classification and statistics

### 🔄 Phase 4: Analysis & Reporting (Future Enhancements)
- [ ] Enhanced statistics dashboard with more metrics
- [ ] Generate performance heatmaps (quality tier × outcome)
- [ ] Export ML training data with outcomes
- [ ] Automated weekly backtest reports
- [ ] Full strategy backtest (entry within 2 hours, stop losses, exit rules)

---

## 💡 Key Design Decisions

### Single-Day Performance Only

**Decision:** Track only intraday same-day performance (9:30-4:00), not multi-day trends.

**Rationale:**
- Gap trading is intraday strategy (open-to-close)
- Clear success/failure criteria (did setup work that day?)
- Avoids complexity of multi-day holding period decisions
- Mechanical: buy-at-open, sell-at-close removes discretionary variables

### No Trade Tracking

**Decision:** Do NOT track whether user actually took the trade.

**Rationale:**
- Strategy validation, not personal P&L tracking
- Measures "if I followed the system perfectly, what would happen?"
- Removes psychological/execution variables from data
- Clean separation: strategy performance vs personal performance

### Immutable Performance Records

**Decision:** Performance data doesn't update after trading day completes.

**Rationale:**
- Trading day bar is final after 4:00 PM close
- Historical snapshot preserves exact conditions
- Force refresh available if data corrections needed
- Audit trail for strategy evolution

### Gap Fill = Touch Reference Price

**Decision:** Gap is "filled" if any intraday bar touches reference price, even if closes above/below.

**Rationale:**
- Conservative definition (most restrictive)
- Intraday touch is objective, verifiable criterion
- Reflects actual trading risk (stop-out if gap fills)
- Consistent with academic gap trading literature

---

## ✅ Success Criteria

### Data Quality
- ✓ 100% of completed trading days have performance data
- ✓ No missing fields (entry/exit/high/low all populated)
- ✓ Gap fill timestamps accurate to the minute
- ✓ Performance metrics calculated consistently

### Strategy Validation
- ✓ Quality tiers show predictive power (excellent > good > fair > poor)
- ✓ Filter effectiveness measurable (exhaustion, volume, Friday)
- ✓ 30+ days of data for statistical significance
- ✓ Win rate and avg return align with strategy expectations

### Operational Efficiency
- ✓ Command runs in <1 minute for 30 days of gaps
- ✓ Polygon API rate limits respected
- ✓ Graceful handling of missing data (delisted stocks, API errors)
- ✓ Clear output showing what was updated and why

---

## 📚 References

- **Gap Results Documentation:** docs/GAP_RESULTS.md
- **Gap Strategy Documentation:** docs/GAP_TRADING_STRATEGY.md
- **Database Schema:** src/database/migrations/004_add_gap_candidate_tables.sql
- **Gap Results Manager:** src/database/managers/gap_candidate_manager.py
- **Gap Performance Manager:** src/database/managers/gap_performance_manager.py
- **Gap Performance Calculator:** src/analysis/gap_performance_calculator.py
- **Gap Analysis Command:** src/cli/gap_commands.py (analyze subcommand)
- **Gap Backtest Command:** src/cli/gap_commands.py (backtest subcommand)
- **Gap Display Classes:** src/output/gap_display.py
- **Polygon API Docs:** https://polygon.io/docs/stocks

---

**Status:** ✅ Implemented and Active
**Current Features:** Simplified backtest (open-to-close), academic gap type classification, statistics dashboard
**Future Enhancements:** Full strategy backtest with entry/exit rules, stop losses, position sizing
