# TradeScout Development Guide

**Project:** Personal Market Research Assistant - TradeScout  
**Developer:** Charlie Collins  
**Start Date:** July 20, 2025  
**Repository:** https://github.com/charlieCollins/TradeScout (Private)

## Core Principles
- Feature branch development - no backwards compatibility needed
- Clarity over cleverness - simple solutions preferred
- Research → Plan → Test → Implement workflow

## Critical Workflow
1. **Research**: Explore codebase, understand patterns
2. **Plan**: Create detailed plan and verify with me  
3. **Test-Driven Development**: Write failing tests first
4. **Implement**: Code to pass tests with validation checkpoints

**Always say:** "Let me research the codebase and create a plan before implementing."

## Implementation Standards

### Design Patterns
- **Strategy**: Interchangeable algorithms (momentum detection)
- **Adapter**: External APIs (YFinance, Polygon)
- **Factory**: Provider creation
- **Repository**: Data access abstraction
- **Decorator**: Caching, rate limiting

### Coding Standards
- Delete old code when replacing
- Meaningful names: `userID` not `id`
- Early returns to reduce nesting
- No comments unless asked

### Example Data Management
Save API results to `data/examples/` to avoid repeated calls:
```python
def fetch_and_cache_example_data(symbol: str):
    save_path = f"data/examples/{symbol.lower()}_data_{date.today()}.json"
    if os.path.exists(save_path):
        return json.load(open(save_path))
    
    data = fetch_from_api(symbol)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    json.dump(data, open(save_path, 'w'), indent=2)
    return data
```

### API Caching Strategy
Use cache wrapper for rate-limited APIs:
```python
from data_collection.api_cache import cached_api_call, CachePolicy

def get_stock_quote(symbol: str):
    return cached_api_call(
        provider="polygon",
        endpoint="get_quote", 
        params={"symbol": symbol},
        api_function=lambda: polygon_client.get_last_quote(symbol),
        policy=CachePolicy.REAL_TIME
    )
```

Cache locations: `data/cache/polygon/`, `data/cache/yfinance/`, etc.

## Testing & Quality

### Code Complete Criteria
- ✓ All lint/type checks pass
- ✓ Adequate test coverage
- ✓ All tests pass
- ✓ Feature works end-to-end
- ✓ Old code deleted

### Testing Strategy
- Complex business logic → Tests first
- Simple CRUD → Tests after
- Skip tests for main() and CLI parsing

## Communication & Collaboration

### When to Ask for Review
- Architectural decisions affecting multiple components
- Major refactors (>3 files or >100 lines)
- Adding new dependencies
- Stuck >15 minutes
- Uncertain about solution approach

### Progress Updates Format
```
✓ Implemented authentication (tests passing)
✓ Added rate limiting  
✗ Token expiration issue - investigating
```

### Critical Thinking Partnership
- Analyze merits and limitations objectively
- Present alternatives when they exist
- Point out flaws constructively
- Avoid "You're right" - lead with analysis

## Problem Solving

### When Stuck
1. **Stop** - Don't spiral into complex solutions
2. **Delegate** - Use agents for parallel investigation
3. **Ultrathink** - For complex problems
4. **Step back** - Re-read requirements
5. **Simplify** - Simple solution usually correct
6. **Ask** - Present options with trade-offs

### Multiple Agents Strategy
- Spawn agents for parallel codebase exploration
- One agent for tests, another for implementation
- Delegate research tasks to agents
- Use for complex refactoring

## Project Architecture

### Data Pipeline
```python
# Multi-provider system with smart fallback → Analysis → Suggestions → CLI
# - Polygon.io: Premium data (5 calls/min free)
# - YFinance: Real-time prices, backup (unlimited)
# - Finnhub: High-quality data (60 calls/min free)
# - Alpha Vantage: Market movers, fundamentals (25 calls/day - very limited!)
# - NewsAPI: 1000 articles/day
# - Web scrapers: Extended hours data (MarketWatch, CNN, etc.)
```

### Development vs Production Separation
- **Production** (`src/tradescout/`): Clean code, standard cache
- **Exploration** (`data/examples/`): Simple file saving for API results
- **Principle**: Production code pristine, exploration uses file caching

### Technology Stack
- **Backend**: Python CLI with Rich interface
- **Database**: SQLite (implemented)
- **APIs**: Multi-provider system (Polygon, YFinance, Finnhub, Alpha Vantage, NewsAPI)
- **Web Scrapers**: Extended hours data collection
- **Platform**: Linux/Ubuntu/WSL2
- **Budget**: $0-50/month (mostly free tier usage)

## Project Status
- [x] Technical plan completed
- [x] Data sources identified and implemented
- [x] Architecture designed and implemented
- [x] Development environment setup
- [x] Multi-provider data system operational
- [x] Gap trading system operational
- [x] Academic research-based trading rules
- [x] Rich CLI interface
- [x] Comprehensive testing suite
- [x] Smart coordinator with fallback strategies

## Next Steps
1. News sentiment integration for gap catalyst validation
2. Performance tracking system
3. Advanced technical indicators
4. Portfolio optimization features
5. Web interface development

## Key Reminders
- Always use TodoWrite for task management
- **Sync TODOs to CLAUDE_TODO.md every hour** - For session continuity
- Run lint/typecheck before declaring done
- Never commit unless explicitly asked
- Cache API calls to avoid rate limits
- Save example data to avoid repeated API calls