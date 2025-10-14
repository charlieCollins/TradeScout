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
def market(app_context):
    """Market-wide data operations and status."""
    pass


@market.command()
@click.option("--force", is_flag=True, help="Force refresh, bypass TTL cache")
@pass_config
def update(app_context, force):
    """
    Update market snapshot data for all assets in universe.

    Fetches fresh market data from Polygon API and updates the database
    with current price information for all assets in the default universe.

    Example:
        tradescout market update
        tradescout market update --force
    """
    from datetime import datetime

    start_time = datetime.now()

    # Display market context at the top
    display_market_context(app_context)

    # Initialize data service
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        data_service = app_context.get_data_service_v2()
    except Exception as e:
        console.print(f"[red]❌ Failed to initialize data provider: {e}[/red]")
        sys.exit(1)

    # Update market snapshot (handles TTL checks, API fetch, transform, save)
    console.print("[bold blue]Updating market snapshot...[/bold blue]")

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            update_task = progress.add_task("Processing market data...", total=None)

            stats = data_service.update_market_snapshot(force_refresh=force)

            progress.update(update_task, completed=True)

    except Exception as e:
        console.print(f"[red]❌ Failed to update market snapshot: {e}[/red]")
        logger.exception("Market snapshot update failed")
        sys.exit(1)

    # Display results
    console.print("")

    # Get timing information
    from models.dataclass.data_update_metadata import DataUpdateMetadataType
    from services.cache_service import CacheConfig

    ttl_minutes = CacheConfig.get_ttl(DataUpdateMetadataType.MARKET_SNAPSHOTS) / 60
    metadata = data_service.metadata_repository.get_latest_by_operation(
        operation_type=DataUpdateMetadataType.MARKET_SNAPSHOTS.value
    )

    if stats.data_was_fresh:
        # Data was fresh - show timing details
        console.print("[green]✅ Data is fresh (within TTL), no update needed[/green]")
        console.print("")

        info_table = Table(show_header=False, box=None, padding=(0, 1))
        info_table.add_column("Info", style="dim")
        info_table.add_column("Value", justify="right")

        if metadata and metadata.completed_at:
            age = datetime.now() - metadata.completed_at
            age_minutes = age.total_seconds() / 60
            info_table.add_row("Last snapshot", metadata.completed_at.strftime("%Y-%m-%d %H:%M:%S"))
            info_table.add_row("Age", f"{age_minutes:.1f} minutes")
            info_table.add_row("TTL setting", f"{ttl_minutes:.0f} minutes")

        console.print(info_table)
        console.print("")
        console.print("[dim]Use --force to fetch fresh data anyway[/dim]")
        return

    if stats.total_tickers == 0:
        console.print("[red]❌ API returned no data[/red]")
        return

    # Calculate update duration
    end_time = datetime.now()
    duration_seconds = (end_time - start_time).total_seconds()

    # Show summary
    console.print(f"[green]✅ Received {stats.total_tickers:,} tickers from Polygon[/green]")
    console.print("")

    if stats.saved > 0:
        console.print(f"[green]✅ Added {stats.saved:,} new price records to database[/green]")
        if stats.duplicates > 0:
            console.print(f"[dim]   ├─ Skipped {stats.duplicates:,} duplicates (already had this data)[/dim]")
    else:
        console.print(f"[yellow]⚠️  No new data - all {stats.duplicates:,} records already in database[/yellow]")

    # Get total records count
    try:
        total_historical_records = data_service.asset_price_repository.count_all()
        console.print(f"[dim]   Total historical price records in database: {total_historical_records:,}[/dim]")
    except Exception:
        pass

    # Show processing stats
    console.print("")
    console.print("[bold]Market Update Complete[/bold]")

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right")

    table.add_row("Tickers from Polygon", f"{stats.total_tickers:,}")
    table.add_row("Matched to our assets", f"{stats.matched_symbols:,}")
    table.add_row("Unmatched symbols", f"{stats.unmatched_symbols:,}")
    table.add_row("Successfully transformed", f"{stats.transformed:,}")
    table.add_row("  ├─ New records added", f"{stats.saved:,}")
    table.add_row("  ├─ Duplicates skipped", f"{stats.duplicates:,}")
    table.add_row("  └─ Invalid/rejected", f"{stats.invalid:,}")
    table.add_row("Update duration", f"{duration_seconds:.1f}s")
    table.add_row("Completed at", end_time.strftime("%Y-%m-%d %H:%M:%S"))

    # Add timing information
    if metadata and metadata.completed_at:
        table.add_row("", "")  # Blank line separator
        age = datetime.now() - metadata.completed_at
        age_minutes = age.total_seconds() / 60
        table.add_row("Last snapshot", metadata.completed_at.strftime("%Y-%m-%d %H:%M:%S"))
        table.add_row("Age", f"{age_minutes:.1f} minutes")
        table.add_row("TTL setting", f"{ttl_minutes:.0f} minutes")

    console.print(table)


@market.command()
@pass_config
def context(app_context):
    """Show current market context, universe composition, and last snapshot status"""

    try:
        # Get universe statistics using data provider
        active_universe = app_context.get_active_universe()
        data_service = app_context.get_data_service_v2()

        # Get universe market breakdown
        universe_markets = data_service.get_universe_market_breakdown(active_universe)

        # Get total universe count
        universe_stats = data_service.get_universe_stats(active_universe)
        total_universe = universe_stats.total_members if universe_stats else 0

        # Get market context - using NYSE as representative since NASDAQ and NYSE share same sessions
        ctx = app_context.market_context

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
            # Query metadata using repository
            metadata = data_service.metadata_repository.get_latest_by_operation(
                operation_type='market_snapshots',
                operation_subtype='fetch'
            )

            if metadata and metadata.completed_at:
                completed_at = metadata.completed_at
                status = metadata.status

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
