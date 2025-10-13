"""FastAPI Web Application - Repository + DAO + Cache-Aside Architecture.

This is the Presentation Layer demonstrating the new architecture:
  FastAPI → DataServiceV2 → CacheService → Repository → DAO (SQLModel) → Database
                                  ↓
                            API Provider

Features:
- Auto-generated OpenAPI docs at /docs
- Request/response validation with Pydantic
- Dependency injection for clean architecture
- Cache-aside pattern demonstrated end-to-end
"""

import logging
import os
from typing import Optional
from typing import List
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlmodel import Session, SQLModel, create_engine
from services.data_service_v2 import DataServiceV2
from models.sqlmodel.asset_sqlmodel import AssetSQLModel
from models.sqlmodel.market_sqlmodel import MarketSQLModel
from models.sqlmodel.fundamentals_sqlmodel import FundamentalsSQLModel
from models.sqlmodel.provider_sqlmodel import ProviderSQLModel
from models.sqlmodel.universe_sqlmodel import UniverseSQLModel, UniverseMembershipSQLModel
from models.sqlmodel.asset_price_sqlmodel import AssetPriceSQLModel

logger = logging.getLogger(__name__)

# ============================================================================
# FastAPI App Setup
# ============================================================================

app = FastAPI(
    title="TradeScout API",
    description="""
    Market research and gap trading analysis API.

    **New Architecture (V2):**
    - Repository + DAO + Cache-Aside pattern
    - SQLModel for type-safe database operations
    - Automatic caching with TTL management
    - On-demand fetching from Polygon API

    **Documentation:**
    - Interactive docs: `/docs` (Swagger UI)
    - Alternative docs: `/redoc` (ReDoc)
    """,
    version="2.0.0-alpha",
    docs_url="/docs",
    redoc_url="/redoc"
)

# ============================================================================
# Database Setup
# ============================================================================

# Get database path from environment or use default
# Use absolute path from project root (one level up from src/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.getenv("TRADESCOUT_DB_PATH", os.path.join(PROJECT_ROOT, "../data/tradescout.db"))
DB_PATH = os.path.abspath(DB_PATH)  # Normalize the path
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Create SQLModel engine
# Note: SQLModel is compatible with existing SQLite schema
engine = create_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL query logging
    connect_args={"check_same_thread": False}  # Required for SQLite
)

# ============================================================================
# Dependency Injection
# ============================================================================

def get_session():
    """Dependency: Provide database session.

    This is the SQLModel session used by repositories.
    FastAPI will automatically close it after request.
    """
    with Session(engine) as session:
        yield session


def get_polygon_api_key() -> str:
    """Dependency: Get Polygon API key from environment.

    Raises:
        HTTPException: If API key not configured
    """
    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="POLYGON_API_KEY not configured in environment"
        )
    return api_key


def get_data_service(
    session: Session = Depends(get_session),
    polygon_api_key: str = Depends(get_polygon_api_key)
) -> DataServiceV2:
    """Dependency: Provide DataServiceV2 with all layers wired.

    This demonstrates dependency injection in action:
    - Session injected (database connection)
    - API key injected (from environment)
    - Returns fully configured DataServiceV2

    The service has:
    - Repository (business queries)
    - CacheService (cache-aside pattern)
    - APIProvider (Polygon API)
    """
    return DataServiceV2(session, polygon_api_key, db_path=DB_PATH)


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint - API information."""
    return {
        "name": "TradeScout API",
        "version": "2.0.0-alpha",
        "architecture": "Repository + DAO + Cache-Aside",
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc"
        },
        "endpoints": {
            "assets": "/api/assets/{symbol}",
            "markets": "/api/markets",
            "market_by_code": "/api/markets/{code}",
            "fundamentals": "/api/fundamentals/{asset_id}",
            "providers": "/api/providers",
            "provider_by_name": "/api/providers/{name}",
            "universes": "/api/universes",
            "universe_by_name": "/api/universes/{name}",
            "universe_memberships": "/api/universes/{name}/memberships",
            "active_universe": "/api/universes/active/current",
            "prices_latest": "/api/prices/{symbol}/latest",
            "prices_with_gaps": "/api/prices/gaps",
            "health": "/health"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint.

    Returns:
        Service health status
    """
    # TODO: Add database connectivity check
    # TODO: Add API provider health check
    return {
        "status": "healthy",
        "service": "tradescout-api",
        "version": "2.0.0-alpha"
    }


