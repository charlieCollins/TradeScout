# Development Guide

Complete guide to setting up, developing, and maintaining TradeScout using modern Python best practices.

## 🏗️ Project Structure

TradeScout follows the modern `src/package/` layout with professional tooling:

```
TradeScout/
├── src/tradescout/                 # Main package
│   ├── __init__.py                 # Package exports
│   ├── data_models/                # Domain layer
│   │   ├── __init__.py
│   │   ├── domain_models_core.py   # Core entities (Asset, Market, etc.)
│   │   ├── domain_models_analysis.py  # Trading-specific models
│   │   ├── interfaces.py           # Abstract interfaces
│   │   └── factories.py            # Object creation patterns
│   ├── data_sources/               # Infrastructure layer
│   │   ├── __init__.py
│   │   ├── yfinance_adapter.py     # Yahoo Finance implementation
│   │   └── yfinance_scanner.py     # Legacy scanner (to be refactored)
│   ├── caches/                     # Caching layer
│   │   ├── __init__.py
│   │   └── api_cache.py            # Intelligent API caching
│   ├── analysis/                   # Application layer
│   │   ├── __init__.py
│   │   └── interfaces.py           # Analysis interfaces
│   ├── storage/                    # Persistence layer
│   │   ├── __init__.py
│   │   └── interfaces.py           # Repository interfaces
│   ├── config/                     # Configuration
│   │   ├── __init__.py
│   │   └── local_config.py         # Local settings
│   └── scripts/                    # CLI tools
│       └── __init__.py
├── tests/                          # Test suite
│   ├── __init__.py
│   ├── conftest.py                 # Pytest fixtures
│   ├── test_data_models.py         # Domain model tests
│   └── test_yfinance_adapter.py    # Adapter tests
├── data/examples/                  # Exploration demos & saved API data
│   ├── exploration_utils.py       # File-based exploration utilities
│   ├── demo_simple_exploration.py # Simple exploration demo
│   ├── demo_nvidia_asset.py       # Domain model demo
│   └── *.json                     # Saved API exploration data
├── docs/                          # Documentation
│   ├── ARCHITECTURE.md            # Technical architecture
│   ├── DEVELOPMENT.md             # This file
│   ├── LESSONS_LEARNED.md         # Development insights
│   └── TRADE_SCOUT_PLAN.md        # Project plan
├── data/                          # Data storage
│   ├── examples/                  # Exploration scripts & saved API data
│   └── cache/                     # Production cache files
├── logs/                          # Application logs
├── deployment/                    # Deployment configs
├── pyproject.toml                 # Modern packaging config
├── tox.ini                        # Multi-environment testing
├── .pre-commit-config.yaml        # Git hooks
├── .gitignore                     # Git ignore rules
├── README.md                      # Project overview
└── CLAUDE.md                      # Development guidelines
```

## 🛠️ Development Environment Setup

### Prerequisites

- **Python 3.9+** (tested on 3.9-3.12)
- **Git** for version control
- **Virtual environment** support

### Step-by-Step Setup

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd TradeScout
   ```

2. **Create and activate virtual environment**
   ```bash
   # Linux/macOS
   python3 -m venv venv
   source venv/bin/activate
   
   # Windows
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Install the package in development mode**
   ```bash
   # Full development setup (recommended)
   pip install -e ".[dev]"
   
   # Runtime only
   pip install -e .
   
   # Test dependencies only
   pip install -e ".[test]"
   ```

4. **Set up development tools**
   ```bash
   # Install pre-commit hooks
   pre-commit install
   
   # Verify installation
   python -c "import tradescout; print(f'✅ TradeScout v{tradescout.__version__}')"
   ```

5. **Run initial tests**
   ```bash
   pytest
   ```

## 🛠️ Command-Line Exploration

### Simple File-Based Exploration

For command-line exploration and development work, use the simple file-based utilities in `data/examples/exploration_utils.py`:

```bash
# Navigate to exploration directory
cd data/examples

# Run exploration demos
python demo_simple_exploration.py
python demo_nvidia_asset.py

# Use exploration utilities directly
python exploration_utils.py
```

### Exploration Workflow

