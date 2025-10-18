"""Asset command group for single asset operations."""

import sys
import logging
from pathlib import Path
from datetime import datetime

import click
from rich.console import Console

from .main import pass_config, create_header

console = Console()
logger = logging.getLogger(__name__)


def display_market_context(app_context):
    """Display market context at the top of asset commands."""
    try:
        # Initialize data service
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from utils.config_loader import get_config_loader
        from models.result.asset_result import MarketContextResult

        data_service = app_context.get_data_service_v2()

        # Get markets from universe config
        config_loader = get_config_loader()
        universe_config = config_loader.load_universe_config("default")
        configured_exchanges = universe_config.get("included", {}).get("exchanges", [])

        if not configured_exchanges:
            console.print(f"[dim]⚠️ No exchanges configured in universe config[/dim]")
            return

        # Get only the configured markets using data service
        market_codes = data_service.get_active_markets_by_codes(configured_exchanges)

        if not market_codes:
            console.print(f"[dim]⚠️ No configured markets found in database[/dim]")
            return

        # Get context for configured markets
        service = app_context.get_market_context_service()

        # Build market status list
        markets = []
        for market_code, market_name in market_codes:
            ctx = service.get_context(market_code)
            status = "OPEN" if ctx.is_market_open else "CLOSED"
            trading_day = "Yes" if ctx.is_trading_day else "No"
            extended = "Yes" if ctx.is_extended_hours else "No"
            markets.append((market_code, ctx.current_session.value, status, trading_day, extended))

        # Create result and use adapter
        result = MarketContextResult(markets=markets)
        app_context.presentation.asset_adapter.display_market_context(result)

    except FileNotFoundError as e:
        # Config file missing - this is a fatal error
        console.print(f"[red]❌ Configuration error: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[dim]⚠️ Market context unavailable: {e}[/dim]")
        console.print()


@click.group()
@pass_config
def asset(app_context):
    """Single asset data operations and information."""
    pass


@asset.command()
@click.argument("symbol", type=str)
@click.option("--force", is_flag=True, help="Force refresh, bypass TTL cache")
@pass_config
def info(app_context, symbol: str, force: bool):
    """
    Show detailed information about a single asset.

    Retrieves and stores fresh asset data from the API including
    symbol, name, market, type, and current pricing information.

    Example:
        tradescout asset info AAPL
        tradescout asset info AAPL --force
    """
    # Display market context at the top
    display_market_context(app_context)

    symbol = symbol.upper()

    # Initialize data service
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))

        data_service = app_context.get_data_service_v2()
    except Exception as e:
        console.print(f"[red]❌ Failed to initialize data service: {e}[/red]")
        sys.exit(1)

    # Get asset info and price data (this fetches and stores fresh data)
    try:
        from models.result.asset_result import AssetInfoResult, PriceDataResult

        asset_info = data_service.get_asset_with_market(symbol)
        if not asset_info:
            app_context.presentation.asset_adapter.display_asset_not_found(symbol)
            return

        asset, market = asset_info

        # Get universe memberships
        all_universes = data_service.get_all_universes()
        member_of = []
        for univ in all_universes:
            if data_service.is_symbol_in_universe(symbol, univ.name):
                member_of.append(univ.name)

        # Get fundamentals if available (service returns dataclass)
        fundamentals = data_service.get_fundamentals(asset.id)

        # Create result and display
        asset_result = AssetInfoResult(
            asset=asset,
            market=market,
            universes=member_of,
            fundamentals=fundamentals
        )
        app_context.presentation.asset_adapter.display_asset_info(asset_result)

        # Fetch fresh ticker snapshot (checks TTL, may use cache or fetch from API)
        console.print()
        if force:
            console.print("[dim]Force fetching latest price data from API...[/dim]")
        else:
            console.print("[dim]Fetching latest price data...[/dim]")

        # Check what we had before the fetch
        old_price_data = data_service.get_latest_asset_price(symbol)
        old_timestamp = old_price_data.provider_updated_at if old_price_data else None

        # Fetch snapshot from API
        ticker_snapshot = data_service.get_ticker_snapshot(symbol)

        # Transform and save the snapshot
        if ticker_snapshot:
            asset_price = data_service.transform_ticker_snapshot_to_asset_price(
                symbol=symbol,
                asset_id=asset.id,
                ticker_snapshot=ticker_snapshot
            )

            if asset_price:
                # Save to database (batch_save handles the dataclass -> SQLModel conversion)
                data_service.batch_save_asset_prices([asset_price])

        # Check what we have after the fetch
        price_data = data_service.get_latest_asset_price(symbol)
        new_timestamp = price_data.provider_updated_at if price_data else None

        if price_data:
            # Determine if we got new data
            is_new_data = (old_timestamp != new_timestamp) if old_timestamp else True

            # Create price result and display
            price_result = PriceDataResult(
                asset_price=price_data,
                is_new_data=is_new_data,
                forced_fetch=force
            )
            app_context.presentation.asset_adapter.display_price_data(price_result)
        else:
            app_context.presentation.asset_adapter.display_no_price_data(symbol)

        # Check if news is stale and fetch if needed (or force refresh if --force flag)
        try:
            # Get news TTL from config (default 30 minutes)
            from utils.config_loader import get_config_loader
            config_loader = get_config_loader()
            ttl_config = config_loader.load_database_ttl_config()
            news_ttl_minutes = ttl_config.get("news_ttl_minutes", 30)

            # Check if we need to fetch fresh news (or force flag is set)
            needs_refresh = force or data_service.is_news_stale(symbol, hours=news_ttl_minutes / 60)

            if needs_refresh:
                console.print()
                if force:
                    console.print(f"[dim]Force fetching latest news articles...[/dim]")
                else:
                    console.print(f"[dim]News data is stale, fetching fresh articles...[/dim]")
                try:
                    # Fetch fresh news (silently - we'll show the results below)
                    data_service.fetch_news_and_sentiment(symbol, limit=10)
                except Exception as e:
                    logger.warning(f"Failed to fetch fresh news: {e}")
                    # Continue anyway - show whatever news we have

        except Exception as e:
            logger.warning(f"Error checking news staleness: {e}")
            # Continue anyway

        # Display recent sentiment events using adapter
        try:
            from models.result.asset_result import SentimentEventsResult

            sentiment_events = data_service.get_sentiment_events(symbol=symbol)

            # Get sentiment type mapping for display
            all_types = data_service.get_all_sentiment_types(active_only=False)
            type_id_to_name = {t.id: t.name for t in all_types}

            # Calculate sentiment score
            sentiment_config = config_loader.load_sentiment_config()
            time_window_days = sentiment_config["analysis"]["default_time_window_days"]
            sentiment_score = data_service.calculate_asset_sentiment(symbol, limit=10, time_window_days=time_window_days)

            # Build result and display
            result = SentimentEventsResult(
                symbol=symbol,
                sentiment_events=sentiment_events,
                type_id_to_name=type_id_to_name,
                sentiment_score=sentiment_score,
                time_window_days=time_window_days
            )
            app_context.presentation.asset_adapter.display_sentiment_events(result)

        except Exception as e:
            console.print()
            console.print(f"[dim]⚠️  Could not fetch sentiment events: {e}[/dim]")

    except Exception as e:
        console.print(f"[red]❌ Error retrieving asset info: {e}[/red]")
        sys.exit(1)


