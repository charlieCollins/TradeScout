"""Bootstrap command group for database and data initialization."""

import sys
from pathlib import Path

import click
from rich.console import Console

from .main import pass_config

console = Console()


@click.group()
@pass_config
def bootstrap(config):
    """Database and data initialization commands."""
    pass


# Database group
@bootstrap.group()
@pass_config
def database(config):
    """Database management commands."""
    pass


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
        from database.bootstrapper_database import DatabaseBootstrapper
        bootstrapper = DatabaseBootstrapper(config.db_path)
    except Exception as e:
        console.print(f"[red]❌ Failed to initialize DatabaseBootstrapper: {e}[/red]")
        sys.exit(1)

    if bootstrapper.bootstrap_database():
        if db_exists:
            console.print("[green]✅ Database verified successfully[/green]")
        else:
            console.print("[green]✅ Database created successfully[/green]")

        # Show database info
        info = bootstrapper.get_database_info()
        console.print(f"Database: {info['database_path']}")
        console.print(f"Schema version: {info.get('schema_version', 'unknown')}")

        if 'tables' in info:
            console.print("Table status:")
            for table, count in info['tables'].items():
                console.print(f"  - {table}: {count} records")

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
        from database.bootstrapper_database import DatabaseBootstrapper
        bootstrapper = DatabaseBootstrapper(config.db_path)
    except Exception as e:
        console.print(f"[red]❌ Failed to initialize DatabaseBootstrapper: {e}[/red]")
        sys.exit(1)

    if bootstrapper.bootstrap_database():
        console.print("[green]✅ Database recreated successfully[/green]")
    else:
        console.print("[red]❌ Database recreation failed[/red]")
        sys.exit(1)


@database.command('info')
@pass_config
def database_info(config):
    """Show database information and statistics."""
    if not Path(config.db_path).exists():
        console.print(f"[red]Database not found: {config.db_path}[/red]")
        sys.exit(1)

    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from database.bootstrapper_database import DatabaseBootstrapper
        bootstrapper = DatabaseBootstrapper(config.db_path)
    except Exception as e:
        console.print(f"[red]❌ Failed to initialize DatabaseBootstrapper: {e}[/red]")
        sys.exit(1)

    info = bootstrapper.get_database_info()

    console.print(f"Database: {info['database_path']}")
    console.print(f"Status: {info.get('status', 'unknown')}")
    console.print(f"Schema version: {info.get('schema_version', 'unknown')}")

    if 'tables' in info:
        console.print("\nTable statistics:")
        total_records = 0
        for table, count in info['tables'].items():
            if isinstance(count, int):
                console.print(f"  - {table}: {count:,} records")
                total_records += count
            else:
                console.print(f"  - {table}: {count}")
        console.print(f"\nTotal records: {total_records:,}")


# Tickers command group
@bootstrap.group()
@pass_config
def tickers(config):
    """Manage ticker data from Polygon API."""
    pass


@tickers.command('init')
@click.option('--limit', type=int, help='Limit number of tickers to fetch (for testing)')
@pass_config
def tickers_init(config, limit):
    """Initialize/update ticker data from Polygon API (idempotent)."""
    console.print("[blue]Initializing tickers from Polygon...[/blue]")

    # Check if database exists
    if not Path(config.db_path).exists():
        console.print(f"[red]Database not found: {config.db_path}[/red]")
        console.print("[yellow]Run 'tradescout bootstrap database init' first[/yellow]")
        sys.exit(1)

    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from database.database_manager import DatabaseManager
        from config.api_keys import POLYGON_API_KEY
        from bootstrapping.bootstrapper_ticker import TickerBootstrapper

        db_manager = DatabaseManager(config.db_path)
        bootstrapper = TickerBootstrapper(api_key=POLYGON_API_KEY, db_manager=db_manager)
    except Exception as e:
        console.print(f"[red]❌ Failed to initialize TickerBootstrapper: {e}[/red]")
        sys.exit(1)

    # Fetch tickers with optional filtering
    success = bootstrapper.bootstrap_all_tickers(limit=limit)

    if success:
        stats = bootstrapper.get_bootstrap_stats()
        console.print("[green]✅ Ticker initialization completed[/green]")
        console.print(f"  Total fetched: {stats.get('total_fetched', 0)}")
        console.print(f"  Inserted: {stats.get('inserted', 0)}")
        console.print(f"  Updated: {stats.get('updated', 0)}")
        console.print(f"  Errors: {stats.get('errors', 0)}")
    else:
        console.print("[red]❌ Ticker initialization failed[/red]")
        sys.exit(1)


