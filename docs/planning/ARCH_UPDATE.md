# Architecture Modernization Planning: FastAPI + SQLModel

**Status:** 📋 Planning / Evaluation
**Date:** 2025-10-11
**Decision:** TBD

## Executive Summary

**Question:** Should we migrate from our hand-rolled managers/providers architecture to modern frameworks (FastAPI + SQLModel)?

**Preliminary Assessment:**
- **FastAPI:** ✅ **Strongly Recommended** - Significant value for web frontend
- **SQLModel:** ⚠️ **Conditional** - Benefits exist but migration cost is HIGH

**Key Finding:** Consider **HYBRID approach** - Adopt FastAPI for web layer while keeping proven custom managers.

---

## Current Architecture Analysis

### What We Built (Hand-Rolled)

**Codebase Size:**
- 79 Python files total
- 18 database managers
- 9 API providers
- Custom patterns throughout

**Core Components:**

#### 1. Database Layer - Custom Managers
```python
# src/database/managers/base_manager.py
class BaseManager(ABC):
    """TTL-based caching, get_or_fetch pattern"""
    - get_or_fetch(key, fetch_fn, force_refresh)
    - TTL validation via metadata tracking
    - Abstract interface for subclasses
```

**Features:**
- ✅ TTL-based refresh logic
- ✅ Operation-level metadata tracking
- ✅ get_or_fetch pattern for cache-or-API
- ✅ Separation: managers don't call APIs
- ✅ Raw SQLite with manual queries
- ✅ Dataclass model mapping

#### 2. API Layer - Custom Providers
```python
# src/api/providers/base_provider.py
class BaseAPIProvider(ABC):
    """HTTP client, rate limiting, authentication"""
    - _make_request(endpoint, params)
    - Rate limit handling (429 responses)
    - Error handling
    - Health checks
```

**Features:**
- ✅ Polygon API integration
- ✅ Rate limiting and retries
- ✅ Authentication abstraction
- ✅ Clean separation from storage

#### 3. Model Layer - Dataclasses
```python
# src/models/asset.py
@dataclass(frozen=True)
class Asset:
    """Immutable domain objects"""
    id: int
    symbol: str
    name: Optional[str]
    # ... 15+ fields
```

**Features:**
- ✅ Type hints throughout
- ✅ Immutability (frozen=True)
- ✅ Enums for classification
- ✅ Computed properties
- ❌ No ORM magic
- ❌ Manual SQL mapping

#### 4. Orchestration - DataService
```python
# src/services/data_service.py
class DataService:
    """Wires together managers + providers"""
    - Coordinates database managers
    - Coordinates API providers
    - Returns result objects
    - Progress reporting support
```

**Strengths:**
1. ✅ **Clean separation of concerns** - Zero coupling between layers
2. ✅ **Custom TTL logic** - Sophisticated caching for API quota management
3. ✅ **Testable** - Each layer independently testable
4. ✅ **No framework lock-in** - Pure Python
5. ✅ **Well-documented** - Clear responsibilities

**Weaknesses:**
1. ❌ **Manual SQL boilerplate** - Every query written by hand
2. ❌ **Manual row mapping** - Tuple → dataclass conversions everywhere
3. ❌ **No migrations** - Schema changes are manual
4. ❌ **No web framework** - Need to build REST API from scratch
5. ❌ **Reinvented wheels** - Request handling, validation, serialization

---

## FastAPI Evaluation

### What is FastAPI?

Modern Python web framework for building APIs:
- Auto-generated OpenAPI/Swagger docs
- Automatic request/response validation (Pydantic)
- Async support (ASGI)
- Dependency injection
- WebSocket support
- Built-in security features

### FastAPI for TradeScout: STRONGLY RECOMMENDED ✅

**Why FastAPI is PERFECT for this project:**

