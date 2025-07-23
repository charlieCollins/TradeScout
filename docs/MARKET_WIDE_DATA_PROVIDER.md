# MarketWideDataProvider Implementation Plan

**Project:** TradeScout - Personal Market Research Assistant  
**Document:** MarketWideDataProvider Core Features Design  
**Created:** 2025-07-22  
**Status:** Planning Phase

---

## Overview

The MarketWideDataProvider extends TradeScout's individual asset capabilities to provide market-wide analysis. The primary use case is **pre-market and post-market analysis** to inform next-day trading decisions, with aggressive caching (1-hour TTL) to respect API rate limits.

## Core Design Principles

1. **Reuse Existing AssetDataProvider**: Leverage our solid individual asset interface wherever possible
2. **Aggressive Caching**: 1-hour cache TTL for all rate-limited APIs (Alpha Vantage, Polygon)
3. **Rate Limit Protection**: Minimize API calls through intelligent caching and bulk operations
4. **End-of-Day Focus**: Optimize for pre/post market analysis rather than real-time trading

---

## Three Core Features

### 1. Market Gainers/Losers Functionality

**Purpose**: Top gainers/losers across entire market for daily trend analysis

**Implementation Strategy:**
```python
class MarketGainersLosers:
    def get_market_gainers(self, limit: int = 20) -> List[MarketMover]
    def get_market_losers(self, limit: int = 20) -> List[MarketMover]  
    def get_most_active(self, limit: int = 20) -> List[MarketMover]
```

**Provider Strategy (Priority Order):**
1. **Alpha Vantage PRIMARY**: `TOP_GAINERS_LOSERS` function
   - ✅ Single API call gets all three lists
   - ⚠️ 25 calls/day limit - cache for 1 hour
   - 📅 Perfect for end-of-day analysis workflow
   - API: `https://www.alphavantage.co/query?function=TOP_GAINERS_LOSERS&apikey=KEY`

2. **YFinance FALLBACK**: Process S&P 500 constituents
   - Use S&P 500 symbols list (500 stocks)
   - Sort by price change percentage locally
   - Unlimited calls but requires iteration

**Data Structure:**
```python
@dataclass
class MarketMover:
    asset: Asset
    current_price: Decimal
    price_change: Decimal
    price_change_percent: Decimal
    volume: int
    market_cap: Optional[int]
    rank: int  # 1 = biggest gainer/loser
    
@dataclass  
class MarketMoversReport:
    gainers: List[MarketMover]
    losers: List[MarketMover] 
    most_active: List[MarketMover]
    timestamp: datetime
    market_status: MarketStatus
```

**Caching Strategy:**
- Cache Alpha Vantage results for **1 hour** (INTRADAY policy)
- Store in `data/cache/alpha_vantage/market_movers_YYYY-MM-DD-HH.json`
- Override cache only with explicit force parameter

---

### 2. Sector Performance Analysis

**Purpose**: Technology, Healthcare, Finance sector tracking for sector rotation strategies

**Implementation Strategy:**
```python
class SectorPerformance:
    def get_sector_performance(self) -> Dict[SectorType, SectorMetrics]
    def get_sector_leaders(self, sector: SectorType, limit: int = 10) -> List[MarketQuote]
    def get_sector_laggards(self, sector: SectorType, limit: int = 10) -> List[MarketQuote]
```

**Sector Classification Approach:**
1. **Static Sector Mapping**: Create sector classification files
2. **Provider Fundamental Data**: Use sector info from YFinance/Finnhub
3. **Representative Stocks**: Track key stocks from each sector

**Provider Strategy:**
1. **YFinance PRIMARY**: Best for bulk sector data
   - Get fundamentals for sector representatives
   - Use sector field from company info
   - Unlimited calls for comprehensive coverage
   - Cache individual stock data for 1 hour

2. **Finnhub SECONDARY**: High-quality sector classifications
   - Company profile2 endpoint has sector data
   - 60 calls/minute allows decent coverage
   - Cache results for 1 hour

