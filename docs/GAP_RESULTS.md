# Gap Results Database & Query System

**Purpose:** Store and query gap analysis results for historical review, performance tracking, and strategy validation

**Status:** Implemented
**Created:** 2025-10-11

---

## 🎯 Overview

When you run `gap analyze`, all candidates (passed, rejected, warnings) can be saved to the database with complete analysis context. The `gap results` command lets you explore this historical data to review past analyses, track patterns, and validate strategy decisions.

**Key Benefits:**
- **Historical review:** "What gaps were found last week?"
- **Pattern analysis:** "How many Friday gaps get rejected?"
- **Filter validation:** "Does volume filter prevent bad setups?"
- **Performance tracking:** Link to actual outcomes (via `gap performance`)

---

## 📊 What Gets Stored

### Every Gap Candidate Record Includes:

**Identification**
- Symbol, name, asset_id
- Analysis timestamp (when analyzed)
- Trading date
- Session type (premarket/afterhours)

**Gap Characteristics**
- Gap percentage and direction (up/down)
- Reference price, current price
- Day/prevday OHLC data

**Volume Analysis**
- Extended hours volume
- Previous day volume
- Volume ratio

**Market Context**
- Market cap
- Sector
- Friday gap flag

**Quality Assessment**
- Quality score (0-100)
- Quality tier (excellent/good/fair/poor)
- Catalyst score
- Volume/gap size/alignment scores

**Filter Results**
- Passed gap filter (boolean)
- Passed volume filter (boolean)
- Passed market cap filter (boolean)
- Passed exhaustion filter (boolean)

**Status & Rejection**
- Status (passed/rejected/warning)
- Rejection reason (detailed explanation)

**News & Sentiment**
- News count
- Sentiment score
- Has tier-1 catalyst flag

---

## 🔍 Query Command: `tradescout gap results`

### Basic Usage

```bash
# Show last 5 days (default)
./tradescout gap results

# Show last 10 days
./tradescout gap results --num-days=10

# Show specific date
./tradescout gap results --date=2025-10-09

# Show more results per day
./tradescout gap results --num-results-per-day=20
```

### Filtering Options

```bash
# Filter by session
./tradescout gap results --session=premarket
./tradescout gap results --session=afterhours
./tradescout gap results --session=all  # default

# Filter by status
./tradescout gap results --status=passed
./tradescout gap results --status=rejected
./tradescout gap results --status=warning
./tradescout gap results --status=all  # default

# Combine filters
./tradescout gap results --session=afterhours --status=passed --num-days=30
```

### Example Output

```
╭────────────────────────────────────────╮
│ Gap Analysis Results - Historical Data │
╰────────────────────────────────────────╯

═══ 2025-10-10 ═══
1 total results
┏━━━━━━┳━━━━━━━━┳━━━━━━┳━━━━━━━━┳━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃      ┃        ┃  Gap ┃    Vol ┃       ┃        ┃                             ┃
┃ Sym… ┃ Sessi… ┃    % ┃  Ratio ┃  MCap ┃ Status ┃ Rejection                   ┃
┡━━━━━━╇━━━━━━━━╇━━━━━━╇━━━━━━━━╇━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ ASST │ 🌙 AF  │ -32… │  2.33x │ $1.7B │ WARNI… │ Friday gap - weekend risk   │
└──────┴────────┴──────┴────────┴───────┴────────┴─────────────────────────────┘

═══ 2025-10-09 ═══
19 total results
┏━━━━━━┳━━━━━━━━┳━━━━━━┳━━━━━━━━┳━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃      ┃        ┃  Gap ┃    Vol ┃       ┃        ┃                             ┃
┃ Sym… ┃ Sessi… ┃    % ┃  Ratio ┃  MCap ┃ Status ┃ Rejection                   ┃
┡━━━━━━╇━━━━━━━━╇━━━━━━╇━━━━━━━━╇━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ AKRO │ 🌅 PR  │ +17… │  4.34x │ $3.7B │ REJEC… │ Volume ratio < 1.5x         │
│ TLRY │ 🌅 PR  │ +15… │  0.12x │ $1.8B │ REJEC… │ Volume ratio < 1.5x         │
│ NEOG │ 🌅 PR  │ +9.… │  0.01x │ $1.3B │ REJEC… │ Volume ratio < 1.5x         │
  ... and 16 more results not shown

Summary:
  Days shown: 2
  Results displayed: 11
  Results hidden: 9

Database Statistics (2025-09-11 to 2025-10-11):
  Total results: 36
  Passed: 0 (0.0%)
  Rejected: 35 (97.2%)
```

