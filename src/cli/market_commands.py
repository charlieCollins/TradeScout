"""Market command group for bulk market operations."""

import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import (BarColumn, Progress, SpinnerColumn,
                           TaskProgressColumn, TextColumn)
from rich.table import Table

from utils.config_loader import get_field_for_context

from .asset_commands import display_market_context
from .main import pass_config

console = Console()
logger = logging.getLogger(__name__)


@click.group()
@pass_config
def market(config):
    """Market-wide data operations and status."""
    pass


@market.command()
@click.option("--force", is_flag=True, help="Force refresh, bypass TTL cache")
@pass_config
def update(config, force):
    """
    Update market snapshot data for all assets in universe.

    Fetches fresh market data from Polygon API and updates the database
    with current price information for all assets in the default universe.

    Example:
        tradescout market update
        tradescout market update --force
    """

    # Display market context at the top
    display_market_context(config)

    # Initialize data provider
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))

        data_service = config.get_data_service()
    except Exception as e:
        console.print(f"[red]❌ Failed to initialize data provider: {e}[/red]")
        sys.exit(1)

    # Fetch ALL tickers from Polygon (manager handles TTL checks)
    console.print("[bold blue]Fetching market snapshot...[/bold blue]")

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            fetch_task = progress.add_task("Checking cache and API...", total=None)

            # Fetch all tickers (None = get everything)
            # Manager returns None if data is fresh (within TTL) and not forced
            bulk_snapshot_data = data_service.get_market_snapshot(
                None, force_refresh=force
            )

            progress.update(fetch_task, completed=True)

        # Manager returns None if data is fresh (within TTL)
        if not bulk_snapshot_data:
            if force:
                # Force was requested but no data returned - API error
                console.print("[red]❌ API returned no data[/red]")
            else:
                # Data is fresh, no update needed
                console.print(
                    "[green]✅ Data is fresh (within TTL), no update needed[/green]"
                )
                console.print("[dim]Use --force to fetch fresh data anyway[/dim]")
            return

        if not bulk_snapshot_data.tickers:
            console.print("[red]❌ API returned empty ticker list[/red]")
            return

        console.print(
            f"[green]✅ Received data for {len(bulk_snapshot_data.tickers):,} tickers from Polygon[/green]"
        )

        # Load all assets for quick symbol lookups
        console.print("")
        console.print("[bold blue]Loading asset database...[/bold blue]")
        try:
            assets_dict = data_service.get_all_assets_dict()

            if not assets_dict:
                console.print("[red]❌ No assets found in database[/red]")
                console.print(
                    "[yellow]💡 Run 'tradescout database bootstrap-assets' to populate assets[/yellow]"
                )
                return

            console.print(
                f"[green]✅ Loaded {len(assets_dict):,} assets from database[/green]"
            )

        except Exception as e:
            console.print(f"[red]❌ Failed to load assets: {e}[/red]")
            return

        # Process tickers - transform to AssetPrice objects for symbols we have in our database
        console.print("")
        console.print("[bold blue]Processing snapshot data...[/bold blue]")

        # Get market context to determine what "active" means for current session
        market_context = config.market_context
        current_session = market_context.current_session.value

        # Load market context rules ONCE (not 11,800 times in the loop!)
        from utils.config_loader import get_config_loader
        config_loader = get_config_loader()
        market_rules = config_loader.load_market_context_rules()
        volume_field_priority = market_rules.get("field_mappings", {}).get("volume", {}).get(current_session, [])

        asset_prices_to_save = []
        processing_stats = {
            "matched_symbols": 0,  # Symbols we have in our database
            "unmatched_symbols": 0,  # Symbols from Polygon we don't have
            "active_trading": 0,  # Currently trading (has data for current session)
            "inactive": 0,  # Not trading (only prevday or old data)
            "transform_failed": 0,  # Failed to transform data
        }

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            processing_task = progress.add_task(
                "Processing snapshot data...", total=len(bulk_snapshot_data.tickers)
            )

            # Process each ticker from the MarketSnapshot model
            for symbol, ticker_snapshot in bulk_snapshot_data.tickers.items():
                try:
                    # Check if we have this asset in our database
                    asset_id = assets_dict.get(symbol)

                    if not asset_id:
                        processing_stats["unmatched_symbols"] += 1
                        progress.update(processing_task, advance=1)
                        continue

                    processing_stats["matched_symbols"] += 1

                    # Transform TickerSnapshot to AssetPrice
                    asset_price = data_service.transform_ticker_snapshot_to_asset_price(
                        symbol, asset_id, ticker_snapshot
                    )

                    if not asset_price:
                        processing_stats["transform_failed"] += 1
                        progress.update(processing_task, advance=1)
                        continue

                    # Determine if actively trading using market context rules
                    # Build available data dict from ticker snapshot
                    available_data = {
                        "min_volume": (
                            ticker_snapshot.min_bar.volume
                            if ticker_snapshot.min_bar
                            else None
                        ),
                        "day_volume": ticker_snapshot.volume,
                        "prevday_volume": ticker_snapshot.prev_volume,
                    }

                    # Get appropriate volume field for current session (use pre-loaded priority list)
                    current_volume = None
                    for field_name in volume_field_priority:
                        value = available_data.get(field_name)
                        if value is not None:
                            current_volume = value
                            break

                    # Active if volume > 0 for the current session's volume field
                    is_active = current_volume is not None and current_volume > 0

                    if is_active:
                        processing_stats["active_trading"] += 1
                    else:
                        processing_stats["inactive"] += 1

                    asset_prices_to_save.append(asset_price)

                except Exception as e:
                    processing_stats["transform_failed"] += 1
                    logger.error(f"Error transforming {symbol}: {e}")

                progress.update(processing_task, advance=1)

        console.print(
            f"[green]✅ Prepared {len(asset_prices_to_save):,} asset prices for database update[/green]"
        )

        # Batch save to database
        console.print("")
        console.print("[bold blue]Saving to database...[/bold blue]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            save_task = progress.add_task("Batch inserting asset prices...", total=None)

            new_records, duplicate_records, successful, failed = (
                data_service.batch_save_asset_prices(asset_prices_to_save)
            )

            progress.update(save_task, completed=True)

        # Get total records count in database after update
        try:
            with data_service.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM asset_prices")
                total_historical_records = cursor.fetchone()[0]
        except Exception:
            total_historical_records = None

        if new_records > 0:
            console.print(
                f"[green]✅ Added {new_records:,} new price records to database[/green]"
            )
            if duplicate_records > 0:
                console.print(f"[dim]   ├─ Skipped {duplicate_records:,} duplicates (already had this data)[/dim]")
        else:
            console.print(
                f"[yellow]⚠️  No new data - all {duplicate_records:,} records already in database[/yellow]"
            )

        if total_historical_records is not None:
            console.print(
                f"[dim]   Total historical price records in database: {total_historical_records:,}[/dim]"
            )
        if failed > 0:
            console.print(f"[red]❌ {failed:,} failed to save[/red]")

    except Exception as e:
        console.print(f"[red]❌ Error during bulk snapshot: {e}[/red]")
        logger.error(f"Market update error: {traceback.format_exc()}")
        return

    # Summary
    console.print("")
    console.print("[bold green]Market Update Complete[/bold green]")

    summary_table = Table(box=box.ROUNDED, show_header=False)
    summary_table.add_column("", style="bold", width=25)
    summary_table.add_column("", style="", width=15)

    summary_table.add_row(
        "Tickers from Polygon", f"{len(bulk_snapshot_data.tickers):,}"
    )
    summary_table.add_row(
        "Matched to our assets", f"{processing_stats['matched_symbols']:,}"
    )
    summary_table.add_row("Processed", f"{successful:,}")
    summary_table.add_row("  ├─ New records added", f"{new_records:,}")
    summary_table.add_row("  └─ Duplicates skipped", f"{duplicate_records:,}")
    if failed > 0:
        summary_table.add_row("Failed to process", f"{failed:,}")
    summary_table.add_row("Completed at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    console.print(summary_table)

    # Processing breakdown
    console.print("")
    console.print("[bold blue]Processing Breakdown:[/bold blue]")

    breakdown_table = Table(box=box.ROUNDED, show_header=False)
    breakdown_table.add_column("Category", style="bold", width=30)
    breakdown_table.add_column("Count", style="", width=12)
    breakdown_table.add_column("Description", style="dim", width=40)

    # Show ticker matching stats
    breakdown_table.add_row(
        "Total tickers from Polygon",
        f"{len(bulk_snapshot_data.tickers):,}",
        "All tickers in API response",
    )
    breakdown_table.add_row(
        "Matched to our assets",
        f"{processing_stats['matched_symbols']:,}",
        "Tickers we have in our database",
    )
    breakdown_table.add_row(
        "Unmatched symbols",
        f"{processing_stats['unmatched_symbols']:,}",
        "Tickers from Polygon we don't track",
    )

    breakdown_table.add_row("", "", "")  # Separator

    # Show trading activity for current session
    if processing_stats["active_trading"] > 0 or processing_stats["inactive"] > 0:
        breakdown_table.add_row("", "", "")  # Separator
        breakdown_table.add_row(
            "Active in session",
            f"{processing_stats['active_trading']:,}",
            f"Symbols with volume > 0 (current session)",
        )
        breakdown_table.add_row(
            "Inactive in session",
            f"{processing_stats['inactive']:,}",
            "Symbols with no volume (current session)",
        )

    # Show error categories if there were errors
    if processing_stats["transform_failed"] > 0 or failed > 0:
        breakdown_table.add_row("", "", "")  # Separator
        breakdown_table.add_row("[bold red]ERRORS", "", "")

        if processing_stats["transform_failed"] > 0:
            breakdown_table.add_row(
                "Data transformation failed",
                f"{processing_stats['transform_failed']:,}",
                "Failed to convert ticker snapshot to asset price",
            )

        if failed > 0:
            breakdown_table.add_row(
                "Database save failed",
                f"{failed:,}",
                "Failed to write asset price data to database",
            )

    console.print(breakdown_table)


@market.command()
@pass_config
def context(config):
    """Show current market context, universe composition, and last snapshot status"""

    try:
        # Get universe statistics using data provider
        active_universe = config.get_active_universe()
        data_service = config.get_data_service()

        # Get universe market breakdown
        universe_markets = data_service.get_universe_market_breakdown(active_universe)

        # Get total universe count
        universe_stats = data_service.get_universe_stats(active_universe)
        total_universe = universe_stats.total_members if universe_stats else 0

        # Get market context - using NYSE as representative since NASDAQ and NYSE share same sessions
        ctx = config.market_context

        # Create main context table
        table = Table(
            title=f"📊 {active_universe.title()} Market Context", show_header=True
        )
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
        table.add_row("Day Type", ctx.day_type.value.replace("_", " ").title())
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
                formatted_name = session_name.replace("_", " ").title()
                if time_val:
                    formatted_time = time_val.strftime("%H:%M")
                else:
                    formatted_time = "N/A"
                times_table.add_row(formatted_name, formatted_time)

            console.print(times_table)

        # Show timezone info
        console.print()
        console.print(
            Panel(
                f"Market Timezone: {ctx.market.timezone}\n"
                f"Currency: {ctx.market.currency}\n"
                f"Extended Hours Support: {'Yes' if ctx.market.has_extended_hours else 'No'}",
                title="Market Details",
            )
        )

        # Show last market snapshot run metadata
        console.print()
        console.print("[bold]Last Market Snapshot Update:[/bold]")

        try:
            # Query data_update_metadata directly
            with data_service.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT completed_at, status
                    FROM data_update_metadata
                    WHERE operation_type = 'market_snapshots' AND operation_subtype = 'fetch'
                    ORDER BY completed_at DESC LIMIT 1
                """)
                result = cursor.fetchone()

            if result:
                completed_at_str, status = result
                completed_at = datetime.fromisoformat(completed_at_str)

                # Calculate age
                age = datetime.now() - completed_at
                if age.total_seconds() < 60:
                    age_str = f"{age.total_seconds():.0f} seconds ago"
                elif age.total_seconds() < 3600:
                    age_str = f"{age.total_seconds() / 60:.1f} minutes ago"
                elif age.total_seconds() < 86400:
                    age_str = f"{age.total_seconds() / 3600:.1f} hours ago"
                else:
                    age_str = f"{age.total_seconds() / 86400:.1f} days ago"

                status_display = {
                    "completed": "[green]✅ Completed[/green]",
                    "failed": "[red]❌ Failed[/red]",
                    "running": "[blue]🔄 Running[/blue]",
                }.get(status, status)

                snapshot_table = Table(box=box.ROUNDED, show_header=False)
                snapshot_table.add_column("", style="bold", width=20)
                snapshot_table.add_column("", style="", width=40)
                snapshot_table.add_row("Status", status_display)
                snapshot_table.add_row("Last Update", completed_at.strftime("%Y-%m-%d %H:%M:%S"))
                snapshot_table.add_row("Data Age", age_str)
                console.print(snapshot_table)
            else:
                console.print("[yellow]No market snapshot data available[/yellow]")
                console.print(
                    "[dim]Run 'tradescout market update' to fetch market data[/dim]"
                )

        except Exception as e:
            console.print(f"[yellow]Unable to fetch snapshot metadata: {e}[/yellow]")

    except Exception as e:
        console.print(f"❌ Error getting market context: {e}")