@app.get(
    "/api/assets/{symbol}",
    response_model=AssetSQLModel,
    summary="Get asset by symbol",
    description="""
    Get asset details with cache-aside pattern.

    **Flow:**
    1. Check local database first (cache)
    2. If missing or stale (3-day TTL) → fetch from Polygon API
    3. Update local database
    4. Return asset

    **Parameters:**
    - `symbol`: Stock ticker symbol (e.g., AAPL, MSFT)
    - `force_refresh`: Bypass cache, always fetch fresh data

    **Example:**
    ```
    GET /api/assets/AAPL
    GET /api/assets/MSFT?force_refresh=true
    ```
    """
)
async def get_asset(
    symbol: str,
    force_refresh: bool = Query(
        default=False,
        description="Force refresh from API, bypass cache"
    ),
    data_service: DataServiceV2 = Depends(get_data_service)
):
    """Get asset by symbol - demonstrates cache-aside pattern.

    This endpoint shows the full architecture in action:
    - FastAPI (this endpoint)
    - DataServiceV2 (orchestration)
    - CacheService (cache-aside pattern)
    - AssetRepository (business queries)
    - AssetSQLModel (DAO/ORM)
    - SQLite database

    Args:
        symbol: Stock ticker symbol
        force_refresh: If True, bypass cache
        data_service: Injected DataServiceV2

    Returns:
        Asset details

    Raises:
        HTTPException: 404 if asset not found
    """
    logger.info(
        f"GET /api/assets/{symbol} "
        f"(force_refresh={force_refresh})"
    )

    # Call service layer (which handles cache-aside pattern)
    asset = data_service.get_asset(symbol, force_refresh=force_refresh)

    if not asset:
        raise HTTPException(
            status_code=404,
            detail=f"Asset '{symbol}' not found"
        )

    return asset


@app.get(
    "/api/markets",
    response_model=List[MarketSQLModel],
    summary="Get all active markets",
    description="""
    Get list of all active trading markets/exchanges.

    **Example:**
    ```
    GET /api/markets
    ```

    **Returns:** List of market objects with trading hours and details.
    """
)
async def get_all_markets(
    data_service: DataServiceV2 = Depends(get_data_service)
):
    """Get all active markets.

    Args:
        data_service: Injected DataServiceV2

    Returns:
        List of all active markets
    """
    logger.info("GET /api/markets")
    markets = data_service.get_all_markets()
    return markets


@app.get(
    "/api/markets/{code}",
    response_model=MarketSQLModel,
    summary="Get market by code",
    description="""
    Get specific market details by market code.

    **Parameters:**
    - `code`: Market code (e.g., XNYS, NASDAQ, NYSE)

    **Example:**
    ```
    GET /api/markets/XNYS
    GET /api/markets/NASDAQ
    ```
    """
)
async def get_market(
    code: str,
    data_service: DataServiceV2 = Depends(get_data_service)
):
    """Get market by code.

    Args:
        code: Market code
        data_service: Injected DataServiceV2

    Returns:
        Market details

    Raises:
        HTTPException: 404 if market not found
    """
    logger.info(f"GET /api/markets/{code}")
    market = data_service.get_market(code)

    if not market:
        raise HTTPException(
            status_code=404,
            detail=f"Market '{code}' not found"
        )

    return market


@app.get(
    "/api/fundamentals/{asset_id}",
    response_model=FundamentalsSQLModel,
    summary="Get fundamentals by asset ID",
    description="""
    Get fundamental data for a specific asset.

    **Parameters:**
    - `asset_id`: Asset database ID

    **Example:**
    ```
    GET /api/fundamentals/1
    ```

    **Returns:** Fundamental data including market cap, sector, P/E ratio, etc.
    """
)
async def get_fundamentals(
    asset_id: int,
    data_service: DataServiceV2 = Depends(get_data_service)
):
    """Get fundamentals for an asset.

    Args:
        asset_id: Asset database ID
        data_service: Injected DataServiceV2

    Returns:
        Fundamentals data

    Raises:
        HTTPException: 404 if fundamentals not found
    """
    logger.info(f"GET /api/fundamentals/{asset_id}")
    fundamentals = data_service.get_fundamentals(asset_id)

    if not fundamentals:
        raise HTTPException(
            status_code=404,
            detail=f"Fundamentals for asset_id '{asset_id}' not found"
        )

    return fundamentals


