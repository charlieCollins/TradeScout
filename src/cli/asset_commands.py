"""Asset command group for single asset operations."""

import sys
import logging
from pathlib import Path
from datetime import datetime

import click
from rich.console import Console
from rich.table import Table
from rich import box
from rich.columns import Columns
from rich.align import Align
from rich.panel import Panel

from .main import pass_config, create_header

console = Console()
logger = logging.getLogger(__name__)


def display_market_context(app_context):
    """Display market context at the top of asset commands."""
    try:
        # Initialize data service
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from utils.config_loader import get_config_loader

        data_service = app_context.get_data_service_v2()

        # Get markets from universe config
        config_loader = get_config_loader()
        universe_config = config_loader.load_universe_config("default_universe")
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

        # Create markets context table
        context_table = Table(box=box.ROUNDED, show_header=True, title="📊 Markets Context")
        context_table.add_column("Market", style="bold", width=8)
        context_table.add_column("Session", width=12)
        context_table.add_column("Status", width=8)
        context_table.add_column("Trading Day", width=12)
        context_table.add_column("Extended Hours", width=15)

        # Add row for each configured market
        for market_code, market_name in market_codes:
            ctx = service.get_context(market_code)
            status = "OPEN" if ctx.is_market_open else "CLOSED"
            trading_day = "Yes" if ctx.is_trading_day else "No"
            extended = "Yes" if ctx.is_extended_hours else "No"
            context_table.add_row(market_code, ctx.current_session.value, status, trading_day, extended)

        console.print(context_table)
        console.print()

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
@pass_config
def local(app_context, symbol: str):
    """
    Show asset information from local database only (no API calls).

    Displays cached asset and price data from the TradeScout database
    without fetching fresh data from external APIs.

    Example:
        tradescout asset local AAPL
    """
    # Display market context at the top
    display_market_context(app_context)

    symbol = symbol.upper()

    # Initialize data service (but we won't call APIs)
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))

        data_service = app_context.get_data_service_v2()
    except Exception as e:
        console.print(f"[red]❌ Failed to initialize data service: {e}[/red]")
        sys.exit(1)

    # Get asset data from database only
    try:
        asset_info = data_service.get_asset_with_market(symbol)
        if not asset_info:
            console.print(f"[red]❌ Asset {symbol} not found in database[/red]")
            console.print(f"[dim]Use 'tradescout asset info {symbol}' to fetch from API[/dim]")
            return

        # Create asset info table
        asset_table = Table(box=box.ROUNDED, show_header=False, title=f"{symbol} (Local Data)")
        asset_table.add_column("", style="bold", width=12)
        asset_table.add_column("", width=30)

        asset, market = asset_info
        asset_table.add_row("Name", asset.name or "N/A")
        asset_table.add_row("Market", f"{market.name} ({market.code})" if market else "N/A")
        asset_table.add_row("Type", asset.asset_type or "N/A")  # Already a string in AssetSQLModel
        asset_table.add_row("Class", asset.asset_class or "N/A")  # Already a string in AssetSQLModel
        asset_table.add_row("Currency", asset.currency or "N/A")
        asset_table.add_row("Status", "✅ Active" if asset.is_active else "❌ Inactive")
        asset_table.add_row("Asset ID", str(asset.id))
        asset_table.add_row("Provider ID", str(asset.provider_id))

        # Get universe memberships
        all_universes = data_service.get_all_universes()
        member_of = []
        for univ in all_universes:
            if data_service.is_symbol_in_universe(symbol, univ.name):
                member_of.append(univ.name)

        if member_of:
            asset_table.add_row("Universes", ", ".join(member_of))
        else:
            asset_table.add_row("Universes", "[dim]none[/dim]")

        console.print(asset_table)

        # Get latest price data from database
        latest_price = data_service.get_latest_asset_price(symbol)
        if latest_price:
            console.print()

            # Provider timestamp header
            provider_time = datetime.fromtimestamp(latest_price.provider_updated_at / 1_000_000_000).strftime("%Y-%m-%d %H:%M:%S ET")
            our_capture_time = latest_price.updated_at.strftime("%Y-%m-%d %H:%M:%S")
            console.print(f"{symbol} | Provider Updated: {provider_time} | Captured: {our_capture_time}")

            # Price data table
            price_table = Table(box=box.ROUNDED, show_header=True)
            price_table.add_column("PrevDay", style="", width=8)
            price_table.add_column("", style="", width=9)
            price_table.add_column("Day", style="", width=8)
            price_table.add_column("", style="", width=9)
            price_table.add_column("Min", style="", width=8)
            price_table.add_column("", style="", width=19)

            def format_price(value):
                return f"${value:.2f}" if value else "N/A"

            def format_volume(value):
                if not value:
                    return "N/A"
                if value >= 1_000_000:
                    return f"{value/1_000_000:.1f}M"
                elif value >= 1_000:
                    return f"{value/1_000:.1f}K"
                return f"{value:,}"

            def format_timestamp(timestamp_ms):
                if not timestamp_ms:
                    return "N/A"
                dt = datetime.fromtimestamp(timestamp_ms / 1000)
                return dt.strftime("%Y-%m-%d %H:%M:%S")

            # Add rows
            price_table.add_row(
                "Open", format_price(latest_price.prevday_open),
                "Open", format_price(latest_price.day_open),
                "Open", format_price(latest_price.min_open)
            )
            price_table.add_row(
                "High", format_price(latest_price.prevday_high),
                "High", format_price(latest_price.day_high),
                "High", format_price(latest_price.min_high)
            )
            price_table.add_row(
                "Low", format_price(latest_price.prevday_low),
                "Low", format_price(latest_price.day_low),
                "Low", format_price(latest_price.min_low)
            )
            price_table.add_row(
                "Close", format_price(latest_price.prevday_close),
                "Close", format_price(latest_price.day_close),
                "Close", format_price(latest_price.min_close)
            )
            price_table.add_row(
                "Volume", format_volume(latest_price.prevday_volume),
                "Volume", format_volume(latest_price.day_volume),
                "Volume", format_volume(latest_price.min_volume)
            )
            price_table.add_row(
                "", "",
                "", "",
                "TS", format_timestamp(latest_price.min_timestamp)
            )

            console.print(price_table)

        else:
            console.print(f"[yellow]⚠️  No price data available for {symbol} in database[/yellow]")
            console.print(f"[dim]Use 'tradescout asset info {symbol}' to fetch from API[/dim]")

    except Exception as e:
        console.print(f"[red]❌ Error retrieving local asset data: {e}[/red]")
        sys.exit(1)

    # Ensure clean exit
    return


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
        asset_info = data_service.get_asset_with_market(symbol)
        if not asset_info:
            console.print(f"[red]❌ Asset {symbol} not found[/red]")
            return

        # Create asset info table
        asset_table = Table(box=box.ROUNDED, show_header=False, title=f"{symbol}")
        asset_table.add_column("", style="bold", width=12)
        asset_table.add_column("", width=30)

        asset, market = asset_info
        asset_table.add_row("Name", asset.name or "N/A")
        asset_table.add_row("Market", f"{market.name} ({market.code})" if market else "N/A")
        asset_table.add_row("Type", asset.asset_type or "N/A")  # Already a string in AssetSQLModel
        asset_table.add_row("Class", asset.asset_class or "N/A")  # Already a string in AssetSQLModel
        asset_table.add_row("Currency", asset.currency or "N/A")
        asset_table.add_row("Status", "✅ Active" if asset.is_active else "❌ Inactive")
        asset_table.add_row("Asset ID", str(asset.id))
        asset_table.add_row("Provider ID", str(asset.provider_id))

        # Get universe memberships
        all_universes = data_service.get_all_universes()
        member_of = []
        for univ in all_universes:
            if data_service.is_symbol_in_universe(symbol, univ.name):
                member_of.append(univ.name)

        if member_of:
            asset_table.add_row("Universes", ", ".join(member_of))
        else:
            asset_table.add_row("Universes", "[dim]none[/dim]")

        console.print(asset_table)

        # Fetch fresh ticker snapshot (checks TTL, may use cache or fetch from API)
        console.print()
        if force:
            console.print("[dim]Force fetching latest price data from API...[/dim]")
        else:
            console.print("[dim]Fetching latest price data...[/dim]")

        # Check what we had before the fetch
        old_price_data = data_service.get_latest_asset_price(symbol)
        old_timestamp = old_price_data.provider_updated_at if old_price_data else None

        # Fetch (may use cache or API depending on TTL and force flag)
        # TODO: Implement force_refresh support in get_ticker_snapshot
        ticker_snapshot = data_service.get_ticker_snapshot(symbol)

        # Check what we have after the fetch
        price_data = data_service.get_latest_asset_price(symbol)
        new_timestamp = price_data.provider_updated_at if price_data else None

        if price_data:
            console.print()

            # Determine if we got new data
            is_new_data = (old_timestamp != new_timestamp) if old_timestamp else True

            # Provider timestamp header
            provider_time = datetime.fromtimestamp(price_data.provider_updated_at / 1_000_000_000).strftime("%Y-%m-%d %H:%M:%S ET")

            if is_new_data:
                console.print(f"[green]✅ New data fetched[/green] | {symbol} | Provider Updated: {provider_time}")
            else:
                # Different messages depending on whether we forced a fetch or used cache
                if force:
                    console.print(f"[yellow]📋 No new data from provider[/yellow] | {symbol} | Provider Updated: {provider_time}")
                else:
                    console.print(f"[yellow]📋 Using cached data[/yellow] | {symbol} | Provider Updated: {provider_time}")

            # Price data table
            price_table = Table(box=box.ROUNDED, show_header=True)
            price_table.add_column("PrevDay", style="", width=8)
            price_table.add_column("", style="", width=9)
            price_table.add_column("Day", style="", width=8)
            price_table.add_column("", style="", width=9)
            price_table.add_column("Min", style="", width=8)
            price_table.add_column("", style="", width=19)

            def format_price(value):
                return f"${value:.2f}" if value else "N/A"

            def format_volume(value):
                if not value:
                    return "N/A"
                if value >= 1_000_000:
                    return f"{value/1_000_000:.1f}M"
                elif value >= 1_000:
                    return f"{value/1_000:.1f}K"
                return f"{value:,}"

            def format_timestamp(timestamp_ms):
                if not timestamp_ms:
                    return "N/A"
                dt = datetime.fromtimestamp(timestamp_ms / 1000)
                return dt.strftime("%Y-%m-%d %H:%M:%S")

            # Add rows
            price_table.add_row(
                "Open", format_price(price_data.prevday_open),
                "Open", format_price(price_data.day_open),
                "Open", format_price(price_data.min_open)
            )
            price_table.add_row(
                "High", format_price(price_data.prevday_high),
                "High", format_price(price_data.day_high),
                "High", format_price(price_data.min_high)
            )
            price_table.add_row(
                "Low", format_price(price_data.prevday_low),
                "Low", format_price(price_data.day_low),
                "Low", format_price(price_data.min_low)
            )
            price_table.add_row(
                "Close", format_price(price_data.prevday_close),
                "Close", format_price(price_data.day_close),
                "Close", format_price(price_data.min_close)
            )
            price_table.add_row(
                "Volume", format_volume(price_data.prevday_volume),
                "Volume", format_volume(price_data.day_volume),
                "Volume", format_volume(price_data.min_volume)
            )
            price_table.add_row(
                "", "",
                "", "",
                "TS", format_timestamp(price_data.min_timestamp)
            )

            console.print(price_table)

        else:
            console.print(f"[yellow]⚠️  No price data available for {symbol}[/yellow]")

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

        # Display recent sentiment events
        try:
            sentiment_events = data_service.get_sentiment_events(symbol=symbol)

            if sentiment_events:
                # Get sentiment type mapping for display
                all_types = data_service.get_all_sentiment_types(active_only=False)
                type_id_to_name = {t.id: t.name for t in all_types}

                # Take only the 5 most recent (already ordered by date DESC)
                recent_events = sentiment_events[:5]

                console.print()
                console.print(f"[cyan]📰 Recent News Sentiment[/cyan] (Latest {len(recent_events)} of {len(sentiment_events)})")

                # Create sentiment table
                sentiment_table = Table(box=box.ROUNDED, show_header=True, show_footer=True)
                sentiment_table.add_column("Date", style="", no_wrap=True)
                sentiment_table.add_column("Time", style="", no_wrap=True)
                sentiment_table.add_column("Type", style="")
                sentiment_table.add_column("Article", style="dim")

                for event in recent_events:
                    # Format date and time
                    event_date = event.event_date.strftime("%Y-%m-%d")
                    event_time = event.event_time.strftime("%H:%M") if event.event_time else "N/A"

                    # Get type name
                    type_name = type_id_to_name.get(event.sentiment_type_id, "unknown")
                    # Clean up type name (remove "news_" prefix if present)
                    if type_name.startswith("news_"):
                        type_name = type_name[5:]  # Remove "news_" prefix

                    # Get article title from details
                    article_title = event.get_detail("title", "N/A")
                    # Truncate if too long
                    if len(article_title) > 47:
                        article_title = article_title[:44] + "..."

                    sentiment_table.add_row(
                        event_date,
                        event_time,
                        type_name.capitalize(),
                        article_title
                    )

                # Calculate and add overall sentiment score as footer
                try:
                    # Load sentiment config for time window
                    sentiment_config = config_loader.load_sentiment_config()
                    time_window_days = sentiment_config["time_window_days"]

                    sentiment_score = data_service.calculate_asset_sentiment(symbol, limit=10, time_window_days=time_window_days)
                    if sentiment_score is not None:
                        score_value = sentiment_score.overall_score

                        # Format score with color coding
                        if score_value > 0.3:
                            score_str = f"[green]+{score_value:.2f}[/green]"
                        elif score_value < -0.3:
                            score_str = f"[red]{score_value:.2f}[/red]"
                        else:
                            score_str = f"[yellow]{score_value:.2f}[/yellow]"

                        sentiment_table.columns[0].footer = "[bold]Overall:[/bold]"
                        sentiment_table.columns[1].footer = ""
                        sentiment_table.columns[2].footer = f"[bold]{score_str} ({sentiment_score.sentiment_label})[/bold]"
                        sentiment_table.columns[3].footer = f"[dim]{sentiment_score.articles_analyzed} articles within {time_window_days}-day window, {sentiment_score.confidence_level} confidence[/dim]"
                except Exception as e:
                    logger.warning(f"Could not calculate overall sentiment: {e}")

                console.print(sentiment_table)
            else:
                console.print()
                console.print(f"[dim]📰 No sentiment events found for {symbol}[/dim]")

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
        from output.cli_adapter import CLIOutputAdapter

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

        # Use CLI adapter to format and display the result
        CLIOutputAdapter.format_news_result(result, sentiment_score=sentiment_score)

    except Exception as e:
        console.print(f"[red]❌ Failed to fetch news: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)