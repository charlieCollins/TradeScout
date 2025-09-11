# TradeScout Domain Model Redesign Proposal

## Overview
This proposal restructures our domain models to align with our interface architecture, creating clear separation between different types of data and operations.

## Core Principles
1. **Alignment with Interfaces** - Each model file corresponds to an interface
2. **Clear Ownership** - Models belong to specific domains
3. **Minimal Dependencies** - Reduce coupling between domains
4. **Type Safety** - Strong typing throughout
5. **Immutability Where Appropriate** - Use frozen dataclasses for value objects

## Proposed Structure

### 1. Base Models (`src/tradescout/data_models/models_base.py`)
**Purpose**: Shared fundamental concepts

```python
- Market - Exchange/market definition
- MarketStatus - Session states (OPEN, PRE_MARKET, etc.)
- MarketType - Market categories (STOCK, OPTIONS, etc.)
- MarketSegment - Classification hierarchy
```

### 2. Asset Models (`src/tradescout/data_models/models_asset.py`)
**Purpose**: Individual asset data - aligns with AssetDataInterface

```python
- Asset - Core financial instrument
- AssetType - Asset categories
- PriceData - OHLC and tick data
- MarketQuote - Current quote with calculations
- Fundamentals - Company financial data
```

### 3. Market Models (`src/tradescout/data_models/models_market.py`)
**Purpose**: Market-wide data - aligns with MarketDataInterface

```python
- MarketMover - Individual mover in market context
- MarketSnapshot - Complete market state
- SectorMetrics - Sector performance
- IndexData - Index tracking
- SectorType - Sector classifications
- IndexType - Index definitions
```

### 4. Sentiment Models (`src/tradescout/data_models/models_sentiment.py`)
**Purpose**: Sentiment data - aligns with SentimentDataInterface

```python
- AssetSentiment - Individual asset sentiment
- MarketSentiment - Overall market sentiment
- NewsItem - News with sentiment scoring
- SocialMention - Social media data
- AnalystReport - Analyst ratings and changes
- SentimentTrend - Sentiment over time
- SentimentSource - Data source types
- AnalystRating - Rating categories
```

### 5. Analysis Models (`src/tradescout/data_models/models_analysis.py`)
**Purpose**: Trading analysis - aligns with AnalysisInterface

```python
- GapAnalysis - Gap trading analysis
- TradeSuggestion - Trade recommendations
- ExtendedHoursActivity - Pre/after market analysis
- TechnicalSignal - Technical indicators
- PerformanceMetrics - Strategy performance
- GapType - Gap classifications
- RiskLevel - Risk categories
- ConfidenceLevel - Confidence ratings
```

## Migration from Current Structure

### What Gets Moved Where:

**From `domain_models_core.py`:**
- Market, MarketStatus, MarketType → `models_base.py`
- Asset, AssetType → `models_asset.py`
- PriceData, MarketQuote → `models_asset.py`
- ExtendedHoursData → `models_analysis.py` (as GapAnalysis)
- CompanyFundamentals → `models_asset.py` (as Fundamentals)
- NewsItem, SocialSentiment → `models_sentiment.py`

**From `domain_models_analysis.py`:**
- TradeSuggestion, TradeSide, TradeStatus → `models_analysis.py`
- GapType, GapStrength, GapRiskLevel → `models_analysis.py`
- TechnicalIndicators → `models_analysis.py` (as TechnicalSignal)
- PerformanceMetrics, ActualTrade → `models_analysis.py`

**From `market_wide_models.py`:**
- MarketMover → `models_market.py`
- MarketMoversReport → `models_market.py` (as part of MarketSnapshot)
- SectorMetrics, IndexData → `models_market.py`
- SectorType, IndexType → `models_market.py`

## Benefits of This Design

1. **Clear Boundaries**: Each domain has its own models
2. **Interface Alignment**: Models match interface methods
3. **Easier Testing**: Mock specific domains independently
4. **Better Imports**: Clear what comes from where
5. **Reduced Coupling**: Domains interact through well-defined types
6. **Extensibility**: New domains can be added without affecting others
7. **Maintenance**: Changes isolated to specific domains

## Key Design Decisions

### Simplified Models
- Removed overly complex nested structures
- Flattened where appropriate for easier use
- Kept calculated properties minimal

### Renamed for Clarity
- `CompanyFundamentals` → `Fundamentals` (simpler)
- `ExtendedHoursData` → Part of `GapAnalysis` (more specific)
- `MarketMoversReport` → Part of `MarketSnapshot` (comprehensive)

### New Additions
- `MarketSnapshot` - Complete market state
- `SentimentTrend` - Sentiment time series
- `ExtendedHoursActivity` - Pre/after market overview
- `TechnicalSignal` - Simplified from TechnicalIndicators

## Usage Examples

### Asset Operations
```python
from models_asset import Asset, MarketQuote, PriceData
from models_base import Market, MarketStatus

# Get a quote
quote = MarketQuote(
    asset=asset,
    price_data=price_data,
    previous_close=Decimal("150.00")
)
```

### Market Operations
```python
from models_market import MarketSnapshot, MarketMover

# Market overview
snapshot = MarketSnapshot(
    timestamp=datetime.now(),
    market_status=MarketStatus.OPEN,
    top_gainers=gainers,
    top_losers=losers
)
```

### Sentiment Operations
```python
from models_sentiment import AssetSentiment, NewsItem

# Asset sentiment
sentiment = AssetSentiment(
    asset=asset,
    overall_score=Decimal("0.75"),
    overall_category=SentimentScore.BULLISH
)
```

### Analysis Operations
```python
from models_analysis import GapAnalysis, TradeSuggestion

# Gap analysis
gap = GapAnalysis(
    asset=asset,
    gap_percent=Decimal("3.5"),
    gap_type=GapType.BREAKAWAY
)
```

## Implementation Plan

1. ✅ Create new model files (DONE)
2. ⏳ Review and approve design
3. ⏳ Update providers to use new models
4. ⏳ Update coordinator to use new models
5. ⏳ Migrate existing code gradually
6. ⏳ Remove old model files
7. ⏳ Update tests

## Backwards Compatibility

During migration:
- Keep old files temporarily
- Add deprecation warnings
- Provide migration guide
- Update imports gradually
- Test thoroughly at each step