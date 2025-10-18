"""Federal Reserve data command group for economic data operations."""

import sys
import logging
from pathlib import Path
from datetime import datetime

import click
from rich.console import Console
from rich.table import Table
from rich import box

from .main import pass_config

console = Console()
logger = logging.getLogger(__name__)


@click.group()
@pass_config
def fed(app_context):
    """Federal Reserve economic data operations."""
    pass


@fed.command()
@click.option("--limit", default=10, help="Number of observations to fetch for each data type (default: 10)")
@pass_config
def update(app_context, limit: int):
    """
    Fetch and store latest Federal Reserve economic data.

    Retrieves data from Polygon API for:
    - Inflation (CPI, PCE, etc.)
    - Inflation expectations
    - Treasury yields (various maturities)

    Example:
        tradescout fed update
        tradescout fed update --limit 20
    """
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))

        data_service = app_context.get_data_service_v2()
    except Exception as e:
        console.print(f"[red]❌ Failed to initialize data service: {e}[/red]")
        sys.exit(1)

    try:
        from models.dataclass.fed_result import FedUpdateResult

        console.print(f"[cyan]📊 Fetching Federal Reserve economic data (limit={limit})...[/cyan]")
        console.print()

        # Fetch all fed data
        start_time = datetime.now()

        # Get the polygon fed provider
        from api.providers.polygon_fed_provider import PolygonFedProvider
        api_key = app_context.polygon_api_key
        fed_provider = PolygonFedProvider(api_key)

        # Fetch all data types
        all_data = fed_provider.fetch_all_fed_data(limit=limit)

        # Store to database
        total_stored = 0
        data_by_type = {}

        for data_type, fed_data_list in all_data.items():
            if fed_data_list:
                stored = data_service.fed_bulk_upsert(fed_data_list)
                total_stored += stored
                data_by_type[data_type] = stored
            else:
                data_by_type[data_type] = 0

        elapsed = (datetime.now() - start_time).total_seconds()

        # Create result and display
        result = FedUpdateResult(
            data_by_type=data_by_type,
            total_stored=total_stored,
            elapsed_seconds=elapsed
        )
        app_context.presentation.fed_adapter.display_fed_update_result(result)

    except Exception as e:
        console.print(f"[red]❌ Failed to update fed data: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


@fed.command()
@click.option("--limit", default=5, help="Number of recent observations to display for each data type (default: 5)")
@pass_config
def info(app_context, limit: int):
    """
    Display latest Federal Reserve economic data.

    Shows recent observations for:
    - Inflation
    - Inflation expectations
    - Treasury yields

    Example:
        tradescout fed info
        tradescout fed info --limit 10
    """
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))

        data_service = app_context.get_data_service_v2()
    except Exception as e:
        console.print(f"[red]❌ Failed to initialize data service: {e}[/red]")
        sys.exit(1)

    try:
        from models.dataclass.fed_result import FedInfoResult, FedInfoSection

        # Get latest for each type
        latest_data = data_service.fed_get_all_latest()

        # Build sections
        data_types = [
            ("inflation", "Inflation"),
            ("inflation_expectations", "Inflation Expectations"),
            ("treasury_yields", "Treasury Yields"),
        ]

        sections = []
        for data_type_key, display_name in data_types:
            latest = latest_data.get(data_type_key)

            # Get recent history
            recent = data_service.fed_get_recent_by_type(data_type_key, limit=limit) if latest else []

            sections.append(FedInfoSection(
                data_type_key=data_type_key,
                display_name=display_name,
                latest=latest,
                recent=recent
            ))

        # Create result and display
        result = FedInfoResult(sections=sections)
        app_context.presentation.fed_adapter.display_fed_info_result(result)

    except Exception as e:
        console.print(f"[red]❌ Failed to display fed data: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)
