"""Market command group for bulk market operations."""

import sys
from pathlib import Path
from datetime import datetime

import click
from rich.console import Console
from rich.table import Table
from rich import box
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.live import Live
from rich.panel import Panel

from .main import pass_config
from .asset_commands import display_market_context

console = Console()


@click.group()
@pass_config
def market(config):
    """Market-wide data operations and status."""
    pass


@market.command()
@pass_config
def info(config):
    """
    Show market snapshot status and metadata.

    Displays when the market snapshot was last run and current market status.

    Example:
        tradescout market info
    """

    # Display market context at the top
    display_market_context(config)

    # Get market context (which includes comprehensive market information)
    with console.status("[bold blue]Checking market context...", spinner="dots"):
        try:
            market_context = config.market_context
        except Exception as e:
            console.print(f"[red]❌ Failed to get market context: {e}[/red]")
            return

    # Display market context
    context_table = Table(
        title="Market Context",
        box=box.ROUNDED,
        header_style="bold blue"
    )
    context_table.add_column("Field", style="bold", width=20)
    context_table.add_column("Value", style="", width=30)

    if market_context:
        # Main market info
        context_table.add_row("Market", market_context.market.name)
        context_table.add_row("Current Session", market_context.current_session.value.title().replace('_', ' '))
        context_table.add_row("Trading Day", "✅ Yes" if market_context.is_trading_day else "❌ No")
        context_table.add_row("Market Open", "✅ Yes" if market_context.is_market_open else "❌ No")

        # Session details
        if market_context.current_session.value == "premarket":
            context_table.add_row("Premarket", "✅ Active")
        elif market_context.current_session.value == "afterhours":
            context_table.add_row("After Hours", "✅ Active")
        elif market_context.current_session.value == "regular":
            context_table.add_row("Regular Hours", "✅ Active")

        # Trading dates
        context_table.add_row("Previous Trading", str(market_context.previous_trading_date))
        if market_context.next_trading_date:
            context_table.add_row("Next Trading", str(market_context.next_trading_date))

        # Current time in market timezone
        context_table.add_row("Current Time", market_context.current_time.strftime("%Y-%m-%d %H:%M:%S %Z"))

    console.print(context_table)

    # Check last market snapshot run metadata
    console.print("")
    console.print("[bold]Last Market Snapshot Run:[/bold]")

    try:
        data_provider = config.get_data_provider()
        snapshot_metadata = data_provider.get_market_snapshot_metadata()

        if snapshot_metadata:
            snapshot_table = Table(
                box=box.ROUNDED,
                show_header=False
            )
            snapshot_table.add_column("", style="bold", width=20)
            snapshot_table.add_column("", style="", width=40)

            # Status with emoji
            status = snapshot_metadata.get('status', 'unknown')
            status_display = {
                "completed": "[green]✅ Completed[/green]",
                "partial": "[yellow]⚠️  Partial[/yellow]",
                "failed": "[red]❌ Failed[/red]",
                "running": "[blue]🔄 Running[/blue]"
            }.get(status, status)

            snapshot_table.add_row("Status", status_display)

            if 'completed_at' in snapshot_metadata and snapshot_metadata['completed_at']:
                completed_at = datetime.fromisoformat(snapshot_metadata['completed_at'])
                snapshot_table.add_row("Completed", completed_at.strftime("%Y-%m-%d %H:%M:%S"))

                # Calculate age
                age = datetime.now() - completed_at
                age_str = f"{age.total_seconds() / 60:.1f} minutes ago"
                if age.total_seconds() > 3600:
                    age_str = f"{age.total_seconds() / 3600:.1f} hours ago"
                if age.total_seconds() > 86400:
                    age_str = f"{age.total_seconds() / 86400:.1f} days ago"
                snapshot_table.add_row("Run age", age_str)

            if 'total_symbols' in snapshot_metadata:
                snapshot_table.add_row("Total symbols", f"{snapshot_metadata['total_symbols']:,}")

            if 'successful_updates' in snapshot_metadata:
                snapshot_table.add_row("Successful", f"{snapshot_metadata['successful_updates']:,}")

            if 'failed_updates' in snapshot_metadata and snapshot_metadata['failed_updates'] > 0:
                snapshot_table.add_row("Failed", f"[red]{snapshot_metadata['failed_updates']:,}[/red]")

            if 'successful_updates' in snapshot_metadata and 'total_symbols' in snapshot_metadata:
                if snapshot_metadata['total_symbols'] > 0:
                    success_rate = (snapshot_metadata['successful_updates'] / snapshot_metadata['total_symbols'] * 100)
                    snapshot_table.add_row("Success rate", f"{success_rate:.1f}%")

            if 'api_calls_made' in snapshot_metadata and snapshot_metadata['api_calls_made']:
                snapshot_table.add_row("API calls", f"{snapshot_metadata['api_calls_made']:,}")

            if 'error_message' in snapshot_metadata and snapshot_metadata['error_message']:
                snapshot_table.add_row("Error", f"[red]{snapshot_metadata['error_message']}[/red]")

            console.print(snapshot_table)

            # Check if currently running
            if status == 'running':
                console.print("")
                console.print(f"[yellow]⚠️  A market snapshot is currently running[/yellow]")

        else:
            console.print("[yellow]No market snapshot data available[/yellow]")
            console.print("[dim]Run 'tradescout market update' to fetch market data[/dim]")

    except Exception as e:
        console.print("[yellow]No market snapshot data available[/yellow]")
        console.print("[dim]Run 'tradescout market update' to fetch market data[/dim]")


