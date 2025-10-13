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
        self._market_context = None
        self._market_context_service = None
        self._active_universe = None
        self._polygon_api_key = None
        self._sqlmodel_engine = None
        self._data_service_v2 = None

    @property
    def polygon_api_key(self):
        """Get Polygon API key."""
        if self._polygon_api_key is None:
            from api.config.api_keys import POLYGON_API_KEY
            self._polygon_api_key = POLYGON_API_KEY
        return self._polygon_api_key

    @property
    def market_context(self):
        """Get current market context (lazy-loaded and cached)."""
        if self._market_context is None:
            service = self.get_market_context_service()
            self._market_context = service.get_context()

            # Log context for debugging
            logger.info(f"Market Context: {self._market_context}")

        return self._market_context

    def get_market_context_service(self):
        """Get market context service (creates if needed)."""
        if self._market_context_service is None:
            from services.market_context_service import MarketContextService

            # Use DataServiceV2 as data provider
            data_service_v2 = self.get_data_service_v2()

            # Create service
            self._market_context_service = MarketContextService(data_service_v2)

        return self._market_context_service

    def get_data_service(self):
        """Get data service instance (DEPRECATED - use get_data_service_v2()).

        Only kept for backwards compatibility with old code.
        Returns DataServiceV2 which has the same universe methods.
        """
        return self.get_data_service_v2()

    def get_sqlmodel_engine(self):
        """Get or create SQLModel engine for DataServiceV2."""
        if self._sqlmodel_engine is None:
            from sqlmodel import create_engine
            database_url = f"sqlite:///{self.db_path}"
            self._sqlmodel_engine = create_engine(
                database_url,
                echo=False,
                connect_args={"check_same_thread": False}
            )
        return self._sqlmodel_engine

    def get_data_service_v2(self):
        """Get DataServiceV2 instance (new architecture).

        This creates DataServiceV2 with a SQLModel session.
        Cached for the lifetime of the Config object.

        Note: The session is long-lived for CLI use. For web apps,
        use per-request sessions instead.
        """
        if self._data_service_v2 is None:
            from sqlmodel import Session
            from services.data_service_v2 import DataServiceV2
            from api.config.api_keys import POLYGON_API_KEY

            # Create engine if needed
            engine = self.get_sqlmodel_engine()

            # Create session (long-lived for CLI)
            # Note: For web apps, use per-request sessions instead
            session = Session(engine)

            # Create DataServiceV2
            self._data_service_v2 = DataServiceV2(
                session=session,
                polygon_api_key=POLYGON_API_KEY,
                db_path=self.db_path
            )

        return self._data_service_v2

    def get_active_universe(self) -> str:
        """Get the currently active universe name."""
        if self._active_universe is None:
            try:
                data_service = self.get_data_service()
                active_universe = data_service.get_active_universe()
                if active_universe:
                    self._active_universe = active_universe.name
                else:
                    # Fallback if no universe is active
                    self._active_universe = "default_universe"
            except Exception as e:
                logger.debug(f"Error getting active universe: {e}")
                self._active_universe = "default_universe"

        return self._active_universe

    def set_active_universe(self, universe_name: str) -> bool:
        """Set the active universe in database."""
        try:
            data_service = self.get_data_service()
            success = data_service.set_active_universe(universe_name)

            if success:
                # Update cache
                self._active_universe = universe_name

            return success

        except Exception as e:
            logger.error(f"Failed to set active universe: {e}")
            return False


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