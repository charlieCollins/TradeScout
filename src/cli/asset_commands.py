"""Asset command group for single asset operations."""

import sys
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


def display_market_context(config):
    """Display market context at the top of asset commands."""
    try:
        # Initialize data service
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from config.universe_config import UNIVERSE_CONFIG

        data_service = config.get_data_service()

        # Get markets from universe config
        universe_config = UNIVERSE_CONFIG.get("default_universe", {})
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
        service = config.get_market_context_service()

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
def asset(config):
    """Single asset data operations and information."""
    pass


@asset.command()
@click.argument("symbol", type=str)
@pass_config
def local(config, symbol: str):
    """
    Show asset information from local database only (no API calls).

    Displays cached asset and price data from the TradeScout database
    without fetching fresh data from external APIs.

    Example:
        tradescout asset local AAPL
    """
    # Display market context at the top
    display_market_context(config)

    symbol = symbol.upper()

    # Initialize data service (but we won't call APIs)
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))

        data_service = config.get_data_service()
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
        asset_table.add_row("Type", asset.asset_type.value if asset.asset_type else "N/A")
        asset_table.add_row("Class", asset.asset_class.value if asset.asset_class else "N/A")
        asset_table.add_row("Currency", asset.currency or "N/A")
        asset_table.add_row("Status", "✅ Active" if asset.is_active else "❌ Inactive")
        asset_table.add_row("Asset ID", str(asset.id))
        asset_table.add_row("Provider ID", str(asset.provider_id))

        console.print(asset_table)

        # Get latest price data from database
        latest_price = data_service.get_latest_asset_price(asset.id)
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
@pass_config
def info(config, symbol: str):
    """
    Show detailed information about a single asset.

    Retrieves and stores fresh asset data from the API including
    symbol, name, market, type, and current pricing information.

    Example:
        tradescout asset info AAPL
    """
    # Display market context at the top
    display_market_context(config)

    symbol = symbol.upper()

    # Initialize data service
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))

        data_service = config.get_data_service()
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
        asset_table.add_row("Type", asset.asset_type.value if asset.asset_type else "N/A")
        asset_table.add_row("Class", asset.asset_class.value if asset.asset_class else "N/A")
        asset_table.add_row("Currency", asset.currency or "N/A")
        asset_table.add_row("Status", "✅ Active" if asset.is_active else "❌ Inactive")
        asset_table.add_row("Asset ID", str(asset.id))
        asset_table.add_row("Provider ID", str(asset.provider_id))

        console.print(asset_table)

        # Get price data (this will fetch fresh data and store it)
        price_data = data_service.get_latest_asset_price(asset.id)
        if price_data:
            console.print()

            # Provider timestamp header
            provider_time = datetime.fromtimestamp(price_data.provider_updated_at / 1_000_000_000).strftime("%Y-%m-%d %H:%M:%S ET")
            console.print(f"{symbol} | Provider Updated: {provider_time}")

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

    except Exception as e:
        console.print(f"[red]❌ Error retrieving asset info: {e}[/red]")
        sys.exit(1)