**Target Sectors:**
```python
class SectorType(Enum):
    TECHNOLOGY = "Technology"
    HEALTHCARE = "Healthcare" 
    FINANCIALS = "Financials"
    ENERGY = "Energy"
    CONSUMER_DISCRETIONARY = "Consumer Discretionary"
    INDUSTRIALS = "Industrials"
    COMMUNICATION_SERVICES = "Communication Services"
    CONSUMER_STAPLES = "Consumer Staples"
    UTILITIES = "Utilities"
    REAL_ESTATE = "Real Estate"
    MATERIALS = "Materials"
```

**Data Structure:**
```python
@dataclass
class SectorMetrics:
    sector: SectorType
    total_market_cap: int
    avg_price_change_percent: Decimal
    top_performers: List[Asset]
    worst_performers: List[Asset]
    volume_leaders: List[Asset]
    constituent_count: int
    timestamp: datetime
```

**Implementation Plan:**
1. Create sector constituent files (`data/sectors/technology.json`, `data/sectors/healthcare.json`)
2. Use existing AssetDataProvider to get quotes for sector stocks
3. Aggregate performance metrics locally
4. Cache sector performance for 1 hour

---

### 3. Market Indices Tracking

**Purpose**: S&P 500, NASDAQ, etc real-time tracking for market context

**Implementation Strategy:**
```python  
class MarketIndices:
    def get_major_indices(self) -> Dict[IndexType, IndexData]
    def get_index_performance(self, index: IndexType) -> IndexPerformanceData
    def compare_indices(self, indices: List[IndexType]) -> IndexComparisonReport
```

**Index Tracking Approach: ETF Proxies (RECOMMENDED)**
- Track index ETFs as individual assets using existing AssetDataProvider
- SPY (S&P 500), QQQ (NASDAQ 100), IWM (Russell 2000)
- ✅ Uses existing individual asset interface
- ✅ Real-time pricing available
- ✅ Extended hours data available

**Target Indices:**
```python
class IndexType(Enum):
    SP500 = "S&P 500"
    NASDAQ = "NASDAQ Composite"  
    DOW = "Dow Jones"
    RUSSELL2000 = "Russell 2000"
    NASDAQ100 = "NASDAQ 100"
    SP500_ETF = "SPDR S&P 500 ETF (SPY)"
    NASDAQ_ETF = "Invesco QQQ (QQQ)"
    RUSSELL_ETF = "iShares Russell 2000 ETF (IWM)"
```

**Provider Strategy:**
1. **YFinance PRIMARY**: Direct index symbols + ETF proxies
   - Symbols: ^GSPC (S&P 500), ^IXIC (NASDAQ), QQQ, SPY, IWM
   - Extended hours and historical data available
   - No rate limits
   - Cache for 1 hour

2. **Finnhub SECONDARY**: ETF data available
   - Professional-grade ETF pricing
   - 60 calls/minute sufficient for major indices
   - Cache for 1 hour

**Data Structure:**
```python
@dataclass
class IndexData:
    index: IndexType
    current_value: Decimal
    price_change: Decimal
    price_change_percent: Decimal
    volume: Optional[int]  # For ETF proxies
    high: Decimal
    low: Decimal
    timestamp: datetime
```

---

## Integration Architecture

**Key Design Principle**: Reuse existing individual asset interface wherever possible

```python
class MarketWideDataProvider:
    """
    Market-wide data provider that extends individual asset capabilities
    
    Primary use case: End-of-day analysis for next-day trading decisions
    Caching strategy: Aggressive 1-hour TTL for rate-limited APIs
    """
    
    def __init__(self, asset_provider: AssetDataProvider):
        self.asset_provider = asset_provider  # Reuse existing providers
        self.sector_map = self._load_sector_classifications()
        self.index_symbols = self._load_index_symbols()
    
    # Market Movers (Alpha Vantage bulk API)
    def get_market_gainers(self, limit: int = 20, force_refresh: bool = False) -> List[MarketMover]:
        """Get market gainers using Alpha Vantage TOP_GAINERS_LOSERS"""
        
    def get_market_losers(self, limit: int = 20, force_refresh: bool = False) -> List[MarketMover]:
        """Get market losers using Alpha Vantage TOP_GAINERS_LOSERS"""
    
    # Sector Performance (Process via AssetDataProvider)  
    def get_sector_performance(self, force_refresh: bool = False) -> Dict[SectorType, SectorMetrics]:
        """Aggregate sector performance from individual asset data"""
        
    def get_sector_leaders(self, sector: SectorType, limit: int = 10) -> List[MarketQuote]:
        """Get top performers in specific sector"""
    
    # Market Indices (ETF proxies via AssetDataProvider)
    def get_major_indices(self, force_refresh: bool = False) -> Dict[IndexType, IndexData]:
        """Track major indices via ETF proxies (SPY, QQQ, IWM)"""
        
    def get_index_performance(self, index: IndexType) -> IndexPerformanceData:
        """Get detailed performance data for specific index"""
```

