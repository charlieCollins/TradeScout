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
        console.print(f"\n[bold green]Total records: {total_records:,}[/bold green]")


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
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from database.database_manager import DatabaseManager
        from bootstrapping.bootstrapper_provider import ProviderBootstrapper

        db_manager = DatabaseManager(config.db_path)
        bootstrapper = ProviderBootstrapper(db_manager=db_manager)
    except Exception as e:
        console.print(f"[red]❌ Failed to initialize ProviderBootstrapper: {e}[/red]")
        sys.exit(1)

    stats = bootstrapper.bootstrap_providers()

    console.print("[green]✅ Provider initialization completed[/green]")
    console.print(f"  Inserted: {stats.get('inserted', 0)}")
    console.print(f"  Updated: {stats.get('updated', 0)}")
    console.print(f"  Errors: {stats.get('errors', 0)}")

    # Show active providers
    active = bootstrapper.get_active_providers()
    if active:
        console.print("\nActive providers:")
        for provider in active:
            console.print(f"  - {provider}")


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
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from database.database_manager import DatabaseManager
        from bootstrapping.bootstrapper_market import MarketBootstrapper

        db_manager = DatabaseManager(config.db_path)
        bootstrapper = MarketBootstrapper(db_manager=db_manager)
    except Exception as e:
        console.print(f"[red]❌ Failed to initialize MarketBootstrapper: {e}[/red]")
        sys.exit(1)

    stats = bootstrapper.bootstrap_markets()

    console.print("[green]✅ Market initialization completed[/green]")
    console.print(f"  Inserted: {stats.get('inserted', 0)}")
    console.print(f"  Updated: {stats.get('updated', 0)}")
    console.print(f"  Errors: {stats.get('errors', 0)}")

    # Show markets
    markets = bootstrapper.get_markets()
    if markets:
        console.print("\nConfigured markets:")
        for market in markets:
            console.print(f"  - {market}")


