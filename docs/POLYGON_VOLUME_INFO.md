# Polygon Volume Data - Complete Reference

**Purpose:** Understand Polygon volume fields, trade eligibility rules, and proper usage for gap trading
**Last Updated:** 2025-10-10

---

## Part 1: Volume Fields Structure

### Available Fields by Session

Polygon Snapshot API provides different volume fields depending on the trading session:

```
prevDay:
  .v  → Total volume for completed previous session (final count)

day:
  .v  → Total volume for regular session (9:30am-4pm ET, final count)

min:
  .v  → Individual minute bar volume (this minute only)
  .av → Accumulated volume (running total from 4:00 AM)
```

**Key Insight:** `av` (accumulated volume) only exists in `min` bar. Completed sessions (`prevDay`, `day`) only have `.v` because they're final totals.

### Database Schema Mapping

```sql
-- All volume fields captured in ticker_snapshots table:
prevday_volume BIGINT              -- prevDay.v
day_volume BIGINT                  -- day.v
min_volume BIGINT                  -- min.v (individual minute)
min_accumulated_volume BIGINT      -- min.av (accumulated total)
```

### Model Objects

```python
@dataclass(frozen=True)
class MinuteBar:
    volume: Optional[int]              # min.v
    accumulated_volume: Optional[int]  # min.av

@dataclass(frozen=True)
class TickerSnapshot:
    prev_volume: Optional[int]         # prevDay.v
    volume: Optional[int]              # day.v
    min_bar: Optional[MinuteBar]       # Contains min.v and min.av
```

---

## Part 2: Trade Eligibility Rules (Why Volumes Differ)

### The Root Cause: CTA/UTP Specifications

**Critical Discovery:** Snapshot volume and Aggregates API volume differ by design, not due to bugs.

