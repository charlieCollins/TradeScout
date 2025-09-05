# TradeScout

Personal Market Research Assistant for momentum trading opportunities. Built with modern Python best practices and clean architecture principles.

**Repository:** https://github.com/charlieCollins/TradeScout (Private)

## 🚀 Quick Start

### Prerequisites
- Python 3.9+ (tested on 3.9-3.12)
- Git

### Development Setup

1. **Clone and enter directory**
   ```bash
   git clone https://github.com/charlieCollins/TradeScout.git
   cd TradeScout
   ```

2. **Create virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install in development mode**
   ```bash
   # Install package with all development dependencies
   pip install -e ".[dev]"
   
   # Or install just runtime dependencies
   pip install -e .
   ```

4. **Set up pre-commit hooks (recommended)**
   ```bash
   pre-commit install
   ```

### First Run

```bash
# Test the installation
python -c "import tradescout; print('✅ TradeScout installed!')"

# Set up API keys (optional - works with free providers)
cp .env.template .env
# Edit .env file with your API keys

# Test the CLI using the convenient wrapper script
./tradescout system status
./tradescout market quote AAPL

# Or use the full Python module path
python -m src.tradescout.scripts.cli system status
python -m src.tradescout.scripts.cli market quote AAPL

# Run the exploration demos
cd data/examples
python demo_simple_exploration.py
python demo_nvidia_asset.py

# Run tests
cd ../..
pytest
```

### 🎯 **CLI Examples**

```bash
# System status with provider information
./tradescout system status

# Gap Trading - Academic Research-Based Suggestions ✅ OPERATIONAL
./tradescout market suggest --limit 5 --min-gap 2.0   # Daily gap trading opportunities
./tradescout market suggest --limit 10 --min-gap 3.0  # High-conviction gaps only
./tradescout market suggest --force                    # Force fresh market scan

# Individual asset analysis
./tradescout market quote AAPL MSFT TSLA              # Current quotes
./tradescout market fundamentals AAPL                  # Company fundamentals

# Market-wide analysis
./tradescout market gainers --limit 10                # Top market gainers
./tradescout market losers --limit 10                 # Top market losers  
./tradescout market movers --limit 5                  # Complete market report

# System information
./tradescout system status                             # System status and provider info
./tradescout system universe --show-symbols           # Show screening universe

# Advanced options
./tradescout --verbose market quote AAPL              # Show provider routing
./tradescout market gainers --force                   # Bypass cache (fresh data)
./tradescout --help                             # Get help
```

## 🧪 Testing & Quality

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test categories
pytest -m unit          # Unit tests only
pytest -m integration   # Integration tests only

# Run specific test file
pytest tests/test_data_models.py

# Run with coverage report
pytest --cov=tradescout --cov-report=html
# View coverage report: open htmlcov/index.html
```

### Code Quality Tools

```bash
# Format code (automatically fixes)
black .

# Sort imports (automatically fixes) 
isort .

# Type checking
mypy src

# Linting
flake8 src tests examples

# Run all quality checks
pre-commit run --all-files