#### 1. Web Frontend - Your Stated Goal
```python
# With FastAPI - Clean, validated, documented
from fastapi import FastAPI, Query
from output.json_adapter import JSONOutputAdapter

app = FastAPI(title="TradeScout API")

@app.post("/api/gap/analyze")
async def analyze_gaps(
    min_gap: float = Query(2.0, ge=0.0, le=100.0, description="Min gap %"),
    min_volume_ratio: float = Query(1.5, ge=1.0, description="Min volume ratio")
) -> GapAnalysisResponse:
    """Analyze gap trading candidates.

    Auto-generated docs show:
    - Request parameters with validation
    - Response schema
    - Try-it-out interface
    """
    analyzer = get_gap_analyzer()
    candidates = analyzer.find_gap_candidates(
        universe_symbols=get_universe(),
        market_context=get_market_context(),
        min_gap_pct=min_gap
    )
    return json_adapter.serialize_gap_candidates(candidates)
```

**You Get:**
- ✅ Auto-generated API docs at `/docs`
- ✅ Request validation (min_gap must be 0-100)
- ✅ Type checking at runtime
- ✅ JSON serialization handled automatically
- ✅ WebSocket support for progress updates
- ✅ CORS middleware for web frontend
- ✅ Production-ready ASGI server (uvicorn)

#### 2. Compatibility with Current Architecture - EXCELLENT

**FastAPI doesn't force you to change your database layer:**

```python
# Keep your managers, just wrap with FastAPI endpoints
from fastapi import FastAPI, Depends
from services.data_service import DataService

app = FastAPI()

def get_data_service() -> DataService:
    """Dependency injection - reuse your existing service"""
    return DataService(db_manager, polygon_api_key)

@app.get("/api/screener/{name}")
def run_screener(
    name: str,
    data_service: DataService = Depends(get_data_service)
):
    """Your existing screener engine, FastAPI endpoint"""
    engine = ScreenerEngine(data_service)
    results = engine.execute_screener(name)
    return {"results": results}  # Auto-serialized to JSON
```

**Key Insight:** FastAPI is a **web layer**, not a replacement for your data layer.

#### 3. Progressive Adoption Path

**Phase 1: Add FastAPI wrapper (2-4 hours)**
```python
# src/api/web_app.py
from fastapi import FastAPI
from cli import gap_commands  # Reuse CLI logic!

app = FastAPI()

@app.post("/api/gap/analyze")
def analyze_gaps(...):
    # Call same logic as CLI analyze command
    # Return JSON instead of Rich tables
```

**Phase 2: Migrate endpoints one by one**
- Start with screener (already returns dicts)
- Then gap analysis (extract display logic - DONE ✅)
- Then market operations
- No big-bang migration needed

**Phase 3: Add advanced features**
- WebSocket progress updates
- Background tasks (market updates)
- Rate limiting per user
- Authentication/authorization

### FastAPI: Benefits Summary

| Feature | Current | With FastAPI | Effort |
|---------|---------|--------------|--------|
| Web API | ❌ None | ✅ Full REST API | 2-4 hours initial |
| API Docs | ❌ Manual | ✅ Auto-generated | Free |
| Validation | ❌ Manual | ✅ Automatic | Free |
| WebSockets | ❌ None | ✅ Built-in | 1-2 hours |
| Production Server | ❌ Flask dev | ✅ Uvicorn ASGI | Free |
| Type Safety | ⚠️ Static only | ✅ Runtime validation | Free |

**Recommendation:** ✅ **ADOPT FASTAPI** - No downside, huge upside

---

## SQLModel Evaluation

### What is SQLModel?

ORM that combines SQLAlchemy (database) + Pydantic (validation):
- Single class definition for database + API
- Automatic migrations with Alembic
- Query builder instead of raw SQL
- Type-safe queries
- Relationship management

### SQLModel for TradeScout: CONDITIONAL ⚠️

**The Case FOR SQLModel:**

