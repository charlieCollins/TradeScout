# Market Indices Tracking - Planning Document

**Purpose:** Plan the architecture for tracking major market indices (VIX, SPX, DJI, NDX, RUT) to enable market regime detection and market alignment scoring for gap analysis.

**Status:** Planning Phase
**Date:** 2025-10-10

---

## Table of Contents
1. [Overview](#overview)
2. [Use Cases](#use-cases)
3. [Polygon Indices API](#polygon-indices-api)
4. [Target Indices](#target-indices)
5. [Data Model Design](#data-model-design)
6. [Provider Architecture](#provider-architecture)
7. [Manager & Storage](#manager--storage)
8. [Integration with Gap Analysis](#integration-with-gap-analysis)
9. [Market Regime Detection](#market-regime-detection)
10. [CLI Commands](#cli-commands)
11. [Configuration](#configuration)
12. [Implementation Phases](#implementation-phases)

---

## Overview

### What Are Market Indices?

Market indices are statistical measures that track the performance of a group of assets, representing overall market or sector performance. Key uses:
- **Market regime detection:** Is volatility high/low? (VIX)
- **Market direction:** Is the broad market up/down? (SPX, DJI, NDX)
- **Market alignment:** Does the stock gap align with market movement?
- **Risk assessment:** Adjust position sizing based on market conditions

### Why We Need Them

**Current Gap Analysis Limitation:**
We analyze individual stock gaps in isolation, without market context. A gap that looks good might be:
- Swimming against the market tide (counter-trend risk)
- Occurring during high volatility (VIX spike = higher risk)
- Part of a broader market selloff (correlation risk)

**Solution:**
Track key market indices to provide context for gap trading decisions.

---

## Use Cases

### Primary: Market Context for Gap Analysis

**1. Market Alignment Scoring (5 points in quality score)**
```python
# Example: AAPL gaps up +3%
# Check market direction
if SPX is up > 0.5%:
    # Stock and market aligned = GOOD
    market_aligned = True
    quality_score += 5
else:
    # Swimming upstream = RISKY
    market_aligned = False
```

**2. Market Regime Detection (VIX-based position sizing)**
```python
# Adjust position sizing based on volatility
if VIX < 15:
    position_multiplier = 1.0  # Normal sizing
elif VIX < 25:
    position_multiplier = 0.8  # Reduce 20%
elif VIX < 35:
    position_multiplier = 0.5  # Reduce 50%
else:
    position_multiplier = 0.0  # No new positions
```

**3. Counter-Trend Detection**
```python
# Flag risky counter-trend gaps
if stock_gap_direction != market_direction:
    warning = "⚠️ COUNTER-TREND GAP - Higher risk"
    confidence_penalty = -10  # Reduce quality score
```

**4. Sector-Specific Market Context**
```python
# Tech stock gap? Check NDX (Nasdaq-100)
if stock_sector == "Technology":
    relevant_index = "I:NDX"
elif stock_sector == "Financials":
    relevant_index = "I:DJI"
else:
    relevant_index = "I:SPX"  # Broad market
```

---

## Polygon Indices API

### Overview
- **10,000+ indices** from S&P, MSCI, FTSE Russell, Dow Jones, Nasdaq, Cboe
- Real-time and historical data
- Same data structure as stock aggregates (OHLC)
- Technical indicators available (SMA, EMA, MACD, RSI)

### Key Endpoints

#### 1. Indices Snapshot - Current Values
**Endpoint:** `GET /v3/snapshot/indices`

**Response:**
```json
{
  "status": "OK",
  "results": [
    {
      "ticker": "I:SPX",
      "name": "S&P 500",
      "value": 4450.23,
      "session": {
        "open": 4420.15,
        "high": 4455.80,
        "low": 4415.30,
        "close": 4450.23,
        "change": 30.08,
        "change_percent": 0.68
      },
      "market_status": "open",
      "last_updated": 1697558400000
    }
  ]
}
```

**Use Cases:**
- Get current index values for real-time market context
- Check market direction (positive/negative)
- Assess intraday volatility (high/low range)

---

#### 2. Indices Aggregates - Historical OHLC
**Endpoint:** `GET /v2/aggs/ticker/{indicesTicker}/range/{multiplier}/{timespan}/{from}/{to}`

**Example:** `GET /v2/aggs/ticker/I:SPX/range/1/day/2025-10-01/2025-10-10`

**Response:**
```json
{
  "ticker": "I:SPX",
  "queryCount": 7,
  "resultsCount": 7,
  "results": [
    {
      "o": 4420.15,
      "h": 4455.80,
      "l": 4415.30,
      "c": 4450.23,
      "t": 1697500800000
    }
  ]
}
```

**Use Cases:**
- 10-day market trend lookback
- Volatility calculation (daily range)
- Historical market alignment analysis

---

#### 3. Previous Day Summary
**Endpoint:** `GET /v2/aggs/ticker/{indicesTicker}/prev`

**Use Cases:**
- Quick access to yesterday's close for gap calculations
- Overnight market change detection

---

### Index Ticker Format

Polygon uses `I:` prefix for indices:
- `I:SPX` - S&P 500
- `I:DJI` - Dow Jones Industrial Average
- `I:NDX` - Nasdaq-100
- `I:RUT` - Russell 2000
- `I:VIX` - CBOE Volatility Index

---

## Target Indices

### Strategy: Track 100 Most Relevant Indices

Instead of just 5 core indices, we'll track **100 comprehensive indices** covering:
- Major market benchmarks (SPX, DJI, NDX, RUT)
- Sector-specific indices (Technology, Healthcare, Financials, etc.)
- International indices (EuroStoxx, FTSE, Nikkei, etc.)
- Volatility indices (VIX, VIX9D, VVIX)
- Bond/Treasury indices
- Commodity indices (Gold, Oil, etc.)
- Crypto indices

**Advantages:**
1. **Richer market context** - Sector-specific alignment scoring
2. **International correlation** - Overnight market impacts
3. **Cross-asset analysis** - Bond yields, commodities, crypto correlation
4. **Future flexibility** - Ready for advanced strategies

**Storage Strategy:**
- Fetch all 100 indices as a single operation (bulk update)
- Store in `index_data` table
- Use single `data_update_metadata` entry for "indices" operation
- TTL: 5 minutes for real-time, 24 hours for daily aggregates

---

### Top 100 Most Relevant Indices

#### Tier 1: Core Market Benchmarks (15 indices)

**US Broad Market:**
| Ticker | Name | Purpose |
|--------|------|---------|
| I:SPX | S&P 500 | US large-cap benchmark |
| I:DJI | Dow Jones Industrial Average | US blue-chip stocks |
| I:NDX | Nasdaq-100 | US tech-heavy benchmark |
| I:COMP | Nasdaq Composite | All Nasdaq-listed stocks |
| I:RUT | Russell 2000 | US small-cap benchmark |
| I:MID | S&P MidCap 400 | US mid-cap stocks |
| I:SML | S&P SmallCap 600 | US small-cap stocks |
| I:OEX | S&P 100 | US largest companies |
| I:NYA | NYSE Composite | All NYSE stocks |
| I:VIX | CBOE Volatility Index | Market fear gauge |
| I:VIX9D | CBOE 9-Day Volatility | Short-term volatility |
| I:VVIX | VIX of VIX | Volatility of volatility |
| I:W5000 | Wilshire 5000 | Total US market |
| I:RUI | Russell 1000 | US large-cap |
| I:RAG | Russell 3000 | US broad market |

---

#### Tier 2: US Sector Indices (25 indices)

**S&P Sector Indices:**
| Ticker | Name | Sector |
|--------|------|--------|
| I:SP500-10 | S&P 500 Energy | Energy |
| I:SP500-15 | S&P 500 Materials | Materials |
| I:SP500-20 | S&P 500 Industrials | Industrials |
| I:SP500-25 | S&P 500 Consumer Discretionary | Consumer Cyclical |
| I:SP500-30 | S&P 500 Consumer Staples | Consumer Defensive |
| I:SP500-35 | S&P 500 Health Care | Healthcare |
| I:SP500-40 | S&P 500 Financials | Financials |
| I:SP500-45 | S&P 500 Information Technology | Technology |
| I:SP500-50 | S&P 500 Communication Services | Communication |
| I:SP500-55 | S&P 500 Utilities | Utilities |
| I:SP500-60 | S&P 500 Real Estate | Real Estate |

**Dow Jones Sector Indices:**
| Ticker | Name | Sector |
|--------|------|--------|
| I:DJUSEN | Dow Jones US Energy | Energy |
| I:DJUSFI | Dow Jones US Financials | Financials |
| I:DJUSHC | Dow Jones US Health Care | Healthcare |
| I:DJUSPR | Dow Jones US Consumer Goods | Consumer |
| I:DJUSBS | Dow Jones US Basic Materials | Materials |
| I:DJUSIN | Dow Jones US Industrials | Industrials |
| I:DJUSCY | Dow Jones US Consumer Services | Services |
| I:DJUSTC | Dow Jones US Technology | Technology |
| I:DJUSUT | Dow Jones US Utilities | Utilities |
| I:DJUSRE | Dow Jones US Real Estate | Real Estate |
| I:DJUSGL | Dow Jones US Oil & Gas | Oil & Gas |
| I:DJUSPH | Dow Jones US Pharmaceuticals | Pharma |
| I:DJUSBK | Dow Jones US Banks | Banks |
| I:DJUSTL | Dow Jones US Telecommunications | Telecom |

---

#### Tier 3: International Indices (20 indices)

**Europe:**
| Ticker | Name | Region |
|--------|------|--------|
| I:STOXX50E | Euro Stoxx 50 | Eurozone |
| I:FTSE | FTSE 100 | UK |
| I:DAX | DAX 40 | Germany |
| I:CAC | CAC 40 | France |
| I:IBEX | IBEX 35 | Spain |
| I:FTSEMIB | FTSE MIB | Italy |
| I:AEX | AEX Index | Netherlands |
| I:SMI | SMI Index | Switzerland |

**Asia-Pacific:**
| Ticker | Name | Region |
|--------|------|--------|
| I:N225 | Nikkei 225 | Japan |
| I:HSI | Hang Seng | Hong Kong |
| I:SSEC | Shanghai Composite | China |
| I:SZSC | Shenzhen Composite | China |
| I:KOSPI | KOSPI Index | South Korea |
| I:TWII | Taiwan Weighted | Taiwan |
| I:STI | Straits Times | Singapore |
| I:SENSEX | BSE Sensex | India |
| I:NIFTY | Nifty 50 | India |

**Americas:**
| Ticker | Name | Region |
|--------|------|--------|
| I:TSX | S&P/TSX Composite | Canada |
| I:MEXBOL | IPC Mexico | Mexico |
| I:IBOV | Bovespa | Brazil |

---

#### Tier 4: Bond & Treasury Indices (10 indices)

| Ticker | Name | Asset Class |
|--------|------|-------------|
| I:TNX | 10-Year Treasury Yield | Bonds |
| I:TYX | 30-Year Treasury Yield | Bonds |
| I:FVX | 5-Year Treasury Yield | Bonds |
| I:IRX | 13-Week Treasury Yield | Bonds |
| I:DXY | US Dollar Index | Currency |
| I:MOVE | MOVE Index | Bond Volatility |
| I:HYG | High Yield Corp Bonds | Credit |
| I:LQD | Investment Grade Bonds | Credit |
| I:TLT | 20+ Year Treasury | Bonds |
| I:AGG | Aggregate Bond Index | Bonds |

---

#### Tier 5: Commodity & Alternative Indices (15 indices)

**Commodities:**
| Ticker | Name | Asset Class |
|--------|------|-------------|
| I:CRB | CRB Commodity Index | Commodities |
| I:GSCI | S&P GSCI Commodity | Commodities |
| I:DBC | Commodity Tracking | Commodities |
| I:GC | Gold Index | Precious Metals |
| I:SI | Silver Index | Precious Metals |
| I:CL | Crude Oil Index | Energy |
| I:NG | Natural Gas Index | Energy |
| I:HG | Copper Index | Industrial Metals |

**Crypto & Alternatives:**
| Ticker | Name | Asset Class |
|--------|------|-------------|
| I:BTC | Bitcoin Index | Crypto |
| I:ETH | Ethereum Index | Crypto |
| I:CMBI10 | Crypto Market Index | Crypto |

**Real Estate:**
| Ticker | Name | Asset Class |
|--------|------|-------------|
| I:REIT | MSCI US REIT | Real Estate |
| I:RMZ | MSCI US REIT Index | Real Estate |
| I:FREL | Fidelity MSCI Real Estate | Real Estate |
| I:REGL | S&P Global REIT | Real Estate |

---

#### Tier 6: Style & Factor Indices (15 indices)

**Growth vs Value:**
| Ticker | Name | Style |
|--------|------|-------|
| I:RLG | Russell 1000 Growth | Large Growth |
| I:RLV | Russell 1000 Value | Large Value |
| I:RMG | Russell MidCap Growth | Mid Growth |
| I:RMV | Russell MidCap Value | Mid Value |
| I:RUO | Russell 2000 Growth | Small Growth |
| I:RUE | Russell 2000 Value | Small Value |

**Factor-Based:**
| Ticker | Name | Factor |
|--------|------|--------|
| I:MTUM | Momentum Index | Momentum |
| I:QUAL | Quality Index | Quality |
| I:SIZE | Size Index | Size |
| I:VLUE | Value Index | Value |
| I:USMV | Low Volatility Index | Low Vol |
| I:SPHB | High Beta Index | High Beta |
| I:SPLV | Low Volatility Index | Low Vol |
| I:DGRO | Dividend Growth | Dividend |
| I:NOBL | Dividend Aristocrats | Dividend |

---

### Index Selection Logic

**Core 5 for Gap Analysis (Primary):**
1. `I:SPX` - Default market alignment
2. `I:VIX` - Volatility regime detection
3. `I:NDX` - Tech sector alignment
4. `I:DJI` - Traditional sector alignment
5. `I:RUT` - Small-cap alignment

**Extended 95 for Context:**
- Sector-specific alignment (11 S&P sectors)
- International correlation
- Bond market signals (risk-on/risk-off)
- Commodity inflation signals
- Factor analysis (momentum, value, quality)

**Dynamic Index Selection:**
```python
def get_relevant_index(stock_sector: str, market_cap: float) -> str:
    """Select most relevant index for a stock.

    Logic:
    1. Market cap < $2B: Use I:RUT (Russell 2000)
    2. Tech sector: Use I:NDX (Nasdaq-100)
    3. Financial sector: Use I:DJUSFI (DJ Financials)
    4. Energy sector: Use I:SP500-10 (S&P Energy)
    5. Default: Use I:SPX (S&P 500)
    """
```

---

## Data Model Design

### Single Table: `index_data`

```sql
CREATE TABLE index_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,                 -- 'I:SPX', 'I:VIX', etc.
    name TEXT NOT NULL,                   -- 'S&P 500', 'CBOE Volatility Index'
    timestamp INTEGER NOT NULL,           -- Unix milliseconds
    timespan TEXT NOT NULL,               -- 'minute', 'day' (for aggregates)

    -- OHLC data
    open REAL,
    high REAL,
    low REAL,
    close REAL,

    -- Calculated fields
    change_percent REAL,                  -- Daily % change
    range_percent REAL,                   -- (high-low)/open * 100

    -- Market status
    market_status TEXT,                   -- 'open', 'closed', 'early_close'

    -- Timestamps
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    UNIQUE(ticker, timestamp, timespan)
);

CREATE INDEX idx_index_data_ticker ON index_data(ticker);
CREATE INDEX idx_index_data_timestamp ON index_data(timestamp DESC);
CREATE INDEX idx_index_data_lookup ON index_data(ticker, timespan, timestamp DESC);
```

**Design Rationale:**
- **Single table** for all indices (simpler than per-index tables)
- **Ticker-based** identification (I:SPX, I:VIX, etc.)
- **Timespan column** to store both minute bars and daily aggregates
- **Unique constraint** on (ticker, timestamp, timespan) prevents duplicates
- **Calculated fields** for quick access to common metrics

---

## Provider Architecture

### PolygonIndicesProvider

```python
class PolygonIndicesProvider(BaseAPIProvider):
    """Provider for market indices from Polygon API."""

    # Core indices we track
    CORE_INDICES = {
        "I:SPX": "S&P 500",
        "I:VIX": "CBOE Volatility Index",
        "I:NDX": "Nasdaq-100",
        "I:DJI": "Dow Jones Industrial Average",
        "I:RUT": "Russell 2000"
    }

    def __init__(self, api_key: str):
        super().__init__(api_key, "https://api.polygon.io")

    # ========================================
    # SNAPSHOT - Current Values
    # ========================================
    def fetch_indices_snapshot(
        self,
        tickers: Optional[List[str]] = None
    ) -> List[IndexData]:
        """Fetch current snapshot for indices.

        Args:
            tickers: List of index tickers (default: CORE_INDICES)

        Returns:
            List of IndexData objects with current values
        """

    def fetch_index_snapshot(self, ticker: str) -> Optional[IndexData]:
        """Fetch snapshot for single index."""

    # ========================================
    # AGGREGATES - Historical OHLC
    # ========================================
    def fetch_index_aggregates(
        self,
        ticker: str,
        timespan: str = "day",
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        limit: int = 10
    ) -> List[IndexData]:
        """Fetch historical aggregates for an index.

        Args:
            ticker: Index ticker (e.g., 'I:SPX')
            timespan: 'minute', 'hour', 'day', 'week', 'month'
            from_date: Start date (default: 10 days ago)
            to_date: End date (default: today)
            limit: Number of bars to fetch

        Returns:
            List of IndexData objects with OHLC data
        """

    # ========================================
    # PREVIOUS DAY
    # ========================================
    def fetch_index_previous_day(self, ticker: str) -> Optional[IndexData]:
        """Fetch previous trading day summary for an index."""

    # ========================================
    # BATCH OPERATIONS
    # ========================================
    def fetch_all_core_indices_snapshot(self) -> Dict[str, IndexData]:
        """Fetch snapshots for all core indices.

        Returns:
            {
                'I:SPX': IndexData(...),
                'I:VIX': IndexData(...),
                'I:NDX': IndexData(...),
                'I:DJI': IndexData(...),
                'I:RUT': IndexData(...)
            }
        """

    def fetch_all_core_indices_history(
        self,
        days: int = 10
    ) -> Dict[str, List[IndexData]]:
        """Fetch historical data for all core indices.

        Args:
            days: Number of days of history

        Returns:
            {
                'I:SPX': [IndexData, IndexData, ...],
                'I:VIX': [IndexData, IndexData, ...],
                ...
            }
        """

    # ========================================
    # MARKET CONTEXT HELPERS
    # ========================================
    def get_market_direction(self) -> str:
        """Get overall market direction based on major indices.

        Returns:
            'bullish', 'bearish', 'neutral'
        """

    def get_volatility_regime(self) -> str:
        """Get current volatility regime based on VIX.

        Returns:
            'low' (VIX < 15),
            'moderate' (VIX 15-25),
            'high' (VIX 25-35),
            'extreme' (VIX > 35)
        """
```

---

## Manager & Storage

### IndexDataManager

```python
class IndexDataManager(BaseManager):
    """Database manager for market indices with TTL support."""

    def get_operation_type(self) -> str:
        return "index_data"

    def get_ttl_seconds(self) -> int:
        """Get TTL from config.

        - Intraday (minute bars): 5 minutes
        - Daily aggregates: 24 hours
        """
        # Based on timespan

    # ========================================
    # Retrieval
    # ========================================
    def get_latest_snapshot(self, ticker: str) -> Optional[IndexData]:
        """Get most recent snapshot for an index."""

    def get_latest_daily(self, ticker: str) -> Optional[IndexData]:
        """Get most recent daily bar for an index."""

    def get_history(
        self,
        ticker: str,
        timespan: str = "day",
        limit: int = 10
    ) -> List[IndexData]:
        """Get historical data for an index."""

    def get_all_core_indices_latest(self) -> Dict[str, IndexData]:
        """Get latest values for all core indices (SPX, VIX, NDX, DJI, RUT)."""

    # ========================================
    # Storage
    # ========================================
    def bulk_upsert(self, index_data_list: List[IndexData]) -> int:
        """Bulk insert/update index data."""

    def upsert_snapshot(self, index_data: IndexData) -> bool:
        """Insert or update single index snapshot."""

    # ========================================
    # TTL & Staleness
    # ========================================
    def is_stale(
        self,
        ticker: str,
        timespan: str = "day"
    ) -> bool:
        """Check if index data needs refresh based on TTL."""

    # ========================================
    # Market Context Helpers
    # ========================================
    def get_market_change_percent(self, ticker: str = "I:SPX") -> Optional[float]:
        """Get today's change % for an index (default: SPX)."""

    def get_vix_level(self) -> Optional[float]:
        """Get current VIX level."""

    def calculate_market_direction(self) -> str:
        """Calculate overall market direction.

        Logic:
        - Average SPX, DJI, NDX daily changes
        - If avg > 0.3%: bullish
        - If avg < -0.3%: bearish
        - Else: neutral
        """

    def calculate_volatility_regime(self) -> str:
        """Calculate volatility regime from VIX level."""
```

---

## Integration with Gap Analysis

### Current Gap Analysis Flow
```
1. Identify price gaps
2. Filter by volume
3. Filter by market cap
4. Filter by exhaustion pattern
5. Calculate quality score (without market context)
6. Display results
```

### Enhanced Gap Analysis Flow
```
1. Identify price gaps
2. Filter by volume
3. Filter by market cap
4. Filter by exhaustion pattern
5. *** FETCH MARKET INDICES DATA ***
6. Calculate market alignment (+5 points if aligned)
7. Adjust for volatility regime (VIX-based position sizing)
8. Flag counter-trend gaps (warning)
9. Display results with market context
```

### Integration Points

**1. Market Alignment Scoring (gap_analyzer.py)**
```python
def calculate_market_alignment(
    self,
    gap_direction: str,  # 'up' or 'down'
    gap_percent: float,
    sector: Optional[str] = None
) -> Tuple[bool, str]:
    """Determine if gap aligns with market direction.

    Args:
        gap_direction: 'up' or 'down'
        gap_percent: Size of gap
        sector: Stock sector (for sector-specific index)

    Returns:
        (is_aligned, relevant_index)

    Example:
        AAPL gaps up 3%
        SPX is up 0.8%
        → (True, 'I:SPX')
    """
    # Get appropriate index based on sector
    if sector == "Technology":
        index = "I:NDX"
    else:
        index = "I:SPX"

    # Get market direction
    market_data = index_manager.get_latest_snapshot(index)
    market_change = market_data.change_percent

    # Alignment logic
    if gap_direction == 'up' and market_change > 0.3:
        return True, index
    elif gap_direction == 'down' and market_change < -0.3:
        return True, index
    else:
        return False, index
```

**2. Volatility-Based Position Sizing**
```python
def get_vix_position_multiplier(vix_level: float) -> float:
    """Get position sizing multiplier based on VIX.

    Args:
        vix_level: Current VIX value

    Returns:
        Multiplier for position sizing (0.0 - 1.0)
    """
    if vix_level < 15:
        return 1.0    # Normal sizing
    elif vix_level < 25:
        return 0.8    # Reduce 20%
    elif vix_level < 35:
        return 0.5    # Reduce 50%
    else:
        return 0.0    # No new positions
```

**3. Enhanced Gap Candidate Display**
```
📈 Gap Candidates with Market Context
════════════════════════════════════════════════════════════

MARKET OVERVIEW
  S&P 500 (I:SPX): 4,450.23 (+0.68%) ↑ BULLISH
  VIX (I:VIX): 16.5 (MODERATE VOLATILITY)
  Position Sizing: 80% of normal (VIX-adjusted)

────────────────────────────────────────────────────────────

AAPL - Gap Up +3.2%
  Price: $185.76 (from $180.00)
  Volume: 2.5x average
  Sector: Technology

  Market Context:
  ✓ Aligned with Nasdaq-100: +1.2% (I:NDX)
  ✓ Aligned with S&P 500: +0.68% (I:SPX)
  ✓ VIX: 16.5 (Moderate - reduce size 20%)

  Quality Score: 85/100 (+5 market alignment bonus)
  Recommended Size: 0.8% (1.0% base × 0.8 VIX multiplier)

  Signal: STRONG BUY with market tailwind

────────────────────────────────────────────────────────────

TSLA - Gap Down -2.8%
  Price: $242.15 (from $249.12)
  Volume: 1.8x average
  Sector: Consumer Cyclical

  Market Context:
  ⚠️ COUNTER-TREND: Stock down, but S&P 500 up +0.68%
  ⚠️ Swimming against market tide (higher risk)
  ✓ VIX: 16.5 (Moderate volatility)

  Quality Score: 55/100 (no market alignment bonus)

  Signal: NEUTRAL - Counter-trend risk
```

---

## Market Regime Detection

### VIX-Based Regimes

| VIX Range | Regime | Position Sizing | Description |
|-----------|--------|----------------|-------------|
| < 12 | **Very Low** | 100% | Complacent market, low fear |
| 12-15 | **Low** | 100% | Normal market conditions |
| 15-20 | **Moderate** | 80% | Slightly elevated uncertainty |
| 20-25 | **Elevated** | 60% | Increased market stress |
| 25-30 | **High** | 40% | Significant fear/volatility |
| 30-40 | **Very High** | 20% | Market panic conditions |
| > 40 | **Extreme** | 0% | Crisis mode - no new positions |

### Market Direction Classification

**Broad Market Direction (using SPX, DJI, NDX average):**
```python
def classify_market_direction(spx_chg: float, dji_chg: float, ndx_chg: float) -> str:
    avg_change = (spx_chg + dji_chg + ndx_chg) / 3

    if avg_change > 1.0:
        return "strongly_bullish"
    elif avg_change > 0.3:
        return "bullish"
    elif avg_change > -0.3:
        return "neutral"
    elif avg_change > -1.0:
        return "bearish"
    else:
        return "strongly_bearish"
```

**Risk Adjustment:**
- **Strongly Bullish + Low VIX:** Maximum risk exposure
- **Bullish + Moderate VIX:** Normal risk
- **Neutral + High VIX:** Reduced risk
- **Bearish + Extreme VIX:** Minimal/no risk

---

## CLI Commands

### 1. Update Index Data

```bash
# Fetch all core indices (SPX, VIX, NDX, DJI, RUT)
./tradescout indices update

# Fetch specific index
./tradescout indices update I:SPX

# Fetch historical data (10 days)
./tradescout indices update --history --days 10

# Auto-update during gap analysis
./tradescout gap analyze --update-indices
```

**Implementation:**
```python
@indices.command()
@click.argument("ticker", required=False)
@click.option("--history", is_flag=True, help="Fetch historical data")
@click.option("--days", default=10, help="Days of history to fetch")
@pass_config
def update(config, ticker, history, days):
    """Fetch and store market indices data."""
```

---

### 2. Display Index Data

```bash
# Show all core indices current values
./tradescout indices info

# Show specific index with history
./tradescout indices info I:VIX

# Show market regime
./tradescout indices regime
```

**Output Example:**
```
📊 Market Indices Overview

S&P 500 (I:SPX)
  Current: 4,450.23
  Change: +30.08 (+0.68%)
  Range: 4,415.30 - 4,455.80
  Status: BULLISH

VIX (I:VIX)
  Current: 16.5
  Change: -0.3 (-1.8%)
  Regime: MODERATE VOLATILITY
  Position Sizing: Reduce to 80%

Nasdaq-100 (I:NDX)
  Current: 15,234.18
  Change: +182.45 (+1.21%)
  Status: STRONGLY BULLISH

Market Summary:
  Overall Direction: BULLISH
  Volatility Regime: MODERATE
  Risk Adjustment: -20% position sizing
  Recommended Exposure: 80% of normal
```

---

### 3. Market Context Command

```bash
# Quick market context check
./tradescout market context

# Detailed 10-day trend
./tradescout market context --days 10
```

**Output:**
```
🌍 Market Context - 2025-10-10 14:30:00

CURRENT CONDITIONS
  S&P 500: +0.68% (BULLISH)
  VIX: 16.5 (MODERATE VOLATILITY)
  Market Direction: BULLISH
  Position Sizing: 80% (VIX-adjusted)

10-DAY TREND
  SPX: +2.3% (8 up days, 2 down days)
  VIX: -5.2% (declining volatility)
  Trend: STRENGTHENING UPTREND

TRADING IMPLICATIONS
  ✓ Bullish environment favors long gaps
  ⚠️ Moderate VIX suggests caution with sizing
  ✓ Declining VIX indicates improving sentiment
```

---

## Configuration

### configs/indices.yaml

```yaml
# Market Indices Configuration

# Core indices to track
core_indices:
  - ticker: "I:SPX"
    name: "S&P 500"
    role: "broad_market"
    weight: 0.5  # Weight in market direction calculation

  - ticker: "I:VIX"
    name: "CBOE Volatility Index"
    role: "volatility"
    weight: 0.0  # Not used in direction calc

  - ticker: "I:NDX"
    name: "Nasdaq-100"
    role: "tech_benchmark"
    weight: 0.3

  - ticker: "I:DJI"
    name: "Dow Jones Industrial Average"
    role: "blue_chip"
    weight: 0.1

  - ticker: "I:RUT"
    name: "Russell 2000"
    role: "small_cap"
    weight: 0.1

# TTL settings (in minutes)
ttl:
  snapshot: 5          # Real-time snapshots: 5 minutes
  daily: 1440          # Daily aggregates: 24 hours
  historical: 10080    # Historical data: 7 days

# VIX regime thresholds
vix_regimes:
  very_low:
    max: 12
    position_multiplier: 1.0
    description: "Complacent market"

  low:
    min: 12
    max: 15
    position_multiplier: 1.0
    description: "Normal conditions"

  moderate:
    min: 15
    max: 20
    position_multiplier: 0.8
    description: "Slightly elevated"

  elevated:
    min: 20
    max: 25
    position_multiplier: 0.6
    description: "Increased stress"

  high:
    min: 25
    max: 30
    position_multiplier: 0.4
    description: "Significant fear"

  very_high:
    min: 30
    max: 40
    position_multiplier: 0.2
    description: "Market panic"

  extreme:
    min: 40
    position_multiplier: 0.0
    description: "Crisis mode"

# Market direction thresholds
market_direction:
  strongly_bullish: 1.0      # Avg index change > 1.0%
  bullish: 0.3               # Avg index change > 0.3%
  neutral_min: -0.3          # Between -0.3% and +0.3%
  neutral_max: 0.3
  bearish: -0.3              # Avg index change < -0.3%
  strongly_bearish: -1.0     # Avg index change < -1.0%

# Gap analysis integration
gap_integration:
  auto_fetch: true                    # Auto-fetch indices during gap analysis
  market_alignment_bonus: 5           # Quality score bonus for alignment
  counter_trend_penalty: -10          # Penalty for counter-trend gaps
  vix_multiplier_enabled: true        # Apply VIX-based position sizing

# Sector-to-index mapping
sector_indices:
  Technology: "I:NDX"                 # Tech → Nasdaq-100
  Communication Services: "I:NDX"
  Consumer Cyclical: "I:SPX"          # Default to S&P 500
  Consumer Defensive: "I:DJI"
  Financial Services: "I:DJI"         # Financials → Dow Jones
  Industrials: "I:DJI"
  Healthcare: "I:SPX"
  Energy: "I:SPX"
  Utilities: "I:DJI"
  Real Estate: "I:SPX"
  Basic Materials: "I:DJI"
  default: "I:SPX"                    # Fallback to S&P 500
```

---

## TTL Management Strategy

### Treat "indices" as Single Operation in data_update_metadata

Unlike per-ticker operations, we'll treat all 100 indices as a **single bulk operation** for efficiency:

**Rationale:**
- Indices don't change independently - market opens/closes affect all simultaneously
- Bulk fetching is more API-efficient (single batch request vs 100 individual requests)
- Simpler TTL management (one timestamp for all indices, not 100 individual timestamps)
- Reduces database overhead (one metadata row, not 100)

**Implementation:**

```python
# In DataService or dedicated IndexService

def update_all_indices(self, force_refresh: bool = False) -> Dict[str, int]:
    """Update all 100 tracked indices as single operation.

    Uses data_update_metadata with operation_type='indices' to track TTL.

    Args:
        force_refresh: Force update even if within TTL

    Returns:
        {'snapshots': 100, 'historicals': 0} - counts of data fetched
    """
    # Check TTL
    if not force_refresh:
        metadata = self.metadata_manager.get_metadata('indices')
        if metadata and not metadata.is_stale():
            logger.debug("Indices data is fresh, skipping update")
            return {'snapshots': 0, 'historicals': 0}

    # Fetch all 100 indices in bulk
    provider = PolygonIndicesProvider(self.api_key)
    all_indices_data = provider.fetch_all_indices_snapshot()

    # Store in database
    stored_count = self.index_manager.bulk_upsert(all_indices_data)

    # Update metadata timestamp
    self.metadata_manager.record_update('indices')

    return {'snapshots': stored_count, 'historicals': 0}
```

**Configuration (configs/database_ttl.yaml):**
```yaml
# Index data TTL (in minutes)
indices_snapshot_ttl_minutes: 5      # Real-time snapshots: 5 minutes
indices_daily_ttl_hours: 24          # Daily aggregates: 24 hours
```

**data_update_metadata Entry:**
```sql
INSERT INTO data_update_metadata (operation_type, last_update, created_at, updated_at)
VALUES ('indices', '2025-10-10 14:30:00', '2025-10-10 14:30:00', '2025-10-10 14:30:00');
```

**Benefits:**
- ✅ Single API call fetches all 100 indices
- ✅ Single database transaction stores all data
- ✅ Single TTL check determines freshness
- ✅ Simpler code (no per-index looping logic)
- ✅ Faster execution (bulk operations)

---

## Implementation Phases

### Phase 1: Foundation (Week 1)
- [ ] Database migration: Create `index_data` table
- [ ] Model: `IndexData` dataclass
- [ ] Provider: `PolygonIndicesProvider` base structure
- [ ] Manager: `IndexDataManager` with TTL support
- [ ] Config: `indices.yaml`

### Phase 2: Core Index Tracking (Week 1-2)
- [ ] Provider: Implement `fetch_indices_snapshot()`
- [ ] Provider: Implement `fetch_index_aggregates()`
- [ ] Manager: Index storage and retrieval methods
- [ ] CLI: `./tradescout indices update`
- [ ] CLI: `./tradescout indices info`
- [ ] Tests: Provider and manager tests

### Phase 3: Market Regime Detection (Week 2)
- [ ] Manager: `calculate_volatility_regime()` using VIX
- [ ] Manager: `calculate_market_direction()` using SPX/DJI/NDX
- [ ] Manager: `get_vix_position_multiplier()`
- [ ] CLI: `./tradescout market context`
- [ ] CLI: Display regime in `indices info`
- [ ] Tests: Regime calculation tests

### Phase 4: Gap Analysis Integration (Week 3)
- [ ] GapAnalyzer: `calculate_market_alignment()` method
- [ ] GapAnalyzer: Auto-fetch indices if stale
- [ ] Quality score: Add +5 for market alignment
- [ ] Quality score: Add -10 for counter-trend
- [ ] Display: Show market context in gap output
- [ ] Display: Show VIX-adjusted position sizing
- [ ] Tests: Gap analysis integration tests

### Phase 5: Advanced Features (Week 4+)
- [ ] Sector-specific index mapping
- [ ] 10-day market trend analysis
- [ ] Historical correlation tracking
- [ ] Market regime change alerts
- [ ] Custom index support (user-defined)

---

## Summary

### What We're Building

**Core Components:**
1. **Database:** `index_data` table for OHLC data across all 100 indices
2. **Provider:** `PolygonIndicesProvider` for bulk fetching 100 indices
3. **Manager:** `IndexDataManager` with TTL and market context helpers
4. **Integration:** Auto-fetch indices during gap analysis for alignment scoring
5. **CLI:** Update, view, and analyze market indices
6. **TTL:** Single `data_update_metadata` entry for "indices" operation

### Key Decisions

✅ **Track 100 comprehensive indices** - broad market, sectors, international, bonds, commodities
✅ **Bulk operation model** - fetch all 100 indices as single API call
✅ **Single TTL tracking** - "indices" operation in data_update_metadata (not per-index)
✅ **Single `index_data` table** - all indices in one table with ticker discriminator
✅ **VIX-based position sizing** - automatic risk adjustment based on volatility regime
✅ **Market alignment scoring** - +5 points for aligned gaps, -10 for counter-trend
✅ **Auto-fetch during gap analysis** - seamless integration with 5-minute TTL
✅ **Dynamic index selection** - choose most relevant index based on sector/market cap
✅ **6-tier index organization** - core (15), sectors (25), international (20), bonds (10), commodities (15), factors (15)

### Success Criteria

Gap analysis will display:
- Current market direction (bullish/bearish/neutral)
- VIX level and volatility regime
- Market alignment for each candidate (✓ aligned or ⚠️ counter-trend)
- VIX-adjusted position sizing recommendations
- Risk warnings during high volatility periods

**End Result:** Gap trading decisions informed by market context, not analyzed in isolation.

---

**Next Steps:** Review this plan, then proceed with Phase 1 implementation (database + foundation).