**Reference:** [Polygon.io: Understanding Trade Eligibility](https://polygon.io/blog/understanding-trade-eligibility)

### Two Different Volume Measurements

#### Snapshot `min.av` (All Trades)
- Includes **ALL trades** regardless of sale conditions
- Raw total count of shares traded
- Does NOT filter based on eligibility rules
- **Use case:** Fast screening only

**What's included:**
- Trade-eligible volume
- Odd-lots (<100 shares)
- Late-reported trades
- Average price trades
- Extended hours special conditions
- Intermarket sweep orders
- Opening/closing cross trades with special conditions

#### Aggregates API (Trade-Eligible Only)
- Follows **CTA/UTP consolidated update guidelines**
- Only includes trades where `updates_volume: true`
- Filters out trades that don't meet eligibility per market specs
- **This is "official" market volume** used by exchanges

**What's excluded:**
- Trades with sale condition codes indicating `updates_volume: false`
- Odd-lot trades that don't meet market specifications
- Late-reported trades
- Special pricing conditions
- Certain extended hours trade types

### How Trade Eligibility Works

Each trade has sale condition codes that determine inclusion:

```json
{
  "update_rules": {
    "consolidated": {
      "updates_high_low": false,
      "updates_open_close": false,
      "updates_volume": true/false  // ← Determines Aggregates inclusion
    }
  }
}
```

If **ANY** sale condition indicates `updates_volume: false`, that trade is **excluded** from Aggregates.

### Expected Variance Patterns

| Variance Range | Stock Type | Explanation |
|---------------|------------|-------------|
| 0-25% | Highly liquid | Mostly eligible trades, minimal noise |
| 25-50% | Medium liquidity | Normal extended hours behavior |
| 50-130% | Low liquidity | High % of odd-lots and special orders |

**During extended hours (premarket/after-hours):**
- Ineligible trades make up higher percentage
- Odd-lot trades (<100 shares) are common
- Late-reported trades increase
- Special order types more prevalent
- **This is normal market behavior, not a data quality issue**

---

## Part 3: Session-Specific Behavior & Test Results

### Premarket (4:00-9:30 AM) ✅ WORKS

**Field to use:** `min.av` (accumulated volume)

**Status:** ⚠️ Acceptable for screening, validate with Aggregates before trading

**Test Results - October 8, 2025 (7:16 AM):**
| Symbol | Snapshot min.av | Aggregates API | Variance | Status |
|--------|----------------|----------------|----------|--------|
| SPY | 104,047 | 97,495 | +6.72% | ✅ Good |
| AAPL | 43,905 | 35,949 | +22.13% | ✅ Good |
| NVDA | 893,019 | 923,176 | -3.27% | ✅ Good |
| TSLA | 554,803 | 555,471 | -0.12% | ✅ Good |

**Test Results - October 8, 2025 (8:50 AM):**
| Symbol | Snap Vol | Agg Vol | Variance | Status |
|--------|----------|---------|----------|--------|
| ON | 15,861 | 12,589 | +26.0% | ⚠️ OK |
| AGI | 13,727 | 5,960 | **+130.3%** | ❌ High |
| BTOG | 654,811 | 460,711 | +42.1% | ⚠️ OK |
| PULM | 1,166 | 1,166 | +0.0% | ✅ Good |
| KBDC | 100 | 100 | +0.0% | ✅ Good |

**Test Results - October 10, 2025 (8:44 AM - Confirmation):**
| Symbol | Snap Vol | Agg Vol | Variance | Status |
|--------|----------|---------|----------|--------|
| AAPL | 167,320 | 84,909 | **+97.1%** | ❌ High |
| DKS | 505 | 500 | +1.0% | ✅ Good |
| FINV | 200 | 200 | +0.0% | ✅ Good |
| NVDA | 3,082,216 | 2,261,558 | +36.3% | ⚠️ OK |
| UBER | 64,138 | 41,540 | +54.4% | ❌ High |

**Key Findings:**
- ✅ `min.av` updates correctly during premarket
- ✅ Variance 0-130% consistent across test dates
- ✅ Trade eligibility explains variance patterns
- ✅ Reliable for screening with 150%+ volume spike threshold
- ⚠️ MUST validate with Aggregates before trading

**Recommendation:**
- **Screen** with `min.av` for fast candidate identification
- **Validate** with Aggregates API before trading (expect 20-50% lower)
- **Trade** based on Aggregates volume, not `min.av`

---

### Regular Hours (9:30 AM-4:00 PM) ✅ RELIABLE

**Field to use:** `day.v` (regular session volume)

**Status:** ✅ Most accurate, always reliable

**Why:** Completed session with final total, no accumulation issues

---

### After-Hours (4:00-8:00 PM) ❌ CRITICAL ISSUE

**Field to use:** ❌ **SNAPSHOT DATA UNUSABLE**

**Status:** ❌ **COMPLETELY UNRELIABLE - DO NOT USE**

**Problem:** `min.av` **FREEZES at `day.v` value** at 4:00 PM market close

**Test Results - October 9, 2025 (6:30 PM during live after-hours):**

**NVDA Example (6:20 PM):**
```json
{
  "min": {
    "av": 182,506,387,    // ❌ Frozen at 4 PM value
    "v": 3,576,           // ✅ Updates (this minute only)
    "t": 1760048400000,   // 6:20 PM timestamp
    "n": 73               // 73 trades this minute
  },
  "day": {
    "v": 182,506,387      // ❌ SAME as min.av
  }
}
```

**Calculation:**
- `min.av - day.v` = 182,506,387 - 182,506,387 = **0** ❌
- Aggregates API 4:00-6:30 PM: **1,943,573 shares** ✅
- Individual minute at 6:20 PM: **3,576 shares** (min.v updates!) ✅
- Accumulated volume: **Does NOT update** (min.av frozen) ❌

**Test Results Across 15 Symbols (100% Failure Rate):**
| Symbol | min.av - day.v | Aggregates (Actual AH Volume) | Status |
|--------|----------------|------------------------------|--------|
| NVDA | 0 | 1,943,573 shares | ❌ |
| AAPL | 0 | 903,457 shares | ❌ |
| AMZN | 0 | 698,708 shares | ❌ |
| TSLA | 0 | 588,813 shares | ❌ |
| MSFT | 0 | 180,326 shares | ❌ |
| PSQ | 0 | 21,781 shares | ❌ |
| BLOX | 0 | 9,252 shares | ❌ |
| MCW | 0 | 10,764 shares | ❌ |

**Confirmed Behavior:**
1. `min.av` accumulates from 4:00 AM through 4:00 PM (premarket + regular)
2. At 4:00 PM market close, `min.av` **STOPS updating** and equals `day.v`
3. From 4:00-8:00 PM, `min.av` remains frozen at `day.v` value
4. Individual minute bars (`min.v`) CONTINUE to update with per-minute volume
5. `min.av - day.v` equals **0** during entire after-hours session
6. Snapshot API provides **NO accumulated volume** for after-hours

**Recommendation:**
- ✅ **Screen** with `min.c - day.c` for PRICE gaps only
- ❌ **NEVER use** `min.av` or `min.av - day.v` for volume
- ✅ **MUST use Aggregates API** for volume validation (mandatory, no alternative)

---

### Closed (8:00 PM-4:00 AM) ✅ RELIABLE

**Field to use:** `prevDay.v` (previous session's volume)

**Status:** ✅ Most recent completed session, always accurate

---

## Part 4: Architecture & Implementation

### Problem: Previous Approach (Inaccurate)

**Old screener YAML:**
```yaml
name: "gainers_premarket"
filters:
  - "((ap.min_close - ap.prevday_close) / ap.prevday_close * 100) >= 2.0"
  - "ap.min_accumulated_volume >= 10000"  # ❌ WRONG: Includes ineligible trades
```

**Issues:**
- Snapshot volume includes ALL trades (eligible + ineligible)
- 30-130% inflated during extended hours
- Inconsistent with professional standards
- Complex session-specific logic needed

---

### Solution: Two-Stage Screening Architecture

#### Stage 1: Price-Based Filtering (Fast - Snapshot API)
- Filter by: price change %, session type, exchange, liquidity
- **NO volume filtering** - ignore snapshot volume completely
- Use snapshot for fast price/session filtering only
- Returns: List of price-qualified candidates

**New screener YAML (Stage 1 only):**
```yaml
name: "gainers_premarket"
description: "Premarket gainers ≥2% (price filter only)"

# Stage 1: Price filtering (snapshot)
filters:
  - "ap.prevday_close IS NOT NULL"
  - "ap.min_close IS NOT NULL"
  - "((ap.min_close - ap.prevday_close) / ap.prevday_close * 100) >= 2.0"
  # NO volume filter here!

# Stage 2: Volume validation (aggregates API)
volume_validation:
  enabled: true
  min_volume_ratio: 1.5  # 1.5x previous day average
  session: "premarket"   # For aggregates time window
```

#### Stage 2: Volume Validation (Accurate - Aggregates API)
- Take candidates from Stage 1
- Query Aggregates API for each candidate
- Calculate volume ratio using **trade-eligible volume only**
- Filter by volume threshold (e.g., ≥1.5x previous day)
- Returns: Final candidates with accurate volume validation

---

### Implementation: ScreenerEngine

```python
class ScreenerEngine:
    def run_screener(
        self,
        config: ScreenerConfig,
        market_context: MarketContext
    ) -> List[ScreenerResult]:
        """Two-stage screening with volume validation."""

        # Stage 1: Price-based SQL filtering (fast)
        sql_candidates = self._run_sql_query(config, market_context)

        # Stage 2: Volume validation via Aggregates API (accurate)
        if config.volume_validation.enabled:
            validated_candidates = self._validate_volume(
                candidates=sql_candidates,
                min_ratio=config.volume_validation.min_volume_ratio,
                session=config.volume_validation.session,
                trading_date=market_context.current_date
            )
            return validated_candidates

        return sql_candidates

    def _validate_volume(
        self,
        candidates: List[AssetPrice],
        min_ratio: float,
        session: str,
        trading_date: date
    ) -> List[ScreenerResult]:
        """Validate volume using Aggregates API."""

        validated = []

        for candidate in candidates:
            # Get trade-eligible volume from Aggregates
            agg_volume = self.data_service.calculate_extended_hours_volume(
                symbol=candidate.symbol,
                trading_date=trading_date,
                session=session
            )

            if agg_volume is None:
                continue  # Skip if no aggregates data

            # Calculate volume ratio vs previous day average
            # Previous day volume / 6.5 hours = hourly average
            prev_day_hourly_avg = candidate.prevday_volume / 6.5

            # Session volumes:
            # - Premarket: 5.5 hours (4:00-9:30)
            # - After-hours: 4 hours (4:00-8:00)
            session_hours = 5.5 if session == "premarket" else 4.0
            expected_volume = prev_day_hourly_avg * session_hours

            volume_ratio = agg_volume / expected_volume if expected_volume > 0 else 0

            if volume_ratio >= min_ratio:
                validated.append(ScreenerResult(
                    asset_price=candidate,
                    volume_ratio=volume_ratio,
                    aggregates_volume=agg_volume,
                    snapshot_volume=candidate.min_accumulated_volume,  # For comparison
                    validation_passed=True
                ))

        return validated
```

---

### Benefits of Two-Stage Architecture

#### 1. Accuracy
- ✅ Uses **trade-eligible volume** (CTA/UTP compliant)
- ✅ Matches what professional traders see
- ✅ No noise from odd-lots, late reports, special conditions

#### 2. Simplicity
- ✅ Single volume source (Aggregates) for all sessions
- ✅ No complex session-specific volume field logic
- ✅ Clear separation: snapshot = price, aggregates = volume

#### 3. Consistency
- ✅ Same approach for premarket AND after-hours
- ✅ Uniform volume calculation methodology
- ✅ Professional-grade filtering

#### 4. Performance
- ✅ Stage 1 (SQL) is still fast - no volume filtering
- ⚠️ Stage 2 requires Aggregates API calls per candidate
- ✅ Can parallelize Aggregates queries if needed

---

### Performance Considerations

**Aggregates API Calls:**
- Each candidate requires 1 Aggregates API call
- If Stage 1 returns 50 candidates → 50 API calls
- Polygon Premium allows sufficient API quota

**Mitigation Strategies:**
1. **Strict Stage 1 filter** - Fewer candidates to validate
2. **Parallel API calls** - Query multiple symbols concurrently
3. **Accept the cost** - Accuracy > speed for trading decisions
4. **Optional rough filter** - Could add `min.av >= 1000` to Stage 1 to eliminate zero-volume stocks

---

### Example Output

```
📊 Premarket Gainers (≥2%) - Volume Validated

Stage 1: 47 price-qualified candidates
Stage 2: 12 volume-validated candidates (≥1.5x previous day)

┌────────┬─────────┬────────────┬──────────────┬─────────────┬──────────┐
│ Symbol │ Change% │ Agg Volume │ Snap Volume  │ Volume Ratio│ Status   │
├────────┼─────────┼────────────┼──────────────┼─────────────┼──────────┤
│ DHAI   │  +5.2%  │   11,891   │   17,653     │    2.3x     │ ✅ Pass  │
│ AGI    │  +8.1%  │    5,960   │   13,727     │    1.8x     │ ✅ Pass  │
│ BTOG   │  +3.4%  │  460,711   │  654,811     │    1.6x     │ ✅ Pass  │
│ MKZR   │  +2.8%  │      335   │      347     │    0.9x     │ ❌ Fail  │
└────────┴─────────┴────────────┴──────────────┴─────────────┴──────────┘

Legend:
- Agg Volume: Trade-eligible volume (CTA/UTP specs)
- Snap Volume: Raw volume (includes ineligible trades)
- Volume Ratio: vs previous day average for session hours
```

---

## Summary: Best Practices

### ✅ DO

1. **Premarket Screening:**
   - Use `min.av` for initial price-based screening (fast)
   - MUST validate with Aggregates API before trading
   - Expect Aggregates to show 20-50% lower volume (this is correct)

2. **Regular Hours:**
   - Use `day.v` for completed session volume (reliable)

3. **After-Hours Screening:**
   - Use `min.c - day.c` for PRICE gaps only
   - MUST use Aggregates API for volume (no snapshot alternative)

4. **Closed Market:**
   - Use `prevDay.v` for previous session volume (reliable)

5. **Volume Validation:**
   - Always use Aggregates API for final trading decisions
   - Accept 1-2 minute processing lag for accuracy
   - Trust Aggregates over snapshot for volume

### ❌ DON'T

1. ❌ **Never use `min.av - day.v` for after-hours volume** (always equals 0)
2. ❌ **Never trade based on `min.av` alone** (includes ineligible trades)
3. ❌ **Never trust snapshot volume for trading decisions** (screening only)
4. ❌ **Don't expect snapshot and Aggregates to match** (they shouldn't!)

### Why Both Are Needed

**Snapshot `min.av` (Screening):**
- Fast, real-time data
- Includes all trades (eligible + ineligible)
- Good for rapid screening (150%+ spikes still detectable)
- NOT what professionals use for decisions

**Aggregates API (Trading):**
- Trade-eligible volume only (CTA/UTP specs)
- Matches what professional traders see
- Excludes noise (odd-lots, late reports, special conditions)
- Represents actual liquid, tradeable volume
- Has 1-2 minute processing lag (acceptable for accuracy)

**Golden Rule:**
**Screen with snapshot → Validate with Aggregates → Trade based on Aggregates**

---

## References

- [Polygon.io: Understanding Trade Eligibility](https://polygon.io/blog/understanding-trade-eligibility)
- [CTA Plan Specification](https://www.ctaplan.com/publicdocs/ctaplan/notifications/trader-update/CTS_BINARY_OUTPUT_SPECIFICATION.pdf)
- [UTP Plan Specification](https://www.utpplan.com/DOC/UtpBinaryOutputSpec.pdf)
- TradeScout Gap Trading Strategy Documentation