@app.get(
    "/api/providers",
    response_model=List[ProviderSQLModel],
    summary="Get all active providers",
    description="""
    Get list of all active data providers (Polygon, YFinance, etc.).

    **Example:**
    ```
    GET /api/providers
    ```

    **Returns:** List of provider objects with API configuration details.
    """
)
async def get_all_providers(
    data_service: DataServiceV2 = Depends(get_data_service)
):
    """Get all active providers.

    Args:
        data_service: Injected DataServiceV2

    Returns:
        List of all active providers
    """
    logger.info("GET /api/providers")
    providers = data_service.get_all_providers()
    return providers


@app.get(
    "/api/providers/{name}",
    response_model=ProviderSQLModel,
    summary="Get provider by name",
    description="""
    Get specific provider details by provider name.

    **Parameters:**
    - `name`: Provider name (e.g., polygon, yfinance)

    **Example:**
    ```
    GET /api/providers/polygon
    GET /api/providers/yfinance
    ```
    """
)
async def get_provider(
    name: str,
    data_service: DataServiceV2 = Depends(get_data_service)
):
    """Get provider by name.

    Args:
        name: Provider name
        data_service: Injected DataServiceV2

    Returns:
        Provider details

    Raises:
        HTTPException: 404 if provider not found
    """
    logger.info(f"GET /api/providers/{name}")
    provider = data_service.get_provider(name)

    if not provider:
        raise HTTPException(
            status_code=404,
            detail=f"Provider '{name}' not found"
        )

    return provider


@app.get(
    "/api/universes",
    response_model=List[UniverseSQLModel],
    summary="Get all universes",
    description="""
    Get list of all asset universes.

    Universes are internal collections of assets for screening and analysis.

    **Example:**
    ```
    GET /api/universes
    ```
    """
)
async def get_all_universes(
    data_service: DataServiceV2 = Depends(get_data_service)
):
    """Get all universes.

    Args:
        data_service: Injected DataServiceV2

    Returns:
        List of all universes
    """
    logger.info("GET /api/universes")
    universes = data_service.get_all_universes()
    return universes


@app.get(
    "/api/universes/active/current",
    response_model=UniverseSQLModel,
    summary="Get active universe",
    description="""
    Get the currently active universe.

    **Business Rule:** Only one universe can be active at a time.

    **Example:**
    ```
    GET /api/universes/active/current
    ```
    """
)
async def get_active_universe(
    data_service: DataServiceV2 = Depends(get_data_service)
):
    """Get active universe.

    Args:
        data_service: Injected DataServiceV2

    Returns:
        Active universe

    Raises:
        HTTPException: 404 if no active universe
    """
    logger.info("GET /api/universes/active/current")
    universe = data_service.get_active_universe()

    if not universe:
        raise HTTPException(
            status_code=404,
            detail="No active universe found"
        )

    return universe


@app.get(
    "/api/universes/{name}",
    response_model=UniverseSQLModel,
    summary="Get universe by name",
    description="""
    Get specific universe details by name.

    **Parameters:**
    - `name`: Universe name (e.g., gap_trading_universe)

    **Example:**
    ```
    GET /api/universes/gap_trading_universe
    ```
    """
)
async def get_universe(
    name: str,
    data_service: DataServiceV2 = Depends(get_data_service)
):
    """Get universe by name.

    Args:
        name: Universe name
        data_service: Injected DataServiceV2

    Returns:
        Universe details

    Raises:
        HTTPException: 404 if universe not found
    """
    logger.info(f"GET /api/universes/{name}")
    universe = data_service.get_universe(name)

    if not universe:
        raise HTTPException(
            status_code=404,
            detail=f"Universe '{name}' not found"
        )

    return universe


