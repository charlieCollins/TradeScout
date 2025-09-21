"""Analyze command group for AssetAnalyzer integration."""

import sys
from pathlib import Path
from datetime import datetime

import click
from rich.console import Console
from rich.table import Table
from rich import box
from rich.columns import Columns
from rich.align import Align

from .main import pass_config, create_header

console = Console()


@click.group()
@pass_config
def analyze(config):
    """Asset analysis commands using TradeScout analyzers."""
    pass


@analyze.command()
@click.argument("symbol", type=str)
@pass_config
def asset(config, symbol: str):
    """
    Show detailed information about a single asset.

    Retrieves asset data from the TradeScout database including
    symbol, name, market, type, and trading status.

    Example:
        tradescout analyze asset AAPL
    """
    symbol = symbol.upper()

    # Initialize AssetAnalyzer with data provider
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from analyzer.asset_analyzer import AssetAnalyzer
        from provider.data_provider import PolygonDataProvider
        from config.api_keys import POLYGON_API_KEY

        data_provider = PolygonDataProvider(POLYGON_API_KEY, config.db_manager)
        analyzer = AssetAnalyzer(data_provider)
    except Exception as e:
        console.print(f"[red]❌ Failed to initialize analyzer: {e}[/red]")
        sys.exit(1)

    # Get asset data
    with console.status(f"[bold blue]Retrieving data for {symbol}...", spinner="dots"):
        result = analyzer.get_asset_data(symbol)

    if not result:
        console.print(f"[red]❌ Asset '{symbol}' not found in database[/red]")
        console.print("[yellow]💡 Make sure the symbol is correct and the database is populated[/yellow]")
        return

    asset, market = result

    # Get price data (automatically fetches from API if stale or missing)
    price_data = analyzer.get_asset_price_data(asset.id)

    # Create asset information table
    asset_table = Table(
        box=box.ROUNDED,
        header_style="bold blue"
    )
    asset_table.add_column(symbol, style="bold", min_width=12)
    asset_table.add_column("", style="", min_width=30)

    # Add asset rows
    asset_table.add_row("Name", asset.display_name)
    asset_table.add_row("Market", market.display_name)
    asset_table.add_row("Type", asset.asset_type.value.title())
    asset_table.add_row("Class", asset.asset_class.value.title())
    asset_table.add_row("Currency", asset.currency)

    # Status with color coding
    status = "✅ Active" if asset.is_active else "❌ Inactive"
    status_style = "green" if asset.is_active else "red"
    asset_table.add_row("Status", f"[{status_style}]{status}[/{status_style}]")

    asset_table.add_row("Asset ID", str(asset.id))
    asset_table.add_row("Provider ID", str(asset.provider_id))

    # Create unified price table with provider timestamp in header
    provider_title = ""
    if price_data and price_data.provider_updated_at:
        provider_updated = datetime.fromtimestamp(price_data.provider_updated_at / 1_000_000_000)
        provider_title = f"{symbol} | Provider Updated: {provider_updated.strftime('%Y-%m-%d %H:%M:%S')} ET"

    price_table = Table(
        title=provider_title if provider_title else "",
        title_justify="left",
        box=box.ROUNDED,
        show_header=True
    )

    # Add 6 columns (2 for each section) with tighter spacing
    price_table.add_column("[bold green]PrevDay[/bold green]", style="bold", width=8)
    price_table.add_column("", style="", width=10)
    price_table.add_column("[bold blue]Day[/bold blue]", style="bold", width=8)
    price_table.add_column("", style="", width=10)
    price_table.add_column("[bold yellow]Min[/bold yellow]", style="bold", width=8)
    price_table.add_column("", style="", width=20)

    # Add data rows
    price_table.add_row(
        "Open", f"${price_data.prevday_open:.2f}" if price_data and price_data.prevday_open else "N/A",
        "Open", f"${price_data.day_open:.2f}" if price_data and price_data.day_open else "N/A",
        "Open", f"${price_data.min_open:.2f}" if price_data and price_data.min_open else "N/A"
    )
    price_table.add_row(
        "High", f"${price_data.prevday_high:.2f}" if price_data and price_data.prevday_high else "N/A",
        "High", f"${price_data.day_high:.2f}" if price_data and price_data.day_high else "N/A",
        "High", f"${price_data.min_high:.2f}" if price_data and price_data.min_high else "N/A"
    )
    price_table.add_row(
        "Low", f"${price_data.prevday_low:.2f}" if price_data and price_data.prevday_low else "N/A",
        "Low", f"${price_data.day_low:.2f}" if price_data and price_data.day_low else "N/A",
        "Low", f"${price_data.min_low:.2f}" if price_data and price_data.min_low else "N/A"
    )
    price_table.add_row(
        "Close", f"${price_data.prevday_close:.2f}" if price_data and price_data.prevday_close else "N/A",
        "Close", f"${price_data.day_close:.2f}" if price_data and price_data.day_close else "N/A",
        "Close", f"${price_data.min_close:.2f}" if price_data and price_data.min_close else "N/A"
    )
    price_table.add_row(
        "Volume", f"{price_data.prevday_volume:,}" if price_data and price_data.prevday_volume else "N/A",
        "Volume", f"{price_data.day_volume:,}" if price_data and price_data.day_volume else "N/A",
        "Volume", f"{price_data.min_volume:,}" if price_data and price_data.min_volume else "N/A"
    )

    # Add timestamp row for min data only
    min_timestamp = "N/A"
    if price_data and price_data.min_timestamp:
        min_datetime = datetime.fromtimestamp(price_data.min_timestamp / 1000)
        min_timestamp = min_datetime.strftime("%Y-%m-%d %H:%M:%S")

    price_table.add_row("", "", "", "", "TS", min_timestamp)

    console.print(asset_table)
    console.print("")  # Add spacing

    # Display unified price table
    console.print(price_table)
    console.print("")  # Add spacing