---

## 📈 Understanding the Data

### Status Classifications

| Status | Meaning | Action |
|--------|---------|--------|
| `passed` | Candidate passed all filters | Consider for trading |
| `rejected` | Failed at least one filter | Do not trade |
| `warning` | Passed filters but has risk flag | Trade with caution |

### Common Rejection Reasons

| Rejection Reason | Filter | Explanation |
|------------------|--------|-------------|
| `Volume ratio < 1.5x` | Volume | Insufficient institutional participation |
| `Exhaustion gap (gap≥5% + vol≥3x)` | Exhaustion | Likely climax move, reversal risk |
| `Friday gap - weekend risk` | Friday | Higher uncertainty over weekend |
| `Market cap < $1B` | Market cap | Liquidity concerns |

### Session Icons

- 🌅 **Premarket** (4:00-9:30 AM) - Gap for day about to open
- 🌙 **Afterhours** (4:00-8:00 PM) - Gap for next trading day

### Quality Tiers

Based on quality score (0-100):
- **Excellent** (85-100): Highest quality setups
- **Good** (70-84): Solid setups
- **Fair** (60-69): Marginal setups
- **Poor** (<60): Low quality, likely rejected

---

## 🔗 Integration with Performance Tracking

Gap results link to performance tracking via the `gap_candidate_result` table:

```bash
# Analyze gaps (saves to gap_candidate)
./tradescout gap analyze

# Later: Update performance data
./tradescout gap performance

# Query results with performance
./tradescout gap results --with-performance
```

See [GAP_PERFORMANCE.md](GAP_PERFORMANCE.md) for details on performance tracking.

---

## 💡 Common Queries & Use Cases

### 1. Review Last Week's Gaps

```bash
./tradescout gap results --num-days=7
```

**Use case:** Weekly review to see what opportunities existed

### 2. See Only Passed Candidates

```bash
./tradescout gap results --status=passed --num-days=30
```

**Use case:** Review high-quality setups from last month

### 3. Analyze Friday Gap Warnings

```bash
./tradescout gap results --status=warning --num-days=90
```

**Use case:** See how often Friday gaps appear and get flagged

### 4. Deep Dive on Specific Date

```bash
./tradescout gap results --date=2025-10-09 --num-results-per-day=100
```

**Use case:** Full analysis of a specific day's candidates

### 5. Premarket vs Afterhours Comparison

```bash
# Premarket only
./tradescout gap results --session=premarket --num-days=30

# Afterhours only
./tradescout gap results --session=afterhours --num-days=30
```

**Use case:** Compare session characteristics and pass rates

---

## 📊 Statistics & Insights

The summary section shows:

**Days Shown:** How many trading days are displayed
**Results Displayed:** Number of candidates shown (respects limits)
**Results Hidden:** Additional candidates not shown (use --num-results-per-day to see more)

**Database Statistics:**
- Date range of all stored results
- Total result count
- Pass/reject rates
- Warning rate

**Example Insights:**

```
Database Statistics (2025-09-11 to 2025-10-11):
  Total results: 156
  Passed: 12 (7.7%)
  Rejected: 142 (91.0%)
  Warnings: 2 (1.3%)
```

**Interpretation:**
- 30 days of data collected
- 92.3% rejection rate shows filters are working (high bar for quality)
- 12 passed candidates = ~2.5 per week average
- Warnings rare (only Friday gaps with otherwise good setups)

---

## 🗄️ Database Schema

### Primary Table: `gap_candidate`

Stores every gap candidate evaluation. Key fields:

