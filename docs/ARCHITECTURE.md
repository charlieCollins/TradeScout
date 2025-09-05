# TradeScout Architecture Documentation

## Overview

TradeScout implements a **commercial-grade data collection architecture** using Polygon.io as the primary data provider. The system uses configuration-driven data type management, intelligent caching strategies, and comprehensive error handling to provide reliable market data. The single-provider architecture with commercial API access eliminates rate limiting concerns while maintaining enterprise-grade reliability.

## Core Architecture Principles

1. **Commercial API Integration**: Single high-quality provider for all data types
2. **Configuration-Driven**: YAML-based data type mapping and caching policies
3. **Circuit Breaker Resilience**: Automatic failure detection and recovery
4. **Interface-First Design**: All components implement abstract interfaces for testability
5. **Single-Provider Reliability**: Commercial-grade API eliminates fallback complexity
6. **Multi-Tier Caching**: TTL-based caching strategies with automatic cleanup
7. **Clean Data Models**: External data transformed to standardized internal models
8. **Separation of Concerns**: Data collection, analysis, and storage are independent

## Data Flow Architecture

```
┌─────────────────────────────────────────────────────────┐
│                External Data Source                     │
├─────────────────────────────────────────────────────────┤
│                 Polygon.io API                          │
│ • Real-time market data     • Extended hours trading    │
│ • Company fundamentals      • News & sentiment          │
│ • Technical indicators      • Crypto & Forex data       │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│              SmartCoordinator                           │
│  • Single-provider architecture                         │
│  • Configuration-driven data type mapping               │
│  • Circuit breaker pattern with exponential backoff     │
│  • Intelligent caching with TTL policies                │
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

## Single-Provider Data Architecture

```
┌─────────────────────────────────────────────────────────┐
│                Data Collection Layer                    │
├─────────────────────────────────────────────────────────┤
│  Polygon.io API Integration:                            │
│                                                         │
│  ┌─────────────────────────────────────────────────────┐ │
│  │            Polygon.io REST API                      │ │
│  │  • Market Movers    • Historical Data              │ │
│  │  • Real-time Quotes • Company Fundamentals         │ │
│  │  • Extended Hours   • News & Sentiment             │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                         │
│  ▼ Data Transformation & Caching ▼                     │
│                                                         │
│  Domain Model Objects with:                             │
│  • Standardized data structure                          │
│  • TTL-based caching                                    │
│  • Error handling and recovery                          │
└─────────────────────────────────────────────────────────┘
```

## Provider Configuration

```yaml
providers:
  polygon:
    name: "Polygon.io"
    type: "api"
    provider_type: "commercial"
    rate_limit_per_minute: 300  # Commercial tier
    priority: 1
    enabled: true
    supports_extended_hours: true
    supports_market_movers: true
    supports_news: true
    supports_fundamentals: true
    api_key_required: true
    
  tiingo:
    name: "Tiingo"
    type: "api"
    provider_type: "commercial"
    enabled: false  # Disabled - using Polygon
    priority: 2

data_types:
  current_quotes:
    providers: ["polygon"]
    cache_ttl_minutes: 1
    
  market_movers:
    providers: ["polygon"]
    cache_ttl_minutes: 15
    
  extended_hours:
    providers: ["polygon"]
    cache_ttl_minutes: 5
    
  company_fundamentals:
    providers: ["polygon"]
    cache_ttl_days: 7
```

## SmartCoordinator Implementation

The SmartCoordinator is the central orchestration layer that provides intelligent data routing and caching for the single-provider Polygon.io architecture.

**Key Features:**
- **Single-Provider Management**: Streamlined architecture with commercial-grade API
- **Configuration-Driven Mapping**: YAML-based data type configuration with caching policies
- **Circuit Breaker Pattern**: Automatic failure detection with exponential backoff
- **Intelligent Caching**: TTL-based caching with fallback to cached data

```python
class SmartCoordinator:
    def __init__(self):
        self._provider_instances = {}      # Polygon and Tiingo providers
        self.config_manager = DataSourcesManager()
        self.cache_manager = APICacheManager()
    
    def get_current_quote(self, symbol: str) -> MarketQuote:
        # Single provider routing through Polygon.io with caching
        
    def get_market_movers(self, provider: str, mover_type: str) -> List[MarketMover]:
        # Polygon.io market movers with intelligent caching
```

## Gap Trading Analysis Pipeline

```
┌─────────────────────────────────────────────────────────┐
│                Gap Trading Pipeline                     │
├─────────────────────────────────────────────────────────┤
│  1. Polygon.io Market Movers Discovery                 │
│     ├── Real-time gainers/losers                       │
│     ├── Most active stocks by volume                   │
│     └── Extended hours pre-market activity             │
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
- **Data Provider**: Single commercial-grade Polygon.io API integration
- **SmartCoordinator**: Single-provider routing with circuit breaker protection
- **Configuration Management**: YAML-based data type mapping and caching policies
- **Caching Strategy**: TTL-based intelligent caching with automatic cleanup
- **Gap Analysis**: Complete academic implementation operational
- **CLI Interface**: Rich interface with comprehensive status monitoring

### Performance Characteristics
- **API Provider**: Commercial Polygon.io with 300+ calls/minute capacity
- **Rate Limiting**: Commercial tier eliminates rate limiting concerns
- **Caching**: Multi-tier TTL-based caching (1m quotes, 7d fundamentals)
- **Reliability**: Circuit breaker pattern with exponential backoff retry logic

## Directory Structure

```
src/tradescout/
│
├── data_sources/                      # Data provider implementations
│   ├── smart_coordinator.py           # Central coordination layer
│   └── yfinance_scanner.py           # YFinance-specific utilities
│
├── data_sources_api/                  # API provider implementations  
│   ├── asset_data_provider_polygon.py  # Primary Polygon.io provider
│   └── asset_data_provider_tiingo.py   # Alternative provider (disabled)
│
├── config/                            # Configuration management
│   ├── data_sources_config.yaml      # Provider configurations
│   ├── cache_config.yaml             # Caching policies and TTL settings
│   ├── data_sources_manager.py       # Configuration loader
│   └── local_config.py               # Local settings
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
└── scripts/                         # Command-line interface
    └── cli.py                       # CLI entry point with all commands
```

## Future Enhancements

### Planned Enhancements
- **Tiingo Integration**: Enable secondary provider for redundancy
- **News Sentiment**: Enhanced sentiment analysis from Polygon news feeds
- **Options Data**: Leverage Polygon's options chain and unusual activity data

### System Improvements
- Enhanced caching strategies
- Real-time data streaming capabilities
- Advanced technical indicators
- Portfolio optimization features
- Web interface development