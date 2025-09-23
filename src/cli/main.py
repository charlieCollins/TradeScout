"""Main CLI entry point for TradeScout."""

import logging
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

# Setup rich console for beautiful output
console = Console()
logger = logging.getLogger(__name__)


class Config:
    """Shared configuration for CLI commands."""
    def __init__(self):
        self.db_path = "data/tradescout.db"
        self.verbose = False
        self.db_manager = None


pass_config = click.make_pass_decorator(Config, ensure=True)


@click.group()
@click.version_option(version="0.1.0", package_name="tradescout")
@click.option(
    "--db-path",
    default="data/tradescout.db",
    help="Path to SQLite database file (default: data/tradescout.db)"
)
@click.option("--debug", "-d", is_flag=True, help="Enable debug logging")
@pass_config
def main(config, db_path: str, debug: bool):
    """
    TradeScout - Personal Market Research Assistant

    Analyze market data and generate trade insights.
    """
    config.db_path = db_path
    config.verbose = debug  # Enable verbose when debug is set

    # Setup logging
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Verify database exists
    if not Path(config.db_path).exists():
        console.print(f"[red]❌ Database not found: {config.db_path}[/red]")
        console.print("[yellow]Run 'bootstrap database init' to create database[/yellow]")
        sys.exit(1)

    # Initialize database manager
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from database.database_manager import DatabaseManager
        config.db_manager = DatabaseManager(config.db_path)
    except Exception as e:
        console.print(f"[red]❌ Failed to initialize database: {e}[/red]")
        sys.exit(1)


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
from .bootstrap_commands import bootstrap
from .market_commands import market


main.add_command(screener)
main.add_command(asset)
main.add_command(bootstrap)
main.add_command(market)


if __name__ == "__main__":
    main()