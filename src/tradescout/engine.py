"""
TradeScout Application Engine

Main application driver that provides high-level API for all TradeScout functionality.
This module contains the business logic that CLI and other interfaces can use.
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any, Union, Callable

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from .data_models.domain_models_core import Asset, AssetType, MarketQuote
from .data_models.factories import MarketFactory
from .data_sources.smart_coordinator import SmartCoordinator
from .storage.sqlite_repository import SQLiteDatabaseManager
from .config.markets_manager import get_markets_manager, TradingSession


class TradeScoutEngine:
    """
    Main TradeScout application engine.

    Provides high-level API for all TradeScout functionality including:
    - Market data retrieval and analysis
    - System status and configuration
    - Trade suggestions and recommendations
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the TradeScout engine.

        Args:
            db_path: Optional path to SQLite database file
        """
        # Initialize database manager
        if db_path:
            from .config.local_config import DATABASE_CONFIG

            # Override default path
            DATABASE_CONFIG["path"] = db_path

        from .storage.sqlite_repository import create_sqlite_database_manager

        self.db_manager = create_sqlite_database_manager(
            db_path or "data/databases/tradescout.db"
        )
        self.db_manager.initialize_database()

        # Initialize smart coordinator
        self.coordinator = SmartCoordinator()

        # Initialize markets manager
        self.markets_manager = get_markets_manager()

        # Initialize market factory
        self.market_factory = MarketFactory()

    # Market Data Methods

    def display_quotes(self, symbols: List[str]) -> Table:
        """
        Get current market quotes display table.

        Args:
            symbols: List of stock symbols

        Returns:
            Rich Table object ready for display
        """
        # Create Rich Table
        table = Table(title="Market Quotes", box=box.ROUNDED)
        table.add_column("Symbol", style="cyan", no_wrap=True)
        table.add_column("Price", style="green", justify="right")
        table.add_column("Change", justify="right")
        table.add_column("Change %", justify="right")
        table.add_column("Volume", justify="right")
        table.add_column("Time", style="dim")

        nasdaq = self.market_factory.create_nasdaq_market()
        quote_symbols = set()

        for symbol in symbols:
            asset = Asset(
                symbol=symbol.upper(),
                name=f"{symbol.upper()} Corp",
                asset_type=AssetType.COMMON_STOCK,
                market=nasdaq,
                currency="USD",
            )

            quote = self.coordinator.get_current_quote(asset.symbol)
            if quote:
                quote_symbols.add(quote.asset.symbol)

                # Format data
                price = f"${quote.price_data.price:.2f}"
                change = f"${quote.price_change:.2f}" if quote.price_change else "N/A"
                change_pct = (
                    f"{quote.price_change_percent:.2f}%"
                    if quote.price_change_percent
                    else "N/A"
                )
                volume = (
                    f"{quote.price_data.volume:,}" if quote.price_data.volume else "0"
                )
                timestamp = quote.price_data.timestamp.strftime("%H:%M:%S")

                # Color change based on positive/negative
                if quote.price_change and quote.price_change > 0:
                    change = f"[green]+{change}[/green]"
                    change_pct = f"[green]+{change_pct}[/green]"
                elif quote.price_change and quote.price_change < 0:
                    change = f"[red]{change}[/red]"
                    change_pct = f"[red]{change_pct}[/red]"

                table.add_row(
                    quote.asset.symbol, price, change, change_pct, volume, timestamp
                )

        # Add error rows for symbols that failed
        for symbol in symbols:
            if symbol.upper() not in quote_symbols:
                table.add_row(
                    symbol.upper(), "[red]Error[/red]", "N/A", "N/A", "N/A", "N/A"
                )

        return table

    def display_fundamentals(self, symbol: str) -> List:
        """
        Get fundamental data display for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            List of display objects (strings, Tables, Panels) ready for printing
        """
        try:
            fundamentals = self.coordinator.get_company_fundamentals(symbol.upper())

            if not fundamentals:
                return [f"[red]❌ No fundamental data found for {symbol.upper()}[/red]"]

            # Format data for display using domain model
            info_text = []

            # Company info section
            if fundamentals.asset.name:
                info_text.append(f"[bold]Company:[/bold] {fundamentals.asset.name}")
            if fundamentals.industry:
                info_text.append(f"[bold]Industry:[/bold] {fundamentals.industry}")
            if fundamentals.description:
                # Truncate description if too long
                desc = fundamentals.description
                if len(desc) > 150:
                    desc = desc[:150] + "..."
                info_text.append(f"[bold]Description:[/bold] {desc}")

            # Add separator for financial metrics
            if info_text:
                info_text.append("")

            # Market metrics
            if fundamentals.market_cap:
                market_cap = f"${fundamentals.market_cap:,.0f}"
                info_text.append(f"[bold]Market Cap:[/bold] {market_cap}")
                info_text.append(
                    f"[bold]Size Category:[/bold] {fundamentals.market_cap_category.replace('_', ' ').title()}"
                )

            if fundamentals.employees:
                info_text.append(f"[bold]Employees:[/bold] {fundamentals.employees:,}")

            # Financial performance (TTM data)
            if any(
                [
                    fundamentals.total_revenue,
                    fundamentals.net_income,
                    fundamentals.operating_income,
                ]
            ):
                info_text.append("")
                info_text.append(
                    "[bold cyan]📈 Financial Performance (TTM)[/bold cyan]"
                )

                if fundamentals.total_revenue:
                    revenue = f"${fundamentals.total_revenue:,.0f}"
                    info_text.append(f"[bold]Total Revenue:[/bold] {revenue}")

                if fundamentals.net_income:
                    net_income = f"${fundamentals.net_income:,.0f}"
                    color = "green" if fundamentals.net_income > 0 else "red"
                    info_text.append(
                        f"[bold]Net Income:[/bold] [{color}]{net_income}[/{color}]"
                    )

                if fundamentals.operating_income:
                    op_income = f"${fundamentals.operating_income:,.0f}"
                    color = "green" if fundamentals.operating_income > 0 else "red"
                    info_text.append(
                        f"[bold]Operating Income:[/bold] [{color}]{op_income}[/{color}]"
                    )

                if fundamentals.net_margin:
                    margin = f"{fundamentals.net_margin:.2f}%"
                    color = "green" if fundamentals.net_margin > 0 else "red"
                    info_text.append(
                        f"[bold]Net Margin:[/bold] [{color}]{margin}[/{color}]"
                    )

            # Balance sheet metrics
            if any(
                [
                    fundamentals.total_assets,
                    fundamentals.shareholders_equity,
                    fundamentals.current_ratio,
                ]
            ):
                info_text.append("")
                info_text.append("[bold cyan]🏦 Balance Sheet[/bold cyan]")

                if fundamentals.total_assets:
                    assets = f"${fundamentals.total_assets:,.0f}"
                    info_text.append(f"[bold]Total Assets:[/bold] {assets}")

                if fundamentals.shareholders_equity:
                    equity = f"${fundamentals.shareholders_equity:,.0f}"
                    info_text.append(f"[bold]Shareholders' Equity:[/bold] {equity}")

                if fundamentals.current_ratio:
                    ratio = f"{fundamentals.current_ratio:.2f}"
                    color = "green" if fundamentals.current_ratio >= 1.0 else "yellow"
                    info_text.append(
                        f"[bold]Current Ratio:[/bold] [{color}]{ratio}[/{color}]"
                    )

            # Cash flow
            if fundamentals.operating_cash_flow:
                info_text.append("")
                info_text.append("[bold cyan]💰 Cash Flow (TTM)[/bold cyan]")
                ocf = f"${fundamentals.operating_cash_flow:,.0f}"
                color = "green" if fundamentals.operating_cash_flow > 0 else "red"
                info_text.append(
                    f"[bold]Operating Cash Flow:[/bold] [{color}]{ocf}[/{color}]"
                )

            # Valuation metrics
            if any(
                [
                    fundamentals.price_to_earnings,
                    fundamentals.price_to_book,
                    fundamentals.dividend_yield,
                ]
            ):
                info_text.append("")
                info_text.append("[bold cyan]💹 Valuation Metrics[/bold cyan]")

                if fundamentals.price_to_earnings:
                    info_text.append(
                        f"[bold]P/E Ratio:[/bold] {fundamentals.price_to_earnings:.2f}"
                    )

                if fundamentals.price_to_book:
                    info_text.append(
                        f"[bold]P/B Ratio:[/bold] {fundamentals.price_to_book:.2f}"
                    )

                if fundamentals.dividend_yield:
                    div_yield = f"{fundamentals.dividend_yield*100:.2f}%"
                    info_text.append(f"[bold]Dividend Yield:[/bold] {div_yield}")

            # Financial health indicator
            if info_text:  # Only show if we have some data
                info_text.append("")
                health_status = (
                    "🟢 Healthy"
                    if fundamentals.is_financially_healthy
                    else "🟡 Needs Review"
                )
                health_color = (
                    "green" if fundamentals.is_financially_healthy else "yellow"
                )
                info_text.append(
                    f"[bold]Financial Health:[/bold] [{health_color}]{health_status}[/{health_color}]"
                )

            # Data source and period information
            if fundamentals.reporting_period:
                info_text.append("")
                info_text.append(
                    f"[dim]📋 Data Period: {fundamentals.reporting_period}[/dim]"
                )
                info_text.append(
                    f"[dim]📡 Source: {fundamentals.data_source.title()}[/dim]"
                )

            if info_text:
                panel = Panel(
                    "\n".join(info_text),
                    title=f"[bold blue]📊 {symbol.upper()} Fundamentals[/bold blue]",
                    border_style="blue",
                )
                return [panel]
            else:
                return [
                    f"[yellow]⚠️  Limited fundamental data available for {symbol.upper()}[/yellow]"
                ]

        except Exception as e:
            return [f"[red]❌ Error: {str(e)}[/red]"]

    def get_fundamentals(self, symbol: str) -> Dict[str, Any]:
        """
        Get fundamental data for a symbol with formatted display.

        Args:
            symbol: Stock symbol

        Returns:
            Dictionary containing formatted fundamental data for display
        """
        try:
            fundamentals_data = self.coordinator.get_company_fundamentals(
                symbol.upper()
            )

            if "error" in fundamentals_data:
                return fundamentals_data

            if not fundamentals_data:
                return {"error": f"No fundamental data found for {symbol.upper()}"}

            # Format data for display
            info_text = []

            # Company info
            if fundamentals_data.get("company_name"):
                info_text.append(
                    f"[bold]Company:[/bold] {fundamentals_data['company_name']}"
                )
            if fundamentals_data.get("sector"):
                info_text.append(f"[bold]Sector:[/bold] {fundamentals_data['sector']}")
            if fundamentals_data.get("industry"):
                info_text.append(
                    f"[bold]Industry:[/bold] {fundamentals_data['industry']}"
                )

            # Financial metrics
            if fundamentals_data.get("market_cap"):
                market_cap = f"${fundamentals_data['market_cap']:,}"
                info_text.append(f"[bold]Market Cap:[/bold] {market_cap}")

            if fundamentals_data.get("pe_ratio"):
                info_text.append(
                    f"[bold]P/E Ratio:[/bold] {fundamentals_data['pe_ratio']:.2f}"
                )

            if fundamentals_data.get("price_to_book"):
                info_text.append(
                    f"[bold]P/B Ratio:[/bold] {fundamentals_data['price_to_book']:.2f}"
                )

            if fundamentals_data.get("dividend_yield"):
                div_yield = f"{fundamentals_data['dividend_yield']*100:.2f}%"
                info_text.append(f"[bold]Dividend Yield:[/bold] {div_yield}")

            if fundamentals_data.get("beta"):
                info_text.append(f"[bold]Beta:[/bold] {fundamentals_data['beta']:.2f}")

            # 52-week range
            if fundamentals_data.get("52_week_high") and fundamentals_data.get(
                "52_week_low"
            ):
                high = fundamentals_data["52_week_high"]
                low = fundamentals_data["52_week_low"]
                info_text.append(
                    f"[bold]52-Week Range:[/bold] ${low:.2f} - ${high:.2f}"
                )

            return {
                "raw_data": fundamentals_data,
                "formatted_text": info_text,
                "has_data": len(info_text) > 0,
                "symbol": symbol.upper(),
            }
        except Exception as e:
            return {"error": str(e), "symbol": symbol.upper()}

    def get_market_gainers(
        self, limit: int = 10, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Get top market gainers with formatted display data.

        Args:
            limit: Number of gainers to return
            force_refresh: Force refresh of cached data

        Returns:
            Dictionary containing gainers data, session info, and formatted table rows
        """
        try:
            current_session = self.markets_manager.get_current_trading_session("nasdaq")
            now = datetime.now()
            gainers = self.coordinator.get_market_gainers(limit, force_refresh)
            session_info = self._get_session_info(current_session, now, "gainers")

            # Format table rows
            formatted_rows = []
            for gainer in gainers:
                change_color = "green" if gainer.price_change >= 0 else "red"
                price_change_str = (
                    f"+{gainer.price_change:.2f}"
                    if gainer.price_change >= 0
                    else f"{gainer.price_change:.2f}"
                )

                formatted_rows.append(
                    {
                        "rank": str(gainer.rank),
                        "symbol": gainer.asset.symbol,
                        "price": f"${gainer.current_price:.2f}",
                        "change": f"[{change_color}]{price_change_str}[/{change_color}]",
                        "change_pct": f"+{gainer.price_change_percent:.2f}%",
                        "volume": f"{gainer.volume:,}" if gainer.volume > 0 else "N/A",
                    }
                )

            return {
                "raw_gainers": gainers,
                "formatted_rows": formatted_rows,
                "session": current_session,
                "timestamp": now,
                "session_info": session_info,
                "table_title": f"Top {len(gainers)} Market Gainers ({session_info.get('timing', 'REGULAR')} Session)",
                "header_text": session_info.get("header", "🟢 Market Gainers"),
                "explanation": session_info.get("explanation", "Market gainers data"),
                "cache_message": {
                    "refresh": "[yellow]🔄 Fresh data retrieved (cache bypassed)[/yellow]",
                    "cached": "[blue]💾 Data cached for 10 minutes. Use --force-refresh to get fresh data.[/blue]",
                },
                "force_refresh": force_refresh,
            }
        except Exception as e:
            return {"error": str(e)}

    def get_market_losers(
        self, limit: int = 10, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Get top market losers with formatted display data.

        Args:
            limit: Number of losers to return
            force_refresh: Force refresh of cached data

        Returns:
            Dictionary containing losers data, session info, and formatted table rows
        """
        try:
            current_session = self.markets_manager.get_current_trading_session("nasdaq")
            now = datetime.now()
            losers = self.coordinator.get_market_losers(limit, force_refresh)
            session_info = self._get_session_info(current_session, now, "losers")

            # Format table rows
            formatted_rows = []
            for loser in losers:
                change_color = "green" if loser.price_change >= 0 else "red"
                price_change_str = (
                    f"+{loser.price_change:.2f}"
                    if loser.price_change >= 0
                    else f"{loser.price_change:.2f}"
                )

                formatted_rows.append(
                    {
                        "rank": str(loser.rank),
                        "symbol": loser.asset.symbol,
                        "price": f"${loser.current_price:.2f}",
                        "change": f"[{change_color}]{price_change_str}[/{change_color}]",
                        "change_pct": f"{loser.price_change_percent:.2f}%",
                        "volume": f"{loser.volume:,}" if loser.volume > 0 else "N/A",
                    }
                )

            return {
                "raw_losers": losers,
                "formatted_rows": formatted_rows,
                "session": current_session,
                "timestamp": now,
                "session_info": session_info,
                "table_title": f"Top {len(losers)} Market Losers ({session_info.get('timing', 'REGULAR')} Session)",
                "header_text": session_info.get("header", "🔴 Market Losers"),
                "explanation": session_info.get("explanation", "Market losers data"),
                "cache_message": {
                    "refresh": "[yellow]🔄 Fresh data retrieved (cache bypassed)[/yellow]",
                    "cached": "[blue]💾 Data cached for 10 minutes. Use --force-refresh to get fresh data.[/blue]",
                },
                "force_refresh": force_refresh,
            }
        except Exception as e:
            return {"error": str(e)}

    def display_market_data_header(self) -> str:
        """Get market data status header for display"""
        if (
            hasattr(self.coordinator, "_provider_instances")
            and self.coordinator._provider_instances
        ):
            provider = list(self.coordinator._provider_instances.values())[0]
            if hasattr(provider, "get_market_data_status"):
                status = provider.get_market_data_status()
                if status["status"] == "cached":
                    return f"[cyan]📊 Market Data: {status['symbols']:,} symbols cached ({status['age_minutes']:.1f} min old)[/cyan]"
                elif status["status"] == "empty":
                    return "[cyan]📊 Market Data: Fetching fresh snapshot from Polygon API...[/cyan]"
                else:
                    return f"[cyan]📊 Market Data: {status['symbols']:,} symbols (stale, refreshing...)[/cyan]"
        return ""

    def display_gainers(self, limit: int = 10, force_refresh: bool = False) -> List:
        """
        Get top market gainers display objects.

        Args:
            limit: Number of gainers to return
            force_refresh: Force refresh of cached data

        Returns:
            List of display objects (strings, Tables, Panels) ready for printing
        """
        try:
            current_session = self.markets_manager.get_current_trading_session("nasdaq")
            now = datetime.now()
            gainers = self.coordinator.get_market_gainers(limit, force_refresh)
            session_info = self._get_session_info(current_session, now, "gainers")

            if not gainers:
                return ["[yellow]⚠️  No gainers data available[/yellow]"]

            # Create header info
            header_text = session_info.get("header", "🟢 Market Gainers")
            explanation = session_info.get("explanation", "Market gainers data")
            timing = session_info.get("timing", "REGULAR")

            # Create Rich Table
            table = Table(
                title=f"Top {len(gainers)} Market Gainers ({timing} Session)",
                box=box.ROUNDED,
            )
            table.add_column("Rank", justify="center", style="dim", width=4)
            table.add_column("Symbol", style="cyan", no_wrap=True)
            table.add_column("Price", style="green", justify="right")
            table.add_column("Change", justify="right")
            table.add_column("Change %", justify="right", style="bold green")
            table.add_column("Volume", justify="right", style="dim")

            # Format and add rows
            for gainer in gainers:
                change_color = "green" if gainer.price_change >= 0 else "red"
                price_change_str = (
                    f"+{gainer.price_change:.2f}"
                    if gainer.price_change >= 0
                    else f"{gainer.price_change:.2f}"
                )

                table.add_row(
                    str(gainer.rank),
                    gainer.asset.symbol,
                    f"${gainer.current_price:.2f}",
                    f"[{change_color}]{price_change_str}[/{change_color}]",
                    f"+{gainer.price_change_percent:.2f}%",
                    f"{gainer.volume:,}" if gainer.volume > 0 else "N/A",
                )

            # Add header info
            info_lines = [f"[green]{header_text}[/green]", f"[dim]{explanation}[/dim]"]

            # Create display objects list
            display_objects = []
            display_objects.extend(info_lines)
            display_objects.append(table)
            cache_msg = (
                "[yellow]🔄 Fresh data retrieved (cache bypassed)[/yellow]"
                if force_refresh
                else "[blue]💾 Data cached for 10 minutes. Use --force-refresh to get fresh data.[/blue]"
            )
            display_objects.append(cache_msg)

            return display_objects

        except Exception as e:
            return [f"[red]❌ {str(e)}[/red]"]

    def display_losers(self, limit: int = 10, force_refresh: bool = False) -> List:
        """
        Get top market losers display objects.

        Args:
            limit: Number of losers to return
            force_refresh: Force refresh of cached data

        Returns:
            List of display objects (strings, Tables, Panels) ready for printing
        """
        try:
            current_session = self.markets_manager.get_current_trading_session("nasdaq")
            now = datetime.now()
            losers = self.coordinator.get_market_losers(limit, force_refresh)
            session_info = self._get_session_info(current_session, now, "losers")

            if not losers:
                return ["[yellow]⚠️  No losers data available[/yellow]"]

            # Create header info
            header_text = session_info.get("header", "🔴 Market Losers")
            explanation = session_info.get("explanation", "Market losers data")
            timing = session_info.get("timing", "REGULAR")

            # Create Rich Table
            table = Table(
                title=f"Top {len(losers)} Market Losers ({timing} Session)",
                box=box.ROUNDED,
            )
            table.add_column("Rank", justify="center", style="dim", width=4)
            table.add_column("Symbol", style="cyan", no_wrap=True)
            table.add_column("Price", style="red", justify="right")
            table.add_column("Change", justify="right")
            table.add_column("Change %", justify="right", style="bold red")
            table.add_column("Volume", justify="right", style="dim")

            # Format and add rows
            for loser in losers:
                change_color = "green" if loser.price_change >= 0 else "red"
                price_change_str = (
                    f"+{loser.price_change:.2f}"
                    if loser.price_change >= 0
                    else f"{loser.price_change:.2f}"
                )

                table.add_row(
                    str(loser.rank),
                    loser.asset.symbol,
                    f"${loser.current_price:.2f}",
                    f"[{change_color}]{price_change_str}[/{change_color}]",
                    f"{loser.price_change_percent:.2f}%",
                    f"{loser.volume:,}" if loser.volume > 0 else "N/A",
                )

            # Add header info
            info_lines = [f"[red]{header_text}[/red]", f"[dim]{explanation}[/dim]"]

            # Create display objects list
            display_objects = []
            display_objects.extend(info_lines)
            display_objects.append(table)
            cache_msg = (
                "[yellow]🔄 Fresh data retrieved (cache bypassed)[/yellow]"
                if force_refresh
                else "[blue]💾 Data cached for 10 minutes. Use --force-refresh to get fresh data.[/blue]"
            )
            display_objects.append(cache_msg)

            return display_objects

        except Exception as e:
            return [f"[red]❌ {str(e)}[/red]"]

    def get_market_movers(
        self, limit: int = 10, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Get comprehensive market movers (gainers and losers) with formatted display data.

        Args:
            limit: Number of stocks per category
            force_refresh: Force refresh of cached data

        Returns:
            Dictionary with gainers, losers, session info, and formatted data
        """
        try:
            current_session = self.markets_manager.get_current_trading_session("nasdaq")
            now = datetime.now()
            session_info = self._get_session_info(current_session, now)

            gainers = self.coordinator.get_market_gainers(limit, force_refresh)
            losers = self.coordinator.get_market_losers(limit, force_refresh)

            # Format gainers table rows
            formatted_gainers = []
            for gainer in gainers:
                change_color = "green" if gainer.price_change >= 0 else "red"
                price_change_str = (
                    f"+{gainer.price_change:.2f}"
                    if gainer.price_change >= 0
                    else f"{gainer.price_change:.2f}"
                )

                formatted_gainers.append(
                    {
                        "rank": str(gainer.rank),
                        "symbol": gainer.asset.symbol,
                        "price": f"${gainer.current_price:.2f}",
                        "change": f"[{change_color}]{price_change_str}[/{change_color}]",
                        "change_pct": f"+{gainer.price_change_percent:.2f}%",
                        "volume": f"{gainer.volume:,}" if gainer.volume > 0 else "N/A",
                    }
                )

            # Format losers table rows
            formatted_losers = []
            for loser in losers:
                change_color = "green" if loser.price_change >= 0 else "red"
                price_change_str = (
                    f"+{loser.price_change:.2f}"
                    if loser.price_change >= 0
                    else f"{loser.price_change:.2f}"
                )

                formatted_losers.append(
                    {
                        "rank": str(loser.rank),
                        "symbol": loser.asset.symbol,
                        "price": f"${loser.current_price:.2f}",
                        "change": f"[{change_color}]{price_change_str}[/{change_color}]",
                        "change_pct": f"{loser.price_change_percent:.2f}%",
                        "volume": f"{loser.volume:,}" if loser.volume > 0 else "N/A",
                    }
                )

            return {
                "raw_gainers": gainers,
                "raw_losers": losers,
                "formatted_gainers": formatted_gainers,
                "formatted_losers": formatted_losers,
                "session": current_session,
                "timestamp": now,
                "session_info": session_info,
                "gainers_title": f"Top {len(gainers)} Market Gainers ({session_info.get('timing', 'REGULAR')} Session)",
                "losers_title": f"Top {len(losers)} Market Losers ({session_info.get('timing', 'REGULAR')} Session)",
                "cache_message": {
                    "refresh": "[yellow]🔄 Fresh data retrieved (cache bypassed)[/yellow]",
                    "cached": "[blue]💾 Data cached for 10 minutes. Use --force-refresh to get fresh data.[/blue]",
                },
                "force_refresh": force_refresh,
            }
        except Exception as e:
            return {"error": str(e)}

    def get_trade_suggestions(
        self, limit: int = 5, force_refresh: bool = False, min_gap: float = 2.0
    ) -> List:
        """
        Generate gap trading suggestions.

        Args:
            limit: Maximum number of suggestions
            force_refresh: Force refresh of data
            min_gap: Minimum gap percentage

        Returns:
            List of trade suggestions
        """
        try:
            return self.coordinator.get_daily_gap_suggestions(
                min_gap_percent=min_gap, movers_limit=limit
            )
        except Exception as e:
            return []

    def get_session_header(self, market_type: str = "suggestions") -> str:
        """Get just the session header for display before processing."""
        current_session = self.markets_manager.get_current_trading_session("nasdaq")
        now = datetime.now()
        session_info = self._get_session_info(current_session, now, market_type)
        return session_info["header"]
    
    def display_trade_suggestions(
        self,
        limit: Optional[int] = 5,
        force_refresh: bool = False,
        min_gap: float = 2.0,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> List:
        """
        Get complete trade suggestions display objects.

        Args:
            limit: Maximum number of suggestions
            force_refresh: Force refresh of data
            min_gap: Minimum gap percentage
            progress_callback: Optional callback for progress updates

        Returns:
            List of display objects (strings, Tables, Panels) ready for printing
        """
        try:
            # Get session information for consistent headers
            current_session = self.markets_manager.get_current_trading_session("nasdaq")
            now = datetime.now()
            session_info = self._get_session_info(current_session, now, "suggestions")

            # Get suggestions with analysis details for header
            # Pass limit as movers_limit to limit market movers analyzed
            suggestion_result = self.coordinator.get_daily_gap_suggestions(
                min_gap_percent=min_gap, movers_limit=limit, progress_callback=progress_callback
            )
            suggestions = (
                suggestion_result.get("suggestions", [])
                if isinstance(suggestion_result, dict)
                else suggestion_result or []
            )

            # Get analysis stats for display
            gap_candidates = (
                suggestion_result.get("gap_candidates", 0)
                if isinstance(suggestion_result, dict)
                else 0
            )
            approved_candidates = (
                suggestion_result.get("approved_candidates", 0)
                if isinstance(suggestion_result, dict)
                else 0
            )
            scanning_stats = (
                suggestion_result.get("scanning_stats", {})
                if isinstance(suggestion_result, dict)
                else {}
            )

            if not suggestions:
                display_lines = []
                # Don't duplicate session header since CLI shows it upfront
                # display_lines.append(session_info["header"])

                # Show detailed processing stats
                movers_analyzed = scanning_stats.get("movers_analyzed", 0)
                data_available = scanning_stats.get("data_available", 0)

                display_lines.append(
                    f"[blue]📊 Analysis: Processed {movers_analyzed} market movers, {data_available} with gap data, {gap_candidates} candidates found, {approved_candidates} passed binary rules[/blue]"
                )
                display_lines.append(
                    f"[yellow]⚠️  No gap trading suggestions found >= {min_gap}%[/yellow]"
                )
                return display_lines

            display_lines = []
            # Don't duplicate session header since CLI shows it upfront
            # display_lines.append(session_info["header"])

            # Show detailed processing stats for successful results too
            movers_analyzed = scanning_stats.get("movers_analyzed", 0)
            data_available = scanning_stats.get("data_available", 0)

            display_lines.append(
                f"[blue]📊 Analysis: Processed {movers_analyzed} market movers, {data_available} with gap data, {gap_candidates} candidates found, {approved_candidates} passed binary rules[/blue]"
            )
            display_lines.append(
                f"[green]✅ Generated {len(suggestions)} trade suggestions >= {min_gap}%[/green]"
            )

            # Create summary table
            from rich.table import Table
            from rich import box

            table = Table(title="Gap Trading Suggestions", box=box.ROUNDED)
            table.add_column("Rank", justify="center", width=4)
            table.add_column("Symbol", style="cyan")
            table.add_column("Gap %", justify="right")
            table.add_column("Direction", justify="center")
            table.add_column("Confidence", justify="center")

            for i, suggestion_data in enumerate(suggestions, 1):
                suggestion = suggestion_data.get("suggestion")
                if not suggestion:
                    continue

                gap_percent = float(suggestion.gap_percent or 0)
                gap_color = "green" if gap_percent > 0 else "red"
                direction = "📈 Long" if suggestion.side.value == "long" else "📉 Short"
                confidence = (
                    float(suggestion.confidence_score * 100)
                    if suggestion.confidence_score
                    else 0
                )

                table.add_row(
                    str(i),
                    suggestion.asset.symbol if suggestion.asset else "N/A",
                    f"[{gap_color}]{gap_percent:.1f}%[/{gap_color}]",
                    direction,
                    f"{confidence:.1f}%",
                )

            # Note: This is a simplified version. The original CLI had much more complex
            # business logic that should ideally be refactored into proper domain services.

            cache_msg = (
                "[yellow]🔄 Fresh data analysis completed[/yellow]"
                if force_refresh
                else "[blue]💾 Analysis cached. Market data refreshed at market close.[/blue]"
            )

            # Create display objects list
            display_objects = []
            display_objects.extend(display_lines)
            display_objects.append(table)
            display_objects.append(cache_msg)

            return display_objects

        except Exception as e:
            return [f"[red]❌ Error generating gap trading suggestions: {str(e)}[/red]"]

    def display_market_movers(
        self, limit: int = 10, force_refresh: bool = False
    ) -> List:
        """
        Get complete market movers display objects.

        Args:
            limit: Number of stocks per category
            force_refresh: Force refresh of cached data

        Returns:
            List of display objects (strings, Tables, Panels) ready for printing
        """
        try:
            movers_data = self.get_market_movers(limit, force_refresh)

            if "error" in movers_data:
                return [f"[red]❌ {movers_data['error']}[/red]"]

            # Get formatted data
            formatted_gainers = movers_data.get("formatted_gainers", [])
            formatted_losers = movers_data.get("formatted_losers", [])
            session_info = movers_data.get("session_info", {})

            # Create header
            header = session_info.get("header", "🟢 Market Movers")
            data_explanation = session_info.get("explanation", "Current market data")
            timestamp = movers_data.get("timestamp")

            header_lines = [f"[bold]{header}[/bold]", f"[dim]{data_explanation}[/dim]"]

            # Create gainers table
            gainers_table = None
            if formatted_gainers:
                gainers_table = Table(box=box.ROUNDED)
                gainers_table.add_column("Rank", justify="center", style="dim", width=4)
                gainers_table.add_column("Symbol", style="cyan")
                gainers_table.add_column("Price", justify="right", style="green")
                gainers_table.add_column("Change", justify="right")
                gainers_table.add_column(
                    "Change %", justify="right", style="bold green"
                )
                gainers_table.add_column("Volume", justify="right", style="dim")

                for row in formatted_gainers:
                    gainers_table.add_row(
                        row["rank"],
                        row["symbol"],
                        row["price"],
                        row["change"],
                        row["change_pct"],
                        row["volume"],
                    )

            # Create losers table
            losers_table = None
            if formatted_losers:
                losers_table = Table(box=box.ROUNDED)
                losers_table.add_column("Rank", justify="center", style="dim", width=4)
                losers_table.add_column("Symbol", style="cyan")
                losers_table.add_column("Price", justify="right", style="red")
                losers_table.add_column("Change", justify="right")
                losers_table.add_column("Change %", justify="right", style="bold red")
                losers_table.add_column("Volume", justify="right", style="dim")

                for row in formatted_losers:
                    losers_table.add_row(
                        row["rank"],
                        row["symbol"],
                        row["price"],
                        row["change"],
                        row["change_pct"],
                        row["volume"],
                    )

            # Cache status
            cache_messages = movers_data.get("cache_message", {})
            cache_msg = (
                cache_messages.get("refresh", "Fresh data retrieved")
                if force_refresh
                else cache_messages.get("cached", "Data cached")
            )

            # Create display objects list
            display_objects = []

            # Add header
            display_objects.extend(header_lines)

            # Add gainers if available
            if formatted_gainers and gainers_table:
                display_objects.append(
                    f"\n[green]{movers_data.get('gainers_title', 'Market Gainers')}[/green]"
                )
                display_objects.append(gainers_table)

            # Add losers if available
            if formatted_losers and losers_table:
                display_objects.append(
                    f"\n[red]{movers_data.get('losers_title', 'Market Losers')}[/red]"
                )
                display_objects.append(losers_table)

            # Add footer
            display_objects.append(f"\n{cache_msg}")

            return display_objects

        except Exception as e:
            return [f"[red]❌ Error: {str(e)}[/red]"]

    def display_ohlc_data(self, symbols: List[str], date: str = None) -> List:
        """
        Get OHLC (Open, High, Low, Close) data display for symbols.

        Args:
            symbols: List of stock symbols
            date: Date string (YYYY-MM-DD) or None for today

        Returns:
            List of display objects (strings, Tables, Panels) ready for printing
        """
        try:
            display_objects = []

            from rich.table import Table
            from rich import box
            from datetime import datetime

            # Use today if no date specified
            if not date:
                date = datetime.now().strftime("%Y-%m-%d")

            display_objects.append(f"[bold blue]📊 OHLC Data for {date}[/bold blue]\n")

            # Create table
            table = Table(title=f"Daily OHLC Data ({date})", box=box.ROUNDED)
            table.add_column("Symbol", style="cyan", no_wrap=True)
            table.add_column("Open", justify="right", style="blue")
            table.add_column("High", justify="right", style="green")
            table.add_column("Low", justify="right", style="red")
            table.add_column("Close", justify="right", style="yellow")
            table.add_column("Volume", justify="right", style="dim")
            table.add_column("Change %", justify="right")

            for symbol in symbols:
                try:
                    # Get OHLC data from coordinator
                    ohlc_data = self.coordinator.get_daily_ohlc(symbol.upper(), date)

                    if ohlc_data:
                        # Format the data
                        open_price = f"${ohlc_data['open']:.2f}"
                        high_price = f"${ohlc_data['high']:.2f}"
                        low_price = f"${ohlc_data['low']:.2f}"
                        close_price = f"${ohlc_data['close']:.2f}"
                        volume = (
                            f"{ohlc_data['volume']:,}"
                            if ohlc_data["volume"] > 0
                            else "N/A"
                        )

                        # Calculate change percentage
                        change_pct = "N/A"
                        if "prev_close" in ohlc_data and ohlc_data["prev_close"]:
                            pct_change = (
                                (ohlc_data["close"] - ohlc_data["prev_close"])
                                / ohlc_data["prev_close"]
                            ) * 100
                            color = "green" if pct_change >= 0 else "red"
                            sign = "+" if pct_change >= 0 else ""
                            change_pct = f"[{color}]{sign}{pct_change:.2f}%[/{color}]"

                        table.add_row(
                            symbol.upper(),
                            open_price,
                            high_price,
                            low_price,
                            close_price,
                            volume,
                            change_pct,
                        )
                    else:
                        table.add_row(
                            symbol.upper(),
                            "[red]Error[/red]",
                            "N/A",
                            "N/A",
                            "N/A",
                            "N/A",
                            "N/A",
                        )

                except Exception as e:
                    table.add_row(
                        symbol.upper(),
                        f"[red]Error[/red]",
                        "N/A",
                        "N/A",
                        "N/A",
                        "N/A",
                        "N/A",
                    )

            display_objects.append(table)
            display_objects.append("\n[dim]📡 Data source: Polygon.io[/dim]")

            return display_objects

        except Exception as e:
            return [f"[red]❌ Error getting OHLC data: {str(e)}[/red]"]

    def display_system_status(self) -> List[str]:
        """
        Get complete system status display.

        Returns:
            List of formatted strings ready for display
        """
        try:
            system_status = self.get_system_status()

            if "error" in system_status:
                return [f"[red]❌ {system_status['error']}[/red]"]

            display_lines = ["[blue]📊 TradeScout System Status[/blue]"]

            # Display database statistics
            database_stats = system_status.get("database", {})
            if database_stats:
                display_lines.append("\n[bold]Database Statistics[/bold]")
                display_lines.append(
                    f"  Total Rows: {database_stats.get('total_rows', 'N/A')}"
                )
                display_lines.append(
                    f"  Database Size: {database_stats.get('size', 'N/A')}"
                )

            # Display market session
            market_session = system_status.get("market_session", "unknown")
            display_lines.append(
                f"\n[bold]Market Session:[/bold] {market_session.title()}"
            )

            # Display coordinator status
            coordinator_info = system_status.get("coordinator", {})
            if coordinator_info:
                display_lines.append(f"\n[bold]Smart Coordinator[/bold]")
                display_lines.append(
                    f"  Active Providers: {coordinator_info.get('active_providers', 0)}"
                )
                providers = coordinator_info.get("provider_names", [])
                if providers:
                    display_lines.append(f"  Provider Names: {', '.join(providers)}")

            # Show timestamp
            timestamp = system_status.get("timestamp", "")
            if timestamp:
                display_lines.append(f"\n[dim]Status generated at: {timestamp}[/dim]")

            return display_lines

        except Exception as e:
            return [f"[red]❌ Error: {str(e)}[/red]"]

    # System Management Methods

    def get_system_status(self) -> Dict[str, Any]:
        """
        Get comprehensive system status.

        Returns:
            Dictionary containing system status information
        """
        try:
            # Database statistics
            db_stats = self.db_manager.get_database_stats()

            # Market status
            current_session = self.markets_manager.get_current_trading_session("nasdaq")

            # Coordinator status
            coordinator_status = {
                "active_providers": len(self.coordinator._provider_instances),
                "provider_names": [
                    p.__class__.__name__
                    for p in self.coordinator._provider_instances.values()
                ],
            }

            return {
                "database": db_stats,
                "market_session": (
                    current_session.value if current_session else "unknown"
                ),
                "coordinator": coordinator_status,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {"error": str(e)}

    def get_universe_info(
        self, universe: str = "default_liquid_universe", show_symbols: bool = False
    ) -> Dict[str, Any]:
        """
        Get information about the screening universe.

        Args:
            universe: Universe name to display
            show_symbols: Whether to include full symbol list

        Returns:
            Dictionary containing universe information
        """
        try:
            from .config.screening_universe_config import get_screening_universe_config

            universe_config = get_screening_universe_config()
            symbols = universe_config.get_universe(universe)

            available_universes = (
                list(universe_config.config.keys())
                if universe_config.config
                else [universe]
            )

            # Get metadata from config
            universe_metadata = universe_config.config.get(universe, {})

            result = {
                "universe_name": universe,
                "total_symbols": len(symbols),
                "unique_symbols": len(set(symbols)),
                "available_universes": available_universes,
                "has_duplicates": len(symbols) != len(set(symbols)),
                "source": universe_metadata.get("source", "Unknown"),
                "last_updated": universe_metadata.get("last_updated", "Unknown"),
                "description": universe_metadata.get("description", ""),
            }

            if show_symbols:
                result["symbols"] = sorted(symbols)

            # Symbol statistics
            if symbols:
                result["stats"] = {
                    "total_count": len(symbols),
                }

            return result

        except Exception as e:
            return {"error": str(e), "universe": universe}

    def display_universe_info(
        self, universe: str = "default_liquid_universe", show_symbols: bool = False
    ) -> List[str]:
        """
        Get complete universe information display.

        Args:
            universe: Universe name to display
            show_symbols: Whether to include full symbol list

        Returns:
            List of formatted strings ready for display
        """
        try:
            universe_info = self.get_universe_info(universe, show_symbols)

            if "error" in universe_info:
                return [f"[red]❌ {universe_info['error']}[/red]"]

            display_lines = ["[blue]🌐 Full Trading Universe[/blue]\n"]

            # Display universe information
            display_lines.append(
                f"[bold]Total Symbols:[/bold] {universe_info.get('total_symbols', 0)}"
            )
            display_lines.append(
                f"[bold]Last Updated:[/bold] {universe_info.get('last_updated', 'Unknown')}"
            )
            display_lines.append(
                f"[bold]Source:[/bold] {universe_info.get('source', 'Manual curation')}"
            )

            if universe_info.get("has_duplicates"):
                display_lines.append(
                    "[yellow]⚠️  Universe contains duplicate symbols[/yellow]"
                )

            if show_symbols and universe_info.get("symbols"):
                symbols = universe_info["symbols"]
                display_lines.append(f"\n[bold]Symbols in {universe}:[/bold]")
                display_lines.append(
                    f"[dim]{', '.join(symbols[:50])}{'...' if len(symbols) > 50 else ''}[/dim]"
                )

            return display_lines

        except Exception as e:
            return [f"[red]❌ Error accessing universe: {str(e)}[/red]"]

    def update_universe_from_polygon(
        self,
        universe: str = "default_liquid_universe",
        dry_run: bool = False,
        limit: Optional[int] = None,
    ) -> List[str]:
        """
        Update universe with new symbols from Polygon all-tickers API.

        Args:
            universe: Universe name to update
            dry_run: Show what would be added without making changes
            limit: Maximum number of tickers to fetch from Polygon (None = ALL)

        Returns:
            List of formatted strings ready for display
        """
        try:
            from datetime import datetime
            from pathlib import Path
            import yaml
            import shutil
            import requests
            import time

            # Get current universe symbols
            from .config.screening_universe_config import get_screening_universe_config

            config = get_screening_universe_config()
            current_symbols = set(config.get_universe(universe))

            display_lines = ["[blue]🔄 Updating Trading Universe[/blue]\n"]
            display_lines.append(
                f"[bold]Current symbols:[/bold] {len(current_symbols)}"
            )

            if limit is None:
                display_lines.append(
                    "[bold]Fetching ALL symbols from Polygon...[/bold]\n"
                )
                limit = float("inf")  # No limit
            else:
                display_lines.append(
                    f"[bold]Fetching up to {limit} symbols from Polygon...[/bold]\n"
                )

            # Get Polygon API key from coordinator
            polygon_provider = None
            try:
                if "polygon" not in self.coordinator._provider_instances:
                    raise ValueError("Polygon provider not initialized")
                polygon_provider = self.coordinator._provider_instances["polygon"]
                api_key = polygon_provider.api_key
            except Exception as e:
                return [f"[red]❌ Could not access Polygon API: {str(e)}[/red]"]

            # Fetch all tickers from Polygon with pagination
            display_lines.append(
                "[yellow]⏳ Fetching tickers from Polygon.io...[/yellow]"
            )

            all_polygon_tickers = []
            next_url = None
            page_count = 0
            max_per_request = 1000  # Polygon max is always 1000
            total_fetched = 0

            # Initial request
            url = "https://api.polygon.io/v3/reference/tickers"

            while total_fetched < limit:
                page_count += 1
                if limit == float("inf"):
                    request_limit = max_per_request  # 1000
                else:
                    remaining = limit - total_fetched
                    request_limit = min(
                        max_per_request, remaining
                    )  # Don't exceed 1000 or remaining

                if next_url:
                    # Use pagination URL and add API key
                    params = {"apikey": api_key}
                    response = requests.get(next_url, params=params)
                else:
                    # Initial request
                    params = {
                        "apikey": api_key,
                        "market": "stocks",
                        "active": "true",
                        "limit": request_limit,
                    }
                    response = requests.get(url, params=params)

                time.sleep(0.5)  # Rate limiting

                if response.status_code != 200:
                    return [
                        f"[red]❌ Polygon API error: {response.status_code} - {response.text}[/red]"
                    ]

                data = response.json()
                page_results = data.get("results", [])

                if not page_results:
                    break  # No more results

                # Add results, but don't exceed limit
                if limit != float("inf") and total_fetched + len(page_results) > limit:
                    # Take only what we need
                    needed = limit - total_fetched
                    all_polygon_tickers.extend(page_results[:needed])
                    total_fetched += needed
                    display_lines.append(
                        f"[dim]Page {page_count}: Retrieved {needed} tickers (total: {total_fetched}, limit reached)[/dim]"
                    )
                    break
                else:
                    all_polygon_tickers.extend(page_results)
                    total_fetched += len(page_results)
                    display_lines.append(
                        f"[dim]Page {page_count}: Retrieved {len(page_results)} tickers (total: {total_fetched})[/dim]"
                    )

                # Check for next page
                next_url = data.get("next_url")
                if not next_url or (limit != float("inf") and total_fetched >= limit):
                    break

            polygon_tickers = all_polygon_tickers

            if not polygon_tickers:
                return [f"[red]❌ No tickers returned from Polygon API[/red]"]

            display_lines.append(
                f"[green]✅ Retrieved {len(polygon_tickers)} total tickers from Polygon ({page_count} pages)[/green]"
            )

            # Filter for US stock symbols and exclude current universe
            new_symbols = []
            filtered_count = 0

            for ticker in polygon_tickers:
                symbol = ticker.get("ticker", "").upper()
                ticker_type = ticker.get("type", "")
                market = ticker.get("market", "")
                primary_exchange = ticker.get("primary_exchange", "")

                # Filter criteria:
                # - Must be common stock (CS)
                # - Must be on major US exchanges
                # - Symbol length 1-5 characters (standard tickers)
                # - Not already in universe
                if (
                    ticker_type == "CS"
                    and market == "stocks"
                    and primary_exchange in ["XNYS", "XNAS", "BATS"]
                    and 1 <= len(symbol) <= 5
                    and symbol.isalpha()
                    and symbol not in current_symbols
                ):
                    new_symbols.append(symbol)
                else:
                    filtered_count += 1

            display_lines.append(
                f"[dim]Filtered out {filtered_count} tickers (non-stocks, duplicates, or invalid symbols)[/dim]"
            )
            display_lines.append(
                f"[bold green]New symbols to add: {len(new_symbols)}[/bold green]\n"
            )

            if not new_symbols:
                display_lines.append(
                    "[yellow]⚠️  No new symbols to add to universe[/yellow]"
                )
                return display_lines

            # Show first 20 symbols that would be added
            if new_symbols:
                display_lines.append("[bold]Sample of new symbols:[/bold]")
                sample = new_symbols[:20]
                display_lines.append(
                    f"[cyan]{', '.join(sample)}{'...' if len(new_symbols) > 20 else ''}[/cyan]\n"
                )

            if dry_run:
                display_lines.append("[yellow]🔍 DRY RUN - No changes made[/yellow]")
                display_lines.append(
                    f"[bold]Would add {len(new_symbols)} new symbols to '{universe}'[/bold]"
                )
                return display_lines

            # Create backup and update universe file
            config_path = config.config_path
            backup_path = config_path.with_suffix(
                f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )

            display_lines.append(
                f"[yellow]💾 Creating backup: {backup_path.name}[/yellow]"
            )
            shutil.copy2(config_path, backup_path)

            # Load current config
            with open(config_path, "r") as f:
                yaml_config = yaml.safe_load(f)

            # Add new symbols to universe
            if universe not in yaml_config:
                display_lines.append(
                    f"[red]❌ Universe '{universe}' not found in config[/red]"
                )
                return display_lines

            current_universe_symbols = yaml_config[universe].get("symbols", [])
            combined_symbols = sorted(list(set(current_universe_symbols + new_symbols)))

            yaml_config[universe]["symbols"] = combined_symbols
            yaml_config[universe]["last_updated"] = datetime.now().strftime("%Y-%m-%d")

            # Add update note
            old_source = yaml_config[universe].get("source", "")
            yaml_config[universe][
                "source"
            ] = f"{old_source} + Polygon all-tickers API update"

            # Write updated config
            with open(config_path, "w") as f:
                yaml.dump(yaml_config, f, default_flow_style=False, sort_keys=False)

            display_lines.append(f"[green]✅ Successfully updated '{universe}'[/green]")
            display_lines.append(f"[bold]Added {len(new_symbols)} new symbols[/bold]")
            display_lines.append(
                f"[bold]Total symbols now: {len(combined_symbols)}[/bold]"
            )
            display_lines.append(f"[dim]Backup saved: {backup_path.name}[/dim]")

            return display_lines

        except Exception as e:
            return [f"[red]❌ Error updating universe: {str(e)}[/red]"]

    def display_initialization_status(self, verbose: bool = False) -> List[str]:
        """
        Get initialization status display messages.

        Args:
            verbose: Whether to show verbose provider information

        Returns:
            List of formatted status messages for display
        """
        display_messages = []

        # Basic initialization status with provider names
        provider_count = len(self.coordinator._provider_instances)
        provider_names = ", ".join(self.coordinator._provider_instances.keys())
        if provider_count > 0:
            display_messages.append(
                f"[green]✅ Initialized TradeScout Engine with {provider_count} data providers ({provider_names})[/green]"
            )
        else:
            display_messages.append(
                f"[yellow]⚠️ Initialized TradeScout Engine with {provider_count} data providers[/yellow]"
            )

        # Verbose provider status
        if verbose:
            try:
                from ..config.data_sources_manager import get_data_sources_manager

                data_manager = get_data_sources_manager()
                status = data_manager.get_provider_status()

                display_messages.append(
                    f"[dim]Available providers: {status['summary']['available']}/{status['summary']['total_configured']}[/dim]"
                )
                display_messages.append(
                    f"[dim]Data types configured: {len(self.coordinator.get_available_data_types())}[/dim]"
                )
            except Exception as e:
                display_messages.append(
                    f"[yellow]⚠️  Warning: Could not get detailed provider status: {e}[/yellow]"
                )

        return display_messages

    # Helper Methods

    def _get_session_info(
        self, session: TradingSession, timestamp: datetime, market_type: str = "gainers"
    ) -> Dict[str, str]:
        """Get human-readable session information with current time and session details."""

        # Format current time
        current_time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S EST")

        # Determine detailed session description
        hour = timestamp.hour
        if session == TradingSession.PREMARKET:
            session_desc = "Extended Hours (Pre-Market)"
        elif session == TradingSession.AFTERHOURS:
            session_desc = "Extended Hours (After-Hours)"
        elif session == TradingSession.REGULAR:
            session_desc = "Regular Trading Hours"
        else:
            # Market closed
            if 20 <= hour or hour < 4:  # 8 PM - 4 AM
                session_desc = "Market Closed [Extended Hours Inactive]"
            else:
                session_desc = "Market Closed"

        if market_type == "losers" or market_type == "suggestions":
            session_map = {
                TradingSession.PREMARKET: {
                    "header": f"🌅 DAILY GAPS (Pre-Market Extended Hours)\nCurrent Time: {current_time_str} ({session_desc})",
                    "explanation": "Pre-market prices vs yesterday's close",
                    "timing": "PRE-MARKET",
                },
                TradingSession.AFTERHOURS: {
                    "header": f"🌆 DAILY GAPS (After-Hours Extended Hours)\nCurrent Time: {current_time_str} ({session_desc})",
                    "explanation": "After-hours prices vs today's close",
                    "timing": "AFTER-HOURS",
                },
                TradingSession.REGULAR: {
                    "header": f"🔴 DAILY GAPS (Regular Session)\nCurrent Time: {current_time_str} ({session_desc})",
                    "explanation": "Current regular session vs previous session",
                    "timing": "DAILY",
                },
            }
        else:  # gainers or default
            session_map = {
                TradingSession.PREMARKET: {
                    "header": f"🌅 DAILY GAPS (Pre-Market Extended Hours)\nCurrent Time: {current_time_str} ({session_desc})",
                    "explanation": "Pre-market prices vs yesterday's close",
                    "timing": "PRE-MARKET",
                },
                TradingSession.AFTERHOURS: {
                    "header": f"🌆 DAILY GAPS (After-Hours Extended Hours)\nCurrent Time: {current_time_str} ({session_desc})",
                    "explanation": "After-hours prices vs today's close",
                    "timing": "AFTER-HOURS",
                },
                TradingSession.REGULAR: {
                    "header": f"🟢 DAILY GAPS (Regular Session)\nCurrent Time: {current_time_str} ({session_desc})",
                    "explanation": "Current regular session vs previous session",
                    "timing": "DAILY",
                },
            }

        default_closed = {
            "header": f"{'🔴' if market_type == 'losers' else '🟢'} DAILY GAPS (Market Closed)\nCurrent Time: {current_time_str} ({session_desc})",
            "explanation": "Most recent daily session vs previous session",
            "timing": "DAILY",
        }

        return session_map.get(session, default_closed)
