# TradeScout Architecture Documentation

## Overview

TradeScout implements a sophisticated **hybrid data collection architecture** that combines API-based providers with web scraping capabilities. The system uses configuration-driven provider selection, intelligent fallback strategies, and comprehensive caching to handle rate-limited APIs effectively. The dual-provider architecture enables robust data collection even when individual providers fail or hit rate limits.

## Core Architecture Principles

1. **Hybrid Data Collection**: Seamlessly combines API providers with web scrapers
2. **Configuration-Driven**: YAML-based provider management and data type mapping
3. **Circuit Breaker Resilience**: Automatic failure detection and recovery
4. **Interface-First Design**: All components implement abstract interfaces for testability
5. **Quality-Based Routing**: Intelligent provider selection based on reliability ratings
6. **Multi-Tier Caching**: Aggressive caching strategies to minimize API rate limit issues
7. **Clean Data Models**: External data transformed to standardized internal models
8. **Separation of Concerns**: Data collection, analysis, and storage are independent

## Data Flow Architecture

```
┌─────────────────────────────────────────────────────────┐
│                External Data Sources                    │
├─────────────────────────┬───────────────────────────────┤
│     API Providers       │      Web Scrapers             │
│ • YFinance              │ • CNNScraper                  │
│ • Polygon               │ • MarketWatchScraper          │
│ • Finnhub               │ • InvestingComScraper         │
│ • AlphaVantage          │ • TipRanksScraper             │
│ • NewsAPI               │ • ADVFNScraper                │
└─────────────────────────┴───────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│              SmartCoordinator                           │
│  • Configuration-driven routing                         │
│  • Dual provider management (APIs + Scrapers)          │
│  • Circuit breaker pattern                              │
│  • Reliability-based fallback strategies               │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                Analysis Engine                          │
│  • Gap analysis (CandidateGapTypeAnalyzer)            │
│  • Momentum detection                                   │
│  • Technical indicators                                 │
│  • Trade suggestion generation                          │
└─────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌─────────────┐  ┌──────────────────┐  ┌─────────────┐
│   SQLite    │  │   Multi-Tier     │  │   CLI       │
│  Repository │  │     Cache        │  │ Interface   │
│             │  │  (API + File)    │  │  (Rich)     │
└─────────────┘  └──────────────────┘  └─────────────┘
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

#### API-Based Data Collection
```python
AssetDataProvider (ABC) [src/tradescout/data_models/interfaces.py]
├── get_current_quote()
├── get_extended_hours_data()
├── get_historical_quotes()
├── scan_volume_leaders()
└── get_fundamental_data()

# Current Implementations in src/tradescout/data_sources_api/
├── AssetDataProviderYFinance (Priority 2, active, unlimited)
├── AssetDataProviderPolygon (Priority 1, 5/min free)  
├── AssetDataProviderFinnhub (Priority 3, 60/min free)
└── AssetDataProviderAlphaVantage (Priority 4, 25/day free - includes market movers)
```

#### Web Scraper-Based Data Collection
```python
AfterHoursWebScraper (ABC) [src/tradescout/data_sources_scraping/interfaces.py]
├── get_after_hours_gainers()
├── get_after_hours_losers()
├── is_after_hours_session()
└── get_session_info()

PreMarketWebScraper (ABC) [src/tradescout/data_sources_scraping/interfaces.py]
├── get_premarket_gainers()
├── get_premarket_losers()  
├── is_premarket_session()
└── get_premarket_session_info()

