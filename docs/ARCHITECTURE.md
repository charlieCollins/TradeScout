# TradeScout Architecture Documentation

## Overview

TradeScout implements a sophisticated **API-first data collection architecture** that combines multiple financial data providers with intelligent routing. The system uses configuration-driven provider selection, intelligent fallback strategies, and comprehensive caching to handle rate-limited APIs effectively. The multi-provider architecture enables robust data collection even when individual providers fail or hit rate limits.

## Core Architecture Principles

1. **API-First Data Collection**: Multiple API providers with intelligent routing
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
├─────────────────────────────────────────────────────────┤
│                API Providers                            │
│ • YFinance              • Polygon.io                    │
│ • Finnhub               • Alpha Vantage                  │
│ • NewsAPI               • (Future: Tiingo, StockData)    │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│              SmartCoordinator                           │
│  • Configuration-driven routing                         │
│  • Multi-provider management                            │
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
┌─────────────┐  ┌─────────────────┐  ┌─────────────┐
│   CLI UI    │  │    Database     │  │    Cache    │
│             │  │   (SQLite)      │  │   (Files)   │
│  • Rich     │  │                 │  │             │
│  • Tables   │  │ • Quotes        │  │ • API calls │
│  • Charts   │  │ • Analysis      │  │ • Results   │
│  • Status   │  │ • Results       │  │ • Metadata  │
└─────────────┘  └─────────────────┘  └─────────────┘
```

## Multi-Source Aggregator Architecture

```
┌─────────────────────────────────────────────────────────┐
│              MultiSourceAggregator                     │
├─────────────────────────────────────────────────────────┤
│  Parallel API Execution:                               │
│                                                         │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐      │
│  │ YFinance    │ │ Polygon     │ │ Alpha Vant. │      │
│  │ Gainers     │ │ Gainers     │ │ Gainers     │      │
│  │ Losers      │ │ Losers      │ │ Losers      │      │
│  └─────────────┘ └─────────────┘ └─────────────┘      │
│                                                         │
│  ▼ Aggregation & Confidence Scoring ▼                  │
│                                                         │
│  ExtendedMarketMover objects with:                      │
│  • Multi-source validation                              │
│  • Confidence scoring                                   │
│  • Source tracking                                      │
└─────────────────────────────────────────────────────────┘
```

## Provider Configuration

```yaml
providers:
  yfinance:
    name: "Yahoo Finance"
    type: "api" 
    provider_type: "free"
    rate_limit_per_minute: 60
    priority: 2
    quality_weight: 7

  polygon:
    name: "Polygon.io"
    type: "api"
    provider_type: "freemium"
    rate_limit_per_minute: 5
    priority: 1
    quality_weight: 10

  finnhub:
    name: "Finnhub"
    type: "api"
    provider_type: "freemium"
    rate_limit_per_minute: 60
    priority: 3
    quality_weight: 9

  alpha_vantage:
    name: "Alpha Vantage"
    type: "api"
    provider_type: "freemium"
    rate_limit_per_day: 25
    priority: 4
    quality_weight: 6

data_types:
  current_quotes:
    providers: ["yfinance", "finnhub", "polygon", "alpha_vantage"]
    fallback_strategy: "first_success"
    
  market_movers:
    providers: ["yfinance", "polygon", "alpha_vantage"]
    fallback_strategy: "first_success"
    
  extended_hours:
    providers: ["polygon", "yfinance"]
    fallback_strategy: "first_success"
```

## SmartCoordinator Implementation

The SmartCoordinator is the central orchestration layer that provides intelligent routing between API providers based on configuration-driven reliability ratings and fallback strategies.

**Key Features:**
- **Multi-Provider Management**: Unified handling of API providers
- **Configuration-Driven Selection**: YAML-based provider configuration with data type mapping
- **Circuit Breaker Pattern**: Automatic provider failure detection and recovery
- **Intelligent Fallback**: Quality-based provider selection with graceful degradation

```python
class SmartCoordinator:
    def __init__(self):
        self._provider_instances = {}      # API provider implementations
        self.config_manager = DataSourcesManager()
        self.cache_manager = APICacheManager()
    
    def get_current_quote(self, symbol: str) -> MarketQuote:
        # API provider routing: polygon → yfinance → finnhub → alpha_vantage
        
    def get_market_movers(self, provider: str, mover_type: str) -> List[MarketMover]:
        # Multi-source market mover aggregation
