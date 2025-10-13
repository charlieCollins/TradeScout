"""Database command group for database management and data initialization."""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, TaskID
from rich.live import Live

from .main import pass_config

console = Console()


@click.group()
@pass_config
def database(config):
    """Database management and data initialization commands."""
    pass


@database.command('info')
@pass_config
def database_info(config):
    """Show database information and statistics."""
    if not Path(config.db_path).exists():
        console.print(f"[red]Database not found: {config.db_path}[/red]")
        console.print(f"[yellow]Run 'tradescout database init' to create database[/yellow]")
        sys.exit(1)

    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from database.database_initializer import DatabaseInitializer
        initializer = DatabaseInitializer(config.db_path)
    except Exception as e:
        console.print(f"[red]❌ Failed to initialize DatabaseInitializer: {e}[/red]")
        sys.exit(1)

    info = initializer.get_database_info()

    # Create a nice table for display
    table = Table(title="Database Information", show_header=True)
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Path", info['database_path'])
    table.add_row("Status", info.get('status', 'unknown'))
    table.add_row("Schema Version", str(info.get('schema_version', 'unknown')))

    console.print(table)

    if 'tables' in info:
        # Create table for statistics
        stats_table = Table(title="\nTable Statistics", show_header=True)
        stats_table.add_column("Table", style="cyan")
        stats_table.add_column("Records", justify="right", style="white")

        total_records = 0
        for table_name, count in sorted(info['tables'].items()):
            if isinstance(count, int):
                stats_table.add_row(table_name, f"{count:,}")
                total_records += count
            else:
                stats_table.add_row(table_name, str(count))

        console.print(stats_table)

    # Add recent operations table
    try:
        import sqlite3
        conn = sqlite3.connect(config.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute("""
                WITH latest_operations AS (
                    SELECT operation_type, operation_subtype, started_at, completed_at, status, total_items,
                           ROW_NUMBER() OVER (
                               PARTITION BY operation_type,
                               CASE WHEN operation_subtype IS NULL THEN '' ELSE operation_subtype END
                               ORDER BY started_at DESC
                           ) as rn
                    FROM data_update_metadata
                )
                SELECT operation_type, operation_subtype, started_at, completed_at, status, total_items,
                       CASE
                           WHEN started_at IS NOT NULL THEN
                               ROUND((julianday('now', 'localtime') - julianday(started_at)) * 24, 1)
                           ELSE NULL
                       END as age_hours
                FROM latest_operations
                WHERE rn = 1
                ORDER BY started_at DESC
            """)
            recent_ops = cursor.fetchall()
        finally:
            conn.close()

        if recent_ops:
            # Create recent operations table
            ops_table = Table(title="\nRecent Data Operations", show_header=True)
            ops_table.add_column("Operation", style="cyan")
            ops_table.add_column("Started", style="white")
            ops_table.add_column("Age", justify="right", style="white")
            ops_table.add_column("Status", style="white")
            ops_table.add_column("Items", justify="right", style="white")
            ops_table.add_column("Duration", justify="right", style="white")

            for op in recent_ops:
                operation_type, operation_subtype, started_at, completed_at, status, total_items, age_hours = op

                # Format operation name
                if operation_subtype:
                    operation_name = f"{operation_type}.{operation_subtype}"
                else:
                    operation_name = operation_type

                # Parse and format started time
                from datetime import datetime
                try:
                    started_dt = datetime.fromisoformat(started_at.replace('T', ' ').replace('Z', ''))
                    started_str = started_dt.strftime("%m-%d %H:%M")
                except:
                    started_str = started_at[:16] if started_at else "N/A"

                # Format status with colors
                if status == "completed":
                    status_str = f"[green]{status}[/green]"
                elif status == "running":
                    status_str = f"[yellow]{status}[/yellow]"
                elif status == "failed":
                    status_str = f"[red]{status}[/red]"
                else:
                    status_str = status or "unknown"

                # Format item count
                items_str = f"{total_items:,}" if total_items else "-"

                # Format age
                if age_hours is not None:
                    if age_hours < 1:
                        age_str = f"{age_hours * 60:.0f}m"  # Show minutes if less than 1 hour
                    elif age_hours < 24:
                        age_str = f"{age_hours:.1f}h"  # Show hours with decimal
                    else:
                        age_str = f"{age_hours / 24:.1f}d"  # Show days
                else:
                    age_str = "-"

                # Calculate duration
                if completed_at and started_at:
                    try:
                        started_dt = datetime.fromisoformat(started_at.replace('T', ' ').replace('Z', ''))
                        completed_dt = datetime.fromisoformat(completed_at.replace('T', ' ').replace('Z', ''))
                        duration = completed_dt - started_dt
                        duration_str = f"{duration.total_seconds():.1f}s"
                    except:
                        duration_str = "-"
                else:
                    duration_str = "-" if status == "completed" else "running"

                ops_table.add_row(operation_name, started_str, age_str, status_str, items_str, duration_str)

            console.print(ops_table)

    except Exception as e:
        # Don't fail the whole command if recent operations table fails
        console.print(f"[yellow]⚠️  Could not load recent operations: {e}[/yellow]")


@database.command('init')
@pass_config
def database_init(config):
    """Initialize database with schema."""
    console.print("[blue]Initializing database...[/blue]")

    # Ensure data directory exists
    db_dir = Path(config.db_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)

    # Check if database already exists
    db_exists = Path(config.db_path).exists()

    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from database.database_initializer import DatabaseInitializer
        initializer = DatabaseInitializer(config.db_path)
    except Exception as e:
        console.print(f"[red]❌ Failed to initialize DatabaseInitializer: {e}[/red]")
        sys.exit(1)

    if initializer.initialize_database():
        if db_exists:
            console.print("[green]✅ Database verified successfully[/green]")
        else:
            console.print("[green]✅ Database created successfully[/green]")

        # Show database info
        info = initializer.get_database_info()
        console.print(f"Database: {info['database_path']}")
        console.print(f"Schema version: {info.get('schema_version', 'unknown')}")

    else:
        console.print("[red]❌ Database initialization failed[/red]")
        sys.exit(1)


@database.command('reset')
@click.option('--force', '-f', is_flag=True, help='Skip confirmation prompt')
@pass_config
def database_reset(config, force):
    """Drop and recreate the database from scratch."""
    # Confirm with user unless forced
    if not force:
        console.print(f"[yellow]⚠️  This will DELETE the database: {config.db_path}[/yellow]")
        console.print("[yellow]All data will be lost![/yellow]")
        if not click.confirm("Are you sure?"):
            console.print("Reset cancelled")
            return

    # Delete the database file if it exists
    if Path(config.db_path).exists():
        console.print(f"Removing existing database: {config.db_path}")
        Path(config.db_path).unlink()
        console.print("[green]✅ Database removed[/green]")
    else:
        console.print("No existing database to remove")

    # Now recreate it
    console.print("Creating fresh database...")
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from database.database_initializer import DatabaseInitializer
        initializer = DatabaseInitializer(config.db_path)
    except Exception as e:
        console.print(f"[red]❌ Failed to initialize DatabaseInitializer: {e}[/red]")
        sys.exit(1)

    if initializer.initialize_database():
        console.print("[green]✅ Database recreated successfully[/green]")
    else:
        console.print("[red]❌ Database recreation failed[/red]")
        sys.exit(1)


@database.command('bootstrap-providers')
@pass_config
def bootstrap_providers(config):
    """Initialize/update all data providers."""
    console.print("[blue]Initializing data providers...[/blue]")

    # Check if database exists
    if not Path(config.db_path).exists():
        console.print(f"[red]Database not found: {config.db_path}[/red]")
        console.print("[yellow]Run 'tradescout database init' first[/yellow]")
        sys.exit(1)

    try:
        data_service = config.get_data_service_v2()
        count = data_service.bootstrap_providers()
    except Exception as e:
        console.print(f"[red]❌ Failed to bootstrap providers: {e}[/red]")
        sys.exit(1)

    if count > 0:
        console.print("[green]✅ Provider initialization completed[/green]")
        console.print(f"  Providers stored: {count}")
    else:
        console.print("[yellow]ℹ️  Provider already exists - skipping[/yellow]")

    # Show active provider
    active_provider = data_service.get_active_provider()
    if active_provider:
        console.print(f"\nActive provider: {active_provider.name}")


@database.command('bootstrap-markets')
@pass_config
def bootstrap_markets(config):
    """Initialize/update market data."""
    console.print("[blue]Initializing markets...[/blue]")

    # Check if database exists
    if not Path(config.db_path).exists():
        console.print(f"[red]Database not found: {config.db_path}[/red]")
        console.print("[yellow]Run 'tradescout database init' first[/yellow]")
        sys.exit(1)

    try:
        data_service = config.get_data_service_v2()
        count = data_service.bootstrap_markets(asset_class="stocks", locale="us")
    except Exception as e:
        console.print(f"[red]❌ Failed to bootstrap markets: {e}[/red]")
        sys.exit(1)

    console.print("[green]✅ Market initialization completed[/green]")
    console.print(f"  Markets stored: {count}")

    # Show markets
    markets = data_service.get_all_markets(active_only=True)
    if markets:
        console.print(f"\nConfigured markets ({len(markets)}):")
        for market in markets[:10]:  # Show first 10
            console.print(f"  - {market.code}: {market.name}")
        if len(markets) > 10:
            console.print(f"  ... and {len(markets) - 10} more")


@database.command('bootstrap-tickers')
@click.option('--limit', type=int, help='Limit number of tickers to fetch (for testing)')
@click.option('--force', '-f', is_flag=True, help='Force refresh even if data is fresh')
@pass_config
def bootstrap_tickers(config, limit, force):
    """Initialize/update ticker data from Polygon API."""
    from output.cli_adapter import CLIOutputAdapter, CLIProgressReporter

    console.print("[blue]Initializing tickers from Polygon...[/blue]")

    if limit:
        console.print(f"[yellow]Note: --limit not supported by bootstrap_assets, will fetch all tickers[/yellow]")

    # Check if database exists
    if not Path(config.db_path).exists():
        console.print(f"[red]Database not found: {config.db_path}[/red]")
        console.print("[yellow]Run 'tradescout database init' first[/yellow]")
        sys.exit(1)

    try:
        data_service = config.get_data_service_v2()

        # Create CLI output adapters
        progress_reporter = CLIProgressReporter(console=console)
        output_adapter = CLIOutputAdapter(console=console)

        # Bootstrap assets with progress reporting
        result = data_service.bootstrap_assets(
            market="stocks", active=True, progress=progress_reporter
        )

        # Display results using adapter
        output_adapter.display_bootstrap_result(result)

    except Exception as e:
        console.print(f"[red]❌ Failed to bootstrap assets: {e}[/red]")
        sys.exit(1)

    # Show stats
    try:
        asset_stats = data_service.get_asset_stats()
        console.print(f"  Total assets in database: {asset_stats.get('total_active_assets', 0):,}")
    except Exception as e:
        console.print(f"[yellow]⚠️  Could not fetch stats: {e}[/yellow]")


@database.command('bootstrap-universes')
@click.option('--force', '-f', is_flag=True, help='Force refresh even if data is fresh')
@pass_config
def bootstrap_universes(config, force):
    """Initialize/update all asset universes from config."""
    console.print("[blue]Initializing all universes from config...[/blue]")

    # Check if database exists
    if not Path(config.db_path).exists():
        console.print(f"[red]Database not found: {config.db_path}[/red]")
        console.print("[yellow]Run 'tradescout database init' first[/yellow]")
        sys.exit(1)

    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from utils.config_loader import get_config_loader

        data_service = config.get_data_service_v2()
    except Exception as e:
        console.print(f"[red]❌ Failed to initialize DataService: {e}[/red]")
        sys.exit(1)

    # Get all universe names from config
    config_loader = get_config_loader()
    all_universes = config_loader.load_all_universes()
    universe_names = list(all_universes.keys())
    console.print(f"[blue]Found {len(universe_names)} universes in config: {', '.join(universe_names)}[/blue]")

    total_success = 0
    total_failed = 0

    # Bootstrap each universe
    for universe_name in universe_names:
        console.print(f"\n[bold]Bootstrapping '{universe_name}'...[/bold]")

        try:
            stats = data_service.bootstrap_universes(universe_name=universe_name, force_refresh=force)

            if stats and not stats.get('skipped', False):
                members = stats.get('filtered_assets', 0)
                if members == 0:
                    console.print(f"[yellow]⚠️  {universe_name}: {members:,} members - Universe is empty! This may indicate missing fundamentals data.[/yellow]")
                else:
                    console.print(f"[green]✅ {universe_name}: {members:,} members[/green]")

                total_success += 1
            elif stats and stats.get('skipped'):
                console.print(f"[cyan]⏭️  {universe_name}: Skipped (data is fresh)[/cyan]")
                total_success += 1
            else:
                console.print(f"[red]❌ {universe_name}: Failed to bootstrap[/red]")
                total_failed += 1

        except Exception as e:
            console.print(f"[red]❌ {universe_name}: Error - {e}[/red]")
            total_failed += 1

    # Set default_universe as active after all universes are created
    if total_success > 0:
        console.print(f"\n[blue]Setting default_universe as active...[/blue]")
        data_service.set_active_universe("default_universe")
        console.print(f"[green]✅ default_universe is now the active universe[/green]")

    # Summary
    console.print(f"\n[bold]Universe Bootstrap Complete[/bold]")
    console.print(f"[green]✅ Successful: {total_success}[/green]")
    if total_failed > 0:
        console.print(f"[red]❌ Failed: {total_failed}[/red]")

    if total_failed > 0:
        sys.exit(1)


@database.command('bootstrap-fundamentals')
@click.option('--symbol', help='Bootstrap fundamentals for specific symbol only')
@click.option('--force', '-f', is_flag=True, help='Refresh existing fundamentals data')
@click.option('--limit', type=int, help='Limit number of symbols to process (for testing)')
@pass_config
def bootstrap_fundamentals(config, symbol, force, limit):
    """Bootstrap fundamentals data from Polygon API ticker overview."""
    from output.cli_adapter import CLIOutputAdapter, CLIProgressReporter

    if symbol:
        console.print(f"[blue]Bootstrapping fundamentals for {symbol}...[/blue]")
        console.print(f"[yellow]Note: Single symbol bootstrap not yet supported, will bootstrap all assets[/yellow]")

    # Check if database exists
    if not Path(config.db_path).exists():
        console.print(f"[red]Database not found: {config.db_path}[/red]")
        console.print("[yellow]Run 'tradescout database init' first[/yellow]")
        sys.exit(1)

    try:
        data_service = config.get_data_service_v2()

        if limit:
            console.print(f"[blue]Processing up to {limit:,} assets from database[/blue]")
        else:
            console.print(f"[blue]Processing all assets from database[/blue]")

        # Create CLI output adapters
        progress_reporter = CLIProgressReporter(console=console)
        output_adapter = CLIOutputAdapter(console=console)

        # Bootstrap fundamentals with progress reporting
        result = data_service.bootstrap_fundamentals(
            limit=limit, progress=progress_reporter
        )

        # Display results using adapter
        output_adapter.display_bootstrap_result(result)

        # Show current database stats
        fundamentals_stats = data_service.get_fundamentals_stats()
        console.print(
            f"  Total fundamentals in database: {fundamentals_stats.get('total_fundamentals', 0):,}"
        )

    except Exception as e:
        console.print(f"[red]❌ Fundamentals bootstrap failed: {e}[/red]")
        sys.exit(1)


@database.command('bootstrap-all')
@click.option('--force', '-f', is_flag=True, help='Skip confirmation prompt')
@pass_config
def bootstrap_all(config, force):
    """Run all bootstrap operations in sequence."""

    # Check if database exists and has data
    if Path(config.db_path).exists() and not force:
        try:
            # Use data service V2 to get database stats
            from sqlmodel import Session, create_engine
            from services.data_service_v2 import DataServiceV2
            from api.config.api_keys import POLYGON_API_KEY

            # Create DataServiceV2
            engine = create_engine(f"sqlite:///{config.db_path}", echo=False,
                                  connect_args={"check_same_thread": False})
            session = Session(engine)
            data_service = DataServiceV2(session, POLYGON_API_KEY, db_path=config.db_path)
            stats = data_service.get_database_stats()

            if not stats:
                console.print("[red]❌ Failed to get database statistics[/red]")
                sys.exit(1)

            asset_count = stats.table_counts.get('assets', 0)
            universe_count = stats.table_counts.get('universe_memberships', 0)

            if asset_count > 0 or universe_count > 0:
                console.print(f"[yellow]⚠️  Database contains existing data:[/yellow]")
                console.print(f"  - {asset_count:,} assets")
                console.print(f"  - {universe_count:,} universe members")
                console.print("[yellow]Running bootstrap will refresh all data from APIs.[/yellow]")

                if not click.confirm("Continue with bootstrap?"):
                        console.print("Bootstrap cancelled")
                        return
        except Exception:
            # If we can't check, just proceed
            pass

    console.print("[blue]Running complete bootstrap sequence...[/blue]")

    # 1. Database
    console.print("\n[bold]Step 1: Database Schema[/bold]")
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from database.database_initializer import DatabaseInitializer
        initializer_db = DatabaseInitializer(config.db_path)
        if not initializer_db.initialize_database():
            console.print("[red]Database initialization failed, stopping[/red]")
            sys.exit(1)
        console.print("[green]✅ Database schema initialized[/green]")
    except Exception as e:
        console.print(f"[red]Database initialization failed: {e}[/red]")
        sys.exit(1)

    # Get DataService for remaining operations
    try:
        data_service = config.get_data_service_v2()
    except Exception as e:
        console.print(f"[red]Failed to initialize DataService: {e}[/red]")
        sys.exit(1)

    # 2. Providers
    console.print("\n[bold]Step 2: Data Providers[/bold]")
    try:
        count = data_service.bootstrap_providers()
        console.print(f"[green]✅ Providers: {count} stored[/green]")
    except Exception as e:
        console.print(f"[red]Provider bootstrap failed: {e}[/red]")
        sys.exit(1)

    # 3. Markets
    console.print("\n[bold]Step 3: Markets[/bold]")
    try:
        count = data_service.bootstrap_markets(asset_class="stocks", locale="us")
        console.print(f"[green]✅ Markets: {count} stored[/green]")
    except Exception as e:
        console.print(f"[red]Market bootstrap failed: {e}[/red]")
        # Continue anyway as markets might be created by ticker bootstrap

    # 4. Assets/Tickers
    console.print("\n[bold]Step 4: Assets from Polygon[/bold]")
    try:
        count = data_service.bootstrap_assets(market="stocks", active=True)
        console.print(f"[green]✅ Assets: {count:,} stored[/green]")
    except Exception as e:
        console.print(f"[red]Asset bootstrap failed: {e}[/red]")
        sys.exit(1)

    # 5. Universes (all from config)
    console.print("\n[bold]Step 5: Asset Universes[/bold]")
    try:
        from utils.config_loader import get_config_loader

        config_loader = get_config_loader()
        all_universes = config_loader.load_all_universes()
        universe_names = list(all_universes.keys())

        for universe_name in universe_names:
            stats = data_service.bootstrap_universes(universe_name=universe_name, force_refresh=force)
            members = stats.get('filtered_assets', 0)
            if members == 0:
                console.print(f"[yellow]⚠️  {universe_name}: {members:,} members - Universe is empty! This may indicate missing fundamentals data.[/yellow]")
            else:
                console.print(f"[green]✅ {universe_name}: {members:,} members[/green]")

        # Set default_universe as active
        data_service.set_active_universe("default_universe")

    except Exception as e:
        console.print(f"[red]Universe bootstrap failed: {e}[/red]")
        sys.exit(1)

    console.print("\n[bold green]✅ Complete bootstrap successful![/bold green]")
    console.print("Database is ready for use.")