# Current Implementations in src/tradescout/data_sources_scraping/
├── CNNScraper (AfterHours ✓, PreMarket ✓)
├── MarketWatchScraper (AfterHours ✓, PreMarket ✓)
├── InvestingComScraper (AfterHours ✓, PreMarket ✓) 
├── TipRanksScraper (AfterHours ✓, PreMarket ✓)
├── ADVFNScraper (AfterHours ✓, PreMarket ✓)
└── TradingViewScraper (planned - not implemented yet)
```

#### Smart Coordination
```python
SmartCoordinator [src/tradescout/data_sources/smart_coordinator.py]
├── Configuration-driven provider selection via YAML
├── Dual routing architecture:
│   ├── _provider_instances: API providers (AssetDataProvider)
│   └── _scraper_instances: Web scrapers (AfterHours + PreMarket)
├── Four fallback strategies:
│   ├── FIRST_SUCCESS: Try providers in priority order
│   ├── MERGE_BEST: Get highest quality result
│   ├── MERGE_ALL: Combine all provider results
│   └── ROUND_ROBIN: Load balance between providers
├── Circuit breaker pattern for failing providers
├── Quality-based provider weighting
└── Extended hours and market movers coordination
```

#### Other Interfaces
```python
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
# Core Analysis Interfaces [src/tradescout/analysis/interfaces.py]
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

# Gap Trading Implementation (Academic Research-Based)
CandidateGapTypeAnalyzer (ABC) [src/tradescout/analysis/interfaces.py]
├── classify_gap_type()        # Academic 4-type classification
├── calculate_gap_magnitude()  # Size-based thresholds (≥2.0%)
├── assess_continuation_probability()  # Statistical likelihood
├── validate_trading_rules()   # Binary good/bad candidate rules
└── generate_gap_candidates()  # 6-step filtering process

# Gap Types Based on Academic Research:
# - Common gaps: <1.5% size, 25% continuation rate  
# - Breakaway gaps: 2-5% size, 70% continuation rate
# - Continuation gaps: 2-7% size, 80% continuation rate
# - Exhaustion gaps: >5% size, 20% continuation rate
```

### Storage Interfaces and Current Implementation

```python
# Database Management [src/tradescout/storage/]
SQLiteRepository [src/tradescout/storage/sqlite_repository.py] ✓ IMPLEMENTED
├── store_quote()              # Market quote storage with indexing
├── get_quotes_by_symbol()     # Historical quote retrieval
├── get_database_stats()       # Storage analytics and size tracking
├── cleanup_old_data()         # Automated data retention
└── execute_raw_query()        # Complex analytics queries