@tickers.command('info')
@pass_config
def tickers_info(config):
    """Show ticker database statistics."""
    console.print("[blue]Fetching ticker statistics...[/blue]")

    # Check if database exists
    if not Path(config.db_path).exists():
        console.print(f"[red]Database not found: {config.db_path}[/red]")
        console.print("[yellow]Run 'tradescout bootstrap database init' first[/yellow]")
        sys.exit(1)

    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from database.database_manager import DatabaseManager
        db_manager = DatabaseManager(config.db_path)
    except Exception as e:
        console.print(f"[red]❌ Failed to initialize DatabaseManager: {e}[/red]")
        sys.exit(1)

    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()

            # Total assets
            cursor.execute("SELECT COUNT(*) FROM assets")
            total_assets = cursor.fetchone()[0]

            # Active vs inactive
            cursor.execute("SELECT is_active, COUNT(*) FROM assets GROUP BY is_active")
            active_stats = dict(cursor.fetchall())

            # By market
            cursor.execute("""
                SELECT m.name, COUNT(*)
                FROM assets a
                JOIN markets m ON a.market_id = m.id
                GROUP BY m.name
            """)
            market_stats = dict(cursor.fetchall())

            # Most recent update
            cursor.execute("SELECT MAX(updated_at) FROM assets")
            last_update = cursor.fetchone()[0]

        console.print("📊 Ticker Database Statistics")
        console.print(f"  Total assets: {total_assets:,}")
        console.print(f"  Active: {active_stats.get(1, 0):,}")
        console.print(f"  Inactive: {active_stats.get(0, 0):,}")
        console.print("  By market:")
        for market, count in market_stats.items():
            console.print(f"    {market}: {count:,}")
        console.print(f"  Last updated: {last_update}")

    except Exception as e:
        console.print(f"[red]Failed to fetch ticker statistics: {e}[/red]")
        sys.exit(1)


# Universe command group
@bootstrap.group()
@pass_config
def universe(config):
    """Manage asset universes."""
    pass


@universe.command('init')
@click.option('--universe', default='default_universe',
              help='Universe name to bootstrap (default: default_universe)')
@pass_config
def universe_init(config, universe):
    """Initialize/update asset universe (idempotent)."""
    console.print(f"[blue]Initializing universe '{universe}'...[/blue]")

    # Check if database exists
    if not Path(config.db_path).exists():
        console.print(f"[red]Database not found: {config.db_path}[/red]")
        console.print("[yellow]Run 'tradescout bootstrap database init' first[/yellow]")
        sys.exit(1)

    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from bootstrapping.bootstrapper_universe import UniverseBootstrapper
        bootstrapper = UniverseBootstrapper(config.db_path)
    except Exception as e:
        console.print(f"[red]❌ Failed to initialize UniverseBootstrapper: {e}[/red]")
        sys.exit(1)

    # Bootstrap specified universe or default
    success = bootstrapper.bootstrap_universe(universe)

    if success:
        stats = bootstrapper.get_universe_stats(universe)
        console.print(f"[green]✅ Universe '{universe}' initialized[/green]")
        console.print(f"  Total members: {stats.get('total_members', 0)}")
        console.print(f"  Active members: {stats.get('active_members', 0)}")

        # Show breakdown by type if available
        if 'by_type' in stats:
            console.print("  By type:")
            for asset_type, count in stats['by_type'].items():
                console.print(f"    - {asset_type}: {count}")
    else:
        console.print(f"[red]❌ Universe initialization failed[/red]")
        sys.exit(1)


