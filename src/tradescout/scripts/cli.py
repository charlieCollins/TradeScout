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


@market.command()
@click.argument("symbols", nargs=-1, required=True)
@click.pass_context
def quote(ctx, symbols: tuple):
    """
    Get current market quotes for one or more symbols.

    Examples:
        tradescout market quote AAPL
        tradescout market quote AAPL MSFT GOOGL
    """
    engine = ctx.obj["engine"]

    console.print(f"[blue]📈 Getting quotes for: {', '.join(symbols)}[/blue]")
    
    with console.status("[bold blue]Fetching quotes...", spinner="dots"):
        table = engine.display_quotes(list(symbols))
    
    console.print(table)


@market.command()
@click.argument("symbol")
@click.pass_context
def fundamentals(ctx, symbol: str):
    """
    Show fundamental data for a symbol.

    Example:
        tradescout market fundamentals AAPL
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
@click.option(
    "--universe",
    "-u",
    default="default_liquid_universe",
    help="Universe name to display",
)
@click.pass_context
def universe(ctx, show_symbols: bool, universe: str):
    """
    Display information about the screening universe.

    Shows the size and composition of the stock universe used for scanning.

    Examples:
        tradescout system universe
        tradescout system universe --show-symbols
        tradescout system universe --universe default_liquid_universe
    """
    engine = ctx.obj["engine"]

    with console.status(f"[bold blue]Loading universe '{universe}'...", spinner="dots"):
        display_objects = engine.display_universe_info(universe, show_symbols)

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

    with console.status("[bold green]Fetching market gainers...", spinner="dots"):
        display_objects = engine.display_gainers(limit, force_refresh)

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

    with console.status("[bold red]Fetching market losers...", spinner="dots"):
        display_objects = engine.display_losers(limit, force_refresh)

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

    with console.status("[bold green]Fetching market movers...", spinner="dots"):
        display_objects = engine.display_market_movers(limit, force_refresh)

    for obj in display_objects:
        console.print(obj)


@market.command()
@click.option("--limit", default=5, help="Maximum number of suggestions (default: 5)")
@click.option("--force-refresh", "--force", is_flag=True, help="Force refresh data")
@click.option("--min-gap", default=2.0, help="Minimum gap percentage (default: 2.0%)")
@click.pass_context
def suggest(ctx, limit: int, force_refresh: bool, min_gap: float):
    """
    Generate daily gap trading suggestions based on academic research.

    Scans for overnight gaps >= 2.0%, applies six-step binary classification,
    and generates ranked trade recommendations with risk/reward analysis.

    Example:
        tradescout market suggest --limit 10 --min-gap 2.5
    """
    engine = ctx.obj["engine"]
    
    with console.status(
        f"[bold blue]Generating gap trading suggestions >= {min_gap}%...",
        spinner="dots",
    ):
        display_objects = engine.display_trade_suggestions(limit, force_refresh, min_gap)

    for obj in display_objects:
        console.print(obj)


if __name__ == "__main__":
    main()
