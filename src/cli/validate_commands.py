"""CLI commands for validation and testing of data assumptions."""

import logging
import random
from datetime import date, datetime
from typing import Optional

import click
from rich.console import Console

from .main import pass_config

logger = logging.getLogger(__name__)
console = Console()


@click.group()
def validate():
    """Validation commands for testing data assumptions and rules."""
    pass


@validate.command()
@click.option(
    "--count",
    "-n",
    type=int,
    default=10,
    help="Number of random assets to test (default: 10)",
)
@click.option(
    "--symbols",
    "-s",
    type=str,
    help="Specific symbols to test (comma-separated, e.g., 'AAPL,NVDA,TSLA')",
)
@pass_config
def volume(app_context, count: int, symbols: Optional[str]):
    """Validate volume calculation rules against Aggregates API.

    Tests our simple volume rules used by screeners:
    - Premarket: min.av (accumulated premarket volume)
    - Regular: day.v (regular session volume)
    - After-hours: min.av (accumulated), min.av - day.v (just after-hours)

    For extended hours sessions, compares snapshot values against
    Aggregates API to verify accuracy.

    Examples:
        tradescout validate volume
        tradescout validate volume --count 5
        tradescout validate volume --symbols AAPL,NVDA,TSLA
    """
    try:
        # Initialize services
        data_service = app_context.get_data_service_v2()
        market_service = app_context.get_market_context_service()

        # Get current market context (default to XNYS)
        market_context = market_service.get_context("XNYS")
        if not market_context:
            console.print("[red]❌ Could not determine market context[/red]")
            return

        session = market_context.current_session.value
        trading_date = (
            market_context.current_date
            if market_context.is_trading_day
            else market_context.previous_trading_date
        )

        # Display session info
        console.print(f"\n[bold]📊 Volume Validation - {session.upper()} Session[/bold]")
        console.print(f"Trading Date: {trading_date}")
        console.print(f"Extended Hours: {session in ['premarket', 'afterhours']}\n")

        # Get test symbols
        if symbols:
            # Use specified symbols
            symbol_list = [s.strip().upper() for s in symbols.split(",")]
            test_asset_ids = data_service.asset_price_repository.get_latest_price_ids_for_symbols(symbol_list)

            if not test_asset_ids:
                console.print(f"[red]❌ No price data found for symbols: {symbols}[/red]")
                return
        else:
            # Get random assets with recent activity (fetch more to filter out DELAYED)
            # For extended hours, get 100 and filter to first 10 with data
            fetch_limit = 100 if session in ["premarket", "afterhours"] else count
            candidate_asset_ids = data_service.asset_price_repository.get_random_assets_with_prices(limit=fetch_limit)

            if not candidate_asset_ids:
                console.print("[red]❌ No assets with price data found[/red]")
                return

            test_asset_ids = candidate_asset_ids

        from models.result.validate_result import VolumeValidationResult, VolumeValidationRow

        # Track successful tests for extended hours
        successful_tests = 0
        target_tests = count if not symbols else len(test_asset_ids)

        # Collect validation rows
        validation_rows = []

        # Test each asset
        for symbol, asset_id, price_id in test_asset_ids:
            # Stop if we have enough successful tests for extended hours
            if session in ["premarket", "afterhours"] and not symbols:
                if successful_tests >= target_tests:
                    break
            # Fetch the full AssetPrice object using asset_id
            # Note: get_latest_by_asset_id returns the LATEST price for this asset
            asset_price = data_service.asset_price_repository.get_latest_by_asset_id(asset_id)
            if not asset_price:
                continue

            # Determine snapshot volume based on session
            if session == "premarket":
                snapshot_vol = asset_price.min_accumulated_volume or 0
            elif session == "regular":
                snapshot_vol = asset_price.day_volume or 0
            elif session == "afterhours":
                # Snapshot does NOT work for after-hours (min.av frozen at day.v)
                snapshot_vol = None  # Will display as "N/A"
            else:  # closed
                snapshot_vol = asset_price.prevday_volume or 0

            # For regular/closed, just show snapshot (no aggregates needed)
            if session in ["regular", "closed"]:
                validation_rows.append(VolumeValidationRow(
                    symbol=symbol,
                    snapshot_volume=snapshot_vol,
                    snapshot_time=None,
                    aggregates_volume=None,
                    aggregates_time=None,
                    diff_percent=None,
                    status=None
                ))
                successful_tests += 1
                continue

            # For extended hours, compare with Aggregates API
            try:
                # Get snapshot timestamp
                snapshot_time = datetime.fromtimestamp(asset_price.provider_updated_at / 1_000_000_000)

                # Get aggregates data
                agg_result = data_service.fetch_minute_bars(
                    symbol=symbol,
                    from_datetime=datetime.combine(trading_date, datetime.min.time()).replace(
                        hour=4 if session == "premarket" else 16, minute=0
                    ),
                    to_datetime=datetime.combine(trading_date, datetime.min.time()).replace(
                        hour=9 if session == "premarket" else 20,
                        minute=30 if session == "premarket" else 0
                    )
                )

                if not agg_result:
                    # Skip symbols with no aggregates data (DELAYED or no trading)
                    continue

                # Calculate volume and get bar time range
                agg_volume = sum(bar.get("v", 0) for bar in agg_result)
                first_bar_time = datetime.fromtimestamp(agg_result[0]['t'] / 1000)
                last_bar_time = datetime.fromtimestamp(agg_result[-1]['t'] / 1000)

                logger.info(
                    f"{symbol}: {len(agg_result)} bars from {first_bar_time.strftime('%Y-%m-%d %H:%M:%S')} "
                    f"to {last_bar_time.strftime('%Y-%m-%d %H:%M:%S')}, volume={agg_volume:,}"
                )

                # Calculate difference (skip if snapshot_vol is None for after-hours)
                if snapshot_vol is None:
                    # After-hours: no snapshot volume available
                    diff_pct = None
                    status = "snap_na"
                elif agg_volume > 0:
                    diff_pct = ((snapshot_vol - agg_volume) / agg_volume) * 100

                    # Determine status (within 25% = good, considering our AAPL test)
                    if abs(diff_pct) <= 25:
                        status = "good"
                    elif abs(diff_pct) <= 50:
                        status = "ok"
                    else:
                        status = "high"
                else:
                    diff_pct = 0.0
                    status = "ok"

                validation_rows.append(VolumeValidationRow(
                    symbol=symbol,
                    snapshot_volume=snapshot_vol,
                    snapshot_time=snapshot_time,
                    aggregates_volume=agg_volume,
                    aggregates_time=last_bar_time,
                    diff_percent=diff_pct,
                    status=status
                ))
                successful_tests += 1

            except Exception as e:
                logger.error(f"Error validating {symbol}: {e}")
                # Skip symbols with errors
                continue

        # Create result and display
        result = VolumeValidationResult(
            session=session,
            trading_date=trading_date,
            is_extended_hours=(session in ["premarket", "afterhours"]),
            rows=validation_rows
        )
        app_context.presentation.validate_adapter.display_volume_validation_result(result)

    except Exception as e:
        logger.error(f"Volume validation failed: {e}", exc_info=True)
        console.print(f"[red]❌ Validation failed: {e}[/red]")