```sql
CREATE TABLE gap_candidate (
    id INTEGER PRIMARY KEY,
    asset_id INTEGER NOT NULL,
    analysis_timestamp TIMESTAMP NOT NULL,
    session_type TEXT NOT NULL,
    trading_date DATE NOT NULL,

    gap_percentage REAL NOT NULL,
    gap_direction TEXT NOT NULL,

    reference_price REAL NOT NULL,
    current_price REAL NOT NULL,
    prevday_close REAL NOT NULL,

    volume_ratio REAL,
    market_cap REAL,

    quality_score REAL,
    quality_tier TEXT,
    catalyst_score REAL,

    passed_gap_filter BOOLEAN NOT NULL,
    passed_volume_filter BOOLEAN NOT NULL,
    passed_market_cap_filter BOOLEAN NOT NULL,
    passed_exhaustion_filter BOOLEAN NOT NULL,
    is_friday_gap BOOLEAN NOT NULL,

    status TEXT NOT NULL,
    rejection_reason TEXT,

    sentiment_score REAL,
    news_count INTEGER,

    FOREIGN KEY (asset_id) REFERENCES assets(id)
);
```

See database migration file `src/database/migrations/004_add_gap_candidate_tables.sql` for complete schema.

---

## 🔄 Data Flow

### 1. Analysis Phase (Create Records)

```
User runs: ./tradescout gap analyze
  ↓
Gap analyzer finds candidates
  ↓
For each candidate:
  - Calculate quality scores
  - Apply filters
  - Determine status/rejection
  ↓
User confirms: Save results to database? [Y/n]
  ↓
All candidates saved to gap_candidate table
```

### 2. Query Phase (Read Records)

```
User runs: ./tradescout gap results --num-days=7
  ↓
Query gap_candidate table
  ↓
Filter by date range, session, status
  ↓
Order by trading_date DESC, quality_score DESC
  ↓
Display formatted results with summary
```

### 3. Performance Phase (Enrich Records)

```
User runs: ./tradescout gap performance
  ↓
Find gap results without performance data
  ↓
For each gap:
  - Fetch intraday bars
  - Calculate returns
  - Detect gap fills
  ↓
Save to gap_candidate_result table
  ↓
Query results now show performance metrics
```

---

## ✅ Data Quality & Completeness

### Automatic Saving

Since gap analysis integration (2025-10-11), all gap candidates are **automatically offered for database storage** with user confirmation:

```
Save results to database? [Y/n]
```

**Best practice:** Always save results (press Enter for default Yes) to build historical data.

### What's Not Stored

- Intermediate calculation steps
- Rejected candidates before volume validation (never got that far in analysis)
- Real-time price updates after analysis completed

### Retention Policy

- No automatic deletion
- Keep all historical data for long-term analysis
- Manual cleanup if desired (SQL DELETE queries)

---

## 🎓 Advanced Analysis Examples

### SQL Queries for Power Users

**Rejection reason frequency:**
```sql
SELECT rejection_reason, COUNT(*) as frequency
FROM gap_candidate
WHERE status = 'rejected'
GROUP BY rejection_reason
ORDER BY frequency DESC;
```

**Average gap size by session:**
```sql
SELECT session_type, AVG(gap_percentage) as avg_gap
FROM gap_candidate
GROUP BY session_type;
```

**Quality tier distribution:**
```sql
SELECT quality_tier, COUNT(*) as count
FROM gap_candidate
WHERE quality_tier IS NOT NULL
GROUP BY quality_tier;
```

**Friday gap frequency:**
```sql
SELECT is_friday_gap, COUNT(*) as count
FROM gap_candidate
GROUP BY is_friday_gap;
```

---

## 📚 Related Documentation

- **[GAP_TRADING_STRATEGY.md](GAP_TRADING_STRATEGY.md)** - Gap trading strategy overview
- **[GAP_TRADING_STRATEGY_RULES.md](GAP_TRADING_STRATEGY_RULES.md)** - Detailed rules and filters
- **[GAP_PERFORMANCE.md](GAP_PERFORMANCE.md)** - Performance tracking system
- **Migration:** `src/database/migrations/004_add_gap_candidate_tables.sql` - Database schema

---

## ✅ Summary

The gap results database provides:

✓ **Complete historical record** of all gap analyses
✓ **Query interface** for exploring past candidates
✓ **Filter validation** data (what gets rejected and why)
✓ **Performance linkage** for outcome tracking
✓ **Pattern analysis** capability for strategy refinement

Every `gap analyze` run adds to this knowledge base, enabling data-driven strategy validation and continuous improvement.