#### 1. Reduced Boilerplate
```python
# Current - Manual SQL + Mapping (50+ lines)
def get_entity_from_database(self, key: str) -> Optional[Asset]:
    cursor.execute("""
        SELECT id, symbol, name, market_id, asset_type,
               asset_class, currency, lot_size, tick_size,
               is_active, is_delisted, listing_date, delisting_date,
               provider_id, created_at, updated_at
        FROM assets
        WHERE symbol = ? AND is_active = 1
    """, (symbol,))
    row = cursor.fetchone()

    # Manual mapping
    return Asset(
        id=row[0],
        symbol=row[1],
        name=row[2],
        # ... 15 more fields
    )

# With SQLModel - Auto-mapping (5 lines)
from sqlmodel import Session, select

def get_asset(symbol: str) -> Optional[Asset]:
    with Session(engine) as session:
        statement = select(Asset).where(Asset.symbol == symbol, Asset.is_active == True)
        return session.exec(statement).first()
```

#### 2. Type-Safe Queries
```python
# Current - Typos found at runtime
cursor.execute("SELECT * FROM assets WHERE symbl = ?", (symbol,))  # Typo!

# SQLModel - Typos found by IDE/mypy
statement = select(Asset).where(Asset.symbl == symbol)  # IDE error immediately
```

#### 3. Automatic Migrations
```python
# Current - Manual schema changes
# 1. Write migration SQL manually
# 2. Version it yourself
# 3. Track what's applied

# SQLModel + Alembic - Auto-generated
alembic revision --autogenerate -m "Add sector to assets"
# Generates migration by comparing models to database
```

#### 4. Relationships
```python
# Current - Manual joins
cursor.execute("""
    SELECT a.*, f.market_cap, f.sector
    FROM assets a
    LEFT JOIN fundamentals f ON a.id = f.asset_id
    WHERE a.symbol = ?
""")

# SQLModel - Automatic
class Asset(SQLModel, table=True):
    fundamentals: Optional[Fundamentals] = Relationship()

asset = session.get(Asset, symbol)
print(asset.fundamentals.market_cap)  # Auto-loaded
```

**The Case AGAINST SQLModel:**

#### 1. HIGH Migration Cost

**What needs to change:**

1. **Model Definitions** (10+ files)
```python
# Before - Simple dataclass
@dataclass(frozen=True)
class Asset:
    id: int
    symbol: str
    # ...

# After - SQLModel
class Asset(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    symbol: str = Field(index=True)
    # ... all fields need Field() annotations
```

2. **All Managers** (18 files) - Complete rewrite
```python
# Before - Custom BaseManager with TTL logic
class AssetManager(BaseManager):
    def get_or_fetch(self, key, fetch_fn):
        if self._is_data_stale():
            # Custom TTL logic

# After - ???
# How do we preserve TTL logic with SQLModel?
# How do we keep the get_or_fetch pattern?
# SQLModel doesn't have TTL caching built-in
```

3. **Loss of Custom Features**
- ❌ Your TTL-based refresh logic
- ❌ Your metadata tracking system
- ❌ Your get_or_fetch pattern
- ❌ Operation-level cache invalidation

**Critical Question:** How do we preserve sophisticated caching with ORM?

#### 2. ORM Overhead

**Performance:**
- SQLModel adds abstraction layer
- Query performance slightly slower
- Eager/lazy loading complexity
- N+1 query problems

**For TradeScout:**
- You're reading snapshots for 2000+ symbols
- Bulk operations are common
- Raw SQL is often faster for bulk reads

#### 3. Learning Curve

**Team needs to learn:**
- SQLAlchemy query API
- Relationship management
- Lazy vs eager loading
- Migration workflow
- Session management
- Connection pooling

**Estimated learning time:** 20-40 hours

#### 4. Framework Lock-In

**Current:** Pure Python, no ORM
- Easy to switch databases (SQLite → PostgreSQL)
- Easy to switch ORMs later
- Clear SQL, no magic

**With SQLModel:** Committed to SQLModel/SQLAlchemy
- Harder to migrate away
- Framework-specific patterns
- More abstraction layers

### SQLModel: Cost-Benefit Analysis

| Aspect | Current | With SQLModel | Migration Effort |
|--------|---------|---------------|------------------|
| Boilerplate | 50 lines/model | 10 lines/model | 40 hours |
| Type Safety | Static only | Runtime + Static | Free after migration |
| Migrations | Manual | Automatic | 8 hours initial |
| Relationships | Manual joins | Automatic | Free after migration |
| TTL Logic | ✅ Built-in | ❌ Must recreate | 16 hours |
| Bulk Operations | ✅ Fast | ⚠️ Slower | N/A |
| Team Learning | ✅ None | ⚠️ 20-40 hours | N/A |
| **Total Effort** | - | - | **84+ hours** |