# Test across multiple Python versions
tox
```

### Development Workflow

```bash
# Before committing (pre-commit hooks do this automatically):
black .
isort .
mypy src
pytest
```

## 🏗️ Architecture

TradeScout uses modern Python package structure with clean architecture:

```
TradeScout/
├── src/tradescout/           # Main package (production code)
│   ├── data_models/          # Domain models & interfaces  
│   ├── data_sources/         # External API adapters
│   ├── caches/              # Production caching infrastructure
│   ├── analysis/            # Trading analysis
│   └── storage/             # Database layer
├── tests/                   # Test suite
├── data/examples/           # Exploration demos & saved API data
├── docs/                    # Documentation
├── pyproject.toml          # Modern packaging config
├── tox.ini                 # Multi-env testing
└── .pre-commit-config.yaml # Git hooks
```

### Key Design Principles

- **Interface-First Design**: All external APIs implement our interfaces
- **Domain-Driven Design**: Rich domain models with business logic
- **Separation of Concerns**: Clear boundaries between layers
- **Clean Production Code**: Zero development tooling references in src/
- **Simple Exploration**: File-based API result saving for command-line work
- **Modern Tooling**: Professional Python development practices

## 📊 Features

### 📈 **Gap Trading System - OPERATIONAL** ✅
- **Academic Research Foundation**: Based on 90-year empirical study (Plastun et al., 2019)
- **6-Step Binary Classification**: Systematic gap candidate evaluation (size, volume, market cap, spread, exhaustion, timing)
- **Professional Risk Management**: 2% max account risk per trade, mandatory intraday-only execution
- **Pre-Market Timing**: Optimized for 4:00-9:30 AM ET gap detection, 9:30-10:30 AM entry window
- **Intelligent Gap Analysis**: 4 gap types (Common, Breakaway, Continuation, Exhaustion) with confidence scoring
- **Rich CLI Interface**: Detailed analysis tables with entry/exit/stop levels, risk/reward ratios
- **Multiple Data Sources**: Smart coordinator with API providers and intelligent routing

### 🎯 **Smart Data Management**
- **Configuration-Driven Architecture**: YAML configuration controls data types and caching policies
- **Intelligent Caching**: TTL-based caching with automatic cleanup and size management
- **Circuit Breaker Protection**: Automatic failure detection with exponential backoff
- **Commercial-Grade Reliability**: Single high-quality provider eliminates multi-provider complexity

### 📈 **Market Analysis & CLI**
- **Real-Time Quotes**: Professional-grade real-time pricing via Polygon.io
- **Company Fundamentals**: Comprehensive company data with financial statements
- **Market-Wide Analysis**: Top gainers, losers, and most active stocks
- **Extended Hours Coverage**: Pre-market and after-hours trading data
- **Volume Analysis**: Unusual volume detection and institutional flow tracking
- **Historical Data**: Multi-timeframe historical OHLCV data
- **Rich CLI Interface**: Beautiful terminal interface with status displays

### ⚡ **Performance & Reliability**
- **Smart Caching**: Different cache TTL for different data types (10m quotes, 7d fundamentals)
- **Rate Limit Management**: Commercial-grade API with 300+ calls/minute capacity
- **Circuit Breaker**: Automatic failure detection with exponential backoff retry
- **Error Recovery**: Comprehensive error handling with fallback to cached data

### 🔌 **Architecture & Extensibility**
- **Interface-First Design**: Clean abstractions prevent vendor lock-in
- **Provider Ecosystem**: Easy to add new data providers
- **Separation of Concerns**: Trading data vs sentiment data vs news data routing
- **Modern Python**: Type hints, dataclasses, enums, and clean architecture

### 🖥️ **Command Line Interface**
- **Convenient Wrapper**: `./tradescout` script handles all environment setup
- **Rich Terminal Output**: Beautiful tables and colored status displays
- **Smart Provider Routing**: Automatic failover visible in verbose mode
- **Database Integration**: Save quotes, view history, manage data

## 💾 Data Sources

### 📊 **Primary Market Data Provider**
- **Polygon.io**: Commercial-grade real-time data (300+ calls/min) - Priority 1, Quality 10
  - Comprehensive market coverage (stocks, options, forex, crypto)
  - Extended hours trading data (4AM-8PM EST)
  - News, fundamentals, and technical indicators
  - Professional-grade API with tick-level data streams

### 🌐 **Extended Hours Data**
- **Polygon.io**: Pre-market (4:00 AM - 9:30 AM EST) and after-hours (4:00 PM - 8:00 PM EST)
- Full market depth with sale conditions tracking
- Real-time extended hours quotes and volume data

### 📰 **News & Sentiment**
- **Polygon.io News**: Integrated company and market news
- Social sentiment analysis capabilities
- Analyst ratings and price target data

### 🎛️ **Single-Provider Architecture**
All data types route through Polygon.io with intelligent caching:
- **Current Quotes**: Real-time pricing with 1-minute cache TTL
- **Company Fundamentals**: Weekly cache refresh (7-day TTL)
- **Extended Hours**: 5-minute cache TTL for pre/after-hours data
- **Market Movers**: 15-minute cache TTL for gainers/losers
- **Historical Data**: 24-hour cache TTL for historical price data

## 🔧 Development Tools & Standards

### Modern Python Toolchain

- **📦 pyproject.toml**: Modern packaging (replaces setup.py)
- **🧪 pytest**: Professional testing framework with fixtures
- **🎨 black**: Automatic code formatting
- **📚 isort**: Import sorting and organization  
- **🔍 mypy**: Static type checking
- **📏 flake8**: Code linting and style checks
- **🪝 pre-commit**: Git hooks for quality enforcement
- **🧪 tox**: Testing across Python versions (3.9-3.12)

### Testing Categories

- **Unit Tests** (`-m unit`): Fast, isolated component tests
- **Integration Tests** (`-m integration`): Multi-component interaction tests
- **API Tests** (`-m api`): Real external API tests (use sparingly)

### Configuration Files

- **pyproject.toml**: All tool configurations in one place
- **tox.ini**: Multi-environment testing setup
- **.pre-commit-config.yaml**: Git hook configurations
- **conftest.py**: Pytest fixtures and configuration

## 📚 Documentation

- **[Development Guide](docs/DEVELOPMENT.md)** - Detailed development setup and workflows
- **[Architecture Guide](docs/ARCHITECTURE.md)** - Technical architecture and design patterns
- **[Project Plan](docs/TRADE_SCOUT_PLAN.md)** - Complete project roadmap and strategy
- **[Lessons Learned](docs/LESSONS_LEARNED.md)** - Development insights and decisions

*API Documentation will be rewritten after architectural changes are complete*

## 🚦 Project Status

### Current Phase: Gap Trading System - OPERATIONAL ✅
- [x] **Complete Gap Trading Workflow**: Pre-market scanning → Binary classification → Trade suggestions
- [x] **Academic Research Integration**: 90-year empirical study implementation with statistical validation
- [x] **Professional Risk Management**: 2% max account risk, intraday-only trades, mandatory stop losses
- [x] **Smart Data Infrastructure**: Multiple API providers with intelligent routing
- [x] **Rich CLI Interface**: Full-featured `suggest` command with detailed analysis tables
- [x] **Binary Classification Engine**: 6-step academic rules (gap size, volume, market cap, spread, exhaustion, timing)
- [x] **Gap Type Analysis**: 4 gap types with confidence scoring and risk assessment
- [x] **Position Sizing Engine**: Automated risk-managed position calculations
- [x] **Pre-Market Timing**: Optimized for 4:00-9:30 AM ET scanning, 9:30-10:30 AM execution
- [x] **Comprehensive Testing**: All components validated with real market data

### Smart Data Platform Foundation ✅
- [x] Modern Python project structure with clean architecture
- [x] Domain models and interfaces
- [x] Smart Coordinator with configuration-driven routing
- [x] Commercial-grade Polygon.io API integration with Tiingo fallback
- [x] YAML-based data source configuration
- [x] Intelligent fallback strategies and circuit breaker protection
- [x] Rich CLI interface with status monitoring
- [x] Clean production code with intelligent caching
- [x] Simple file-based exploration utilities
- [x] Comprehensive test suite (26+ tests passing)
- [x] Professional development toolchain

### Next Phase: Advanced Analytics
- [ ] News sentiment analysis integration for gap catalyst validation
- [ ] Technical indicator calculation with provider routing
- [ ] Performance tracking system with trade outcome analytics
- [ ] Portfolio optimization and correlation analysis
- [ ] Web interface for monitoring and alerts

### Future Phases
- [ ] Web interface for monitoring
- [ ] Advanced pattern recognition
- [ ] Portfolio optimization
- [ ] Cloud deployment

## 🛠️ Troubleshooting

### Common Issues

**Import errors after installation:**
```bash
# Make sure you're in the virtual environment
source venv/bin/activate
pip install -e ".[dev]"
```

**Tests failing:**
```bash
# Update dependencies
pip install --upgrade -e ".[dev]"

