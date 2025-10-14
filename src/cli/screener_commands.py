"""Screener command group for market screening."""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from .main import pass_config
from .asset_commands import display_market_context

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from screener.screener_config import ScreenerConfig
from screener.screener_engine import ScreenerEngine
from screener.screener_display import ScreenerDisplay

console = Console()


@click.command()
@click.argument("screener_name", required=False)
@click.option("--list", "list_screeners", is_flag=True, help="List available screeners")
@pass_config
def screener(app_context, screener_name: str, list_screeners: bool):
    """
    Run market screeners to find trading opportunities.

    Examples:
        tradescout screener --list           # List available screener names
        tradescout screener gainers          # Run the 'gainers' screener
        tradescout screener losers           # Run the 'losers' screener
        tradescout screener gaps             # Run the 'gaps' screener
    """

    # Display market context at the top
    display_market_context(app_context)

    # Handle list flag
    if list_screeners:
        try:
            screener_config = ScreenerConfig()
            available_screeners = screener_config.list_available_screeners()

            table = Table(title="Available Screeners", show_header=True)
            table.add_column("Screener", style="cyan", no_wrap=True)
            table.add_column("Description", style="white")

            for screener in available_screeners:
                table.add_row(screener["name"], screener["description"])

            console.print(table)
            console.print("\n[dim]Screeners are loaded from configs/screeners/*.yaml[/dim]")
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
        screener_display = ScreenerDisplay()

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
        except Exception:
            pass

        # Get valid sessions from screener config
        valid_sessions = screener_def.get('valid_sessions', [])
        sessions_text = f"Valid sessions: {', '.join(valid_sessions)}" if valid_sessions else ""

        # Get market context from app_context (not data_service)
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
        console.print(f"[yellow]📊 Running '{screener_name}' screener...[/yellow]")
        results = screener_engine.execute_screener(screener_def, market_context)

        # Display results
        screener_display.display_results(
            results,
            screener_def,
            session=market_context.session_name,
            snapshot_time=snapshot_time,
            sessions_text=sessions_text,
            warnings=all_warnings
        )

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print("[dim]Use 'tradescout screener --list' to see available screeners[/dim]")
    except RuntimeError as e:
        console.print(f"[red]Screener execution failed: {e}[/red]")
        console.print("[dim]Check API connectivity and authentication[/dim]")
    except Exception as e:
        console.print(f"[red]Screener execution failed: {e}[/red]")
        console.print("[dim]Check system configuration and database[/dim]")