**Recommendation:** ⚠️ **DEFER SQLModel** - Cost doesn't justify benefits right now

---

## Hybrid Approach: RECOMMENDED ✅

### Strategy: FastAPI (Web) + Keep Custom Managers (Data)

**Philosophy:** Use frameworks where they add clear value, keep custom code where it works well.

```
┌─────────────────────────────────────────────────────────────┐
│ WEB LAYER - FastAPI (NEW)                                   │
│  ✅ REST API endpoints                                       │
│  ✅ Auto-generated docs                                      │
│  ✅ Request validation                                       │
│  ✅ WebSocket support                                        │
└─────────────────────────────────────────────────────────────┘
                           ↓ calls
┌─────────────────────────────────────────────────────────────┐
│ OUTPUT LAYER - Adapters (CURRENT - Keep)                    │
│  ✅ JSONOutputAdapter (NEW) for FastAPI                     │
│  ✅ CLIOutputAdapter (EXISTING) for Rich                    │
│  ✅ GapAnalysisDisplay (EXISTING) for CLI                   │
└─────────────────────────────────────────────────────────────┘
                           ↓ uses
┌─────────────────────────────────────────────────────────────┐
│ BUSINESS LAYER - Services/Analyzers (CURRENT - Keep)        │
│  ✅ DataService orchestration                               │
│  ✅ GapAnalyzer business logic                              │
│  ✅ ScreenerEngine query execution                          │
└─────────────────────────────────────────────────────────────┘
                           ↓ uses
┌─────────────────────────────────────────────────────────────┐
│ DATA LAYER - Custom Managers (CURRENT - Keep)               │
│  ✅ TTL-based caching                                        │
│  ✅ get_or_fetch pattern                                     │
│  ✅ Metadata tracking                                        │
│  ✅ Raw SQL (fast for bulk operations)                      │
└─────────────────────────────────────────────────────────────┘
                           ↓ queries
┌─────────────────────────────────────────────────────────────┐
│ DATABASE - SQLite (CURRENT - Keep)                          │
└─────────────────────────────────────────────────────────────┘
```

### Benefits of Hybrid Approach

| Benefit | Description |
|---------|-------------|
| **Low Risk** | Keep proven data layer, add web layer on top |
| **Fast Implementation** | 8-12 hours to working API |
| **Best of Both** | FastAPI benefits + Custom caching |
| **Incremental** | Can revisit SQLModel later if needed |
| **Proven Architecture** | Your managers work well, why replace? |

### Why Keep Custom Managers?

**Your managers are GOOD:**

1. **Sophisticated TTL Logic**
   - Operation-level metadata tracking
   - Configurable TTL per data type
   - Force refresh support
   - This is valuable, not boilerplate

2. **API Quota Management**
   - TTL prevents unnecessary API calls
   - Metadata prevents duplicate fetches
   - Critical for Polygon premium subscription

3. **Clean Separation**
   - Managers don't call APIs ✅
   - Providers don't access database ✅
   - Clear responsibilities ✅

4. **Battle-Tested**
   - Already working in production
   - Handles edge cases
   - No surprises

5. **Performance**
   - Raw SQL is fast
   - Bulk operations optimized
   - No ORM overhead

**SQLModel Doesn't Offer Enough to Justify 84+ Hour Migration**

---

## Migration Path: FastAPI Only

### Phase 1: Add FastAPI Web Layer (8-12 hours)

#### Step 1: Install FastAPI (30 min)
```bash
pip install fastapi uvicorn
```

