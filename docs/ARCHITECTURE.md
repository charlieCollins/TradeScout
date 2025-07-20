# TradeScout Architecture Documentation

## Overview

TradeScout uses a clean, interface-driven architecture that separates concerns and enables easy testing, mocking, and future extensibility. All external APIs are adapted to our internal interfaces, ensuring consistency and maintainability.

## Core Principles

1. **Interface-First Design**: All components implement abstract interfaces
2. **Clean Data Models**: External API data is transformed to our standardized models
3. **Separation of Concerns**: Data collection, analysis, and storage are independent
4. **Cloud-Ready**: Architecture supports seamless migration from local to cloud
5. **Testable**: All components can be easily mocked and unit tested

## Data Flow Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   External      │    │   TradeScout     │    │   Analysis      │
│   Data Sources  │───▶│   Interfaces     │───▶│   Engine        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
        │                        │                        │
        │                        │                        ▼
        │                        │               ┌─────────────────┐
        │                        │               │  Trade          │
        │                        │               │  Suggestions    │
        │                        │               └─────────────────┘
        │                        │                        │
        │                        ▼                        │
        │               ┌──────────────────┐              │
        │               │   Data Storage   │              │
        │               │   (SQLite/Cloud) │◀─────────────┘
        │               └──────────────────┘
        │                        │
        ▼                        ▼
┌─────────────────┐    ┌──────────────────┐
│   Rate Limiting │    │   Performance    │
│   & Caching     │    │   Tracking       │
└─────────────────┘    └──────────────────┘
```

## Core Data Models

### Market Data Models

#### `MarketQuote`
- Real-time price and volume data
- Automatic calculation of price changes and gaps
- Volume surge detection
- Market session awareness

#### `ExtendedHoursData`
- Pre-market and after-hours trading data
- Gap analysis vs regular market close
- Volume and price action during extended hours

#### `TechnicalIndicators`
- RSI, MACD, moving averages
- Support/resistance levels
- Trend analysis results
- Pattern detection flags

### Analysis Models

#### `TradeSuggestion`
- Complete trade recommendation with entry/exit points
- Risk/reward analysis
- Confidence scoring
- Rationale and supporting factors
- Performance tracking fields

#### `ActualTrade`
- User's actual trade execution
- Links to originating suggestion (if applicable)
- Performance tracking and lessons learned
- Manual notes and observations

### News & Sentiment Models

#### `NewsItem`
- Structured news data with sentiment analysis
- Symbol relevance and keyword extraction
- Impact scoring
- Source attribution

#### `SocialSentiment`
- Aggregated social media sentiment
- Mention counts and trending keywords
- Bullish/bearish ratio analysis

## Interface Hierarchy

### Data Collection Interfaces

```python
MarketDataProvider (ABC)
├── get_current_quote()
├── get_extended_hours_data()
├── get_historical_quotes()
├── scan_volume_leaders()
└── get_fundamental_data()

NewsProvider (ABC)
├── get_latest_news()
├── get_news_by_timeframe()
└── search_news_by_keywords()

SentimentProvider (ABC)
├── get_sentiment_data()
├── get_trending_symbols()
└── get_sentiment_timeline()
```

### Analysis Interfaces

```python
MomentumDetector (ABC)
├── analyze_gap_momentum()
├── analyze_volume_momentum()
├── analyze_news_momentum()
└── calculate_momentum_score()

TechnicalAnalyzer (ABC)
├── analyze_trend()
├── detect_breakout_patterns()
├── calculate_support_resistance()
└── analyze_indicators()

SuggestionEngine (ABC)
├── generate_suggestion()
├── rank_suggestions()
├── filter_suggestions()
└── validate_suggestion()
```

### Storage Interfaces

```python
DatabaseManager (ABC)
├── QuoteRepository
├── NewsRepository
├── SentimentRepository
├── SuggestionRepository
├── TradeRepository
└── PerformanceRepository
```

## Implementation Strategy

### Phase 1: Core Foundation
1. Implement SQLite-based storage repositories
2. Create basic market data providers (yfinance)
3. Build simple momentum detection
4. Basic suggestion engine

### Phase 2: Enhanced Analysis
1. Add news and sentiment providers
2. Implement technical analysis
3. Advanced momentum detection
4. Performance tracking

### Phase 3: Production Features
1. Email notifications
2. Web dashboard
3. Real-time scanning
4. Cloud migration support

## Data Provider Adapters

External APIs are wrapped in adapter classes that implement our interfaces:

### YFinanceAdapter implements MarketDataProvider
```python
class YFinanceAdapter(MarketDataProvider):
    def get_current_quote(self, symbol: str) -> Optional[MarketQuote]:
        # Fetch from Yahoo Finance API
        raw_data = yf.Ticker(symbol).info
        # Transform to our MarketQuote model
        return self._transform_quote(raw_data)
