# Technical Indicators System - Planning Document

**Purpose:** Plan the architecture for technical indicators (RSI, MACD, SMA, EMA) to enhance gap analysis with ticker-specific momentum and trend signals.

**Status:** Planning Phase
**Date:** 2025-10-10

---

## Table of Contents
1. [Overview](#overview)
2. [Use Cases](#use-cases)
3. [Polygon API Endpoints](#polygon-api-endpoints)
4. [Data Model Design](#data-model-design)
5. [Provider Architecture](#provider-architecture)
6. [Manager & Storage](#manager--storage)
7. [Integration with Gap Analysis](#integration-with-gap-analysis)
8. [CLI Commands](#cli-commands)
9. [Configuration](#configuration)
10. [Implementation Phases](#implementation-phases)
11. [Future Extensibility](#future-extensibility)

---

## Overview

### What Are Technical Indicators?

Technical indicators are mathematical calculations based on historical price, volume, or open interest data. They help traders:
- Identify trends (momentum, direction)
- Detect overbought/oversold conditions
- Generate buy/sell signals
- Confirm price movements

### Why We Need Them

**Current Gap Analysis Limitation:**
Our gap analysis identifies price gaps and filters by volume/liquidity, but lacks **momentum and trend context**. A stock might gap up, but is it:
- Overbought and likely to reverse?
- In a strong uptrend with RSI confirmation?
- Showing MACD crossover signaling continued momentum?

**Solution:**
Add ticker-specific indicators at the **final stage** of gap candidate evaluation to provide technical confirmation.

---

## Use Cases

### Primary: Gap Analysis Enhancement
After identifying gap candidates (price gap + volume + liquidity filters), enrich each candidate with:

1. **RSI (Relative Strength Index)** - Detect overbought/oversold
   - RSI > 70: Overbought (potential reversal)
   - RSI < 30: Oversold (potential reversal)
   - RSI 30-70: Neutral zone

2. **MACD (Moving Average Convergence/Divergence)** - Momentum signals
   - MACD line crosses signal line: Buy/sell signals
   - Histogram: Momentum strength/direction
   - Divergence: Trend weakness/reversal

3. **SMA/EMA (Moving Averages)** - Trend context
   - Price above/below MA: Trend direction
   - MA crossovers: Trend changes
   - Dynamic support/resistance levels

### Example Gap Candidate Enrichment
```
Gap Candidate: AAPL
- Gap: +3.2% (from $180 → $185.76)
- Volume: 2.5x average
- Market Cap: $2.8T
- Liquidity: Excellent

INDICATORS:
- RSI (14-day): 68.5 (approaching overbought)
- MACD: Bullish crossover (signal: BUY)
- 50-day SMA: $178 (price above = uptrend)
- 20-day EMA: $182 (strong support)

SIGNAL: Strong buy with momentum, watch for RSI overbought reversal near 70
```

---

## Polygon API Endpoints

### 1. RSI - Relative Strength Index
**Endpoint:** `GET /v1/indicators/rsi/{stockTicker}`

**Parameters:**
- `timestamp` - Date (YYYY-MM-DD) or millisecond timestamp
- `timespan` - Aggregate window (minute, hour, day, week, month)
- `adjusted` - Adjust for splits (default: true)
- `window` - RSI calculation window size (default: 14)
- `series_type` - Price type: close, open, high, low
- `order` - asc/desc by timestamp
- `limit` - Number of results (default: 10, max: 5000)

**Response:**
```json
{
  "status": "OK",
  "results": {
    "values": [
      {
        "timestamp": 1234567890000,
        "value": 65.3
      }
    ]
  },
  "next_url": "..."
}
```

**Key Metrics:**
- Value range: 0-100
- Overbought: > 70
- Oversold: < 30

---

### 2. MACD - Moving Average Convergence/Divergence
**Endpoint:** `GET /v1/indicators/macd/{stockTicker}`

**Parameters:**
- `timestamp` - Date (YYYY-MM-DD) or millisecond timestamp
- `timespan` - Aggregate window
- `adjusted` - Adjust for splits (default: true)
- `short_window` - Short EMA window (default: 12)
- `long_window` - Long EMA window (default: 26)
- `signal_window` - Signal line window (default: 9)
- `series_type` - Price type: close, open, high, low
- `order` - asc/desc
- `limit` - Number of results (default: 10, max: 5000)

**Response:**
```json
{
  "status": "OK",
  "results": {
    "values": [
      {
        "timestamp": 1234567890000,
        "value": 2.5,
        "signal": 1.8,
        "histogram": 0.7
      }
    ]
  }
}
```

**Key Metrics:**
- MACD line: Short EMA - Long EMA
- Signal line: EMA of MACD line
- Histogram: MACD - Signal (momentum strength)

---

### 3. SMA - Simple Moving Average
**Endpoint:** `GET /v1/indicators/sma/{stockTicker}`

**Parameters:**
- `timestamp` - Date (YYYY-MM-DD) or millisecond timestamp
- `timespan` - Aggregate window
- `adjusted` - Adjust for splits (default: true)
- `window` - SMA calculation window (e.g., 20, 50, 200)
- `series_type` - Price type: close, open, high, low
- `order` - asc/desc
- `limit` - Number of results (default: 10, max: 5000)

**Response:**
```json
{
  "status": "OK",
  "results": {
    "values": [
      {
        "timestamp": 1234567890000,
        "value": 178.45
      }
    ]
  }
}
```

**Common Windows:**
- 20-day: Short-term trend
- 50-day: Medium-term trend
- 200-day: Long-term trend

---

### 4. EMA - Exponential Moving Average
**Endpoint:** `GET /v1/indicators/ema/{stockTicker}`

**Parameters:**
- `timestamp` - Date (YYYY-MM-DD) or millisecond timestamp
- `timespan` - Aggregate window
- `adjusted` - Adjust for splits (default: true)
- `window` - EMA calculation window (e.g., 12, 20, 50)
- `series_type` - Price type: close, open, high, low
- `order` - asc/desc
- `limit` - Number of results (default: 10, max: 5000)

**Response:**
```json
{
  "status": "OK",
  "results": {
    "values": [
      {
        "timestamp": 1234567890000,
        "value": 182.30
      }
    ]
  }
}
```

**Key Difference from SMA:**
- Places greater weight on recent prices
- Faster response to price changes
- Preferred for short-term trading

---

## Data Model Design

### Option 1: Single Polymorphic Table (RECOMMENDED)

**Table:** `indicators`

```sql
CREATE TABLE indicators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    indicator_type TEXT NOT NULL,  -- 'rsi', 'macd', 'sma', 'ema'
    timestamp INTEGER NOT NULL,    -- Unix milliseconds
    timespan TEXT NOT NULL,        -- 'day', 'hour', 'minute'
    window INTEGER,                -- Window size (e.g., 14 for RSI, 20 for SMA)
    series_type TEXT,              -- 'close', 'open', 'high', 'low'
    value REAL,                    -- Primary value (RSI value, SMA value, etc.)
    details TEXT,                  -- JSON blob for complex indicators (MACD has value, signal, histogram)
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (asset_id) REFERENCES assets(id),
    UNIQUE(asset_id, indicator_type, timestamp, timespan, window)
);

CREATE INDEX idx_indicators_asset ON indicators(asset_id);
CREATE INDEX idx_indicators_type ON indicators(indicator_type);
CREATE INDEX idx_indicators_timestamp ON indicators(timestamp DESC);
CREATE INDEX idx_indicators_lookup ON indicators(asset_id, indicator_type, timespan, window, timestamp DESC);
```

**Pros:**
- Single table for all indicators (simpler queries)
- Flexible JSON details for complex indicators (MACD)
- Easy to add new indicator types
- Efficient composite index for lookups

**Cons:**
- MACD has 3 values (value, signal, histogram) - must use JSON
- NULL columns for simple indicators

**Details JSON Examples:**
```json
// RSI (simple value)
{"value": 65.3}

// MACD (complex)
{
  "value": 2.5,
  "signal": 1.8,
  "histogram": 0.7
}

// SMA/EMA (simple value)
{"value": 178.45}
```

---

### Option 2: Separate Tables Per Indicator

**Tables:** `rsi_indicators`, `macd_indicators`, `sma_indicators`, `ema_indicators`

**Pros:**
- Strongly typed columns for each indicator
- No NULL columns

**Cons:**
- 4+ tables to maintain
- Duplicate schema patterns
- Complex queries across indicators
- Harder to add new indicators

**Decision: Use Option 1 (Single Polymorphic Table)**

---

## Provider Architecture

### PolygonIndicatorsProvider

```python
class PolygonIndicatorsProvider(BaseAPIProvider):
    """Provider for technical indicators from Polygon API."""

    def __init__(self, api_key: str):
        super().__init__(api_key, "https://api.polygon.io")

    # ========================================
    # RSI
    # ========================================
    def fetch_rsi(
        self,
        symbol: str,
        timespan: str = "day",
        window: int = 14,
        series_type: str = "close",
        limit: int = 10,
        timestamp: Optional[str] = None
    ) -> List[Indicator]:
        """Fetch RSI (Relative Strength Index) data."""

    # ========================================
    # MACD
    # ========================================
    def fetch_macd(
        self,
        symbol: str,
        timespan: str = "day",
        short_window: int = 12,
        long_window: int = 26,
        signal_window: int = 9,
        series_type: str = "close",
        limit: int = 10,
        timestamp: Optional[str] = None
    ) -> List[Indicator]:
        """Fetch MACD (Moving Average Convergence/Divergence) data."""

    # ========================================
    # SMA
    # ========================================
    def fetch_sma(
        self,
        symbol: str,
        timespan: str = "day",
        window: int = 50,
        series_type: str = "close",
        limit: int = 10,
        timestamp: Optional[str] = None
    ) -> List[Indicator]:
        """Fetch SMA (Simple Moving Average) data."""

    # ========================================
    # EMA
    # ========================================
    def fetch_ema(
        self,
        symbol: str,
        timespan: str = "day",
        window: int = 20,
        series_type: str = "close",
        limit: int = 10,
        timestamp: Optional[str] = None
    ) -> List[Indicator]:
        """Fetch EMA (Exponential Moving Average) data."""

    # ========================================
    # Batch Fetch
    # ========================================
    def fetch_all_indicators(
        self,
        symbol: str,
        timespan: str = "day"
    ) -> Dict[str, List[Indicator]]:
        """Fetch all standard indicators for a symbol.

        Returns:
            {
                'rsi': [Indicator, ...],
                'macd': [Indicator, ...],
                'sma_20': [Indicator, ...],
                'sma_50': [Indicator, ...],
                'ema_12': [Indicator, ...]
            }
        """
```

---

## Manager & Storage

### IndicatorsManager

```python
class IndicatorsManager(BaseManager):
    """Database manager for technical indicators with TTL support."""

    def get_operation_type(self) -> str:
        return "indicators"

    def get_ttl_seconds(self) -> int:
        """Get TTL from config (default: 1 hour for intraday, 24 hours for daily)."""
        # Configurable based on timespan

    # ========================================
    # Retrieval
    # ========================================
    def get_latest_rsi(
        self,
        asset_id: int,
        timespan: str = "day",
        window: int = 14
    ) -> Optional[Indicator]:
        """Get most recent RSI value."""

    def get_latest_macd(
        self,
        asset_id: int,
        timespan: str = "day"
    ) -> Optional[Indicator]:
        """Get most recent MACD values (value, signal, histogram)."""

    def get_latest_sma(
        self,
        asset_id: int,
        timespan: str = "day",
        window: int = 50
    ) -> Optional[Indicator]:
        """Get most recent SMA value."""

    def get_latest_ema(
        self,
        asset_id: int,
        timespan: str = "day",
        window: int = 20
    ) -> Optional[Indicator]:
        """Get most recent EMA value."""

    def get_indicator_history(
        self,
        asset_id: int,
        indicator_type: str,
        timespan: str = "day",
        limit: int = 30
    ) -> List[Indicator]:
        """Get historical indicator values."""

    # ========================================
    # Storage
    # ========================================
    def bulk_upsert(
        self,
        indicators: List[Indicator]
    ) -> int:
        """Bulk insert/update indicators."""

    # ========================================
    # TTL & Staleness
    # ========================================
    def is_stale(
        self,
        asset_id: int,
        indicator_type: str,
        timespan: str,
        window: Optional[int] = None
    ) -> bool:
        """Check if indicators need refresh based on TTL."""

    # ========================================
    # Analysis Helpers
    # ========================================
    def get_gap_indicators(
        self,
        asset_id: int
    ) -> Dict[str, Any]:
        """Get all relevant indicators for gap analysis.

        Returns standard indicator set:
        {
            'rsi_14': 65.3,
            'macd': {'value': 2.5, 'signal': 1.8, 'histogram': 0.7},
            'sma_50': 178.45,
            'ema_20': 182.30
        }
        """
```

---

## Integration with Gap Analysis

### Current Gap Analysis Flow

```
1. Identify price gaps (pre/post/regular sessions)
2. Filter by volume criteria
3. Filter by market cap/liquidity
4. Filter by universe membership
5. Display results
```

### Enhanced Gap Analysis Flow

```
1. Identify price gaps (pre/post/regular sessions)
2. Filter by volume criteria
3. Filter by market cap/liquidity
4. Filter by universe membership
5. *** FETCH INDICATORS FOR EACH CANDIDATE ***
6. Enrich gap candidates with technical signals
7. Display results with indicator context
```

### Integration Point: GapAnalyzer

**File:** `src/analysis/gap_analyzer.py`

**New Method:**
```python
def enrich_with_indicators(
    self,
    gap_candidates: List[GapCandidate],
    data_service: DataService
) -> List[EnrichedGapCandidate]:
    """Enrich gap candidates with technical indicators.

    For each candidate:
    1. Fetch/retrieve indicators (RSI, MACD, SMA, EMA)
    2. Calculate signals (overbought/oversold, momentum, trend)
    3. Assign confidence score based on indicator alignment

    Args:
        gap_candidates: List of basic gap candidates
        data_service: Data service for fetching indicators

    Returns:
        List of enriched candidates with indicator context
    """
```

**New Model:**
```python
@dataclass
class IndicatorSignals:
    """Technical indicator signals for a gap candidate."""
    rsi: Optional[float] = None
    rsi_signal: Optional[str] = None  # 'overbought', 'oversold', 'neutral'

    macd_value: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    macd_crossover: Optional[str] = None  # 'bullish', 'bearish', 'none'

    sma_50: Optional[float] = None
    price_vs_sma: Optional[str] = None  # 'above', 'below'

    ema_20: Optional[float] = None
    price_vs_ema: Optional[str] = None  # 'above', 'below'

    overall_signal: str = 'neutral'  # 'strong_buy', 'buy', 'neutral', 'sell', 'strong_sell'
    confidence: float = 0.0  # 0.0 - 1.0

@dataclass
class EnrichedGapCandidate:
    """Gap candidate enriched with technical indicators."""
    symbol: str
    gap_percentage: float
    gap_direction: str  # 'up', 'down'
    volume_ratio: float
    market_cap: float
    current_price: float

    # NEW: Indicator signals
    indicators: IndicatorSignals

    # Metadata
    timestamp: datetime
```

### Signal Interpretation Logic

**RSI Signal:**
```python
def interpret_rsi(rsi_value: float) -> str:
    if rsi_value >= 70:
        return 'overbought'
    elif rsi_value <= 30:
        return 'oversold'
    else:
        return 'neutral'
```

**MACD Crossover:**
```python
def detect_macd_crossover(
    current_macd: float,
    current_signal: float,
    previous_macd: float,
    previous_signal: float
) -> str:
    if current_macd > current_signal and previous_macd <= previous_signal:
        return 'bullish'  # MACD crossed above signal
    elif current_macd < current_signal and previous_macd >= previous_signal:
        return 'bearish'  # MACD crossed below signal
    else:
        return 'none'
```

**Overall Signal Calculation:**
```python
def calculate_overall_signal(indicators: IndicatorSignals) -> Tuple[str, float]:
    """Calculate overall trading signal and confidence.

    Logic:
    - RSI overbought/oversold: Strong reversal signal
    - MACD crossover: Momentum confirmation
    - Price vs MA: Trend confirmation
    - Alignment of signals increases confidence
    """
    signals = []

    # RSI contribution
    if indicators.rsi_signal == 'oversold':
        signals.append(('buy', 0.8))
    elif indicators.rsi_signal == 'overbought':
        signals.append(('sell', 0.8))

    # MACD contribution
    if indicators.macd_crossover == 'bullish':
        signals.append(('buy', 0.7))
    elif indicators.macd_crossover == 'bearish':
        signals.append(('sell', 0.7))

    # Trend contribution (MA)
    if indicators.price_vs_sma == 'above' and indicators.price_vs_ema == 'above':
        signals.append(('buy', 0.5))
    elif indicators.price_vs_sma == 'below' and indicators.price_vs_ema == 'below':
        signals.append(('sell', 0.5))

    # Calculate weighted average
    # ... (aggregation logic)

    return overall_signal, confidence
```

---

## CLI Commands

### 1. Update Indicators

```bash
# Fetch indicators for specific symbol
./tradescout indicators update AAPL

# Fetch specific indicator type
./tradescout indicators update AAPL --type rsi
./tradescout indicators update AAPL --type macd

# Fetch for all gap candidates
./tradescout indicators update --gap-candidates

# Batch update for universe
./tradescout indicators update --universe default_universe
```

**Implementation:**
```python
@indicators.command()
@click.argument("symbol", required=False)
@click.option("--type", "indicator_type", help="Specific indicator: rsi, macd, sma, ema")
@click.option("--gap-candidates", is_flag=True, help="Update indicators for all gap candidates")
@click.option("--universe", help="Update indicators for universe assets")
@pass_config
def update(config, symbol, indicator_type, gap_candidates, universe):
    """Fetch and store technical indicators."""
```

---

### 2. Display Indicators

```bash
# Show all indicators for symbol
./tradescout indicators info AAPL

# Show specific indicator
./tradescout indicators info AAPL --type rsi

# Show indicator history
./tradescout indicators history AAPL --type rsi --days 30
```

**Implementation:**
```python
@indicators.command()
@click.argument("symbol")
@click.option("--type", "indicator_type", help="Specific indicator type")
@pass_config
def info(config, symbol, indicator_type):
    """Display current indicators for a symbol."""

@indicators.command()
@click.argument("symbol")
@click.option("--type", "indicator_type", required=True)
@click.option("--days", default=30, help="Number of days of history")
@pass_config
def history(config, symbol, indicator_type, days):
    """Display indicator history with chart."""
```

**Output Example:**
```
📊 Technical Indicators - AAPL
════════════════════════════════════════════════════════════

RSI (14-day)
  Current: 65.3 (NEUTRAL)
  Timestamp: 2025-10-08 16:00:00

MACD (12,26,9)
  Value: 2.5
  Signal: 1.8
  Histogram: 0.7 (BULLISH CROSSOVER)
  Timestamp: 2025-10-08 16:00:00

Moving Averages
  50-day SMA: $178.45 (ABOVE - Uptrend)
  20-day EMA: $182.30 (ABOVE - Strong support)

Overall Signal: BUY (Confidence: 75%)
```

---

### 3. Gap Analysis Integration

```bash
# Show gaps with indicators
./tradescout gap identify --with-indicators

# Filter gaps by indicator signals
./tradescout gap identify --with-indicators --signal buy
./tradescout gap identify --with-indicators --min-confidence 0.7
```

**Enhanced Output:**
```
📈 Gap Candidates with Technical Indicators
════════════════════════════════════════════════════════════

AAPL - Gap Up +3.2%
  Price: $185.76 (from $180.00)
  Volume: 2.5x average

  Indicators:
  ✓ RSI: 65.3 (Neutral)
  ✓ MACD: Bullish crossover
  ✓ Above 50-day SMA ($178.45)
  ✓ Above 20-day EMA ($182.30)

  Signal: STRONG BUY (Confidence: 85%)

────────────────────────────────────────────────────────────

TSLA - Gap Down -2.8%
  Price: $242.15 (from $249.12)
  Volume: 1.8x average

  Indicators:
  ⚠ RSI: 72.5 (Overbought)
  ✓ MACD: Bearish crossover
  ✗ Below 50-day SMA ($245.80)
  ✗ Below 20-day EMA ($247.20)

  Signal: SELL (Confidence: 70%)
```

---

## Configuration

### configs/indicators.yaml

```yaml
# Technical Indicators Configuration

# TTL settings (in hours)
ttl:
  intraday: 1      # 1 hour for minute/hour timespans
  daily: 24        # 24 hours for day timespan
  weekly: 168      # 7 days for week/month timespans

# Default parameters
defaults:
  rsi:
    window: 14
    timespan: day
    series_type: close

  macd:
    short_window: 12
    long_window: 26
    signal_window: 9
    timespan: day
    series_type: close

  sma:
    windows: [20, 50, 200]  # Multiple SMAs
    timespan: day
    series_type: close

  ema:
    windows: [12, 20, 50]   # Multiple EMAs
    timespan: day
    series_type: close

# Signal thresholds
signals:
  rsi:
    overbought: 70
    oversold: 30

  macd:
    histogram_threshold: 0.5  # Minimum histogram for signal

  confidence:
    strong_buy: 0.8
    buy: 0.6
    neutral: 0.4
    sell: 0.6
    strong_sell: 0.8

# Gap analysis integration
gap_analysis:
  enabled: true
  fetch_on_identify: true
  min_confidence: 0.5  # Filter candidates below this confidence
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1)
- [ ] Database migration: Create `indicators` table
- [ ] Model: `Indicator` dataclass
- [ ] Provider: `PolygonIndicatorsProvider` base structure
- [ ] Manager: `IndicatorsManager` with TTL support
- [ ] Config: `indicators.yaml`

### Phase 2: RSI Implementation (Week 1-2)
- [ ] Provider: `fetch_rsi()` method
- [ ] Manager: RSI-specific retrieval methods
- [ ] CLI: `./tradescout indicators update AAPL --type rsi`
- [ ] CLI: `./tradescout indicators info AAPL --type rsi`
- [ ] Tests: RSI provider and manager tests

### Phase 3: MACD Implementation (Week 2)
- [ ] Provider: `fetch_macd()` method
- [ ] Manager: MACD-specific retrieval methods
- [ ] CLI: MACD commands
- [ ] Signal interpretation: Detect crossovers
- [ ] Tests: MACD provider and manager tests

### Phase 4: Moving Averages (Week 2-3)
- [ ] Provider: `fetch_sma()` and `fetch_ema()` methods
- [ ] Manager: MA-specific retrieval methods
- [ ] CLI: MA commands
- [ ] Signal interpretation: Price vs MA positioning
- [ ] Tests: MA provider and manager tests

### Phase 5: Gap Analysis Integration (Week 3-4)
- [ ] Model: `IndicatorSignals` and `EnrichedGapCandidate`
- [ ] GapAnalyzer: `enrich_with_indicators()` method
- [ ] Signal calculation: Overall buy/sell/neutral logic
- [ ] Confidence scoring algorithm
- [ ] CLI: `./tradescout gap identify --with-indicators`
- [ ] Tests: Gap analysis enrichment tests

### Phase 6: Advanced Features (Week 4+)
- [ ] Batch updates for universe assets
- [ ] Indicator history charting (ASCII charts in terminal)
- [ ] Custom indicator configurations per screener
- [ ] Alert system: Notify when signals change
- [ ] Backtesting: Historical indicator performance

---

## Future Extensibility

### Market-Wide Indicators (Future)

Currently focused on **ticker-specific** indicators for gap analysis. Future expansion:

1. **Market Breadth Indicators**
   - Advance/Decline Line
   - New Highs/New Lows
   - Put/Call Ratio
   - VIX (Volatility Index)

2. **Sector Indicators**
   - Sector rotation signals
   - Relative strength vs. S&P 500
   - Sector momentum rankings

3. **Custom Indicators**
   - User-defined formulas
   - Combined indicators (e.g., RSI + MACD composite)
   - Machine learning derived signals

### Architecture Preparation

**Current design supports future expansion:**
- Polymorphic `indicators` table can store any indicator type
- `indicator_type` field is extensible (not enum)
- JSON `details` allows complex/custom data structures
- Provider pattern easily extended to new data sources

---

## Summary

### What We're Building

**Core Components:**
1. **Database:** Single `indicators` table with polymorphic design
2. **Provider:** `PolygonIndicatorsProvider` for RSI, MACD, SMA, EMA
3. **Manager:** `IndicatorsManager` with TTL and gap-specific helpers
4. **Integration:** Enrich gap candidates with technical signals
5. **CLI:** Update, view, and filter by indicator signals

### Key Decisions

✅ **Single polymorphic table** (vs. separate tables per indicator)
✅ **JSON details column** for complex indicators (MACD)
✅ **Integration at end of gap analysis** (not during filtering)
✅ **Configurable signals/thresholds** via YAML
✅ **Standard indicator set** for gap analysis (RSI-14, MACD 12/26/9, SMA-50, EMA-20)

### Success Criteria

Gap candidates will display:
- Current technical indicator values
- Interpreted signals (overbought/oversold, crossovers, trend)
- Overall buy/sell/neutral signal
- Confidence score
- Actionable trading context

**End Result:** Gap analysis becomes a complete trading signal system, not just a price movement detector.

---

**Next Steps:** Review this plan, then proceed with Phase 1 implementation (database + foundation).