#### Step 2: Create Basic App (1 hour)
```python
# src/api/web_app.py
from fastapi import FastAPI, Depends
from services.data_service import DataService
from output.json_adapter import JSONOutputAdapter

app = FastAPI(
    title="TradeScout API",
    description="Market research and gap trading analysis",
    version="1.0.0"
)

# Dependency injection
def get_data_service() -> DataService:
    """Reuse existing DataService"""
    db_manager = get_db_manager()
    return DataService(db_manager, POLYGON_API_KEY)

def get_json_adapter() -> JSONOutputAdapter:
    return JSONOutputAdapter()
```

#### Step 3: Add Startup Validation (1 hour)
```python
@app.on_event("startup")
async def startup_checks():
    """Fail fast if prerequisites not met"""
    db_manager = get_db_manager()

    checks = {
        "Database exists": lambda: Path(db_path).exists(),
        "Providers loaded": lambda: provider_manager.count() > 0,
        "Markets loaded": lambda: markets_manager.count() > 0,
        "Assets loaded": lambda: asset_manager.count() > 1000,
    }

    for name, check in checks.items():
        if not check():
            raise StartupError(f"{name} - Run: tradescout database bootstrap-*")

    logger.info("✅ TradeScout API ready")
```

#### Step 4: Create Response Models (2 hours)
```python
# src/api/models/responses.py
from pydantic import BaseModel
from typing import List

class GapCandidateResponse(BaseModel):
    """Pydantic model for API response"""
    symbol: str
    name: str
    gap_percentage: float
    gap_amount: float
    direction: str
    current_price: float
    market_cap: float
    volume_ratio: Optional[float]
    quality_score: Optional[int]
    risk_level: Optional[str]

class GapAnalysisResponse(BaseModel):
    candidates: List[GapCandidateResponse]
    total_candidates: int
    passed: int
    rejected: int
```

#### Step 5: Implement Endpoints (4-6 hours)
```python
# Screener endpoint (easiest - already returns dicts)
@app.get("/api/screener/{screener_name}")
async def run_screener(
    screener_name: str,
    data_service: DataService = Depends(get_data_service)
):
    """Run market screener"""
    engine = ScreenerEngine(data_service)
    results = engine.execute_screener(screener_name)
    return {"results": results, "count": len(results)}

# Gap analysis endpoint
@app.post("/api/gap/analyze")
async def analyze_gaps(
    min_gap: float = Query(2.0, ge=0.0, le=100.0),
    min_volume_ratio: float = Query(1.5, ge=1.0),
    data_service: DataService = Depends(get_data_service),
    json_adapter: JSONOutputAdapter = Depends(get_json_adapter)
) -> GapAnalysisResponse:
    """Analyze gap trading candidates"""
    analyzer = get_gap_analyzer(data_service)
    market_context = get_market_context(data_service)

    candidates = analyzer.find_gap_candidates(
        universe_symbols=get_universe_symbols(data_service),
        market_context=market_context,
        min_gap_pct=min_gap
    )

    return json_adapter.serialize_gap_candidates(candidates)

# Market context endpoint
@app.get("/api/market/context")
async def get_market_context(
    data_service: DataService = Depends(get_data_service)
):
    """Get current market context"""
    context = data_service.market_context_service.get_current_context()
    return {
        "session": context.session_name,
        "date": context.current_date.isoformat(),
        "market": context.market.name,
        "is_trading_day": context.is_trading_day,
    }
```

#### Step 6: Run Server (30 min)
```bash
# Development
uvicorn api.web_app:app --reload --port 8000

# Production
uvicorn api.web_app:app --host 0.0.0.0 --port 8000 --workers 4
```

#### Step 7: Test API (1 hour)
```bash
# Auto-generated docs
open http://localhost:8000/docs

# Test endpoints
curl http://localhost:8000/api/screener/gainers
curl -X POST http://localhost:8000/api/gap/analyze
```

### Phase 2: WebSocket Progress (Optional, 2-3 hours)

```python
# src/api/web_app.py
from fastapi import WebSocket

@app.websocket("/ws/progress/{task_id}")
async def websocket_progress(websocket: WebSocket, task_id: str):
    """Real-time progress updates"""
    await websocket.accept()

    # Create WebSocket progress reporter
    progress = WebSocketProgressReporter(websocket)

    # Run operation with progress updates
    if task_id == "gap_analyze":
        # Your existing gap analysis with progress callbacks
        await run_gap_analysis(progress=progress)
```