@market.command()
@pass_config
def update(config):
    """
    Update market snapshot data for all assets in universe.

    Fetches fresh market data from Polygon API and updates the database
    with current price information for all assets in the default universe.

    Example:
        tradescout market update
    """

    # Display market context at the top
    display_market_context(config)

    # Initialize data provider
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from provider.data_provider import PolygonDataProvider

        data_provider = config.get_data_provider()
    except Exception as e:
        console.print(f"[red]❌ Failed to initialize data provider: {e}[/red]")
        sys.exit(1)

    # Check if we need to update based on snapshot metadata
    console.print("[bold blue]Checking last update time...[/bold blue]")
    try:
        snapshot_metadata = data_provider.get_market_snapshot_metadata()
        if snapshot_metadata and snapshot_metadata.get('status') == 'running':
            console.print("[yellow]⚠️  Market snapshot is currently running. Please wait.[/yellow]")
            return

        # Could add time-based checks here if needed
        # if snapshot_metadata and recent enough: return early

    except Exception as e:
        console.print(f"[yellow]⚠️  Could not check snapshot metadata: {e}[/yellow]")

    # Get universe assets from data provider
    console.print("[bold blue]Loading asset universe...[/bold blue]")
    try:
        universe_symbols = data_provider.get_active_universe_symbols()

        if not universe_symbols:
            console.print("[red]❌ No active assets found in universe[/red]")
            console.print("[yellow]💡 Run 'tradescout bootstrap universe' to populate the universe[/yellow]")
            return

        console.print(f"[green]✅ Found {len(universe_symbols)} assets in universe[/green]")

    except Exception as e:
        console.print(f"[red]❌ Failed to load universe: {e}[/red]")
        return

    # Start snapshot run tracking
    console.print("[bold blue]Starting market snapshot run...[/bold blue]")
    operation_id = data_provider.start_market_snapshot_run(len(universe_symbols))
    if not operation_id:
        console.print("[red]❌ Failed to start snapshot run tracking[/red]")
        return

    # Fetch bulk market snapshot - chunked API calls for universe symbols
    console.print(f"[bold blue]Fetching bulk market snapshot for {len(universe_symbols)} universe symbols...[/bold blue]")

    try:
        # Calculate chunk info for progress display
        chunk_size = 100
        total_chunks = (len(universe_symbols) + chunk_size - 1) // chunk_size

        console.print(f"[bold blue]Making {total_chunks} API calls (100 symbols per chunk)...[/bold blue]")

        # Progress tracking for chunks
        progress_text = f"Processing chunk 0/{total_chunks}"

        def update_progress(chunk_num, total, chunk_symbols):
            nonlocal progress_text
            progress_text = f"Processing chunk {chunk_num}/{total} ({chunk_symbols} symbols)"

        with Live(progress_text, console=console, refresh_per_second=10) as live:
            # Chunked API calls for universe symbols (100 symbols per chunk)
            bulk_snapshot_data = data_provider.get_market_snapshot(
                universe_symbols,
                progress_callback=lambda chunk_num, total, symbols: (
                    live.update(f"[blue]Processing chunk {chunk_num}/{total} ({symbols} symbols)[/blue]")
                )
            )

        if not bulk_snapshot_data or not bulk_snapshot_data.tickers:
            console.print("[red]❌ No data returned from bulk snapshot API[/red]")
            data_provider.complete_market_snapshot_run(operation_id, 0, len(universe_symbols), total_chunks, "Failed: No data returned")
            return

        console.print(f"[green]✅ Received data for {len(bulk_snapshot_data.tickers)} symbols[/green]")

        # Process each ticker from the chunked response
        total_updated = 0
        total_errors = 0
        total_skipped = 0

        # Track processing categories
        processing_stats = {
            "with_recent_trading": 0,    # updated > 0 (actively trading)
            "without_recent_trading": 0, # updated = 0 (no recent activity, still valid data)
            "no_asset_data": 0,          # Asset not found in database (actual error)
            "transform_failed": 0,       # Failed to transform data (actual error)
            "save_failed": 0,           # Database save failed (actual error)
            "other_errors": []          # Other exceptions with details (actual errors)
        }

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:

            processing_task = progress.add_task("Processing snapshot data...", total=len(bulk_snapshot_data.tickers))

            # Process each ticker from the MarketSnapshot model
            for symbol, ticker_snapshot in bulk_snapshot_data.tickers.items():

                try:
                    # Get asset data for this symbol
                    asset_data = data_provider.get_asset_data(symbol)
                    if not asset_data:
                        total_errors += 1
                        processing_stats["no_asset_data"] += 1
                        progress.update(processing_task, advance=1)
                        continue

                    asset, market = asset_data
                    asset_id = asset.id

                    # Transform TickerSnapshot to AssetPrice using the model
                    asset_price = data_provider.transform_ticker_snapshot_to_asset_price(symbol, asset_id, ticker_snapshot)

                    if not asset_price:
                        total_errors += 1
                        processing_stats["transform_failed"] += 1
                        progress.update(processing_task, advance=1)
                        continue

                    # Track whether this symbol had recent trading activity
                    # Check if last_timestamp exists and is not None
                    has_recent_trading = ticker_snapshot.last_timestamp is not None
                    if has_recent_trading:
                        processing_stats["with_recent_trading"] += 1
                    else:
                        processing_stats["without_recent_trading"] += 1

                    if data_provider.save_asset_price_data(asset_price):
                        total_updated += 1
                    else:
                        total_errors += 1
                        processing_stats["save_failed"] += 1

                except Exception as e:
                    total_errors += 1
                    processing_stats["other_errors"].append(f"{symbol}: {str(e)}")

                progress.update(processing_task, advance=1)

        # Complete snapshot run tracking
        error_message = f"Errors: {total_errors}" if total_errors > 0 else None
        data_provider.complete_market_snapshot_run(operation_id, total_updated, total_errors, total_chunks, error_message)

    except Exception as e:
        console.print(f"[red]❌ Error during bulk snapshot: {e}[/red]")
        data_provider.complete_market_snapshot_run(operation_id, 0, len(universe_symbols), total_chunks, f"API Error: {e}")
        return

    # Summary
    console.print("")
    console.print("[bold green]Market Update Complete[/bold green]")

    summary_table = Table(
        box=box.ROUNDED,
        show_header=False
    )
    summary_table.add_column("", style="bold", width=20)
    summary_table.add_column("", style="", width=15)

    summary_table.add_row("Assets processed", f"{total_updated + total_errors:,}")
    summary_table.add_row("Successfully updated", f"{total_updated:,}")
    summary_table.add_row("Errors", f"{total_errors:,}")
    summary_table.add_row("Success rate", f"{(total_updated / (total_updated + total_errors) * 100):.1f}%" if (total_updated + total_errors) > 0 else "0%")
    summary_table.add_row("Completed at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    console.print(summary_table)

    # Processing breakdown
    console.print("")
    console.print("[bold blue]Processing Breakdown:[/bold blue]")

    breakdown_table = Table(
        box=box.ROUNDED,
        show_header=False
    )
    breakdown_table.add_column("Category", style="bold", width=25)
    breakdown_table.add_column("Count", style="", width=10)
    breakdown_table.add_column("Description", style="dim", width=40)

    # Show successful processing categories
    if processing_stats["with_recent_trading"] > 0:
        breakdown_table.add_row(
            "With recent trading",
            f"{processing_stats['with_recent_trading']:,}",
            "Symbols with active trading data (updated > 0)"
        )

    if processing_stats["without_recent_trading"] > 0:
        breakdown_table.add_row(
            "Without recent trading",
            f"{processing_stats['without_recent_trading']:,}",
            "Symbols with prevDay data only (updated = 0)"
        )

    # Show error categories if there were errors
    if total_errors > 0:
        breakdown_table.add_row("", "", "")  # Separator
        breakdown_table.add_row("[bold red]ERRORS", "", "")

        if processing_stats["no_asset_data"] > 0:
            breakdown_table.add_row(
                "Asset not in database",
                f"{processing_stats['no_asset_data']:,}",
                "Symbols in snapshot but not in our universe database"
            )

        if processing_stats["transform_failed"] > 0:
            breakdown_table.add_row(
                "Data transformation failed",
                f"{processing_stats['transform_failed']:,}",
                "Failed to convert snapshot data to asset price format"
            )

        if processing_stats["save_failed"] > 0:
            breakdown_table.add_row(
                "Database save failed",
                f"{processing_stats['save_failed']:,}",
                "Failed to write asset price data to database"
            )

        if processing_stats["other_errors"]:
            breakdown_table.add_row(
                "Other exceptions",
                f"{len(processing_stats['other_errors']):,}",
                "Various processing errors (see details below)"
            )

    console.print(breakdown_table)

    # Show details of other errors if any (but limit to first 5)
    if processing_stats["other_errors"]:
        console.print("")
        console.print("[dim]Other error details (first 5):[/dim]")
        for i, error in enumerate(processing_stats["other_errors"][:5]):
            console.print(f"[dim]  • {error}[/dim]")
        if len(processing_stats["other_errors"]) > 5:
            console.print(f"[dim]  ... and {len(processing_stats['other_errors']) - 5} more[/dim]")


@market.command()
@pass_config
def context(config):
    """Show current market context for default universe"""

    try:
        # Get universe statistics using data provider
        active_universe = config.get_active_universe()
        data_provider = config.get_data_provider()

        # Get universe market breakdown
        universe_markets = data_provider.get_universe_market_breakdown(active_universe)

        # Get total universe count
        universe_stats = data_provider.get_universe_stats(active_universe)
        total_universe = universe_stats.total_members if universe_stats else 0

        # Get market context - using NYSE as representative since NASDAQ and NYSE share same sessions
        ctx = config.market_context

        # Create main context table
        table = Table(title=f"📊 {active_universe.title()} Market Context", show_header=True)
        table.add_column("Property", style="cyan", width=25)
        table.add_column("Value", style="white")

        # Show universe composition - use abbreviated names for conciseness
        market_names = []
        for code, name, _ in universe_markets:
            if code == "XNYS":
                market_names.append("NYSE")
            elif code == "XNAS":
                market_names.append("NASDAQ")
            else:
                market_names.append(f"{name} ({code})")

        markets_str = ", ".join(market_names)
        table.add_row("Universe Markets", markets_str)
        table.add_row("Total Universe Assets", f"{total_universe:,}")

        # Add market distribution with abbreviated names
        for code, name, count in universe_markets:
            pct = (count / total_universe * 100) if total_universe > 0 else 0
            if code == "XNYS":
                display_name = "NYSE"
            elif code == "XNAS":
                display_name = "NASDAQ"
            else:
                display_name = code
            table.add_row(f"  └─ {display_name}", f"{count:,} ({pct:.1f}%)")

        table.add_row("", "")  # Separator

        # Trading status (same for both NASDAQ and NYSE)
        table.add_row("Is Trading Day", "✅ Yes" if ctx.is_trading_day else "❌ No")
        table.add_row("Previous Trading Date", str(ctx.previous_trading_date))
        table.add_row("Current Session", ctx.current_session.value)

        # Add additional context
        table.add_row("Day Type", ctx.day_type.value.replace('_', ' ').title())
        table.add_row("Current Date", str(ctx.current_date))
        table.add_row("Current Time", ctx.current_time.strftime("%Y-%m-%d %H:%M:%S %Z"))
        table.add_row("Session Name (for screeners)", ctx.session_name)

        # Market status indicators
        table.add_row("Market Open", "✅ Yes" if ctx.is_market_open else "❌ No")
        table.add_row("Regular Hours", "✅ Yes" if ctx.is_regular_hours else "❌ No")
        table.add_row("Extended Hours", "✅ Yes" if ctx.is_extended_hours else "❌ No")

        if ctx.next_trading_date:
            table.add_row("Next Trading Date", str(ctx.next_trading_date))

        console.print(table)

        # Show session times
        session_times = ctx.get_session_times()
        if any(session_times.values()):
            console.print()
            times_table = Table(title="🕐 Session Times (Today)", show_header=True)
            times_table.add_column("Session", style="cyan")
            times_table.add_column("Time", style="white")

            for session_name, time_val in session_times.items():
                formatted_name = session_name.replace('_', ' ').title()
                if time_val:
                    formatted_time = time_val.strftime("%H:%M")
                else:
                    formatted_time = "N/A"
                times_table.add_row(formatted_name, formatted_time)

            console.print(times_table)

        # Show timezone info
        console.print()
        console.print(Panel(
            f"Market Timezone: {ctx.market.timezone}\n"
            f"Currency: {ctx.market.currency}\n"
            f"Extended Hours Support: {'Yes' if ctx.market.has_extended_hours else 'No'}",
            title="Market Details"
        ))

    except Exception as e:
        console.print(f"❌ Error getting market context: {e}")


@market.command()
@pass_config
def session(config):
    """Show just the current session info"""

    try:
        ctx = config.market_context

        # Simple session display
        console.print(f"Current Session: [bold]{ctx.current_session.value}[/bold]")
        console.print(f"Session Name (screeners): [bold]{ctx.session_name}[/bold]")
        console.print(f"Market Status: [bold]{'OPEN' if ctx.is_market_open else 'CLOSED'}[/bold]")

        if ctx.is_extended_hours:
            console.print("[yellow]⚠️ Extended hours trading[/yellow]")

        if not ctx.is_trading_day:
            console.print(f"[red]📅 Not a trading day ({ctx.day_type.value})[/red]")

    except Exception as e:
        console.print(f"❌ Error getting session info: {e}")