**1. Create Exploration Script:**
```python
# data/examples/my_exploration.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from exploration_utils import get_or_fetch_api_data
from tradescout.data_sources.yfinance_adapter import create_yfinance_adapter

def fetch_my_data():
    adapter = create_yfinance_adapter()
    # ... your exploration code
    return {"symbol": "AAPL", "data": "..."}

# Save for reuse to avoid API quota usage
data = get_or_fetch_api_data(
    "my_exploration_data",
    fetch_my_data,
    "Description of what this data represents"
)
```

**2. Run and Iterate:**
```bash
cd data/examples
python my_exploration.py  # First run: fetches from API
python my_exploration.py  # Next runs: loads from file instantly
```

**3. Manage Saved Data:**
```python
from exploration_utils import list_saved_results, load_api_result

# See all saved exploration files
list_saved_results()

# Load specific saved data
previous_data = load_api_result("my_exploration_data")
```

### Key Benefits

- **No API Quota Waste**: Avoid repeated API calls during development
- **Fast Iteration**: Instant loading from saved JSON files
- **Human Readable**: Easy to inspect and debug saved data
- **Version Control**: Can commit useful exploration data
- **Clean Separation**: Production code stays pristine

### File Organization

```
data/examples/
├── exploration_utils.py          # Core utilities
├── demo_simple_exploration.py    # Demo script
├── my_exploration.py             # Your exploration work
├── nvidia_quote.json            # Saved API data
├── aapl_analysis.json           # Saved exploration data
└── custom_research.json         # Your saved research
```

## 🧪 Testing Framework

### Test Organization

- **Unit Tests** (`@pytest.mark.unit`): Fast, isolated component tests
- **Integration Tests** (`@pytest.mark.integration`): Multi-component interactions
- **API Tests** (`@pytest.mark.api`): Real external API calls (use sparingly)
- **Slow Tests** (`@pytest.mark.slow`): Long-running performance tests

### Running Tests

```bash
# All tests
pytest

# Verbose output
pytest -v

# Specific test categories
pytest -m unit                    # Unit tests only
pytest -m integration             # Integration tests only
pytest -m "not slow"              # Exclude slow tests

# Specific test files
pytest tests/test_data_models.py
pytest tests/test_yfinance_adapter.py::TestYFinanceAdapter::test_get_current_quote_success

# With coverage
pytest --cov=tradescout --cov-report=html
# View: open htmlcov/index.html

# Parallel execution (if you install pytest-xdist)
pytest -n auto

# Watch mode (if you install pytest-watch)
ptw
```

### Test Configuration

**conftest.py** provides shared fixtures:

- `sample_market`: Test market (NASDAQ)
- `sample_market_segment`: Test market segment (Technology)
- `sample_asset`: Test asset (AAPL)
- `mock_yfinance_ticker`: Mocked yfinance API
- `test_cache`: Clean cache instance
- `sample_quote_data`: Test market data

### Writing Tests

```python
import pytest
from decimal import Decimal
from datetime import datetime

from tradescout.data_models.domain_models_core import Asset, AssetType

@pytest.mark.unit
def test_asset_creation(sample_market):
    """Test basic asset creation"""
    asset = Asset(
        symbol="MSFT",
        name="Microsoft Corporation",
        asset_type=AssetType.COMMON_STOCK,
        market=sample_market,
        currency="USD"
    )
    
    assert asset.symbol == "MSFT"
    assert str(asset) == "MSFT (Microsoft Corporation)"

@pytest.mark.integration
def test_yfinance_adapter_with_cache(sample_asset, mock_cache):
    """Test adapter with caching"""
    from tradescout.data_sources.yfinance_adapter import YFinanceAdapter
    
    adapter = YFinanceAdapter(cache=mock_cache)
    # Test implementation...
```

## 🎯 Code Quality Standards

### Automated Quality Tools

All configured in `pyproject.toml`:

#### **Black** - Code Formatting
```bash
# Format all code
black .

# Check formatting without changes
black --check .

# Format specific files
black src/tradescout/data_models/
```

#### **isort** - Import Sorting
```bash
# Sort imports
isort .

# Check import sorting
isort --check-only .

# Show differences
isort --diff .
```

#### **mypy** - Type Checking
```bash
# Type check the source
mypy src

# Type check with verbose output
mypy src --verbose

# Type check specific module
mypy src/tradescout/data_models/
```

