"""Main CLI entry point for TradeScout."""

import logging
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from utils.app_context import AppContext

# Setup rich console for beautiful output
console = Console()
logger = logging.getLogger(__name__)

# Create Click decorator for passing AppContext to commands
pass_config = click.make_pass_decorator(AppContext, ensure=True)


@click.group()
@click.version_option(version="0.1.0", package_name="tradescout")
@click.option(
    "--db-path",
    default="data/tradescout.db",
    help="Path to SQLite database file (default: data/tradescout.db)"
)
@click.option("--debug", "-d", is_flag=True, help="Enable debug logging")
@pass_config
def main(app_context, db_path: str, debug: bool):
    """
    TradeScout - Personal Market Research Assistant

    Analyze market data and generate trade insights.
    """
    app_context.db_path = db_path
    app_context.verbose = debug  # Enable verbose when debug is set

    # Setup logging
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Verify database exists
    if not Path(app_context.db_path).exists():
        console.print(f"[red]❌ Database not found: {app_context.db_path}[/red]")
        console.print("[yellow]Run 'tradescout database init' to create database[/yellow]")
        sys.exit(1)

    # Add src to path for imports
    sys.path.insert(0, str(Path(__file__).parent.parent))


def create_header(title: str, symbol: str = None) -> Panel:
    """Create a fancy ASCII header panel."""
    header_text = Text()
    header_text.append("🔍 ", style="bold blue")
    header_text.append(title.upper(), style="bold white")

    if symbol:
        header_text.append("\n═══════════════════════", style="dim")
        header_text.append(f"\nSymbol: {symbol.upper()}", style="bold cyan")

    return Panel(
        header_text,
        padding=(0, 1),
        style="blue"
    )


# Import and register command groups
from .screener_commands import screener
from .asset_commands import asset
from .database_commands import database
from .market_commands import market
from .gap_commands import gap
from .universe_commands import universes
from .validate_commands import validate
from .fed_commands import fed


main.add_command(screener)
main.add_command(asset)
main.add_command(database)
main.add_command(market)
main.add_command(gap)
main.add_command(universes)
main.add_command(validate)
main.add_command(fed)


if __name__ == "__main__":
    main()