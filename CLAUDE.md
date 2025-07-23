# TradeScout Development Guide

**Project:** Personal Market Research Assistant - TradeScout  
**Developer:** Charlie Collins  
**Start Date:** July 20, 2025

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
# Polygon.io FREE + yfinance → Analysis → Suggestions → Email/Dashboard
# - Polygon.io: Fundamentals, historical (5 calls/min)
# - yfinance: Real-time prices, after-hours (unlimited)
# - NewsAPI: 1000 articles/day
# - Reddit API: Unlimited sentiment
```

### Development vs Production Separation
- **Production** (`src/tradescout/`): Clean code, standard cache
- **Exploration** (`data/examples/`): Simple file saving for API results
- **Principle**: Production code pristine, exploration uses file caching

### Technology Stack
- **Backend**: Python + Flask
- **Database**: SQLite (start simple)
- **APIs**: Polygon.io (free) + yfinance + NewsAPI + Reddit
- **Platform**: Linux/Ubuntu
- **Budget**: $0-50/month

## Project Status
- [x] Technical plan completed
- [x] Data sources identified
- [x] Architecture designed
- [ ] Development environment setup
- [ ] API keys acquired
- [ ] MVP scope defined

## Next Steps
1. Environment setup with API keys
2. Basic data pipeline implementation
3. Momentum detection algorithm
4. Suggestion generation system
5. Performance tracking

## Key Reminders
- Always use TodoWrite for task management
- **Sync TODOs to docs/TODO.md every hour** - For session continuity
- Run lint/typecheck before declaring done
- Never commit unless explicitly asked
- Cache API calls to avoid rate limits
- Save example data to avoid repeated API calls