"""Market command group for bulk market operations."""

import sys
from pathlib import Path
from datetime import datetime

import click
from rich.console import Console
from rich.table import Table
from rich import box
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .main import pass_config

console = Console()


@click.group()
@pass_config
def market(config):
    """Market-wide data operations and status."""
    pass


@market.command()
@pass_config
def status(config):
    """
    Show market snapshot status and metadata.

    Displays when the market snapshot was last run and current market status.

    Example:
        tradescout market status
    """
    # Initialize data provider
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from provider.data_provider import PolygonDataProvider
        from config.api_keys import POLYGON_API_KEY

        data_provider = PolygonDataProvider(POLYGON_API_KEY, config.db_manager)
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
        # The market status API returns a simple structure
        status_table.add_row("Market", market_status.get("market", "Unknown"))

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

        # Handle serverTime if present
        server_time = market_status.get("serverTime")
        if server_time:
            try:
                # Convert to numeric if it's a string
                if isinstance(server_time, str):
                    server_time = float(server_time)

                # Check if it's in milliseconds or nanoseconds
                if server_time > 1e12:  # Likely milliseconds
                    server_dt = datetime.fromtimestamp(server_time / 1000)
                else:
                    server_dt = datetime.fromtimestamp(server_time)
                status_table.add_row("Server Time", server_dt.strftime("%Y-%m-%d %H:%M:%S ET"))
            except (ValueError, TypeError):
                status_table.add_row("Server Time", str(server_time))

        # Early hours and after hours status
        early_hours = market_status.get("earlyHours", False)
        after_hours = market_status.get("afterHours", False)
        if early_hours:
            status_table.add_row("Early Hours", "✅ Active")
        if after_hours:
            status_table.add_row("After Hours", "✅ Active")

    console.print(status_table)

    # Check last market snapshot run metadata
    console.print("")
    console.print("[bold]Last Market Snapshot Run:[/bold]")

    try:
        with config.db_manager.get_connection() as conn:
            cursor = conn.cursor()

            # Get latest market snapshot run
            cursor.execute("""
                SELECT
                    started_at, completed_at, total_symbols,
                    successful_updates, failed_updates, status,
                    error_message, api_calls_made
                FROM market_snapshot_runs
                WHERE status IN ('completed', 'partial')
                ORDER BY completed_at DESC
                LIMIT 1
            """)
            result = cursor.fetchone()

            if result:
                started_at = datetime.fromisoformat(result[0])
                completed_at = datetime.fromisoformat(result[1]) if result[1] else None
                total_symbols = result[2]
                successful_updates = result[3]
                failed_updates = result[4]
                status = result[5]
                error_message = result[6]
                api_calls = result[7]

                snapshot_table = Table(
                    box=box.ROUNDED,
                    show_header=False
                )
                snapshot_table.add_column("", style="bold", width=20)
                snapshot_table.add_column("", style="", width=40)

                # Status with emoji
                status_display = {
                    "completed": "[green]✅ Completed[/green]",
                    "partial": "[yellow]⚠️  Partial[/yellow]",
                    "failed": "[red]❌ Failed[/red]",
                    "running": "[blue]🔄 Running[/blue]"
                }.get(status, status)

                snapshot_table.add_row("Status", status_display)

                if completed_at:
                    snapshot_table.add_row("Completed", completed_at.strftime("%Y-%m-%d %H:%M:%S"))

                    # Calculate age
                    age = datetime.now() - completed_at
                    age_str = f"{age.total_seconds() / 60:.1f} minutes ago"
                    if age.total_seconds() > 3600:
                        age_str = f"{age.total_seconds() / 3600:.1f} hours ago"
                    if age.total_seconds() > 86400:
                        age_str = f"{age.total_seconds() / 86400:.1f} days ago"
                    snapshot_table.add_row("Run age", age_str)

                snapshot_table.add_row("Total symbols", f"{total_symbols:,}")
                snapshot_table.add_row("Successful", f"{successful_updates:,}")

                if failed_updates > 0:
                    snapshot_table.add_row("Failed", f"[red]{failed_updates:,}[/red]")

                if successful_updates > 0:
                    success_rate = (successful_updates / total_symbols * 100)
                    snapshot_table.add_row("Success rate", f"{success_rate:.1f}%")

                if api_calls:
                    snapshot_table.add_row("API calls", f"{api_calls:,}")

                if error_message:
                    snapshot_table.add_row("Error", f"[red]{error_message}[/red]")

                console.print(snapshot_table)

                # Check if currently running
                cursor.execute("""
                    SELECT started_at FROM market_snapshot_runs
                    WHERE status = 'running'
                    ORDER BY started_at DESC
                    LIMIT 1
                """)
                running = cursor.fetchone()
                if running:
                    console.print("")
                    console.print(f"[yellow]⚠️  A market snapshot is currently running (started {running[0]})[/yellow]")

            else:
                console.print("[yellow]No market snapshot runs found[/yellow]")
                console.print("[dim]Run 'tradescout market update' to fetch market data[/dim]")

    except Exception as e:
        console.print(f"[red]❌ Failed to check database: {e}[/red]")


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
        from config.api_keys import POLYGON_API_KEY

        data_provider = PolygonDataProvider(POLYGON_API_KEY, config.db_manager)
    except Exception as e:
        console.print(f"[red]❌ Failed to initialize data provider: {e}[/red]")
        sys.exit(1)

    # Get universe assets from database
    console.print("[bold blue]Loading asset universe...[/bold blue]")
    try:
        with config.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT symbol FROM assets
                WHERE is_active = 1
                ORDER BY symbol
            """)
            universe_symbols = [row[0] for row in cursor.fetchall()]

        if not universe_symbols:
            console.print("[red]❌ No active assets found in universe[/red]")
            console.print("[yellow]💡 Run 'tradescout bootstrap universe' to populate the universe[/yellow]")
            return

        console.print(f"[green]✅ Found {len(universe_symbols)} assets in universe[/green]")

    except Exception as e:
        console.print(f"[red]❌ Failed to load universe: {e}[/red]")
        return

    # Fetch bulk market snapshot
    console.print(f"[bold blue]Fetching market snapshot for {len(universe_symbols)} symbols...[/bold blue]")

    # Split symbols into chunks for API calls (Polygon has limits)
    chunk_size = 100  # Adjust based on API limits
    symbol_chunks = [universe_symbols[i:i + chunk_size] for i in range(0, len(universe_symbols), chunk_size)]

    total_updated = 0
    total_errors = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:

        main_task = progress.add_task("Processing market data...", total=len(symbol_chunks))

        for chunk_idx, symbol_chunk in enumerate(symbol_chunks):
            progress.update(main_task, description=f"Processing chunk {chunk_idx + 1}/{len(symbol_chunks)}")

            try:
                # Get market snapshot for this chunk
                snapshot_data = data_provider.get_market_snapshot(symbol_chunk)

                if not snapshot_data or "results" not in snapshot_data:
                    console.print(f"[yellow]⚠️  No data returned for chunk {chunk_idx + 1}[/yellow]")
                    continue

                # Process each ticker in the response
                for ticker_data in snapshot_data["results"]:
                    symbol = ticker_data.get("ticker", "")

                    try:
                        # Get asset_id for this symbol
                        with config.db_manager.get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute("SELECT id FROM assets WHERE symbol = ? AND is_active = 1", (symbol,))
                            result = cursor.fetchone()

                            if not result:
                                continue

                            asset_id = result[0]

                        # Transform and save the ticker data
                        # Wrap the individual ticker data in the expected format
                        wrapped_data = {"ticker": ticker_data}
                        asset_price = data_provider.transform_snapshot_to_asset_price(symbol, asset_id, wrapped_data)

                        if asset_price and data_provider.save_asset_price_data(asset_price):
                            total_updated += 1
                        else:
                            total_errors += 1

                    except Exception as e:
                        console.print(f"[red]❌ Error processing {symbol}: {e}[/red]")
                        total_errors += 1

            except Exception as e:
                console.print(f"[red]❌ Error fetching chunk {chunk_idx + 1}: {e}[/red]")
                total_errors += len(symbol_chunk)

            progress.update(main_task, advance=1)

    # Summary
    console.print("")
    console.print("[bold green]Market Update Complete[/bold green]")

    summary_table = Table(
        box=box.ROUNDED,
        show_header=False
    )
    summary_table.add_column("", style="bold", width=20)
    summary_table.add_column("", style="", width=15)

    summary_table.add_row("Assets updated", f"{total_updated:,}")
    summary_table.add_row("Errors", f"{total_errors:,}")
    summary_table.add_row("Success rate", f"{(total_updated / (total_updated + total_errors) * 100):.1f}%" if (total_updated + total_errors) > 0 else "0%")
    summary_table.add_row("Completed at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    console.print(summary_table)