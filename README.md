# TradeScout

Personal Market Research Assistant - A Python CLI tool for real-time market screening and analysis.

**Repository:** https://github.com/charlieCollins/TradeScout (Private)

## What It Does

TradeScout provides real-time market screening across different trading sessions:

- **Market Screeners**: Find gainers, losers, high volume, and momentum stocks
- **Session-Aware Analysis**: Premarket, regular, and afterhours screening
- **Real-Time Data**: Live market data via Polygon.io Premium API
- **SQLite Database**: Local caching and historical data storage

## Current Features

### Screeners Available

**Regular Session:**
- `gainers_regular` - Top gaining stocks (current price vs day open)
- `losers_regular` - Top losing stocks (current price vs day open)

**Extended Hours:**
- `gainers_premarket` - Premarket gap-ups from previous close
- `losers_premarket` - Premarket gap-downs from previous close
- `gainers_after_hours` - Afterhours gainers vs 4PM close
- `losers_after_hours` - Afterhours losers vs 4PM close

**Closed Session:**
- `gainers_closed_scope_regular` - Regular session gainers (day open to close)
- `losers_closed_scope_regular` - Regular session losers (day open to close)

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
- `tradescout database bootstrap-tickers` - Populate asset universe
- `tradescout database bootstrap-universes` - Initialize asset universes
- `tradescout database bootstrap-fundamentals` - Bootstrap fundamentals data
- `tradescout database bootstrap-all` - Run all bootstrap operations

### Data Management
- **Database**: SQLite with 13 tables (location: `data/tradescout.db`)
- **Universe**: ~7,500 filtered stocks (XNYS/XNAS exchanges, active, 1-5 char symbols)
- **Data Source**: Polygon.io Premium subscription (15-minute delayed, extended hours support)
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

2. **Configure API Keys**:
   ```bash
   export POLYGON_API_KEY="your_polygon_api_key_here"
   ```
   Or copy the example environment file and edit it:
   ```bash
   cp .env.example .env
   # Edit .env and add your Polygon.io API key
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

# Find afterhours gainers
./tradescout screener gainers_after_hours

# Find regular session gainers
./tradescout screener gainers_regular

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

- **CLI Layer**: Click framework with Rich output formatting
- **Data Provider**: Centralized data access layer with typed models
- **Market Context**: Comprehensive market session and trading day intelligence
- **Database**: SQLite with custom DatabaseManager and proper schema
- **API Integration**: Polygon.io Premium with rate limiting and model conversion
- **Screeners**: YAML-configured with dynamic SQL generation
- **Universe Management**: Multi-universe asset filtering and organization
- **Session Management**: Real-time market session detection with trading calendar awareness

### Key Components
- **MarketContext**: Replaces simple market status with comprehensive session intelligence
- **Typed Models**: MarketSnapshot, TickerSnapshot, AssetFundamentals, Universe models
- **Data Provider Pattern**: CLI → Data Provider → Database (no layer bypassing)
- **Universe System**: Configurable asset universes with filtering and statistics

## Requirements

- **Python 3.8+**
- **Polygon.io Premium API** ($50/month - provides extended hours data)
- **SQLite** (included with Python)
- **Linux/Ubuntu/WSL2** (primary development platform)

## Documentation

### Getting Started
- **[Getting Started Guide](docs/GETTING_STARTED.md)** - Complete installation and setup tutorial

### API Reference
- **[Base Classes](docs/API_REFERENCE_BASE_CLASSES.md)** - BaseManager and BaseProvider documentation
- **[DataService](docs/API_REFERENCE_DATA_SERVICE.md)** - Complete DataService API reference

### Architecture
- **[Database Managers](docs/ARCHITECTURE_MANAGERS.md)** - Manager/Provider pattern and TTL logic
- **[API Providers](docs/ARCHITECTURE_API_PROVIDERS.md)** - External API integration patterns
- **[Database Schema](docs/DATABASE.md)** - Complete database schema and table reference

### Feature Guides
- **[Screeners](docs/SCREENERS.md)** - Screener system and configuration
- **[Bootstrapping](docs/BOOTSTRAPPING.md)** - Reference data initialization
- **[Gap Trading](docs/GAP_TRADING_STRATEGY.md)** - Gap analysis and trading strategies
- **[Sentiment](docs/SENTIMENT.md)** - Sentiment detection system (future feature)

### Data Sources
- **[Polygon.io Integration](docs/DATA_SOURCE_POLYGON.md)** - Polygon API usage
- **[Snapshot API Details](docs/DATA_SOURCE_POLYGON_SNAPSHOT_INFO.md)** - Snapshot API behavior by session

### Project Management
- **[Lessons Learned](CLAUDE_LESSONS_LEARNED.md)** - Development insights and anti-patterns

---

*TradeScout focuses on real-time market screening and data management. Built for rapid analysis across different trading sessions with clean, maintainable code architecture.*