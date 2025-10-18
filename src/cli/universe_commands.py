"""Universe management commands for TradeScout."""

import sys
from pathlib import Path

import click
from rich.console import Console

from .main import pass_config

console = Console()


@click.group()
@pass_config
def universes(app_context):
    """Manage asset universes for trading."""
    pass


@universes.command('list')
@pass_config
def universe_list(app_context):
    """List all available universes."""
    try:
        from models.result.universe_result import UniverseListResult, UniverseListItem

        data_service = app_context.get_data_service_v2()
        universes_list = data_service.get_all_universes()

        if not universes_list:
            console.print("[yellow]No universes found[/yellow]")
            return

        # Build list items with counts
        items = []
        for universe in universes_list:
            # Get asset count for this universe
            stats = data_service.get_universe_stats(universe.name)
            asset_count = stats.total_members if stats else 0

            items.append(UniverseListItem(
                universe=universe,
                asset_count=asset_count
            ))

        # Create result and display
        result = UniverseListResult(universes=items)
        app_context.presentation.universe_adapter.display_universe_list(result)

    except Exception as e:
        console.print(f"[red]❌ Failed to list universes: {e}[/red]")
        sys.exit(1)


@universes.command('info')
@click.argument('universe_name', required=False)
@pass_config
def universe_info(app_context, universe_name):
    """Show detailed information about a universe."""
    # Use active universe if not specified
    if not universe_name:
        universe_name = app_context.get_active_universe()

    try:
        from models.result.universe_result import UniverseInfoResult

        data_service = app_context.get_data_service_v2()

        # Get universe details
        universes_list = data_service.get_all_universes()
        universe = next((u for u in universes_list if u.name == universe_name), None)

        if not universe:
            app_context.presentation.universe_adapter.display_universe_not_found(universe_name)
            return

        # Get universe statistics
        stats = data_service.get_universe_stats(universe_name)
        if not stats:
            console.print(f"[red]Unable to get stats for universe '{universe_name}'[/red]")
            return

        # Create result and display
        result = UniverseInfoResult(
            universe=universe,
            stats=stats
        )
        app_context.presentation.universe_adapter.display_universe_info(result)

    except Exception as e:
        console.print(f"[red]❌ Failed to get universe info: {e}[/red]")
        sys.exit(1)


@universes.command('activate')
@click.argument('universe_name')
@pass_config
def universe_activate(app_context, universe_name):
    """Set a universe as the active trading universe."""
    if app_context.set_active_universe(universe_name):
        console.print(f"[green]✅ Activated universe: {universe_name}[/green]")

        # Show brief info about the activated universe
        data_service = app_context.get_data_service_v2()
        stats = data_service.get_universe_stats(universe_name)
        count = stats.total_members if stats else 0
        console.print(f"[dim]This universe contains {count:,} assets[/dim]")
    else:
        console.print(f"[red]❌ Failed to activate universe '{universe_name}'[/red]")
        console.print("[yellow]Use 'tradescout universes list' to see available universes[/yellow]")
        sys.exit(1)


@universes.command('current')
@pass_config
def universe_current(app_context):
    """Show the currently active universe."""
    active = app_context.get_active_universe()
    console.print(f"Active universe: [bold cyan]{active}[/bold cyan]")