```

### PolygonAdapter implements MarketDataProvider
```python
class PolygonAdapter(MarketDataProvider):
    def get_current_quote(self, symbol: str) -> Optional[MarketQuote]:
        # Fetch from Polygon.io API
        raw_data = self.client.get_last_quote(symbol)
        # Transform to our MarketQuote model
        return self._transform_quote(raw_data)
```

## Rate Limiting & Caching

### RateLimiter
- Tracks API calls per provider
- Prevents hitting rate limits
- Calculates wait times between requests

### DataCache
- In-memory caching with TTL
- Reduces redundant API calls
- Improves response times

## Database Schema Design

### Local SQLite Schema
```sql
-- Market quotes with extended information
CREATE TABLE quotes (
    id INTEGER PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    timestamp DATETIME NOT NULL,
    price DECIMAL(10,4) NOT NULL,
    volume INTEGER,
    session VARCHAR(20),
    -- ... additional fields
    INDEX idx_symbol_timestamp (symbol, timestamp)
);

-- Trade suggestions with tracking
CREATE TABLE suggestions (
    id VARCHAR(36) PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    timestamp DATETIME NOT NULL,
    confidence_score DECIMAL(3,2),
    suggested_entry DECIMAL(10,4),
    stop_loss DECIMAL(10,4),
    take_profit_1 DECIMAL(10,4),
    status VARCHAR(20),
    -- ... additional fields
);

-- Actual trades for performance tracking
CREATE TABLE actual_trades (
    id VARCHAR(36) PRIMARY KEY,
    suggestion_id VARCHAR(36),
    symbol VARCHAR(10) NOT NULL,
    entry_price DECIMAL(10,4),
    exit_price DECIMAL(10,4),
    realized_pnl DECIMAL(10,4),
    -- ... additional fields
    FOREIGN KEY (suggestion_id) REFERENCES suggestions(id)
);
```

### Cloud Migration Path
- Replace SQLite with PostgreSQL/MySQL
- Use SQLAlchemy ORM for seamless transition
- Maintain same interface contracts
- Add connection pooling and optimization

## Error Handling Strategy

### Data Collection Errors
- Graceful degradation when APIs are unavailable
- Fallback to cached data or alternative providers
- Comprehensive logging for debugging

### Analysis Errors
- Validate input data before analysis
- Skip invalid data points gracefully
- Continue processing remaining symbols

### Storage Errors
- Transaction rollbacks for consistency
- Automatic retries for transient failures
- Backup and recovery procedures

## Testing Strategy

### Unit Testing
- Mock all external dependencies
- Test each interface implementation independently
- Validate data model transformations

### Integration Testing
- Test full data flow end-to-end
- Verify API rate limiting works correctly
- Test database operations under load

### Performance Testing
- Measure analysis speed with realistic data volumes
- Test memory usage during extended operations
- Validate caching effectiveness

## Configuration Management

### Environment-Specific Config
```python
# Local development
DATABASE_URL = "sqlite:///storage/tradescout.db"
CACHE_TTL = 60  # 1 minute for development

# Production
DATABASE_URL = "postgresql://user:pass@host/db"
CACHE_TTL = 300  # 5 minutes for production
```

### API Key Management
- Environment variables for all keys
- Separate config for each environment
- Never commit secrets to git

## Monitoring & Observability

### Logging Strategy
- Structured logging with correlation IDs
- Separate log levels for different components
- Performance metrics logging

### Metrics Collection
- API call counts and response times
- Analysis execution times
- Database query performance
- Suggestion accuracy rates

### Health Checks
- API endpoint availability
- Database connectivity
- Cache hit rates
- Recent analysis completion

## Security Considerations

### API Key Security
- Environment variables only
- Principle of least privilege
- Regular key rotation

### Data Protection
- No storage of sensitive personal data
- Encryption for cloud databases
- Secure backup procedures

### Input Validation
- Sanitize all external API responses
- Validate data model constraints
- Prevent injection attacks

## Scalability Considerations

### Horizontal Scaling
- Stateless analysis components
- Database connection pooling
- Distributed caching support

### Performance Optimization
- Batch processing for historical data
- Async processing for non-critical tasks
- Database query optimization

### Resource Management
- Memory-efficient data processing
- CPU-bound task optimization
- I/O operation batching

## Future Extension Points

### Machine Learning Integration
- Interface for ML model predictions
- Feature engineering pipeline
- Model training and evaluation

### Additional Data Sources
- Options data providers
- Economic indicators
- Crypto market data

### Advanced Features
- Portfolio management
- Risk management automation
- Strategy backtesting

This architecture provides a solid foundation for TradeScout that can grow from a simple local application to a sophisticated cloud-based trading system while maintaining clean, testable code throughout the evolution.