@universe.command('info')
@click.option('--universe', default='default_universe',
              help='Universe name to show (default: default_universe)')
@pass_config
def universe_info(config, universe):
    """Show asset universe statistics."""
    console.print(f"[blue]Fetching universe '{universe}' statistics...[/blue]")

    # Check if database exists
    if not Path(config.db_path).exists():
        console.print(f"[red]Database not found: {config.db_path}[/red]")
        console.print("[yellow]Run 'tradescout bootstrap database init' first[/yellow]")
        sys.exit(1)

    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from bootstrapping.bootstrapper_universe import UniverseBootstrapper
        bootstrapper = UniverseBootstrapper(config.db_path)
    except Exception as e:
        console.print(f"[red]❌ Failed to initialize UniverseBootstrapper: {e}[/red]")
        sys.exit(1)

    try:
        stats = bootstrapper.get_universe_stats(universe)

        if stats.get('total_members', 0) == 0:
            console.print(f"[yellow]📊 Universe '{universe}' is empty or doesn't exist[/yellow]")
            console.print("[yellow]Run 'tradescout bootstrap universe init' to populate it[/yellow]")
            return

        console.print(f"📊 Universe '{universe}' Statistics")
        console.print(f"  Total members: {stats.get('total_members', 0):,}")
        console.print(f"  Active members: {stats.get('active_members', 0):,}")
        console.print(f"  Inactive members: {stats.get('inactive_members', 0):,}")

        # Show breakdown by type if available
        if 'by_type' in stats:
            console.print("  By asset type:")
            for asset_type, count in stats['by_type'].items():
                console.print(f"    - {asset_type}: {count:,}")

        # Show breakdown by market if available
        if 'by_market' in stats:
            console.print("  By market:")
            for market, count in stats['by_market'].items():
                console.print(f"    - {market}: {count:,}")

        # Last updated
        if 'last_updated' in stats:
            console.print(f"  Last updated: {stats['last_updated']}")

    except Exception as e:
        console.print(f"[red]Failed to fetch universe statistics: {e}[/red]")
        sys.exit(1)


# All command
@bootstrap.command('all')
@pass_config
def bootstrap_all(config):
    """Run all bootstrap operations in sequence."""
    console.print("[blue]Running complete bootstrap sequence...[/blue]")

    # 1. Database
    console.print("\n=== Step 1: Database ===")
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from database.bootstrapper_database import DatabaseBootstrapper
        bootstrapper_db = DatabaseBootstrapper(config.db_path)
        if not bootstrapper_db.bootstrap_database():
            console.print("[red]Database initialization failed, stopping[/red]")
            sys.exit(1)
    except Exception as e:
        console.print(f"[red]Database bootstrap failed: {e}[/red]")
        sys.exit(1)

    # 2. Tickers
    console.print("\n=== Step 2: Tickers ===")
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from config.api_keys import POLYGON_API_KEY
        from database.database_manager import DatabaseManager
        from bootstrapping.bootstrapper_ticker import TickerBootstrapper

        db_manager = DatabaseManager(config.db_path)
        bootstrapper_ticker = TickerBootstrapper(api_key=POLYGON_API_KEY, db_manager=db_manager)
        if not bootstrapper_ticker.bootstrap_all_tickers():
            console.print("[red]Ticker bootstrap failed, stopping[/red]")
            sys.exit(1)
    except Exception as e:
        console.print(f"[red]Ticker bootstrap failed: {e}[/red]")
        sys.exit(1)

    # 3. Universe
    console.print("\n=== Step 3: Universe ===")
    try:
        from bootstrapping.bootstrapper_universe import UniverseBootstrapper
        bootstrapper_universe = UniverseBootstrapper(config.db_path)
        if not bootstrapper_universe.bootstrap_universe("default_universe"):
            console.print("[red]Universe bootstrap failed, stopping[/red]")
            sys.exit(1)
    except Exception as e:
        console.print(f"[red]Universe bootstrap failed: {e}[/red]")
        sys.exit(1)

    console.print("\n[green]✅ Complete bootstrap successful![/green]")