# Planned Repository Extensions (interfaces defined)
DatabaseManager (ABC)
├── QuoteRepository ✓          # Currently implemented in SQLiteRepository
├── NewsRepository             # Interface ready, implementation pending
├── SentimentRepository        # Interface ready, implementation pending
├── SuggestionRepository       # Interface ready, implementation pending
├── TradeRepository            # Interface ready, implementation pending
└── PerformanceRepository      # Interface ready, implementation pending
```

## Current Implementation Status

### ✅ Phase 1: Core Data Collection (Complete)
- **Market Data Providers**: 4 API providers + 5 web scrapers operational
- **SmartCoordinator**: Dual routing architecture with circuit breaker
- **Configuration Management**: YAML-based provider selection
- **Caching System**: Multi-tier caching with aggressive TTL policies
- **CLI Interface**: Rich CLI with 8+ commands for market analysis
- **Extended Hours Support**: Both pre-market and after-hours data collection

### ✅ Phase 2: Market Analysis (Complete)
- **Market Movers**: Alpha Vantage + YFinance fallback for gainers/losers
- **Quote System**: Real-time and historical quote collection
- **Volume Analysis**: Volume leaders and surge detection
- **Extended Hours Analysis**: Pre-market and after-hours market movers
- **Web Scraping**: 5 scrapers for comprehensive market coverage

### 🔄 Phase 3: Gap Trading Implementation (In Progress)
- **Gap Strategy Framework**: Academic research integration complete
- **Binary Classification Rules**: Machine-readable gap candidate rules
- **CandidateGapTypeAnalyzer**: Interface defined, implementation pending
- **Gap Screening Logic**: Binary rules-based screening system needed
- **Performance Tracking**: Basic framework in place

### 🔮 Phase 4: Advanced Features (Planned)
- **News and Sentiment**: NewsProvider and SentimentProvider interfaces
- **Technical Analysis**: TechnicalAnalyzer implementation
- **Trade Suggestions**: SuggestionEngine with confidence scoring
- **Portfolio Management**: Trade tracking and performance analysis
- **Email Notifications**: Alert system for gap candidates
- **Web Dashboard**: React-based frontend for visual analysis

## Smart Data Coordination Architecture

### SmartCoordinator: Unified Data Routing

The SmartCoordinator is the central orchestration layer that provides intelligent routing between API providers and web scrapers based on configuration-driven reliability ratings and fallback strategies.

**Key Features:**
- **Dual Provider Management**: Separate handling of API providers vs web scrapers
- **Configuration-Driven Selection**: YAML-based provider configuration with data type mapping
- **Circuit Breaker Pattern**: Automatic provider failure detection and recovery
- **Quality-Based Routing**: Weighted provider selection based on reliability ratings
- **Comprehensive Caching**: Multi-tier caching with provider-specific TTL policies

```python
class SmartCoordinator:
    """
    Central data orchestration with hybrid provider architecture:
    - API Providers: Structured data (quotes, fundamentals, historical)
    - Web Scrapers: Market movers and extended hours data
    """
    
    def __init__(self):
        self._provider_instances = {}      # AssetDataProvider implementations
        self._scraper_instances = {}       # Web scraper implementations
        self.config_manager = DataSourcesManager()
        self.cache_manager = APICacheManager()
    
    # Core routing methods with intelligent fallback
    def get_current_quote(self, symbol: str) -> MarketQuote:
        # Routes through: yfinance → finnhub → alpha_vantage
    
    def get_extended_hours_data(self, symbol: str) -> ExtendedHoursData:
        # API providers: polygon → yfinance
        # Fallback to web scrapers if APIs fail
    
    def get_extended_hours_gainers(self, limit: int) -> List[Dict]:
        # Web scraper routing: marketwatch → cnn → tipranks → investing_com
```

### Configuration-Driven Data Type Mapping

**Current Data Types and Provider Mapping:**

```yaml
# data_sources_config.yaml structure
data_types:
  current_quotes:
    providers: ["yfinance", "finnhub", "alpha_vantage"]
    fallback_strategy: "first_success"
    cache_ttl_minutes: 60
    
  extended_hours:
    providers: ["polygon", "yfinance", "marketwatch_scraper", "investing_com_scraper", "cnn_scraper", "tipranks_scraper"]
    fallback_strategy: "first_success"
    cache_ttl_minutes: 5
    
  market_movers:
    providers: ["alpha_vantage_market", "yfinance"]
    fallback_strategy: "first_success"
    cache_ttl_minutes: 60
    
  company_fundamentals:
    providers: ["finnhub", "alpha_vantage", "yfinance"]
    fallback_strategy: "merge_best"
    cache_ttl_minutes: 1440  # 24 hours

# Provider reliability and quality weighting
quality_weights:
  # API Providers (structured data)
  polygon: 10              # Premium API, highest quality
  finnhub: 9               # High quality, good free tier
  yfinance: 7              # Good quality, widely used
  alpha_vantage: 6         # Limited free tier
  alpha_vantage_market: 8  # Specialized market data
  
  # Web Scrapers (reliability-based)
  marketwatch_scraper: 8   # highly_reliable
  investing_com_scraper: 8 # highly_reliable  
  cnn_scraper: 6          # moderately_reliable
  tipranks_scraper: 6     # moderately_reliable
  advfn_scraper: 3        # inconsistent (disabled by default)