### Phase 3: Advanced Features (Later)

- Background tasks (market data updates)
- Rate limiting per API key
- Authentication/authorization
- CORS configuration
- Response caching
- OpenAPI schema customization

---

## Comparison: Options Summary

### Option A: FastAPI Only (RECOMMENDED ✅)

**What Changes:**
- Add FastAPI web layer (new files)
- Create JSONOutputAdapter (1 new file)
- Keep all managers, providers, services

**Effort:** 8-12 hours

**Benefits:**
- ✅ Web API with auto-generated docs
- ✅ Request validation
- ✅ Type safety
- ✅ WebSocket support
- ✅ Production-ready server
- ✅ Keep proven caching logic

**Risks:**
- Low - FastAPI is stable, widely used

**Recommendation:** ✅ **DO THIS** - Clear win

---

### Option B: FastAPI + SQLModel (NOT RECOMMENDED ⚠️)

**What Changes:**
- Add FastAPI web layer
- Rewrite 18 managers
- Rewrite 10+ models
- Recreate TTL logic
- Port all queries
- Learn SQLAlchemy patterns

**Effort:** 84+ hours (2+ weeks full-time)

**Benefits:**
- ✅ All FastAPI benefits
- ✅ Less SQL boilerplate
- ✅ Type-safe queries
- ✅ Auto migrations

**Risks:**
- ⚠️ High - Major rewrite
- ⚠️ Lose proven TTL logic
- ⚠️ ORM overhead
- ⚠️ Learning curve

**Recommendation:** ⚠️ **DEFER** - Cost > Benefit right now

---

### Option C: Status Quo (Baseline)

**What Changes:**
- Nothing

**Effort:** 0 hours

**Benefits:**
- ✅ Keep working system

**Drawbacks:**
- ❌ No web API
- ❌ Manual web framework setup
- ❌ Build REST endpoints from scratch

**Recommendation:** ⚠️ **Not viable** if you want web frontend

---

## Decision Matrix

| Criteria | Status Quo | FastAPI Only | FastAPI + SQLModel |
|----------|-----------|--------------|-------------------|
| **Web Frontend** | ❌ None | ✅ Complete | ✅ Complete |
| **API Docs** | ❌ None | ✅ Auto-gen | ✅ Auto-gen |
| **Implementation Time** | 0h | 8-12h | 84+h |
| **Risk Level** | None | Low | High |
| **Preserve TTL Logic** | ✅ Yes | ✅ Yes | ⚠️ Must recreate |
| **Learning Curve** | None | Minimal | Steep |
| **Bulk Query Performance** | ✅ Fast | ✅ Fast | ⚠️ Slower |
| **SQL Boilerplate** | ❌ High | ❌ High | ✅ Low |
| **Type Safety** | ⚠️ Static | ✅ Runtime | ✅ Runtime |
| **Framework Lock-In** | ✅ None | ⚠️ FastAPI | ⚠️ FastAPI + SQLModel |

**Winner:** FastAPI Only

---

## Recommendation: Adopt FastAPI, Defer SQLModel

### Immediate Action (Next Session)

✅ **Implement FastAPI web layer**

**Steps:**
1. Install FastAPI + uvicorn
2. Create `src/api/web_app.py`
3. Add startup validation
4. Create 3-5 endpoints (screener, gap, market context)
5. Test via `/docs`

**Timeline:** 8-12 hours
**Risk:** Low
**Value:** High - Unblocks web frontend

### Future Consideration (6+ months)

⏳ **Re-evaluate SQLModel**

**Revisit when:**
- SQL boilerplate becomes painful (>100 query methods)
- Team wants auto-migrations
- Need relationships everywhere
- Performance isn't critical

**Don't migrate if:**
- Current managers work well ✅ (they do)
- TTL logic is valuable ✅ (it is)
- Bulk operations are common ✅ (they are)
- Team is small ✅ (it is)

---

## Implementation Checklist

### Phase 1: FastAPI Setup (Session 1: 8-12 hours)