---

## Caching Strategy

**Updated Cache Policies (Aggressive for Rate-Limited APIs):**
```python
CachePolicy.REAL_TIME: 60 minutes   # Was 2 minutes - now 1 hour
CachePolicy.INTRADAY: 60 minutes    # Was 15 minutes - now 1 hour  
CachePolicy.DAILY: 240 minutes      # Unchanged - 4 hours
CachePolicy.FUNDAMENTAL: 10080 minutes  # Unchanged - 1 week
CachePolicy.HISTORICAL: 43200 minutes   # Unchanged - 30 days
```

**Rationale:**
- **End-of-day focus**: Perfect for pre/post market analysis workflow
- **Rate limit protection**: Prevents exceeding Alpha Vantage 25 calls/day
- **Force refresh option**: Override cache when needed
- **Consistent data**: All related calls use same cached dataset

---

## Implementation Phases

### Phase 1: Market Gainers/Losers (Highest Value)
- Implement Alpha Vantage `TOP_GAINERS_LOSERS` integration
- Add YFinance fallback for S&P 500 processing
- Test with aggressive caching strategy

### Phase 2: Market Indices Tracking (Foundation)
- Implement ETF proxy tracking (SPY, QQQ, IWM)
- Add direct index symbol support (^GSPC, ^IXIC)
- Create index comparison utilities

### Phase 3: Sector Performance Analysis (Advanced)
- Create sector classification files
- Implement sector aggregation logic
- Add sector leader/laggard identification

---

## File Structure

```
src/tradescout/market_wide/
├── __init__.py
├── interfaces.py           # MarketWideDataProvider interface
├── market_movers.py        # Gainers/losers implementation
├── sector_analysis.py      # Sector performance tracking
├── index_tracking.py       # Market indices implementation
└── providers/
    ├── alpha_vantage_market.py    # Alpha Vantage market endpoints
    └── composite_market.py        # Multi-provider market data

data/market_wide/
├── sectors/
│   ├── technology.json     # Tech sector constituents
│   ├── healthcare.json     # Healthcare sector constituents
│   └── financials.json     # Financial sector constituents
└── indices/
    └── major_indices.json  # Index symbol mappings
```

---

## Success Metrics

**Implementation Success:**
- ✅ Market gainers/losers data available in single API call
- ✅ Major indices tracked without additional API overhead
- ✅ Sector performance calculated from existing data
- ✅ All data cached aggressively (1-hour TTL)
- ✅ Force refresh capability for real-time needs

**Usage Success:**
- 📊 Daily market overview available pre-market
- 📊 Sector rotation analysis for strategy decisions
- 📊 Index context for individual stock analysis
- 📊 Rate limits respected (< 25 Alpha Vantage calls/day)

---

---

## CLI Usage

**Market-Wide Analysis Commands:**
```bash
# Get help and see all commands
./tradescout --help

# Top market gainers 
./tradescout gainers --limit 10

# Top market losers
./tradescout losers --limit 10

# Most active stocks by volume
./tradescout active --limit 10

# Complete market overview (gainers, losers, most active)
./tradescout movers --limit 5

# Force refresh to bypass 1-hour cache
./tradescout gainers --force
./tradescout gainers --force-refresh    # Same as --force

# Get command-specific help
./tradescout gainers --help
```

**Cache Behavior:**
- **Cache Hit**: 💾 Blue message + "Cache HIT" in logs with age
- **Fresh Data**: 🔄 Yellow message + "API CALL (force refresh)" in logs
- **1-Hour TTL**: All market data cached aggressively to protect API quotas

---

This plan provides a solid foundation for market-wide analysis while protecting our limited API quotas and building on our existing infrastructure.