```

### Dual Provider Architecture Implementation

```
┌─────────────────────────────────────────────────────────┐
│                SmartCoordinator                         │
│  Configuration Manager + Circuit Breaker + Cache       │
├─────────────────────────┬───────────────────────────────┤
│     API Providers       │      Web Scrapers             │
│  (AssetDataProvider)    │  (AfterHours + PreMarket)     │
├─────────────────────────┼───────────────────────────────┤
│ • YFinance (Priority 2) │ • CNNScraper                  │
│ • Polygon (Disabled)    │ • MarketWatchScraper          │
│ • Finnhub (Priority 3)  │ • InvestingComScraper         │
│ • AlphaVantage (P4)     │ • TipRanksScraper             │
│ • NewsAPI               │ • ADVFNScraper (disabled)     │
└─────────────────────────┴───────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│           Multi-Tier Caching Strategy                   │
│ • Provider-specific cache directories                   │
│ • Policy-based TTL (Real-time, Extended Hours, etc.)   │
│ • LRU eviction with 500MB limit                        │
│ • MD5-based cache keys                                 │
└─────────────────────────────────────────────────────────┘
```

### Fallback Strategy Implementation

**Four Built-in Fallback Strategies:**

1. **FIRST_SUCCESS** (Default)
   - Try providers in priority order until one succeeds
   - Fastest response time, used for real-time data

2. **MERGE_BEST**
   - Get data from multiple providers, return highest quality result
   - Used for fundamental data where quality matters

3. **MERGE_ALL**
   - Combine results from all available providers
   - Used for comprehensive market scanning

4. **ROUND_ROBIN**
   - Rotate between providers for load balancing
   - Used to distribute API rate limit usage

### Circuit Breaker Pattern

**Provider Health Monitoring:**
- Track failures per provider in sliding window
- Automatically disable providers after 5 failures in 10 minutes  
- Re-enable providers after cooling off period
- Real-time status reporting via CLI `./tradescout status`

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

## Advanced Caching and Rate Limiting

### Multi-Tier Caching Architecture

**File-Based Cache System** (`src/tradescout/caches/api_cache.py`):
- **Provider-Specific Directories**: `data/cache/{provider}/`
- **Policy-Based TTLs**: Different cache durations by data type
  - Real-time quotes: 1 hour (aggressive caching for rate-limited APIs)
  - Extended hours: 5 minutes
  - Fundamentals: 24 hours
  - Historical data: 30 days
- **LRU Eviction**: Automatic cleanup when cache exceeds 500MB
- **MD5 Cache Keys**: Hash of provider + endpoint + parameters
- **Compression Support**: JSON with optional compression

**Example Data Caching** (`data/examples/`):
- Save API responses to avoid repeated calls during development
- Timestamped JSON files for debugging and analysis
- Screenshot storage for web scraper debugging

### Rate Limiting Strategy

**Per-Provider Rate Limits**:
- **Alpha Vantage**: 25 calls/day (very limited)
- **Finnhub**: 60 calls/minute (free tier)
- **YFinance**: 60 calls/minute (estimated)
- **Polygon**: 5 calls/minute (free tier, disabled by default)

**Rate Limit Management**:
- Automatic backoff strategies (exponential, linear, fixed)
- Cache-first approach to minimize API calls
- Circuit breaker integration with rate limit tracking
- Provider rotation to distribute load

**Cache Policies by Data Type**:
```python
class CachePolicy(Enum):
    REAL_TIME = "real_time"      # 1 hour TTL
    INTRADAY = "intraday"        # 1 hour TTL
    PREMARKET = "premarket"      # 1 hour TTL
    AFTERHOURS = "afterhours"    # 1 hour TTL
    FUNDAMENTALS = "fundamentals" # 24 hours TTL
    HISTORICAL = "historical"    # 30 days TTL
```

## Database Schema Design

### Current SQLite Schema Implementation

**Implemented Schema** (`src/tradescout/storage/sqlite_repository.py`):
```sql
-- Market quotes with extended information (IMPLEMENTED)
CREATE TABLE quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol VARCHAR(10) NOT NULL,
    timestamp DATETIME NOT NULL,
    price DECIMAL(10,4) NOT NULL,
    volume INTEGER,
    change_amount DECIMAL(10,4),
    change_percent DECIMAL(5,2),
    day_high DECIMAL(10,4),
    day_low DECIMAL(10,4),
    previous_close DECIMAL(10,4),
    market_cap BIGINT,
    session VARCHAR(20),
    provider VARCHAR(50),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
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

