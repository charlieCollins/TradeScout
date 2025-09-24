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

from .main import pass_config

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
    # Initialize data provider
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from provider.data_provider import PolygonDataProvider

        data_provider = PolygonDataProvider(config.db_manager)
    except Exception as e:
        console.print(f"[red]❌ Failed to initialize data provider: {e}[/red]")
        sys.exit(1)

    # Get market status from API
    with console.status("[bold blue]Checking market status...", spinner="dots"):
        try:
            market_status = data_provider.get_market_status()
        except Exception as e:
            console.print(f"[red]❌ Failed to get market status: {e}[/red]")
            return

    # Display market status
    status_table = Table(
        title="Market Status",
        box=box.ROUNDED,
        header_style="bold blue"
    )
    status_table.add_column("Field", style="bold", width=20)
    status_table.add_column("Value", style="", width=30)

    if market_status:
        # Main market status
        market = market_status.get("market", "unknown")
        status_table.add_row("Market", market.title())

        # Early hours and after hours status
        early_hours = market_status.get("earlyHours", False)
        after_hours = market_status.get("afterHours", False)

        # Session details
        if early_hours:
            status_table.add_row("Premarket", "✅ Active")
        else:
            status_table.add_row("Premarket", "❌ Closed")

        if after_hours:
            status_table.add_row("After Hours", "✅ Active")
        else:
            status_table.add_row("After Hours", "❌ Closed")

        # Get exchanges info if available
        exchanges = market_status.get("exchanges", {})
        if exchanges:
            # Check NYSE and NASDAQ status
            nyse = exchanges.get("nyse", "unknown")
            nasdaq = exchanges.get("nasdaq", "unknown")
            status_table.add_row("NYSE", nyse.title() if isinstance(nyse, str) else str(nyse))
            status_table.add_row("NASDAQ", nasdaq.title() if isinstance(nasdaq, str) else str(nasdaq))

        # Get currencies if available
        currencies = market_status.get("currencies", {})
        if currencies:
            fx = currencies.get("fx", "unknown")
            status_table.add_row("Forex", fx.title() if isinstance(fx, str) else str(fx))

        # Handle serverTime if present - Polygon returns ISO format
        server_time = market_status.get("serverTime")
        if server_time:
            status_table.add_row("Server Time", str(server_time))

    console.print(status_table)

    # Check last market snapshot run metadata
    console.print("")
    console.print("[bold]Last Market Snapshot Run:[/bold]")

    try:
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
    # Initialize data provider
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from provider.data_provider import PolygonDataProvider

        data_provider = PolygonDataProvider(config.db_manager)
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
    if not data_provider.start_market_snapshot_run(len(universe_symbols)):
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

        if not bulk_snapshot_data or "tickers" not in bulk_snapshot_data:
            console.print("[red]❌ No data returned from bulk snapshot API[/red]")
            data_provider.complete_market_snapshot_run(0, len(universe_symbols), "Failed: No data returned")
            return

        console.print(f"[green]✅ Received data for {len(bulk_snapshot_data['tickers'])} symbols[/green]")

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

            processing_task = progress.add_task("Processing snapshot data...", total=len(bulk_snapshot_data["tickers"]))

            for ticker_data in bulk_snapshot_data["tickers"]:
                symbol = ticker_data.get("ticker", "")

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

                    # Transform and save using existing data provider methods
                    # Wrap the ticker data in the expected format
                    wrapped_data = {"ticker": ticker_data}
                    asset_price = data_provider.transform_snapshot_to_asset_price(symbol, asset_id, wrapped_data)

                    if not asset_price:
                        total_errors += 1
                        processing_stats["transform_failed"] += 1
                        progress.update(processing_task, advance=1)
                        continue

                    # Track whether this symbol had recent trading activity
                    has_recent_trading = ticker_data.get("updated") and ticker_data.get("updated") != 0
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
        data_provider.complete_market_snapshot_run(total_updated, total_errors, error_message)

    except Exception as e:
        console.print(f"[red]❌ Error during bulk snapshot: {e}[/red]")
        data_provider.complete_market_snapshot_run(0, len(universe_symbols), f"API Error: {e}")
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