- [ ] Install dependencies (`pip install fastapi uvicorn pydantic`)
- [ ] Create `src/api/web_app.py` with FastAPI app
- [ ] Add startup validation (check prerequisites)
- [ ] Create `src/api/models/responses.py` (Pydantic models)
- [ ] Create `src/output/json_adapter.py` (serialization)
- [ ] Implement `/api/screener/{name}` endpoint
- [ ] Implement `/api/gap/analyze` endpoint
- [ ] Implement `/api/market/context` endpoint
- [ ] Test via Swagger docs at `/docs`
- [ ] Write integration tests

### Phase 2: WebSocket Progress (Session 2: 2-3 hours)

- [ ] Create `WebSocketProgressReporter` class
- [ ] Add WebSocket endpoint `/ws/progress/{task_id}`
- [ ] Test real-time progress for gap analysis
- [ ] Test real-time progress for market updates

### Phase 3: Production Readiness (Session 3: 4-6 hours)

- [ ] Add CORS middleware
- [ ] Add error handlers
- [ ] Add request logging
- [ ] Configure uvicorn for production
- [ ] Add rate limiting (optional)
- [ ] Add authentication (optional)
- [ ] Deploy to server
- [ ] Update docs/ARCHITECTURE.md

---

## Sample Code: Complete FastAPI App

### Minimal Working Example

```python
# src/api/web_app.py
from fastapi import FastAPI, Depends, HTTPException, Query
from services.data_service import DataService
from output.json_adapter import JSONOutputAdapter
from analysis.gap_analyzer import GapAnalyzer
from api.providers.polygon_aggregates_provider import PolygonAggregatesProvider
from api.config.api_keys import POLYGON_API_KEY
from database.database_manager import DatabaseManager
from pathlib import Path

# Initialize FastAPI
app = FastAPI(
    title="TradeScout API",
    description="Market research and gap trading analysis API",
    version="1.0.0",
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc"  # ReDoc
)

# Dependencies
def get_db_manager() -> DatabaseManager:
    """Get database manager instance"""
    db_path = Path("data/tradescout.db")
    if not db_path.exists():
        raise HTTPException(500, "Database not initialized. Run: tradescout database init")
    return DatabaseManager(str(db_path))

def get_data_service(db_manager: DatabaseManager = Depends(get_db_manager)) -> DataService:
    """Get data service instance"""
    return DataService(db_manager, POLYGON_API_KEY)

def get_json_adapter() -> JSONOutputAdapter:
    """Get JSON output adapter"""
    return JSONOutputAdapter()

# Startup validation
@app.on_event("startup")
async def startup_checks():
    """Validate prerequisites on startup"""
    from database.managers import ProviderManager, MarketsManager, AssetManager

    db_manager = get_db_manager()

    provider_mgr = ProviderManager(db_manager, None)
    markets_mgr = MarketsManager(db_manager, None)
    asset_mgr = AssetManager(db_manager, None)

    if provider_mgr.count() == 0:
        raise Exception("Run: tradescout database bootstrap-providers")
    if markets_mgr.count() == 0:
        raise Exception("Run: tradescout database bootstrap-markets")
    if asset_mgr.count() == 0:
        raise Exception("Run: tradescout database bootstrap-tickers")

    print("✅ TradeScout API ready at http://localhost:8000")
    print("📚 Docs available at http://localhost:8000/docs")

# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "tradescout"}

# Screener endpoint
@app.get("/api/screener/{screener_name}")
async def run_screener(
    screener_name: str,
    data_service: DataService = Depends(get_data_service)
):
    """Run a market screener

    Available screeners:
    - gainers: Top gaining stocks
    - losers: Top losing stocks
    - volume: Unusual volume stocks
    - momentum: Momentum candidates
    """
    from screener.screener_engine import ScreenerEngine

    engine = ScreenerEngine(data_service)
    results = engine.execute_screener(screener_name)

    return {
        "screener": screener_name,
        "results": results,
        "count": len(results)
    }

# Gap analysis endpoint
@app.post("/api/gap/analyze")
async def analyze_gaps(
    min_gap: float = Query(2.0, ge=0.0, le=100.0, description="Minimum gap percentage"),
    min_market_cap: int = Query(1_000_000_000, description="Minimum market cap"),
    min_volume_ratio: float = Query(1.5, ge=1.0, description="Minimum volume ratio"),
    limit: int = Query(50, ge=1, le=200, description="Max candidates to analyze"),
    data_service: DataService = Depends(get_data_service),
    json_adapter: JSONOutputAdapter = Depends(get_json_adapter)
):
    """Analyze gap trading candidates

    Returns candidates that meet gap, market cap, and volume criteria.
    Only runs during premarket (4-9:30 AM) or after-hours (4-8 PM).
    """
    # Get market context
    market_context = data_service.market_context_service.get_current_context()

    # Get universe symbols
    universe_mgr = data_service.universe_manager
    active_universe = universe_mgr.get_entity_from_database("default_universe")
    if not active_universe:
        raise HTTPException(500, "No active universe found")

    # Create gap analyzer
    aggregates_provider = PolygonAggregatesProvider(POLYGON_API_KEY)
    analyzer = GapAnalyzer(data_service, aggregates_provider)

    # Find candidates
    candidates = analyzer.find_gap_candidates(
        universe_symbols=active_universe.symbols[:limit],
        market_context=market_context,
        min_gap_pct=min_gap
    )

    # Serialize to JSON
    return json_adapter.serialize_gap_candidates(candidates)

# Market context endpoint
@app.get("/api/market/context")
async def get_market_context(
    data_service: DataService = Depends(get_data_service)
):
    """Get current market context and session info"""
    context = data_service.market_context_service.get_current_context()

    return {
        "date": context.current_date.isoformat(),
        "session": context.session_name,
        "market": context.market.name,
        "is_trading_day": context.is_trading_day,
        "day_type": context.day_type.value,
        "next_trading_day": context.next_trading_day.isoformat() if context.next_trading_day else None
    }

# List screeners endpoint
@app.get("/api/screeners")
async def list_screeners():
    """List available screeners"""
    from pathlib import Path

    screener_dir = Path("configs/screeners")
    screeners = [f.stem for f in screener_dir.glob("*.yaml")]

    return {"screeners": screeners}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Run the Server

```bash
# Development (auto-reload on code changes)
uvicorn api.web_app:app --reload --port 8000