## Current Project Structure

```
TradeScout/
├── src/tradescout/                    # Core application code
│   ├── data_sources_api/              # API provider implementations
│   │   ├── asset_data_provider_yfinance.py
│   │   ├── asset_data_provider_finnhub.py
│   │   ├── asset_data_provider_alpha_vantage.py
│   │   └── smart_coordinator.py       # Central routing logic
│   │
│   ├── data_sources_scraping/         # Web scraper implementations  
│   │   ├── cnn_scraper.py
│   │   ├── marketwatch_scraper.py
│   │   ├── investing_com_scraper.py
│   │   ├── tipranks_scraper.py
│   │   └── advfn_scraper.py
│   │
│   ├── config/                        # Configuration management
│   │   ├── data_sources_config.yaml   # Provider configuration
│   │   └── data_sources_manager.py    # Config parsing logic
│   │
│   ├── caches/                        # Caching infrastructure
│   │   └── api_cache.py              # Multi-tier cache system
│   │
│   ├── storage/                       # Data persistence
│   │   └── sqlite_repository.py      # SQLite implementation
│   │
│   ├── analysis/                      # Analysis interfaces
│   │   └── interfaces.py             # Gap analysis, momentum detection
│   │
│   ├── market_wide/                   # Market-wide data providers
│   │   ├── market_movers.py          # Market gainers/losers logic
│   │   └── providers/alpha_vantage_market.py
│   │
│   ├── data_models/                   # Core data structures
│   │   ├── interfaces.py             # AssetDataProvider interface
│   │   ├── domain_models.py          # Market quotes, extended hours
│   │   └── domain_models_analysis.py # Gap analysis models
│   │
│   └── scripts/                       # CLI and utilities
│       └── cli.py                    # Rich CLI interface
│
├── data/                              # Data storage and examples
│   ├── cache/                        # Provider-specific cache directories
│   ├── examples/                     # API response examples and screenshots
│   └── storage/                      # SQLite database files
│
├── docs/                              # Documentation
│   ├── ARCHITECTURE.md               # This document
│   ├── GAP_TRADING_STRATEGY.md       # Academic research-based strategy
│   ├── GAP_TRADING_STRATEGY_RULES.md # Machine-readable binary rules
│   ├── WEB_SCRAPERS.md              # Scraper capabilities matrix
│   └── MARKET_HOURS.md              # Trading session definitions
│
├── tests/                            # Test suite
│   └── test_*.py                    # Unit and integration tests
│
└── Configuration Files
    ├── CLAUDE.md                     # Development guidelines
    ├── CLAUDE_TODO.md               # Task tracking
    ├── CLAUDE_CONTEXT.md            # Session continuity
    └── .env                         # API keys (not in repo)
```

## Summary and Evolution Path

TradeScout has evolved from a simple market data collection tool into a sophisticated **hybrid data architecture** that demonstrates enterprise-level reliability patterns:

**Current Strengths:**
- Robust dual-provider architecture (APIs + web scraping)
- Configuration-driven provider management with intelligent fallback
- Comprehensive caching reduces API rate limit issues
- Circuit breaker pattern ensures system resilience
- Rich CLI interface with real-time market data
- Academic research-based gap trading strategy framework

**Architecture Highlights:**
- **SmartCoordinator** as central orchestration layer
- **Quality-based routing** with provider reliability ratings  
- **Multi-tier caching** with provider-specific policies
- **Interface-first design** enabling easy testing and extension
- **Configuration-driven** provider selection and fallback strategies

**Growth Path:**
- Current foundation supports seamless extension to web dashboard
- Interface-based design enables cloud migration without refactoring
- Gap analysis framework ready for machine learning integration
- Comprehensive data collection enables advanced technical analysis

This architecture provides a solid foundation that can scale from a personal research tool to a sophisticated cloud-based trading system while maintaining clean, testable code throughout the evolution.