@database.command('bootstrap-tickers')
@click.option('--limit', type=int, help='Limit number of tickers to fetch (for testing)')
@click.option('--force', '-f', is_flag=True, help='Force refresh even if data is fresh')
@pass_config
def bootstrap_tickers(config, limit, force):
    """Initialize/update ticker data from Polygon API."""
    console.print("[blue]Initializing tickers from Polygon...[/blue]")

    # Check if database exists
    if not Path(config.db_path).exists():
        console.print(f"[red]Database not found: {config.db_path}[/red]")
        console.print("[yellow]Run 'tradescout database init' first[/yellow]")
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
    success = bootstrapper.bootstrap_all_tickers(limit=limit, force=force)

    if success:
        stats = bootstrapper.get_bootstrap_stats()
        console.print("[green]✅ Ticker initialization completed[/green]")
        console.print(f"  Total fetched: {stats.get('total_fetched', 0):,}")
        console.print(f"  Inserted: {stats.get('inserted', 0):,}")
        console.print(f"  Updated: {stats.get('updated', 0):,}")
        console.print(f"  Errors: {stats.get('errors', 0):,}")
    else:
        console.print("[red]❌ Ticker initialization failed[/red]")
        sys.exit(1)


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
        from bootstrapping.bootstrapper_universe import UniverseBootstrapper
        from config.universe_config import UNIVERSE_CONFIG

        bootstrapper = UniverseBootstrapper(db_manager=config.db_manager)
    except Exception as e:
        console.print(f"[red]❌ Failed to initialize UniverseBootstrapper: {e}[/red]")
        sys.exit(1)

    # Get all universe names from config
    universe_names = list(UNIVERSE_CONFIG.keys())
    console.print(f"[blue]Found {len(universe_names)} universes in config: {', '.join(universe_names)}[/blue]")

    total_success = 0
    total_failed = 0

    # Bootstrap each universe
    for universe_name in universe_names:
        console.print(f"\n[bold]Bootstrapping '{universe_name}'...[/bold]")

        try:
            success = bootstrapper.bootstrap_universe(universe_name, force=force)

            if success:
                stats = bootstrapper.get_universe_stats(universe_name)
                members = stats.get('total_members', 0)
                if members == 0:
                    console.print(f"[yellow]⚠️  {universe_name}: {members:,} members - Universe is empty! This may indicate missing fundamentals data.[/yellow]")
                else:
                    console.print(f"[green]✅ {universe_name}: {members:,} members[/green]")

                # Show breakdown by type if available
                if 'by_type' in stats and stats['by_type']:
                    breakdown = ", ".join([f"{t}: {c}" for t, c in stats['by_type'].items()])
                    console.print(f"[dim]  └─ {breakdown}[/dim]")

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
        if config.set_active_universe("default_universe"):
            console.print(f"[green]✅ default_universe is now the active universe[/green]")
        else:
            console.print(f"[yellow]⚠️  Could not set default_universe as active[/yellow]")

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
    if symbol:
        console.print(f"[blue]Bootstrapping fundamentals for {symbol}...[/blue]")
    else:
        console.print("[blue]Bootstrapping fundamentals for active universe assets...[/blue]")

    # Check if database exists
    if not Path(config.db_path).exists():
        console.print(f"[red]Database not found: {config.db_path}[/red]")
        console.print("[yellow]Run 'tradescout database init' first[/yellow]")
        sys.exit(1)

    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from bootstrapping.bootstrapper_fundamentals import FundamentalsBootstrapper

        bootstrapper = FundamentalsBootstrapper(db_manager=config.db_manager)
    except Exception as e:
        console.print(f"[red]❌ Failed to initialize FundamentalsBootstrapper: {e}[/red]")
        sys.exit(1)

    try:
        # Set up progress tracking
        progress_task = None
        current_symbol = None

        def progress_callback(symbol_name, current, total):
            nonlocal progress_task, current_symbol
            current_symbol = symbol_name
            if progress_task:
                progress.update(progress_task, completed=current, description=f"Processing {symbol_name}")

        # Run the bootstrap with progress display
        if symbol:
            console.print(f"[blue]Processing single symbol: {symbol}[/blue]")
            stats = bootstrapper.bootstrap_fundamentals(symbol=symbol, force=force, limit=limit)
        else:
            # Get active universe info for display
            data_provider = config.get_data_provider()
            active_universe = data_provider.get_active_universe()
            universe_name = active_universe.name if active_universe else "unknown"
            universe_stats = data_provider.get_universe_stats(universe_name) if active_universe else None
            num_assets = universe_stats.total_members if universe_stats else 0

            if limit:
                console.print(f"[blue]Processing up to {limit:,} assets from active universe: [cyan]{universe_name}[/cyan] ({num_assets:,} assets)[/blue]")
            else:
                console.print(f"[blue]Processing assets from active universe: [cyan]{universe_name}[/cyan] ({num_assets:,} assets)[/blue]")

            # Rich Live for real-time updates
            progress_text = "Initializing..."

            with Live(progress_text, console=console, refresh_per_second=4) as live:
                def enhanced_progress_callback(symbol_name, current, total):
                    # Get current stats from bootstrapper
                    current_stats = getattr(bootstrapper, 'current_stats', {})
                    not_found_count = current_stats.get('not_found', 0)

                    # Calculate percentage
                    percentage = (current / total * 100) if total > 0 else 0

                    if not_found_count > 0:
                        status_text = f"[blue]Processing [cyan]{symbol_name}[/cyan] ({current:,}/{total:,}) [yellow]404s: {not_found_count}[/yellow] - {percentage:.1f}%[/blue]"
                    else:
                        status_text = f"[blue]Processing [cyan]{symbol_name}[/cyan] ({current:,}/{total:,}) - {percentage:.1f}%[/blue]"

                    live.update(status_text)

                stats = bootstrapper.bootstrap_fundamentals(
                    symbol=symbol,
                    force=force,
                    limit=limit,
                    progress_callback=enhanced_progress_callback
                )

            # Show completion message like market update
            total_processed = stats['inserted'] + stats['updated']
            console.print(f"[green]✅ Processed {total_processed:,} fundamentals records[/green]")

        # Display results
        console.print("\n[bold]Fundamentals Bootstrap Results:[/bold]")
        console.print(f"[green]✅ Inserted: {stats['inserted']:,}[/green]")
        console.print(f"[cyan]🔄 Updated: {stats['updated']:,}[/cyan]")
        console.print(f"[yellow]⏭️ Skipped: {stats['skipped']:,}[/yellow]")
        console.print(f"[blue]📡 API Calls: {stats['api_calls']:,}[/blue]")

        if stats.get('not_found', 0) > 0:
            console.print(f"[yellow]🔍 Not Found (404): {stats['not_found']:,}[/yellow]")

        if stats['errors'] > 0:
            console.print(f"[red]❌ Errors: {stats['errors']:,}[/red]")

        total_processed = stats['inserted'] + stats['updated']
        console.print(f"\n[bold green]✅ Fundamentals bootstrap complete: {total_processed:,} records processed[/bold green]")

        # Show not found symbols if any
        not_found_symbols = stats.get('not_found_symbols', [])
        if not_found_symbols:
            console.print(f"\n[yellow]❓ Symbols not found in Polygon API ({len(not_found_symbols)})[/yellow]")
            if len(not_found_symbols) <= 20:
                # Show all if 20 or fewer
                console.print(f"[dim]{', '.join(not_found_symbols)}[/dim]")
            else:
                # Show first 15 and indicate there are more
                console.print(f"[dim]{', '.join(not_found_symbols[:15])}, ... and {len(not_found_symbols) - 15} more[/dim]")

        if total_processed == 0 and not symbol:
            console.print("[yellow]ℹ️  No new fundamentals data was added. Use --force to refresh existing data.[/yellow]")

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
            from database.database_manager import DatabaseManager
            db_manager = DatabaseManager(config.db_path)

            # Use data provider to get database stats
            from provider.data_provider import PolygonDataProvider
            data_provider = PolygonDataProvider(db_manager)
            stats = data_provider.get_database_stats()

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

    # 2. Providers
    console.print("\n[bold]Step 2: Data Providers[/bold]")
    try:
        from database.database_manager import DatabaseManager
        from bootstrapping.bootstrapper_provider import ProviderBootstrapper

        db_manager = DatabaseManager(config.db_path)
        bootstrapper_provider = ProviderBootstrapper(db_manager=db_manager)
        stats = bootstrapper_provider.bootstrap_providers()
        console.print(f"[green]✅ Providers: {stats['inserted']} inserted, {stats['updated']} updated[/green]")
    except Exception as e:
        console.print(f"[red]Provider bootstrap failed: {e}[/red]")
        sys.exit(1)

    # 3. Markets (if bootstrapper exists)
    console.print("\n[bold]Step 3: Markets[/bold]")
    try:
        from bootstrapping.bootstrapper_market import MarketBootstrapper
        bootstrapper_market = MarketBootstrapper(db_manager=db_manager)
        stats = bootstrapper_market.bootstrap_markets()
        console.print(f"[green]✅ Markets: {stats['inserted']} inserted, {stats['updated']} updated[/green]")
    except ImportError:
        console.print("[yellow]⚠️  Market bootstrapper not found, skipping[/yellow]")
    except Exception as e:
        console.print(f"[red]Market bootstrap failed: {e}[/red]")
        # Continue anyway as markets might be created by ticker bootstrap

    # 4. Tickers
    console.print("\n[bold]Step 4: Tickers from Polygon[/bold]")
    try:
        from config.api_keys import POLYGON_API_KEY
        from bootstrapping.bootstrapper_ticker import TickerBootstrapper

        bootstrapper_ticker = TickerBootstrapper(api_key=POLYGON_API_KEY, db_manager=db_manager)
        if not bootstrapper_ticker.bootstrap_all_tickers(force=force):
            console.print("[red]Ticker bootstrap failed, stopping[/red]")
            sys.exit(1)
        stats = bootstrapper_ticker.get_bootstrap_stats()
        console.print(f"[green]✅ Tickers: {stats['inserted']:,} inserted, {stats['updated']:,} updated[/green]")
    except Exception as e:
        console.print(f"[red]Ticker bootstrap failed: {e}[/red]")
        sys.exit(1)

    # 5. Universes (all from config)
    console.print("\n[bold]Step 5: Asset Universes[/bold]")
    try:
        from bootstrapping.bootstrapper_universe import UniverseBootstrapper
        from config.universe_config import UNIVERSE_CONFIG

        bootstrapper_universe = UniverseBootstrapper(db_manager=config.db_manager)
        universe_names = list(UNIVERSE_CONFIG.keys())

        total_members = 0
        for universe_name in universe_names:
            if bootstrapper_universe.bootstrap_universe(universe_name, force=force):
                stats = bootstrapper_universe.get_universe_stats(universe_name)
                members = stats.get('total_members', 0)
                if members == 0:
                    console.print(f"[yellow]⚠️  {universe_name}: {members:,} members - Universe is empty! This may indicate missing fundamentals data.[/yellow]")
                else:
                    console.print(f"[green]✅ {universe_name}: {members:,} members[/green]")
                if universe_name == 'default_universe':  # Track default for summary
                    total_members = members
            else:
                console.print(f"[red]❌ {universe_name}: Failed[/red]")

        if total_members == 0:
            console.print("[red]Universe bootstrap failed, stopping[/red]")
            sys.exit(1)

    except Exception as e:
        console.print(f"[red]Universe bootstrap failed: {e}[/red]")
        sys.exit(1)

    console.print("\n[bold green]✅ Complete bootstrap successful![/bold green]")
    console.print("Database is ready for use.")