#### **flake8** - Linting
```bash
# Lint source code
flake8 src

# Lint tests
flake8 tests

# Lint with specific rules
flake8 src --select=E,W,F
```

#### **pre-commit** - Git Hooks
```bash
# Install hooks (one time)
pre-commit install

# Run hooks on all files
pre-commit run --all-files

# Run specific hook
pre-commit run black

# Skip hooks for emergency commit
git commit --no-verify -m "Emergency fix"
```

### Quality Configuration

**pyproject.toml** contains all tool configurations:

```toml
[tool.black]
line-length = 88
target-version = ['py39']

[tool.isort]
profile = "black"
multi_line_output = 3
line_length = 88

[tool.mypy]
python_version = "3.9"
warn_return_any = true
disallow_untyped_defs = true

[tool.pytest.ini_options]
minversion = "7.0"
testpaths = ["tests"]
markers = [
    "slow: marks tests as slow",
    "integration: marks tests as integration tests",
    "unit: marks tests as unit tests",
    "api: marks tests that make external API calls",
]
```

## 🚀 Development Workflow

### Daily Development

1. **Start development session**
   ```bash
   source venv/bin/activate
   git pull origin main
   git checkout -b feature/your-feature-name
   ```

2. **Make changes and test frequently**
   ```bash
   # Make your changes...
   
   # Run relevant tests
   pytest tests/test_your_module.py
   
   # Run quality checks
   black .
   mypy src
   ```

3. **Before committing (pre-commit does this automatically)**
   ```bash
   black .
   isort .
   mypy src
   pytest
   ```

4. **Commit and push**
   ```bash
   git add .
   git commit -m "Add: your feature description"
   git push origin feature/your-feature-name
   ```

### Pre-commit Hook Workflow

Pre-commit hooks run automatically on `git commit`:

```bash
git commit -m "Your message"
# Hooks run automatically:
# - trailing-whitespace: fixes trailing spaces
# - end-of-file-fixer: ensures newline at file end
# - black: formats Python code
# - isort: sorts imports
# - flake8: checks code quality
# - mypy: checks types

# If hooks fail, fix issues and commit again
git add .
git commit -m "Your message"  # Try again after fixes
```

### Multi-Environment Testing

**tox** tests across Python versions:

```bash
# Test all configured environments
tox

# Test specific Python version
tox -e py39
tox -e py312

# Test specific task
tox -e lint      # Just linting
tox -e type-check  # Just type checking
tox -e coverage    # With coverage report

# Clean tox environments
tox -e clean
```

## 🏗️ Architecture Patterns

### Domain-Driven Design

**Domain Models** (`src/tradescout/data_models/`):
- **Core entities**: Asset, Market, MarketSegment, PriceData
- **Value objects**: MarketQuote, ExtendedHoursData
- **Business logic**: Calculated properties and domain methods

```python
# Rich domain model example
@dataclass
class MarketQuote:
    asset: Asset
    price_data: PriceData
    previous_close: Optional[Decimal] = None
    
    # Business logic in the domain
    @property  
    def price_change_percent(self) -> Optional[Decimal]:
        if self.previous_close and self.previous_close > 0:
            return (self.price_data.price - self.previous_close) / self.previous_close * 100
        return None
```

### Interface-First Design

**Abstract Interfaces** define contracts:

```python
class MarketDataProvider(ABC):
    @abstractmethod
    def get_current_quote(self, asset: Asset) -> Optional[MarketQuote]:
        """Get current market quote for an asset"""
        pass
    
    @property
    @abstractmethod
    def rate_limit_per_minute(self) -> int:
        """Return the rate limit for this provider"""
        pass
```

**Concrete Implementations** adapt external APIs:

```python
class YFinanceAdapter(MarketDataProvider):
    def get_current_quote(self, asset: Asset) -> Optional[MarketQuote]:
        # Implementation using yfinance library
        # Returns our domain model, not yfinance objects
```

### Dependency Injection

**Factory Pattern** for object creation:

```python
class AssetFactory:
    def create_apple(self) -> Asset:
        return Asset(
            symbol="AAPL",
            name="Apple Inc.",
            asset_type=AssetType.COMMON_STOCK,
            market=self.nasdaq_market,
            currency="USD"
        )
```

### Caching Strategy

**Cache-First Pattern** for API calls:

```python
# Intelligent caching with TTL policies
def get_current_quote(self, asset: Asset) -> Optional[MarketQuote]:
    # Check cache first
    cached_data = self.cache.get(
        provider="yfinance",
        endpoint="get_quote", 
        params={"symbol": asset.symbol},
        policy=CachePolicy.REAL_TIME  # 2 minute TTL
    )
    
    if cached_data:
        return self._build_quote_from_cache(cached_data)
    
    # Cache miss - make API call
    fresh_data = self._fetch_from_api(asset)
    self.cache.set(...)
    return self._build_quote_from_fresh(fresh_data)
```

## 🔧 Advanced Development

### Adding New Data Sources

1. **Define interface** (if needed)
2. **Implement adapter**
3. **Add caching support**
4. **Write comprehensive tests**
5. **Update documentation**

Example structure:
```python
# src/tradescout/data_sources/polygon_adapter.py
class PolygonAdapter(MarketDataProvider):
    def __init__(self, api_key: str, cache: APICache = None):
        self.api_key = api_key
        self.cache = cache or APICache()
    
    def get_current_quote(self, asset: Asset) -> Optional[MarketQuote]:
        # Implementation...
```

### Adding New Domain Models

1. **Define in appropriate module**
2. **Add validation and business logic**
3. **Create factory methods**
4. **Write comprehensive tests**
5. **Update interfaces if needed**

### Performance Optimization

- **Caching**: API responses cached with intelligent TTL
- **Async operations**: Use `asyncio` for concurrent API calls
- **Database optimization**: Use appropriate indexes
- **Memory management**: Large datasets handled in chunks

### Monitoring and Logging

```python
import logging

logger = logging.getLogger(__name__)

# Use structured logging
logger.info("API call completed", extra={
    "provider": "yfinance",
    "symbol": asset.symbol,
    "response_time_ms": 234,
    "cache_hit": False
})
```

## 📊 Code Metrics and Coverage

### Coverage Reports

```bash
# Generate coverage report
pytest --cov=tradescout --cov-report=html --cov-report=term

# View detailed report
open htmlcov/index.html

# Coverage with missing line numbers
pytest --cov=tradescout --cov-report=term-missing
```

### Quality Metrics

- **Test Coverage**: Target 80%+ coverage
- **Type Coverage**: `mypy` should pass with no errors
- **Complexity**: Keep functions simple and focused
- **Documentation**: Docstrings for all public APIs

## 🐛 Debugging and Troubleshooting

### Common Development Issues

**Import errors:**
```bash
# Make sure you're in the virtual environment
which python  # Should show venv path

# Reinstall in development mode
pip install -e ".[dev]"
```

**Test failures:**
```bash
# Clear pytest cache
pytest --cache-clear

# Run specific test with verbose output
pytest -v -s tests/test_specific.py::test_method

# Debug test with breakpoint
pytest --pdb tests/test_failing.py
```

**Type checking errors:**
```bash
# Check specific file
mypy src/tradescout/data_models/domain_models_core.py

# Ignore specific error temporarily
# type: ignore[error-code]
```

### Debugging Tools

- **pytest --pdb**: Drop into debugger on test failure
- **logging**: Use appropriate log levels
- **IDE debugging**: IntelliJ IDEA, VSCode breakpoints
- **Memory profiling**: `memory_profiler` for memory issues
- **Performance profiling**: `cProfile` for performance bottlenecks

## 📚 Best Practices Summary

### Code Organization
- ✅ Keep domain models pure (no external dependencies)
- ✅ Use interfaces to prevent vendor lock-in
- ✅ Separate concerns clearly between layers
- ✅ Factory pattern for complex object creation

### Testing
- ✅ Write tests before implementation (TDD)
- ✅ Use descriptive test names
- ✅ Test behavior, not implementation
- ✅ Mock external dependencies

### Quality
- ✅ Run quality tools before committing
- ✅ Write type hints for all functions
- ✅ Keep functions small and focused
- ✅ Use meaningful variable names

### Performance
- ✅ Cache expensive operations
- ✅ Use appropriate data structures
- ✅ Profile before optimizing
- ✅ Handle errors gracefully

---

This development guide ensures consistent, high-quality development practices across the TradeScout project. Regular updates to this document help maintain current best practices as the project evolves.