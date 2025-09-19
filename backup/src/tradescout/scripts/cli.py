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
@click.option("--force-refresh", "--force", is_flag=True, help="Force refresh cache")
@click.pass_context
def market(ctx, force_refresh: bool):
    """Market data and analysis commands"""
    ctx.ensure_object(dict)
    ctx.obj["force_refresh"] = force_refresh


@main.group()
@click.pass_context
def system(ctx):
    """System management and configuration commands"""
    pass


@main.group()
@click.option("--force-refresh", "--force", is_flag=True, help="Force refresh cache")
@click.pass_context
def asset(ctx, force_refresh: bool):
    """Individual asset data and analysis commands"""
    ctx.ensure_object(dict)
    ctx.obj["force_refresh"] = force_refresh


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
    force_refresh = ctx.obj.get("force_refresh", False)

    # Display market data header first
    market_header = engine.display_market_data_header()
    if market_header:
        console.print(market_header)

    console.print(f"[blue]📈 Getting quotes for: {', '.join(symbols)}[/blue]")

    from ..utils.progress_context import progress_context

    # Create a progress callback for database operations
    spinner_status = console.status("[bold blue]Fetching quotes...", spinner="dots")

    def update_progress(symbol: str, current: int, total: int):
        """Update spinner with current ticker being processed for database"""
        percentage = (current / total * 100) if total > 0 else 0
        spinner_status.update(
            f"[bold blue]Initializing database: {percentage:3.0f}% - {symbol} ({current}/{total})[/bold blue]"
        )

    with spinner_status, progress_context(update_progress):
        table = engine.display_quotes(list(symbols), force_refresh)

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

    # Display market data header first
    market_header = engine.display_market_data_header()
    if market_header:
        console.print(market_header)

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
    "--name", "-n", default="default_liquid_universe", help="Universe name to display"
)
@click.pass_context
def universe(ctx, show_symbols: bool, name: str):
    """
    Display information about the trading universe (from database).

    Shows the size and composition of the stock universe used for scanning.

    Examples:
        tradescout system universe
        tradescout system universe --show-symbols
        tradescout system universe --name gap_trading
    """
    from ..storage.universe_manager import UniverseManager
    from ..storage.sqlite_repository import SQLiteDatabaseManager

    db_manager = SQLiteDatabaseManager("storage/tradescout.db")
    manager = UniverseManager(db_manager)

    try:
        # Get universe symbols from database
        symbols = manager.get_universe_assets(name)

        if not symbols:
            console.print(f"[yellow]Universe '{name}' not found or empty[/yellow]")
            return

        # Create display panel
        from rich.panel import Panel
        from rich.text import Text

        info_text = Text()
        info_text.append(f"Universe: ", style="bold")
        info_text.append(f"{name}\n", style="cyan")
        info_text.append(f"Total Symbols: ", style="bold")
        info_text.append(f"{len(symbols):,}\n", style="green")
        info_text.append(f"Source: ", style="bold")
        info_text.append("SQLite Database\n")

        panel = Panel(info_text, title="Trading Universe", border_style="cyan")
        console.print(panel)

        if show_symbols:
            # Create table for symbols
            from rich.table import Table
            from rich import box

            table = Table(title=f"Symbols in {name}", box=box.ROUNDED)
            table.add_column("Index", justify="right", style="dim")
            table.add_column("Symbol", style="cyan")

            for i, symbol in enumerate(symbols, 1):
                table.add_row(str(i), symbol)

            console.print(table)

    except Exception as e:
        console.print(f"[red]Error loading universe: {e}[/red]")

    return


