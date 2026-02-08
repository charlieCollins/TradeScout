# TradeScout

Personal Market Research Assistant - A Python CLI tool for real-time market screening and analysis.

**Repository:** https://github.com/charlieCollins/TradeScout (Private)

## What It Does

TradeScout provides real-time market screening across different trading sessions:

- **Market Screeners**: Find gainers, losers, high volume, and momentum stocks
- **Session-Aware Analysis**: Premarket, regular, and afterhours screening
- **Free Data Providers**: Live market data via yfinance, SEC EDGAR, Finnhub, FRED (no paid APIs required)
- **SQLite Database**: Local caching and historical data storage

## Current Features

### Screeners Available

**Context-Aware Screeners** (automatically adapt to current market session):
- `gainers` - Top gaining stocks
  - Premarket: vs previous close
  - Regular: vs day open
  - Afterhours: vs 4PM close
  - Closed: last available vs appropriate reference
- `losers` - Top losing stocks (mirror of gainers for downward moves)
- `momentum` - High momentum stocks (largest absolute price moves)
- `volume` - High volume stocks (unusual trading activity)

All screeners use a template-based system that automatically selects appropriate price/volume calculations based on the current market session.

### Commands

#### Screener Commands
- `tradescout screener <name>` - Run a market screener
- `tradescout screener --list` - Show available screeners

#### Asset Commands
- `tradescout asset info <symbol>` - Get detailed asset information
- `tradescout asset status` - Show market context for configured exchanges

#### Market Commands
- `tradescout market info` - Show market status and snapshot metadata
- `tradescout market update` - Update market data for all universe assets
- `tradescout market context` - Show current market context with session info
- `tradescout market session` - Display session information

#### Universe Commands
- `tradescout universe list` - List all available universes
- `tradescout universe info [name]` - Show detailed universe information
- `tradescout universe current` - Show currently active universe
- `tradescout universe activate <name>` - Set active universe
- `tradescout universe create <name>` - Create new universe
- `tradescout universe delete <name>` - Delete universe

#### Gap Analysis Commands
- `tradescout gap analyze <symbols>` - Analyze specific symbols for gap information
- `tradescout gap candidates` - Find gap candidates using screeners
- `tradescout gap setup` - Setup catalyst database for analysis

#### Database Commands
- `tradescout database init` - Initialize database schema
- `tradescout database info` - Show database information and statistics
- `tradescout database reset` - Reset database (with confirmation)
- `tradescout database bootstrap-providers` - Initialize data providers
- `tradescout database bootstrap-markets` - Initialize market data
- `tradescout database bootstrap-tickers` - Populate asset universe (15k+ tickers)
- `tradescout database bootstrap-universes` - Initialize asset universes
- `tradescout database bootstrap-fundamentals` - Bootstrap fundamentals data
- `tradescout database bootstrap-sentiment-types` - Initialize sentiment types
- `tradescout database bootstrap-all` - Run all bootstrap operations
- `tradescout database results-backup` - Backup gap analysis results to JSON
- `tradescout database results-restore` - Restore gap analysis results from JSON

### Data Management
- **Database**: SQLite with 13 tables (location: `data/tradescout.db`)
- **Universe**: ~11,750 filtered stocks (XNYS/XNAS exchanges, active, 1-5 char symbols)
- **Data Sources**: yfinance (snapshots/aggregates), NASDAQ Trader (ticker listing), SEC EDGAR (fundamentals), Finnhub (news), FRED (economic data)
- **Caching**: TTL-based caching with automatic refresh logic

### Session Awareness
- **Market Sessions**: Premarket (4-9:30 AM), Regular (9:30 AM-4 PM), Afterhours (4-8 PM), Closed
- **Session Validation**: Screeners only run during appropriate sessions
- **Smart Warnings**: Context-aware warnings about market state and data freshness

## Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure API Keys** (free):
   ```bash
   # Create .env file with free API keys
   cp .env.example .env
   # Add: FINNHUB_API_KEY=your_key (free at finnhub.io)
   # Add: FRED_API_KEY=your_key (free at fred.stlouisfed.org)
   ```

