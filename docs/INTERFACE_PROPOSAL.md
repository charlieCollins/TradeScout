# TradeScout Interface Redesign Proposal

## Overview
This proposal restructures our data provider interfaces into minimal, focused contracts that match our actual usage patterns.

## Core Principles
1. **Minimal Surface Area** - Only methods that are actually used
2. **Clear Separation** - Asset operations vs Market operations  
3. **Simple Types** - Use basic Python types where possible
4. **No Over-Engineering** - Remove unused abstractions

## Proposed Structure

### 1. Asset Data Interface (`src/tradescout/interfaces/interface_asset.py`)
**Purpose**: Individual stock/asset operations

```python
- get_current_quote(symbol) -> MarketQuote  # Always returns latest price (including extended hours)
- get_fundamentals(symbol) -> Dict
- get_historical_data(symbol, start, end, interval) -> List[PriceData]
- get_ohlc(symbol, date) -> Dict
```

### 2. Market Data Interface (`src/tradescout/interfaces/interface_market.py`)
**Purpose**: Market-wide scanning and raw data collection

```python
- get_market_gainers(limit, force_refresh) -> List[MarketMover]
- get_market_losers(limit, force_refresh) -> List[MarketMover]
- get_most_active(limit, force_refresh) -> List[MarketMover]
- get_market_snapshot(force_refresh) -> Dict
```

### 3. Sentiment Data Interface (`src/tradescout/interfaces/interface_sentiment.py`)
**Purpose**: Sentiment data for both assets and markets

```python
- get_asset_sentiment(symbol, lookback_hours) -> Dict  # Individual stock sentiment
- get_market_sentiment(market, lookback_hours) -> Dict  # Overall market mood
- get_trending_sentiment(limit, threshold) -> List[Dict]  # Strongest signals
- get_news_sentiment(symbols, limit) -> List[Dict]  # News with sentiment
- get_social_sentiment(symbol, platforms) -> Dict  # Social media sentiment
- get_analyst_sentiment(symbol, days_back) -> Dict  # Analyst ratings
```

### 4. Analysis Interface (`src/tradescout/interfaces/interface_analysis.py`)
**Purpose**: Trading analysis and strategy operations on top of data

```python
# Main analysis methods
- get_gap_candidates(min_gap_percent, max_gap_percent, session_type) -> List[Dict]
- analyze_gap_fill_probability(symbol, gap_data) -> Dict
- get_trade_suggestions(analysis_type, limit, risk_level) -> List[Dict]
- scan_extended_hours_activity(min_volume, min_price_change_pct) -> Dict

# Specialized gap analysis (optional interface)
- identify_gaps(market_data, min_gap_percent) -> List[Dict]
- classify_gap_type(gap_data) -> str
- calculate_gap_metrics(symbol, prices, volume) -> Dict
```

### 5. Combined Provider Interface (`src/tradescout/interfaces/interface_provider.py`)
**Purpose**: Flexible provider combinations

```python
class DataProvider(AssetDataInterface, MarketDataInterface, SentimentDataInterface):
    # Standard for most data providers (includes sentiment as core data type)
    
class FullProvider(AssetDataInterface, MarketDataInterface, SentimentDataInterface, AnalysisInterface):
    # For providers offering everything: data + sentiment + analysis
    
class SentimentOnlyProvider(SentimentDataInterface):
    # For dedicated sentiment providers (news APIs, social media, etc.)
    
class AnalysisOnlyProvider(AnalysisInterface):
    # For pure analysis engines working on existing data
```

## Benefits of This Design

1. **Clarity**: Clear separation between data types (price, sentiment) and analysis
2. **Flexibility**: Providers can implement just what they support
3. **Simplicity**: Minimal methods, no unused complexity
4. **Type Safety**: Clear return types for each method
5. **Testability**: Small interfaces are easier to mock and test
6. **Extensibility**: Each interface can grow independently
7. **Separation of Concerns**: Raw data vs. sentiment vs. analysis clearly separated
8. **Completeness**: Sentiment recognized as core data type alongside price data

## Migration Path

1. ✅ Create new interface files (DONE)
2. ⏳ Review and approve design
3. ⏳ Update existing provider (Polygon) to implement new interfaces
4. ⏳ Update smart coordinator to use new interfaces
5. ⏳ Remove old interface file
6. ⏳ Update tests

## What Gets Removed

From the current `interfaces.py`:
- NewsProvider (not used)
- SentimentProvider (not used)  
- TechnicalAnalysisProvider (not used)
- EventProvider (not used)
- DataCollectionCoordinator (redundant with smart_coordinator)
- DataValidator Protocol (not used)
- DataTransformer Protocol (not used)
- RateLimiter class (should be internal to providers)
- DataCache interface (using database now)
- scan_volume_leaders (not used)
- Many other unused methods

## Next Steps

After approval:
1. Refactor `AssetDataProviderPolygon` to implement `DataProvider`
2. Update `SmartCoordinator` to expect these interfaces
3. Remove old interface file and unused code