@app.get(
    "/api/universes/{name}/memberships",
    response_model=List[UniverseMembershipSQLModel],
    summary="Get universe memberships",
    description="""
    Get list of assets in a universe.

    **Parameters:**
    - `name`: Universe name

    **Example:**
    ```
    GET /api/universes/gap_trading_universe/memberships
    ```

    **Returns:** List of membership objects with asset_id and universe_id.
    """
)
async def get_universe_memberships(
    name: str,
    data_service: DataServiceV2 = Depends(get_data_service)
):
    """Get universe memberships.

    Args:
        name: Universe name
        data_service: Injected DataServiceV2

    Returns:
        List of memberships

    Raises:
        HTTPException: 404 if universe not found
    """
    logger.info(f"GET /api/universes/{name}/memberships")

    # Check universe exists
    universe = data_service.get_universe(name)
    if not universe:
        raise HTTPException(
            status_code=404,
            detail=f"Universe '{name}' not found"
        )

    memberships = data_service.get_universe_memberships(name)
    return memberships


@app.get(
    "/api/prices/{symbol}/latest",
    response_model=AssetPriceSQLModel,
    summary="Get latest price for symbol",
    description="""
    Get most recent price/snapshot data for a symbol.

    **Critical for gap analysis** - includes previous day and current day data.

    **Parameters:**
    - `symbol`: Stock symbol (e.g., AAPL)

    **Example:**
    ```
    GET /api/prices/AAPL/latest
    ```

    **Returns:** Price data including prevday_close, day_open, min_close, gap calculations
    """
)
async def get_latest_price(
    symbol: str,
    data_service: DataServiceV2 = Depends(get_data_service)
):
    """Get latest price for symbol.

    Args:
        symbol: Stock symbol
        data_service: Injected DataServiceV2

    Returns:
        Latest price data

    Raises:
        HTTPException: 404 if no price data found
    """
    logger.info(f"GET /api/prices/{symbol}/latest")
    price = data_service.get_latest_price(symbol)

    if not price:
        raise HTTPException(
            status_code=404,
            detail=f"No price data found for symbol '{symbol}'"
        )

    return price


@app.get(
    "/api/prices/gaps",
    response_model=List[AssetPriceSQLModel],
    summary="Find assets with gaps",
    description="""
    Find assets with significant price gaps (gap trading screener).

    **Gap:** Difference between previous close and current open.

    **Parameters:**
    - `min_gap_percent`: Minimum gap percentage (default: 2%)

    **Example:**
    ```
    GET /api/prices/gaps?min_gap_percent=3.0
    ```

    **Returns:** List of prices with gaps meeting criteria, includes gap_amount and gap_percent properties
    """
)
async def find_prices_with_gaps(
    min_gap_percent: float = Query(
        default=2.0,
        description="Minimum gap percentage (e.g., 2.0 for 2%)"
    ),
    data_service: DataServiceV2 = Depends(get_data_service)
):
    """Find assets with price gaps.

    Args:
        min_gap_percent: Minimum gap percentage
        data_service: Injected DataServiceV2

    Returns:
        List of prices with gaps
    """
    logger.info(f"GET /api/prices/gaps (min_gap_percent={min_gap_percent}%)")
    prices = data_service.find_prices_with_gaps(min_gap_percent)
    return prices


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if os.getenv("DEBUG") else "An error occurred"
        }
    )


# ============================================================================
# Startup/Shutdown Events
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Run startup checks."""
    logger.info("TradeScout API starting up...")

    # Check database exists
    if not os.path.exists(DB_PATH):
        logger.warning(
            f"Database not found at {DB_PATH}. "
            "Run: ./tradescout database init"
        )

    # Check API key configured
    if not os.getenv("POLYGON_API_KEY"):
        logger.warning(
            "POLYGON_API_KEY not set. "
            "API calls will fail."
        )

    logger.info("✅ TradeScout API ready")
    logger.info(f"📚 Docs available at http://localhost:8000/docs")


@app.on_event("shutdown")
async def shutdown_event():
    """Run shutdown cleanup."""
    logger.info("TradeScout API shutting down...")


# ============================================================================
# CLI Runner (for testing)
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "web_app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload on code changes (dev only)
        log_level="info"
    )