# Production (multiple workers)
uvicorn api.web_app:app --host 0.0.0.0 --port 8000 --workers 4
```

### Test the API

```bash
# Via browser
open http://localhost:8000/docs

# Via curl
curl http://localhost:8000/health
curl http://localhost:8000/api/screeners
curl http://localhost:8000/api/screener/gainers
curl http://localhost:8000/api/market/context
curl -X POST "http://localhost:8000/api/gap/analyze?min_gap=2.0&min_volume_ratio=1.5"
```

---

## Conclusion

### Final Recommendation

✅ **Adopt FastAPI, Keep Custom Managers**

**Why:**
1. FastAPI solves your immediate need (web frontend)
2. Low implementation cost (8-12 hours)
3. Preserves your proven caching architecture
4. Minimal risk
5. Can add SQLModel later if needed

**Don't:**
- Migrate to SQLModel now (84+ hours, marginal benefit)
- Build custom web framework (FastAPI is better)
- Feel pressure to "modernize" working code

**Your current architecture is GOOD.** The managers, TTL logic, and separation of concerns are well-designed. FastAPI is additive, not replacement.

### Next Steps

1. **This session:** Review this document, discuss concerns
2. **Next session:** Implement FastAPI web layer (8-12 hours)
3. **Following session:** Add WebSocket progress (2-3 hours)
4. **After that:** Build frontend with React/Vue consuming your new API

**Timeline to Web Frontend:** 2-3 sessions (~16-20 hours total)

---

**Status:** 📋 **PLANNING COMPLETE** - Ready for implementation decision
**Recommendation:** ✅ **FastAPI Only** - Defer SQLModel
**Next Action:** Get approval and start FastAPI implementation
