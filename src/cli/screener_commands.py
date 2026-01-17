"""Screener command group for market screening."""

import logging
import sys
from pathlib import Path

import click
from rich.console import Console

from .main import pass_config

logger = logging.getLogger(__name__)
from .asset_commands import display_market_context

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from screener.screener_config import ScreenerConfig
from screener.screener_engine import ScreenerEngine

console = Console()


@click.command()
@click.argument("screener_name", required=False)
@click.option("--list", "list_screeners", is_flag=True, help="List available screeners")
@click.option("--date", "reference_date", type=str, help="Reference date for historical screening (YYYY-MM-DD)")
@pass_config
def screener(app_context, screener_name: str, list_screeners: bool, reference_date: str):
    """
    Run market screeners to find trading opportunities.

    Examples:
        tradescout screener --list                    # List available screener names
        tradescout screener gainers                   # Run gainers for current market state
        tradescout screener gainers --date 2025-10-17 # Run gainers for Oct 17, 2025
        tradescout screener losers                    # Run the 'losers' screener
        tradescout screener gaps                      # Run the 'gaps' screener
    """

    # Display market context at the top
    display_market_context(app_context)

    # Handle list flag
    if list_screeners:
        try:
            from models.result.screener_result import ScreenerListItem, ScreenerListResult

            screener_config = ScreenerConfig()
            available_screeners = screener_config.list_available_screeners()

            # Build result model
            screener_items = [
                ScreenerListItem(name=s["name"], description=s["description"])
                for s in available_screeners
            ]

            result = ScreenerListResult(screeners=screener_items)

            # Display using adapter
            app_context.presentation.screener_adapter.display_screener_list(result)
            return
        except Exception as e:
            console.print(f"[red]Error loading screeners: {e}[/red]")
            return

    # Show help if no screener name provided
    if not screener_name:
        ctx = click.get_current_context()
        click.echo(ctx.get_help())
        return

    # Load and execute screener
    try:
        # Initialize components
        screener_config = ScreenerConfig()
        data_service = app_context.get_data_service_v2()
        screener_engine = ScreenerEngine(data_service, app_context)

        # Get screener definition
        screener_def = screener_config.get_screener(screener_name)

        # Get snapshot metadata for display
        snapshot_time = None
        snapshot_warning = None
        try:
            metadata = data_service.get_market_snapshot_metadata()
            if metadata and metadata.get('completed_at'):
                from datetime import datetime
                completed_at = datetime.fromisoformat(metadata['completed_at'])
                age = datetime.now() - completed_at
                age_minutes = age.total_seconds() / 60
                age_str = f"{age_minutes:.0f}m ago"
                if age.total_seconds() > 3600:
                    age_str = f"{age.total_seconds() / 3600:.1f}h ago"
                snapshot_time = f"Last snapshot: {completed_at.strftime('%Y-%m-%d %H:%M:%S')} ({age_str})"

                # Add warning if snapshot is older than 30 minutes
                if age_minutes > 30:
                    snapshot_warning = f"⚠️  Warning: Market data is {age_str} old - results may be stale"
        except Exception as e:
            logger.debug(f"Could not fetch market snapshot metadata: {e}")

        # Get valid sessions from screener config
        valid_sessions = screener_def.get('valid_sessions', [])
        sessions_text = f"Valid sessions: {', '.join(valid_sessions)}" if valid_sessions else ""

        # Get market context - either live or historical based on --date flag
        if reference_date:
            # Parse reference date
            from datetime import datetime, date as date_type
            try:
                ref_date = datetime.strptime(reference_date, "%Y-%m-%d").date()
            except ValueError:
                console.print(f"[red]Invalid date format '{reference_date}'. Use YYYY-MM-DD (e.g., 2025-10-17)[/red]")
                return

            # Create historical market context for this date
            console.print(f"[dim]Running screener for reference date: {ref_date}[/dim]")
            market_context_service = app_context.get_market_context_service()
            market_context = market_context_service.get_historical_context(
                date=ref_date,
                market_code=app_context._get_primary_market_from_universe()
            )
        else:
            # Use live market context
            market_context = app_context.market_context

        current_session = market_context.current_session.value

        # Add session-specific warnings
        session_warnings = []

        if current_session == "closed":
            session_warnings.append("⚠️  Markets are closed - showing data from last trading session")
        elif current_session == "premarket":
            session_warnings.append("📈 Premarket session - limited trading volume")
        elif current_session == "afterhours":
            session_warnings.append("🌙 After-hours session - limited trading volume")

        # Combine warnings as a list
        all_warnings = []
        if snapshot_warning:
            all_warnings.append(snapshot_warning)
        all_warnings.extend(session_warnings)

        # Execute screener
        results, excluded_count = screener_engine.execute_screener(screener_def, market_context)

        # Get data date summary for validation
        data_service_v2 = app_context.get_data_service_v2()
        data_date_summary = data_service_v2.asset_price_repository.get_data_date_summary()

        # Get resolved config for result model
        from screener.template_resolver import TemplateResolver
        resolver = TemplateResolver(screener_def, market_context.session_name)
        resolved_config = resolver.get_resolved_config()

        # Build output-agnostic result model
        from models.result.screener_result import ScreenerResult
        result = ScreenerResult(
            screener_name=screener_name,
            results=results,
            screener_def=screener_def,
            resolved_config=resolved_config,
            market_context=market_context,
            excluded_count=excluded_count,
            snapshot_time=snapshot_time,
            sessions_text=sessions_text,
            warnings=all_warnings,
            data_date_summary=data_date_summary
        )

        # Display results using injected adapter from presentation context (CLI/Web/JSON agnostic)
        app_context.presentation.screener_adapter.display_screener_results(result)

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print("[dim]Use 'tradescout screener --list' to see available screeners[/dim]")
    except RuntimeError as e:
        console.print(f"[red]Screener execution failed: {e}[/red]")
        console.print("[dim]Check API connectivity and authentication[/dim]")
    except Exception as e:
        console.print(f"[red]Screener execution failed: {e}[/red]")
        console.print("[dim]Check system configuration and database[/dim]")