@system.command("universe-list")
@click.pass_context
def universe_list(ctx):
    """List all available universes"""
    from ..storage.universe_manager import UniverseManager
    from ..storage.sqlite_repository import SQLiteDatabaseManager

    db_manager = SQLiteDatabaseManager("storage/tradescout.db")
    manager = UniverseManager(db_manager)

    conn = manager._get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT u.name, u.description,
                   COUNT(DISTINCT um.asset_id) as asset_count
            FROM universes u
            LEFT JOIN universe_memberships um ON u.id = um.universe_id AND um.is_active = 1
            GROUP BY u.id, u.name, u.description
            ORDER BY asset_count DESC
        """
        )

        universes = cursor.fetchall()

        # Create table
        from rich.table import Table
        from rich import box

        table = Table(title="Asset Universes", box=box.ROUNDED)
        table.add_column("Universe", style="cyan")
        table.add_column("Assets", justify="right")
        table.add_column("Description", max_width=50)

        for univ in universes:
            table.add_row(
                univ[0],  # name
                str(univ[2]),  # asset_count
                univ[1] or "No description",  # description
            )

        console.print(table)

    finally:
        conn.close()


@system.command("universe-add")
@click.argument("symbol")
@click.argument("universe_name")
@click.option("--reason", help="Reason for adding")
@click.pass_context
def universe_add(ctx, symbol: str, universe_name: str, reason: str):
    """Add a symbol to a universe"""
    from ..storage.universe_manager import UniverseManager
    from ..storage.sqlite_repository import SQLiteDatabaseManager

    db_manager = SQLiteDatabaseManager("storage/tradescout.db")
    manager = UniverseManager(db_manager)

    try:
        if manager.add_to_universe(symbol, universe_name, reason):
            console.print(f"[green]✅ Added {symbol} to {universe_name}[/green]")
        else:
            console.print(f"[red]Failed to add {symbol} to {universe_name}[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@market.command()
@click.option("--limit", default=10, help="Number of gainers to show (default: 10)")
@click.pass_context
def gainers(ctx, limit: int):
    force_refresh = ctx.obj.get("force_refresh", False)
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
        console.print(
            "[cyan]📊 Market Data: Force refreshing from Polygon API...[/cyan]"
        )

    from ..utils.progress_context import progress_context

    # Create a progress callback for database operations
    spinner_status = console.status(
        "[bold green]Fetching market gainers...", spinner="dots"
    )

    def update_progress(symbol: str, current: int, total: int):
        """Update spinner with current ticker being processed for database"""
        percentage = (current / total * 100) if total > 0 else 0
        spinner_status.update(
            f"[bold green]Initializing database: {percentage:3.0f}% - {symbol} ({current}/{total})[/bold green]"
        )

    with spinner_status, progress_context(update_progress):
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
@click.pass_context
def losers(ctx, limit: int):
    force_refresh = ctx.obj.get("force_refresh", False)
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
        console.print(
            "[cyan]📊 Market Data: Force refreshing from Polygon API...[/cyan]"
        )

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
@click.pass_context
def movers(ctx, limit: int):
    force_refresh = ctx.obj.get("force_refresh", False)
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
        console.print(
            "[cyan]📊 Market Data: Force refreshing from Polygon API...[/cyan]"
        )

    with console.status("[bold green]Fetching market movers...", spinner="dots"):
        display_objects = engine.display_market_movers(limit, force_refresh)

    # Show updated market data status after force refresh
    if force_refresh:
        updated_header = engine.display_market_data_header()
        if updated_header:
            console.print(updated_header)

    for obj in display_objects:
        console.print(obj)


@market.command("suggest-single")
@click.argument("symbol", type=str)
@click.pass_context
def suggest_single(ctx, symbol: str):
    """
    Analyze gap trading potential for a SINGLE symbol.

    Shows detailed gap analysis including:
    - Previous session close
    - Current real-time price (including extended hours)
    - Gap percentage and direction
    - Binary classification results
    - Trading recommendation if qualified

    Example:
        tradescout market suggest-single AAPL
        tradescout market suggest-single TSLA --force
    """
    force_refresh = ctx.obj.get("force_refresh", False)
    engine = ctx.obj["engine"]
    symbol = symbol.upper()

    # Display session header
    session_header = engine.get_session_header("single_symbol_analysis")
    console.print(session_header)
    console.print(f"[bold cyan]Analyzing {symbol}...[/bold cyan]\n")

    with console.status(
        f"[bold blue]Fetching real-time data for {symbol}...", spinner="dots"
    ):
        display_objects = engine.analyze_single_symbol_gap(symbol, force_refresh)

    for obj in display_objects:
        console.print(obj)


@market.command()
@click.option(
    "--limit",
    default=None,
    type=int,
    help="Limit gainers/losers to analyze (default: analyze all)",
)
@click.option("--min-gap", default=2.0, help="Minimum gap percentage (default: 2.0%)")
@click.pass_context
def suggest(ctx, limit: Optional[int], min_gap: float):
    """
    Generate daily gap trading suggestions based on academic research.

    Scans for overnight gaps >= 2.0%, applies six-step binary classification,
    and generates ranked trade recommendations with risk/reward analysis.

    Example:
        tradescout market suggest --limit 10 --min-gap 2.5
    """
    force_refresh = ctx.obj.get("force_refresh", False)
    engine = ctx.obj["engine"]

    # Display market data header first (unless force refresh)
    if not force_refresh:
        market_header = engine.display_market_data_header()
        if market_header:
            console.print(market_header)
    else:
        console.print(
            "[cyan]📊 Market Data: Force refreshing from Polygon API...[/cyan]"
        )

    # Display session header before starting the spinner
    session_header = engine.get_session_header("suggestions")
    console.print(session_header)

    from ..utils.progress_context import progress_context

    # Create a progress callback for the spinner
    spinner_status = console.status(
        f"[bold blue]Generating gap trading suggestions >= {min_gap}%...",
        spinner="dots",
    )

    def update_progress(symbol: str, current: int, total: int):
        """Update spinner with current ticker being processed"""
        percentage = (current / total * 100) if total > 0 else 0
        spinner_status.update(
            f"[bold blue]Analyzing gaps: {percentage:3.0f}% - {symbol} ({current}/{total})[/bold blue]"
        )

    with spinner_status, progress_context(update_progress):
        display_objects = engine.display_trade_suggestions(
            limit, force_refresh, min_gap
        )

    # Show updated market data status after force refresh
    if force_refresh:
        updated_header = engine.display_market_data_header()
        if updated_header:
            console.print(updated_header)

    for obj in display_objects:
        console.print(obj)


@asset.command()
@click.argument("symbols", nargs=-1, required=True)
@click.option(
    "--date", default=None, help="Date for OHLC data (YYYY-MM-DD), defaults to today"
)
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

    # Display market data header first
    market_header = engine.display_market_data_header()
    if market_header:
        console.print(market_header)

    with console.status(
        f"[bold blue]Getting OHLC data for {len(symbols)} symbols...", spinner="dots"
    ):
        display_objects = engine.display_ohlc_data(list(symbols), date)

    for obj in display_objects:
        console.print(obj)


if __name__ == "__main__":
    main()
