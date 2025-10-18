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
from typing import List, Dict, Any
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, SQLModel, create_engine
from services.data_service_v2 import DataServiceV2
from screener.screener_config import ScreenerConfig
from screener.screener_engine import ScreenerEngine
from utils.app_context import AppContext
from models.sqlmodel.asset_sqlmodel import AssetSQLModel

# Load environment variables from .env file
load_dotenv()
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

# Mount static files for web interface
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

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


def get_app_context() -> AppContext:
    """Dependency: Provide AppContext for screeners.

    AppContext provides:
    - Market context (session, trading day status)
    - Data service access
    - Configuration
    """
    return AppContext(db_path=DB_PATH)


def get_presentation_context():
    """Dependency: Provide PresentationContext with web output adapters.

    Returns PresentationContext configured with web-specific adapters
    that return JSON-ready dictionaries for FastAPI serialization.
    """
    from utils.presentation_context import PresentationContext
    from output.web_screener_adapter import WebScreenerOutputAdapter
    from output.web_market_adapter import WebMarketOutputAdapter
    from output.web_news_adapter import WebNewsOutputAdapter
    from output.web_gap_adapter import WebGapOutputAdapter
    from output.web_fed_adapter import WebFedOutputAdapter
    from output.web_universe_adapter import WebUniverseOutputAdapter
    from output.web_validate_adapter import WebValidateOutputAdapter
    from output.web_asset_adapter import WebAssetOutputAdapter

    return PresentationContext(
        screener_adapter=WebScreenerOutputAdapter(),
        market_adapter=WebMarketOutputAdapter(),
        news_adapter=WebNewsOutputAdapter(),
        gap_analysis_adapter=WebGapOutputAdapter(),
        gap_performance_adapter=WebGapOutputAdapter(),  # Same adapter for now
        fed_adapter=WebFedOutputAdapter(),
        universe_adapter=WebUniverseOutputAdapter(),
        validate_adapter=WebValidateOutputAdapter(),
        asset_adapter=WebAssetOutputAdapter(),
        bootstrap_adapter=None,  # Bootstrap is CLI-only
    )


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the web interface."""
    html_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    else:
        # Fallback to API info if static files not available
        return JSONResponse({
            "name": "TradeScout API",
            "version": "2.0.0-alpha",
            "message": "Web interface not found. Check static files are deployed.",
            "documentation": {
                "swagger": "/docs",
                "redoc": "/redoc"
            }
        })


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
    "/api/assets/{symbol}/info",
    response_model=Dict[str, Any],
    summary="Get comprehensive asset information",
    description="""
    Get complete asset information including details, fundamentals, latest price, and sentiment.

    **Parameters:**
    - `symbol`: Stock ticker symbol (e.g., AAPL, MSFT)

    **Example:**
    ```
    GET /api/assets/AAPL/info
    ```

    **Returns:** Complete asset information with all available data
    """
)
async def get_asset_info(
    symbol: str,
    data_service: DataServiceV2 = Depends(get_data_service),
    presentation = Depends(get_presentation_context)
):
    """Get comprehensive asset information.

    Args:
        symbol: Stock ticker symbol
        data_service: Injected DataServiceV2
        presentation: Injected PresentationContext with web adapters

    Returns:
        Complete asset information

    Raises:
        HTTPException: 404 if asset not found
    """
    logger.info(f"GET /api/assets/{symbol}/info")

    try:
        from models.result.asset_result import AssetInfoResult, PriceDataResult, SentimentEventsResult
        from utils.config_loader import get_config_loader
        from services.converters import (
            convert_asset_sqlmodel_to_dataclass,
            convert_market_sqlmodel_to_dataclass,
            convert_asset_price_sqlmodel_to_dataclass
        )

        symbol = symbol.upper()

        # Get asset with market (returns SQLModel objects)
        asset_info = data_service.get_asset_with_market(symbol)
        if not asset_info:
            raise HTTPException(
                status_code=404,
                detail=f"Asset '{symbol}' not found"
            )

        asset_sqlmodel, market_sqlmodel = asset_info

        # Convert SQLModel to dataclass for result models
        asset = convert_asset_sqlmodel_to_dataclass(asset_sqlmodel)
        market = convert_market_sqlmodel_to_dataclass(market_sqlmodel) if market_sqlmodel else None

        # Get universe memberships
        all_universes = data_service.get_all_universes()
        member_of = []
        for univ in all_universes:
            if data_service.is_symbol_in_universe(symbol, univ.name):
                member_of.append(univ.name)

        # Get fundamentals if available
        fundamentals = data_service.get_fundamentals(asset.id)

        # Create asset info result
        asset_result = AssetInfoResult(
            asset=asset,
            market=market,
            universes=member_of,
            fundamentals=fundamentals
        )

        # Get latest price data (returns SQLModel)
        price_sqlmodel = data_service.get_latest_asset_price(symbol)
        price_result = None
        if price_sqlmodel:
            # Convert to dataclass
            price_data = convert_asset_price_sqlmodel_to_dataclass(price_sqlmodel)
            price_result = PriceDataResult(
                asset_price=price_data,
                is_new_data=False,
                forced_fetch=False
            )

        # Get sentiment events - check if news is stale and fetch if needed
        sentiment_result = None
        try:
            config_loader = get_config_loader()

            # Check if news is stale and fetch if needed
            ttl_config = config_loader.load_database_ttl_config()
            news_ttl_minutes = ttl_config.get("news_ttl_minutes", 30)

            needs_refresh = data_service.is_news_stale(symbol, hours=news_ttl_minutes / 60)

            if needs_refresh:
                logger.info(f"News data is stale for {symbol}, fetching fresh articles...")
                try:
                    # Fetch fresh news (limit to 10 articles)
                    data_service.fetch_news_and_sentiment(symbol, limit=10)
                except Exception as e:
                    logger.warning(f"Failed to fetch fresh news for {symbol}: {e}")
                    # Continue anyway - show whatever news we have

            # Get sentiment events (whether we just fetched or not)
            sentiment_events = data_service.get_sentiment_events(symbol=symbol)

            # Get sentiment type mapping
            all_types = data_service.get_all_sentiment_types(active_only=False)
            type_id_to_name = {t.id: t.name for t in all_types}

            # Calculate sentiment score
            sentiment_config = config_loader.load_sentiment_config()
            time_window_days = sentiment_config["analysis"]["default_time_window_days"]
            sentiment_score = data_service.calculate_asset_sentiment(symbol, limit=10, time_window_days=time_window_days)

            # Build result (even if empty, so UI can show "no news")
            sentiment_result = SentimentEventsResult(
                symbol=symbol,
                sentiment_events=sentiment_events,
                type_id_to_name=type_id_to_name,
                sentiment_score=sentiment_score,
                time_window_days=time_window_days
            )
        except Exception as e:
            logger.warning(f"Could not fetch sentiment events for {symbol}: {e}")

        # Use adapters to format all data
        response = {
            "asset": presentation.asset_adapter.display_asset_info(asset_result),
        }

        if price_result:
            response["price"] = presentation.asset_adapter.display_price_data(price_result)

        if sentiment_result:
            response["sentiment"] = presentation.asset_adapter.display_sentiment_events(sentiment_result)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting asset info for {symbol}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error getting asset info: {str(e)}"
        )


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


@app.get(
    "/api/screeners",
    response_model=List[Dict[str, Any]],
    summary="List available screeners",
    description="""
    Get list of all available screeners with their configurations.

    **Example:**
    ```
    GET /api/screeners
    ```

    **Returns:** List of screener objects with name, description, and enabled status
    """
)
async def list_screeners():
    """List all available screeners.

    Returns:
        List of screener configurations
    """
    logger.info("GET /api/screeners")
    try:
        screener_config = ScreenerConfig()
        screeners = screener_config.list_available_screeners()
        return screeners
    except Exception as e:
        logger.error(f"Error loading screeners: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error loading screeners: {str(e)}"
        )


@app.get(
    "/api/screeners/{name}/run",
    response_model=Dict[str, Any],
    summary="Run a screener",
    description="""
    Execute a screener and return results.

    **Parameters:**
    - `name`: Screener name (e.g., gainers, losers, momentum)

    **Example:**
    ```
    GET /api/screeners/gainers/run
    GET /api/screeners/losers/run
    ```

    **Returns:** Screener results with market context and matching stocks
    """
)
async def run_screener(
    name: str,
    app_context: AppContext = Depends(get_app_context),
    presentation = Depends(get_presentation_context)
):
    """Run a screener by name.

    Args:
        name: Screener name
        app_context: Injected AppContext
        presentation: Injected PresentationContext with web adapters

    Returns:
        Screener results with context and data

    Raises:
        HTTPException: 404 if screener not found, 400 if not valid for session
    """
    logger.info(f"GET /api/screeners/{name}/run")

    try:
        # Load screener configuration
        screener_config = ScreenerConfig()
        screener_def = screener_config.get_screener(name)

        # Get market context
        market_context = app_context.market_context
        data_service = app_context.get_data_service_v2()

        # Execute screener (returns tuple: results, excluded_count)
        screener_engine = ScreenerEngine(data_service, app_context)
        results, excluded_count = screener_engine.execute_screener(screener_def, market_context)

        # Get resolved config for result model
        from screener.template_resolver import TemplateResolver
        resolver = TemplateResolver(screener_def, market_context.session_name)
        resolved_config = resolver.get_resolved_config()

        # Build output-agnostic result model
        from models.result.screener_result import ScreenerResult
        result = ScreenerResult(
            screener_name=name,
            results=results,
            screener_def=screener_def,
            resolved_config=resolved_config,
            market_context=market_context,
            excluded_count=excluded_count,
            snapshot_time=None,
            sessions_text=None,
            warnings=None,
            data_date_summary=None
        )

        # Use adapter to format for web/JSON
        return presentation.screener_adapter.display_screener_results(result)

    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Screener '{name}' not found"
        )
    except ValueError as e:
        # Session validation errors
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error running screener '{name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error running screener: {str(e)}"
        )


@app.get(
    "/api/market/context",
    response_model=Dict[str, Any],
    summary="Get current market context",
    description="""
    Get current market context including session, trading status, and universe info.

    **Example:**
    ```
    GET /api/market/context
    ```

    **Returns:** Market context with session info, universe stats, and last snapshot details
    """
)
async def get_market_context(
    app_context: AppContext = Depends(get_app_context),
    presentation = Depends(get_presentation_context)
):
    """Get current market context.

    Args:
        app_context: Injected AppContext
        presentation: Injected PresentationContext with web adapters

    Returns:
        Market context information
    """
    logger.info("GET /api/market/context")

    try:
        from models.result.market_result import MarketContextResult
        from datetime import datetime

        # Get universe statistics using data provider
        active_universe = app_context.get_active_universe()
        data_service = app_context.get_data_service_v2()

        # Get universe market breakdown
        universe_markets = data_service.get_universe_market_breakdown(active_universe)

        # Get total universe count
        universe_stats = data_service.get_universe_stats(active_universe)
        total_universe = universe_stats.total_members if universe_stats else 0

        # Get market context - uses the universe's primary market (first market listed)
        ctx = app_context.market_context

        # Get last snapshot metadata
        last_snapshot_status = None
        last_snapshot_time = None
        last_snapshot_age_str = None

        try:
            # Query metadata using repository
            metadata = data_service.metadata_repository.get_latest_by_operation(
                operation_type='market_snapshots',
                operation_subtype='fetch'
            )

            if metadata and metadata.completed_at:
                last_snapshot_time = metadata.completed_at
                last_snapshot_status = metadata.status

                # Calculate age
                age = datetime.now() - last_snapshot_time
                if age.total_seconds() < 60:
                    last_snapshot_age_str = f"{age.total_seconds():.0f}s ago"
                elif age.total_seconds() < 3600:
                    last_snapshot_age_str = f"{age.total_seconds() / 60:.1f}m ago"
                elif age.total_seconds() < 86400:
                    last_snapshot_age_str = f"{age.total_seconds() / 3600:.1f}h ago"
                else:
                    last_snapshot_age_str = f"{age.total_seconds() / 86400:.1f}d ago"

        except Exception as e:
            logger.warning(f"Unable to fetch snapshot metadata: {e}")

        # Create result and use adapter
        result = MarketContextResult(
            universe_name=active_universe,
            universe_markets=universe_markets,
            total_universe=total_universe,
            market_context=ctx,
            last_snapshot_status=last_snapshot_status,
            last_snapshot_time=last_snapshot_time,
            last_snapshot_age_str=last_snapshot_age_str
        )

        return presentation.market_adapter.display_market_context(result)

    except Exception as e:
        logger.error(f"Error getting market context: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error getting market context: {str(e)}"
        )


@app.post(
    "/api/market/update",
    response_model=Dict[str, Any],
    summary="Update market snapshot data",
    description="""
    Trigger market data update (current snapshot or historical backfill).

    **Query Parameters:**
    - `date`: Optional date for historical backfill (YYYY-MM-DD format)
    - `force`: Force refresh, bypass TTL cache

    **Examples:**
    ```
    POST /api/market/update                          # Update current snapshot
    POST /api/market/update?force=true               # Force update
    POST /api/market/update?date=2025-10-15          # Backfill specific date
    POST /api/market/update?date=2025-10-15&force=true  # Force backfill
    ```

    **Returns:** Update statistics including tickers processed, saved, duplicates, etc.
    """
)
async def update_market_data(
    date: Optional[str] = Query(default=None, description="Date for historical backfill (YYYY-MM-DD)"),
    force: bool = Query(default=False, description="Force refresh, bypass cache"),
    data_service: DataServiceV2 = Depends(get_data_service),
    presentation = Depends(get_presentation_context)
):
    """Update market data.

    Args:
        date: Optional date for backfill
        force: Force refresh flag
        data_service: Injected DataServiceV2
        presentation: Injected PresentationContext with web adapters

    Returns:
        Update statistics

    Raises:
        HTTPException: 400 if date format invalid, 500 if update fails
    """
    logger.info(f"POST /api/market/update (date={date}, force={force})")

    try:
        from datetime import datetime
        from models.result.market_result import MarketUpdateResult, MarketBackfillResult
        from models.dataclass.data_update_metadata import DataUpdateMetadataType
        from services.cache_service import CacheConfig

        if date:
            # BACKFILL MODE
            try:
                target_date = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid date format: {date}. Use YYYY-MM-DD"
                )

            # Run backfill
            stats = data_service.backfill_market_data(
                target_date=target_date,
                force_refresh=force
            )

            # Get total records
            total_historical_records = None
            try:
                total_historical_records = data_service.asset_price_repository.count_all()
            except Exception:
                pass

            # Build result and use adapter
            result = MarketBackfillResult(
                target_date=target_date,
                force_refresh=force,
                total_tickers=stats.total_tickers,
                matched_symbols=stats.matched_symbols,
                unmatched_symbols=stats.unmatched_symbols,
                transformed=stats.transformed,
                saved=stats.saved,
                duplicates=stats.duplicates,
                invalid=stats.invalid,
                invalid_no_timestamp=stats.invalid_no_timestamp,
                invalid_exception=stats.invalid_exception,
                duration_seconds=0.0,  # Could track if needed
                completed_at=datetime.now(),
                total_historical_records=total_historical_records
            )

            return presentation.market_adapter.display_market_backfill_result(result)

        else:
            # SNAPSHOT MODE
            stats = data_service.update_market_snapshot(force_refresh=force)

            # Get TTL and metadata for timing info
            ttl_minutes = CacheConfig.get_ttl(DataUpdateMetadataType.MARKET_SNAPSHOTS) / 60
            metadata = data_service.metadata_repository.get_latest_by_operation(
                operation_type=DataUpdateMetadataType.MARKET_SNAPSHOTS.value
            )

            last_snapshot_time = None
            age_minutes = None
            if metadata and metadata.completed_at:
                last_snapshot_time = metadata.completed_at
                age = datetime.now() - metadata.completed_at
                age_minutes = age.total_seconds() / 60

            # Get total records
            total_historical_records = None
            try:
                total_historical_records = data_service.asset_price_repository.count_all()
            except Exception:
                pass

            # Build result and use adapter
            result = MarketUpdateResult(
                data_was_fresh=stats.data_was_fresh,
                total_tickers=stats.total_tickers,
                matched_symbols=stats.matched_symbols,
                unmatched_symbols=stats.unmatched_symbols,
                transformed=stats.transformed,
                saved=stats.saved,
                duplicates=stats.duplicates,
                invalid=stats.invalid,
                invalid_no_timestamp=stats.invalid_no_timestamp,
                invalid_exception=stats.invalid_exception,
                duration_seconds=0.0,  # Could track if needed
                completed_at=datetime.now(),
                last_snapshot_time=last_snapshot_time,
                age_minutes=age_minutes,
                ttl_minutes=ttl_minutes,
                total_historical_records=total_historical_records
            )

            return presentation.market_adapter.display_market_update_result(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating market data: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error updating market data: {str(e)}"
        )


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
    logger.info("TradeScout Web Interface starting up...")

    # Check database exists
    if not os.path.exists(DB_PATH):
        logger.error(
            f"❌ Database not found at {DB_PATH}"
        )
        logger.error("   Run: ./tradescout database init")
    else:
        logger.info(f"✓ Database found: {DB_PATH}")

    # Check API key configured
    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key or len(api_key) < 10:
        logger.error("❌ POLYGON_API_KEY not configured")
        logger.error("   Set environment variable: export POLYGON_API_KEY='your_key'")
    else:
        logger.info(f"✓ Polygon API key configured ({api_key[:4]}...{api_key[-4:]})")

    logger.info("✅ TradeScout Web Interface ready")
    logger.info(f"🌐 Web Interface: http://localhost:8000")
    logger.info(f"📚 API Docs: http://localhost:8000/docs")


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