```

## Gap Trading Analysis Pipeline

```
┌─────────────────────────────────────────────────────────┐
│                Gap Trading Pipeline                     │
├─────────────────────────────────────────────────────────┤
│  1. Multi-Source Market Movers Discovery               │
│     ├── YFinance market movers                         │
│     ├── Polygon gainers/losers                         │
│     └── Alpha Vantage TOP_GAINERS_LOSERS              │
│                                                         │
│  2. True Gap Calculation                                │
│     ├── Previous close vs current/premarket price      │
│     ├── Filter by minimum gap threshold (2%+)          │
│     └── Volume and liquidity validation                │
│                                                         │
│  3. Academic Binary Classification                      │
│     ├── Gap Size (>2%, <5% optimal)                   │
│     ├── Volume Surge (>150% average)                   │
│     ├── Market Cap (>$500M for safety)                 │
│     ├── Bid-Ask Spread (<2% for liquidity)            │
│     ├── Exhaustion Gap Detection                       │
│     └── Trading Session Timing                         │
│                                                         │
│  4. Risk-Managed Trade Suggestions                     │
│     ├── Position sizing (2% account risk max)          │
│     ├── Entry, target, and stop levels                 │
│     └── Risk/reward ratio validation                   │
└─────────────────────────────────────────────────────────┘
```

## System Status & Metrics

### Current Implementation Status
- **Data Providers**: 4 API providers operational
- **SmartCoordinator**: Multi-provider routing with circuit breaker
- **Configuration Management**: YAML-based provider selection
- **Caching Strategy**: File-based API response caching
- **Gap Analysis**: Complete academic implementation
- **CLI Interface**: Rich interface with status monitoring

### Performance Characteristics
- **API Providers**: 4 active providers with intelligent fallback
- **Rate Limiting**: Configured per-provider limits with throttling
- **Caching**: TTL-based caching for optimal performance
- **Reliability**: Circuit breaker pattern for automatic failure recovery

## Directory Structure

```
src/tradescout/
│
├── data_sources/                      # Data provider implementations
│   ├── smart_coordinator.py           # Central coordination layer
│   └── yfinance_scanner.py           # YFinance-specific utilities
│
├── data_sources_api/                  # API provider implementations  
│   ├── asset_data_provider_yfinance.py
│   ├── asset_data_provider_finnhub.py
│   ├── asset_data_provider_polygon.py
│   └── asset_data_provider_alpha_vantage.py
│
├── config/                            # Configuration management
│   ├── data_sources_config.yaml      # Provider configurations
│   ├── data_sources_manager.py       # Configuration loader
│   └── local_config.py              # Local settings
│
├── analysis/                          # Analysis implementations
│   ├── multi_source_aggregator.py    # Multi-provider aggregation
│   ├── gap_market_scanner.py         # Gap detection engine
│   └── academic_gap_analyzer.py      # Academic classification
│
├── data_models/                       # Domain models and interfaces
│   ├── domain_models_core.py         # Core data models
│   ├── market_wide_models.py         # Market-level models
│   └── interfaces.py                 # Abstract interfaces
│
├── caches/                           # Caching implementations
│   └── api_cache.py                  # API response caching
│
├── storage/                          # Database interfaces
│   └── sqlite_repository.py         # SQLite implementation
│
└── cli/                             # Command-line interface
    ├── main.py                      # CLI entry point
    └── suggest_command.py           # Gap trading suggestions
```

## Future Enhancements

### Planned API Integrations
- **Tiingo**: Additional market data provider
- **StockData.org**: News sentiment analysis
- **IEX Cloud**: Alternative financial data source

### System Improvements
- Enhanced caching strategies
- Real-time data streaming capabilities
- Advanced technical indicators
- Portfolio optimization features
- Web interface development