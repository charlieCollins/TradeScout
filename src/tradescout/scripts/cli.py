#!/usr/bin/env python3
"""
TradeScout CLI Interface

Command-line interface for TradeScout market research assistant.
Provides commands for data collection, analysis, and market research.
"""

import logging
from datetime import datetime
from typing import Optional

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..engine import TradeScoutEngine

# Setup rich console for beautiful output  
console = Console()
logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version="0.1.0", package_name="tradescout")
@click.option(
    "--db-path",
    default=None,
    help="Path to SQLite database file (default: from config)",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.pass_context
def main(ctx, db_path: Optional[str], verbose: bool):
    """
    TradeScout - Personal Market Research Assistant

    Analyze market activity and generate trade suggestions.
    """
    # Setup logging
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Initialize TradeScout engine
    try:
        from ..engine import TradeScoutEngine

        engine = TradeScoutEngine(db_path)
        
        # Display initialization status
        status_messages = engine.display_initialization_status(verbose)
        for message in status_messages:
            console.print(message)
            
    except Exception as e:
        console.print(f"[red]❌ Failed to initialize TradeScout Engine: {e}[/red]")
        ctx.exit(1)

    # Store in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj["engine"] = engine
    ctx.obj["verbose"] = verbose


@main.group()
@click.pass_context
def market(ctx):
    """Market data and analysis commands"""
    pass


@main.group()
@click.pass_context
def system(ctx):
    """System management and configuration commands"""
    pass


@main.group()
@click.pass_context
def asset(ctx):
    """Individual asset data and analysis commands"""
    pass


@asset.command()
@click.argument("symbols", nargs=-1, required=True)
@click.pass_context
def quote(ctx, symbols: tuple):
    """
    Get current market quotes for one or more symbols.

    Examples:
        tradescout asset quote AAPL
        tradescout asset quote AAPL MSFT GOOGL
    """
    engine = ctx.obj["engine"]

    console.print(f"[blue]📈 Getting quotes for: {', '.join(symbols)}[/blue]")
    
    with console.status("[bold blue]Fetching quotes...", spinner="dots"):
        table = engine.display_quotes(list(symbols))
    
    console.print(table)


@asset.command()
@click.argument("symbol")
@click.pass_context
def fundamentals(ctx, symbol: str):
    """
    Show fundamental data for a symbol.

    Example:
        tradescout asset fundamentals AAPL
    """
    engine = ctx.obj["engine"]

    console.print(f"[blue]📋 Fundamental data for {symbol.upper()}[/blue]")

    with console.status(
        f"[bold blue]Fetching fundamentals for {symbol.upper()}...", spinner="dots"
    ):
        display_objects = engine.display_fundamentals(symbol)

    for obj in display_objects:
        console.print(obj)


@system.command()
@click.pass_context
def status(ctx):
    """
    Show TradeScout system status and database statistics.
    """
    engine = ctx.obj["engine"]

    with console.status("[bold blue]Gathering system status...", spinner="dots"):
        display_objects = engine.display_system_status()

    for obj in display_objects:
        console.print(obj)

    return
@system.command()
@click.option(
    "--show-symbols", "-s", is_flag=True, help="Show all symbols in the universe"
)
@click.pass_context
def universe(ctx, show_symbols: bool):
    """
    Display information about the trading universe.

    Shows the size and composition of the stock universe used for scanning.

    Examples:
        tradescout system universe
        tradescout system universe --show-symbols
    """
    engine = ctx.obj["engine"]

    with console.status("[bold blue]Loading trading universe...", spinner="dots"):
        display_objects = engine.display_universe_info("default_liquid_universe", show_symbols)

    for obj in display_objects:
        console.print(obj)

    return


@system.command()
@click.option(
    "--dry-run", 
    is_flag=True,
    help="Show what would be added without making changes"
)
@click.option(
    "--limit",
    default=None,
    type=int,
    help="Maximum number of tickers to fetch from Polygon (if not specified, gets ALL)"
)
@click.pass_context
def universe_update(ctx, dry_run: bool, limit: Optional[int]):
    """
    Update trading universe with new symbols from Polygon all-tickers API.
    
    Creates backup of existing universe file before updating.
    Only adds symbols not already present in the universe.
    
    Examples:
        tradescout system universe-update
        tradescout system universe-update --dry-run
        tradescout system universe-update --limit 1000
    """
    engine = ctx.obj["engine"]
    
    with console.status("[bold blue]Updating universe from Polygon all-tickers API...", spinner="dots"):
        display_objects = engine.update_universe_from_polygon("default_liquid_universe", dry_run, limit)
        
    for obj in display_objects:
        console.print(obj)
        
    return


@market.command()
@click.option("--limit", default=10, help="Number of gainers to show (default: 10)")
@click.option("--force-refresh", "--force", is_flag=True, help="Force refresh cache")
@click.pass_context
def gainers(ctx, limit: int, force_refresh: bool):
    """
    Show top market gainers based on current trading session.

    - Regular Hours: Show regular session movers
    - Pre-Market: Show pre-market gaps vs yesterday close
    - After-Hours: Show after-hours gaps vs today close
    - Closed: Show most recent session data

    Example:
        tradescout market gainers --limit 20
    """
    engine = ctx.obj["engine"]

    # Display market data header first (unless force refresh)
    if not force_refresh:
        market_header = engine.display_market_data_header()
        if market_header:
            console.print(market_header)
    else:
        console.print("[cyan]📊 Market Data: Force refreshing from Polygon API...[/cyan]")
    
    with console.status("[bold green]Fetching market gainers...", spinner="dots"):
        display_objects = engine.display_gainers(limit, force_refresh)

    # Show updated market data status after force refresh
    if force_refresh:
        updated_header = engine.display_market_data_header()
        if updated_header:
            console.print(updated_header)

    for obj in display_objects:
        console.print(obj)


@market.command()
@click.option("--limit", default=10, help="Number of losers to show (default: 10)")
@click.option("--force-refresh", "--force", is_flag=True, help="Force refresh cache")
@click.pass_context
def losers(ctx, limit: int, force_refresh: bool):
    """
    Show top market losers based on current trading session.

    - Regular Hours: Show regular session movers
    - Pre-Market: Show pre-market gaps vs yesterday close
    - After-Hours: Show after-hours gaps vs today close
    - Closed: Show most recent session data

    Example:
        tradescout market losers --limit 20
    """
    engine = ctx.obj["engine"]

    # Display market data header first (unless force refresh)
    if not force_refresh:
        market_header = engine.display_market_data_header()
        if market_header:
            console.print(market_header)
    else:
        console.print("[cyan]📊 Market Data: Force refreshing from Polygon API...[/cyan]")
    
    with console.status("[bold red]Fetching market losers...", spinner="dots"):
        display_objects = engine.display_losers(limit, force_refresh)

    # Show updated market data status after force refresh
    if force_refresh:
        updated_header = engine.display_market_data_header()
        if updated_header:
            console.print(updated_header)

    for obj in display_objects:
        console.print(obj)


@market.command()
@click.option("--limit", default=10, help="Number of stocks per category (default: 10)")
@click.option("--force-refresh", "--force", is_flag=True, help="Force refresh cache")
@click.pass_context
def movers(ctx, limit: int, force_refresh: bool):
    """
    Show comprehensive market movers report (gainers and losers).

    Shows top gainers and losers based on current trading session.

    Example:
        tradescout market movers --limit 10
    """
    engine = ctx.obj["engine"]

    # Display market data header first (unless force refresh)
    if not force_refresh:
        market_header = engine.display_market_data_header()
        if market_header:
            console.print(market_header)
    else:
        console.print("[cyan]📊 Market Data: Force refreshing from Polygon API...[/cyan]")
    
    with console.status("[bold green]Fetching market movers...", spinner="dots"):
        display_objects = engine.display_market_movers(limit, force_refresh)

    # Show updated market data status after force refresh
    if force_refresh:
        updated_header = engine.display_market_data_header()
        if updated_header:
            console.print(updated_header)

    for obj in display_objects:
        console.print(obj)


@market.command()
@click.option("--limit", default=None, type=int, help="Limit gainers/losers to analyze (default: analyze all)")
@click.option("--force-refresh", "--force", is_flag=True, help="Force refresh data")
@click.option("--min-gap", default=2.0, help="Minimum gap percentage (default: 2.0%)")
@click.pass_context
def suggest(ctx, limit: Optional[int], force_refresh: bool, min_gap: float):
    """
    Generate daily gap trading suggestions based on academic research.

    Scans for overnight gaps >= 2.0%, applies six-step binary classification,
    and generates ranked trade recommendations with risk/reward analysis.

    Example:
        tradescout market suggest --limit 10 --min-gap 2.5
    """
    engine = ctx.obj["engine"]

    # Display market data header first (unless force refresh)
    if not force_refresh:
        market_header = engine.display_market_data_header()
        if market_header:
            console.print(market_header)
    else:
        console.print("[cyan]📊 Market Data: Force refreshing from Polygon API...[/cyan]")
    
    with console.status(
        f"[bold blue]Generating gap trading suggestions >= {min_gap}%...",
        spinner="dots",
    ):
        display_objects = engine.display_trade_suggestions(limit, force_refresh, min_gap)

    # Show updated market data status after force refresh
    if force_refresh:
        updated_header = engine.display_market_data_header()
        if updated_header:
            console.print(updated_header)

    for obj in display_objects:
        console.print(obj)


@asset.command()
@click.argument("symbols", nargs=-1, required=True)
@click.option("--date", default=None, help="Date for OHLC data (YYYY-MM-DD), defaults to today")
@click.pass_context
def ohlc(ctx, symbols: tuple, date: str):
    """
    Get OHLC (Open, High, Low, Close) data for one or more symbols.
    
    Shows daily open, high, low, close, volume data from Polygon API.
    
    Examples:
        tradescout asset ohlc AMZN
        tradescout asset ohlc AMZN GOOGL TSLA
        tradescout asset ohlc AMZN --date 2025-09-05
    """
    engine = ctx.obj["engine"]
    
    with console.status(f"[bold blue]Getting OHLC data for {len(symbols)} symbols...", spinner="dots"):
        display_objects = engine.display_ohlc_data(list(symbols), date)
    
    for obj in display_objects:
        console.print(obj)


if __name__ == "__main__":
    main()