# Clear pytest cache
pytest --cache-clear
```

**Pre-commit hooks failing:**
```bash
# Run quality fixes manually
black .
isort .
mypy src

# Then commit again
git commit -m "Your message"
```

## 💡 Gap Trading Quick Start

### Pre-Market Workflow (4:00-9:30 AM ET)

```bash
# 1. Scan for overnight gaps (run during pre-market hours)
./tradescout market suggest --limit 5 --min-gap 2.0

# 2. Review suggestions with detailed analysis
# - Gap size and direction
# - Volume confirmation (2x+ average required)
# - Entry/stop/target prices
# - Risk/reward ratios
# - Academic confidence levels

# 3. Execute during market open (9:30-10:30 AM ET)
# - Enter positions within first hour
# - Set stop losses immediately
# - Target 1:1 to 2:1 risk/reward
# - Mandatory exit by 4:00 PM ET
```

### Key Trading Rules
- **Timing**: Pre-market analysis, market open execution, same-day exit only
- **Risk**: Maximum 2% account risk per trade, professional position sizing
- **Quality**: Only trade gaps ≥2% with ≥2x volume confirmation
- **Academic**: Based on 90-year research study with statistical validation

### Weekend/After Hours Behavior
```bash
# Expected output when markets are closed or no gaps present
./tradescout market suggest
# ⚠️  No gap candidates found >= 2.0%
```

## 🤝 Contributing

This is a personal learning project, but the architecture demonstrates professional Python development practices:

1. **Fork & Clone**: Standard GitHub workflow
2. **Create Virtual Environment**: `python3 -m venv venv && source venv/bin/activate`
3. **Install Development Mode**: `pip install -e ".[dev]"`
4. **Run Tests**: `pytest` (all tests must pass)
5. **Quality Checks**: `pre-commit run --all-files` (must be clean)
6. **Submit PR**: With clear description and tests

## 📄 License

Personal project - Educational and learning purposes. Not for distribution.

---

**Built with ❤️ using modern Python best practices**