3. **Initialize Database**:
   ```bash
   ./tradescout database init
   ./tradescout database bootstrap-all
   ```

4. **Update Market Data**:
   ```bash
   ./tradescout market update
   ```

## Usage Examples

```bash
# Show current market context and session
./tradescout market context

# Run context-aware gainers screener (adapts to current session)
./tradescout screener gainers

# Run losers screener
./tradescout screener losers

# Get detailed stock info
./tradescout asset info AAPL

# Manage universes
./tradescout universe list
./tradescout universe info default_universe

# List all available screeners
./tradescout screener --list

# Database management
./tradescout database info
```

## Architecture

TradeScout uses a **layered repository architecture** with clean separation of concerns:

### Core Layers
- **CLI Layer**: Click framework with output-agnostic commands
- **Presentation Layer**: Output adapters (CLI with Rich formatting, Web with JSON)
- **Service Layer**: Business logic orchestration (DataServiceV2, MarketContextService)
- **Repository Layer**: Type-safe data access with SQLModel
- **Provider Layer**: External API integration (yfinance, NASDAQ Trader, SEC EDGAR, Finnhub, FRED)
- **Database**: SQLite with dual model system (domain dataclasses + ORM SQLModels)

### Key Patterns
- **Result Model → Adapter Pattern**: Commands build output-agnostic result models, adapters handle formatting
  - 11 CLI adapters for terminal display (Rich tables/colors)
  - 9 Web adapters for JSON API responses
  - Same business logic works for CLI and Web
- **Repository Pattern**: Business-focused data access, hiding database complexity
- **Cache-Aside Pattern**: TTL-based caching with automatic refresh
- **Dependency Injection**: PresentationContext injects appropriate adapters (CLI vs Web)

### Key Components
- **PresentationContext**: Manages output adapters for display-agnostic commands
- **Result Models**: Output-agnostic data containers (ScreenerResult, GapAnalysisResult, etc.)
- **MarketContext**: Comprehensive market session and trading day intelligence
- **Typed Models**: Domain dataclasses (Asset, Market) + ORM SQLModels for persistence
- **Universe System**: Configurable asset universes with filtering and statistics

## Requirements

- **Python 3.8+**
- **SQLite** (included with Python)
- **Linux/Ubuntu/WSL2** (primary development platform)
- **Free API keys**: Finnhub (news), FRED (economic data) - optional but recommended

## Documentation

### Getting Started
- **[Getting Started Guide](docs/GETTING_STARTED.md)** - Complete installation and setup tutorial

### Architecture
- **[Architecture Guide](docs/ARCHITECTURE.md)** - System architecture and design patterns
- **[Database Schema](docs/DATABASE.md)** - Complete database schema and table reference
- **[Presentation Context](docs/PRESENTATION_CONTEXT.md)** - Output adapter system

### Feature Guides
- **[Screeners](docs/SCREENERS.md)** - Context-aware screener system
- **[Bootstrapping](docs/BOOTSTRAPPING.md)** - Reference data initialization
- **[Gap Trading Strategy](docs/GAP_TRADING_STRATEGY.md)** - Gap analysis methodology
- **[Gap Results](docs/GAP_RESULTS.md)** - Gap tracking and reporting
- **[Gap Backtest](docs/GAP_BACKTEST.md)** - Historical gap analysis
- **[Sentiment](docs/SENTIMENT.md)** - News sentiment analysis

### Data Sources (Legacy Reference)
- **[Polygon.io Integration](docs/POLYGON.md)** - Legacy Polygon API reference (fallback provider)
- **[Polygon Implementation](docs/POLYGON_IMPLEMENTATION.md)** - Legacy implementation details
- **[Volume Fields Reference](docs/POLYGON_VOLUME_INFO.md)** - Volume data reference

### Project Management
- **[Lessons Learned](CLAUDE_LESSONS_LEARNED.md)** - Development insights and anti-patterns

---

*TradeScout focuses on real-time market screening and data management. Built for rapid analysis across different trading sessions with clean, maintainable code architecture.*