@asset.command()
@click.argument("symbol", type=str)
@click.option("--limit", default=10, help="Maximum number of articles to fetch (default: 10)")
@pass_config
def news(app_context, symbol: str, limit: int):
    """
    Fetch recent news and sentiment analysis for a symbol.

    Retrieves news articles from Polygon API, extracts sentiment data,
    and stores sentiment events in the database for gap trading analysis.

    Example:
        tradescout asset news PLUG
        tradescout asset news AAPL --limit 5
    """
    # Display market context at the top
    display_market_context(app_context)

    symbol = symbol.upper()

    # Initialize data service
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))

        data_service = app_context.get_data_service_v2()
    except Exception as e:
        console.print(f"[red]❌ Failed to initialize data service: {e}[/red]")
        sys.exit(1)

    # Fetch news and sentiment
    try:
        console.print(f"[cyan]📰 Fetching news for {symbol}...[/cyan]")
        console.print()

        result = data_service.fetch_news_and_sentiment(symbol, limit=limit)

        # Calculate overall sentiment score from database events
        sentiment_score = data_service.calculate_asset_sentiment(symbol, limit=10, time_window_days=5)

        # Fetch recent sentiment events to display in table
        # Get asset from database
        asset = data_service.asset_repository.get_by_symbol(symbol)
        if asset:
            recent_events = data_service.sentiment_event_repository.find_recent_by_asset(
                asset.id, days=5, limit=10
            )
            # Convert SQLModel events to dataclass events for display
            from models.dataclass.sentiment_event import SentimentEvent
            from decimal import Decimal
            import json

            display_events = []
            for event_sql in recent_events:
                event = SentimentEvent(
                    id=event_sql.id,
                    asset_id=event_sql.asset_id,
                    sentiment_type_id=event_sql.sentiment_type_id,
                    event_date=event_sql.event_date,
                    event_time=event_sql.event_time,
                    session=event_sql.session,
                    value=event_sql.value or Decimal('0'),
                    magnitude=event_sql.magnitude or 'medium',
                    details=json.loads(event_sql.details) if event_sql.details else {},
                    created_at=event_sql.created_at
                )
                display_events.append(event)

            # Add events to result for display
            result.sentiment_events = display_events

        # Use injected news adapter from presentation context
        app_context.presentation.news_adapter.display_news_result(result, sentiment_score=sentiment_score)

    except Exception as e:
        console.print(f"[red]❌ Failed to fetch news: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)