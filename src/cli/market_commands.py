"""Market command group for bulk market operations."""

import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import (BarColumn, Progress, SpinnerColumn,
                           TaskProgressColumn, TextColumn)

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
@click.option("--date", help="Specific date to backfill (YYYY-MM-DD)")
@click.option("--force", is_flag=True, help="Force refresh, bypass TTL cache or overwrite existing data")
@pass_config
def update(app_context, date, force):
    """
    Update market snapshot data or backfill historical data.

    If --date is provided, backfills historical data for that specific date.
    If no --date is provided, updates current market snapshot for all assets.

    Examples:
        tradescout market update                      # Update current snapshot
        tradescout market update --force              # Force update current snapshot
        tradescout market update --date 2025-10-15    # Backfill data for Oct 15
        tradescout market update --date 2025-10-15 --force  # Force backfill for Oct 15
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

    # Branch based on whether date is provided
    if date:
        # BACKFILL MODE: Historical data for specific date
        # Parse date
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            console.print(f"[red]❌ Invalid date format: {date}. Use YYYY-MM-DD (e.g., 2025-10-15)[/red]")
            sys.exit(1)

        # Backfill market data
        console.print(f"[bold blue]Backfilling market data for {target_date}...[/bold blue]")

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                backfill_task = progress.add_task("Processing grouped daily bars...", total=None)

                stats = data_service.backfill_market_data(target_date=target_date, force_refresh=force)

                progress.update(backfill_task, completed=True)

        except Exception as e:
            console.print(f"[red]❌ Failed to backfill market data: {e}[/red]")
            logger.exception("Market backfill failed")
            sys.exit(1)

        # Build backfill result
        from models.result.market_result import MarketBackfillResult

        # Calculate update duration
        end_time = datetime.now()
        duration_seconds = (end_time - start_time).total_seconds()

        # Get total records count
        total_historical_records = None
        try:
            total_historical_records = data_service.asset_price_repository.count_all()
        except Exception as e:
            logger.warning(f"Could not get total price record count: {e}")

        # Create result and display
        result = MarketBackfillResult(
            target_date=target_date,
            force_refresh=force,
            total_tickers=stats.total_tickers,
            matched_symbols=stats.matched_symbols,
            unmatched_symbols=stats.unmatched_symbols,
            transformed=stats.transformed,
            saved=stats.saved,
            duplicates=stats.duplicates,
            invalid=stats.invalid,
            invalid_no_timestamp=stats.invalid_no_timestamp,
            invalid_exception=stats.invalid_exception,
            duration_seconds=duration_seconds,
            completed_at=end_time,
            total_historical_records=total_historical_records
        )
        app_context.presentation.market_adapter.display_market_backfill_result(result)

    else:
        # SNAPSHOT MODE: Current market data
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

        # Build snapshot result
        from models.result.market_result import MarketUpdateResult
        from models.dataclass.data_update_metadata import DataUpdateMetadataType
        from services.cache_service import CacheConfig

        ttl_minutes = CacheConfig.get_ttl(DataUpdateMetadataType.MARKET_SNAPSHOTS) / 60
        metadata = data_service.metadata_repository.get_latest_by_operation(
            operation_type=DataUpdateMetadataType.MARKET_SNAPSHOTS.value
        )

        # Calculate update duration
        end_time = datetime.now()
        duration_seconds = (end_time - start_time).total_seconds()

        # Get timing information
        last_snapshot_time = None
        age_minutes = None
        if metadata and metadata.completed_at:
            last_snapshot_time = metadata.completed_at
            age = datetime.now() - metadata.completed_at
            age_minutes = age.total_seconds() / 60

        # Get total records count
        total_historical_records = None
        try:
            total_historical_records = data_service.asset_price_repository.count_all()
        except Exception:
            pass

        # Create result and display
        result = MarketUpdateResult(
            data_was_fresh=stats.data_was_fresh,
            total_tickers=stats.total_tickers,
            matched_symbols=stats.matched_symbols,
            unmatched_symbols=stats.unmatched_symbols,
            transformed=stats.transformed,
            saved=stats.saved,
            duplicates=stats.duplicates,
            invalid=stats.invalid,
            invalid_no_timestamp=stats.invalid_no_timestamp,
            invalid_exception=stats.invalid_exception,
            duration_seconds=duration_seconds,
            completed_at=end_time,
            last_snapshot_time=last_snapshot_time,
            age_minutes=age_minutes,
            ttl_minutes=ttl_minutes,
            total_historical_records=total_historical_records
        )
        app_context.presentation.market_adapter.display_market_update_result(result)


@market.command()
@pass_config
def context(app_context):
    """Show current market context, universe composition, and last snapshot status"""

    try:
        from models.result.market_result import MarketContextResult

        # Get universe statistics using data provider
        active_universe = app_context.get_active_universe()
        data_service = app_context.get_data_service_v2()

        # Get universe market breakdown
        universe_markets = data_service.get_universe_market_breakdown(active_universe)

        # Get total universe count
        universe_stats = data_service.get_universe_stats(active_universe)
        total_universe = universe_stats.total_members if universe_stats else 0

        # Get market context - uses the universe's primary market (first market listed)
        ctx = app_context.market_context

        # Get last snapshot metadata
        last_snapshot_status = None
        last_snapshot_time = None
        last_snapshot_age_str = None

        try:
            # Query metadata using repository
            metadata = data_service.metadata_repository.get_latest_by_operation(
                operation_type='market_snapshots',
                operation_subtype='fetch'
            )

            if metadata and metadata.completed_at:
                last_snapshot_time = metadata.completed_at
                last_snapshot_status = metadata.status

                # Calculate age
                age = datetime.now() - last_snapshot_time
                if age.total_seconds() < 60:
                    last_snapshot_age_str = f"{age.total_seconds():.0f} seconds ago"
                elif age.total_seconds() < 3600:
                    last_snapshot_age_str = f"{age.total_seconds() / 60:.1f} minutes ago"
                elif age.total_seconds() < 86400:
                    last_snapshot_age_str = f"{age.total_seconds() / 3600:.1f} hours ago"
                else:
                    last_snapshot_age_str = f"{age.total_seconds() / 86400:.1f} days ago"

        except Exception as e:
            logger.warning(f"Unable to fetch snapshot metadata: {e}")

        # Create result and display
        result = MarketContextResult(
            universe_name=active_universe,
            universe_markets=universe_markets,
            total_universe=total_universe,
            market_context=ctx,
            last_snapshot_status=last_snapshot_status,
            last_snapshot_time=last_snapshot_time,
            last_snapshot_age_str=last_snapshot_age_str
        )
        app_context.presentation.market_adapter.display_market_context(result)

    except Exception as e:
        console.print(f"❌ Error getting market context: {e}")
