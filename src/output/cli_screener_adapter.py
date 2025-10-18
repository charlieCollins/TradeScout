"""CLI output adapter for screener results using Rich formatting.

Formats screener results for terminal display with Rich tables and styling.
"""

import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.table import Table
from rich.text import Text

from screener.template_resolver import TemplateResolver


class CLIScreenerOutputAdapter:
    """Format and display screener results for CLI using Rich."""

    def __init__(self):
        """Initialize CLI screener output adapter."""
        self.console = Console()

    def display_screener_results(self, result):
        """Display screener results from a ScreenerResult model.

        This is the main entry point for output-agnostic screener commands.
        Commands create a ScreenerResult and pass it to this method.

        Args:
            result: ScreenerResult model containing all screener data
        """
        from models.dataclass.screener_result import ScreenerResult

        # Extract session from market context
        session = result.market_context.session_name

        # Call existing display method
        self.display_results(
            results=result.results,
            screener_def=result.screener_def,
            session=session,
            snapshot_time=result.snapshot_time,
            sessions_text=result.sessions_text,
            warnings=result.warnings,
            market_context=result.market_context,
            data_date_summary=result.data_date_summary,
            screener_name=result.screener_name,
            excluded_count=result.excluded_count
        )

    def display_results(
        self,
        results: List[Dict[str, Any]],
        screener_def: Dict,
        session: str,
        date: Optional[str] = None,
        snapshot_time: Optional[str] = None,
        sessions_text: Optional[str] = None,
        warnings: Optional[List[str]] = None,
        market_context: Optional[Any] = None,
        data_date_summary: Optional[Dict[str, Any]] = None,
        screener_name: Optional[str] = None,
        excluded_count: Optional[int] = None
    ):
        """Display screener results in a formatted table.

        Args:
            results: List of stock results
            screener_def: Screener configuration with display settings
            session: Current market session for context-aware columns
            date: Date string (deprecated, use market_context)
            snapshot_time: Optional snapshot time string to display
            sessions_text: Optional sessions info to display
            warnings: Optional list of warning messages to display
            market_context: MarketContext with expected data date
            data_date_summary: Summary of actual data dates
            screener_name: Name of screener being run
            excluded_count: Number of assets excluded due to no data
        """
        # Show screener running message
        if screener_name:
            self.console.print(f"[yellow]📊 Running '{screener_name}' screener...[/yellow]")

        # Show exclusion message if assets were filtered out by date
        if excluded_count and excluded_count > 0 and market_context:
            self.console.print(
                f"[yellow]🗑️  {excluded_count} assets excluded (no price data for {market_context.expected_data_date})[/yellow]"
            )

        # Show last snapshot time
        if snapshot_time:
            self.console.print(f"[dim]{snapshot_time}[/dim]")
        if sessions_text:
            self.console.print(f"[dim]{sessions_text}[/dim]")

        # Display warnings
        if warnings:
            for warning in warnings:
                self.console.print(f"[yellow]{warning}[/yellow]")

        if not results:
            self.console.print("[yellow]No stocks match the screener criteria.[/yellow]")
            return

        # Get display columns and resolved config using template resolver
        resolver = TemplateResolver(screener_def, session)
        columns_config = resolver.resolve_display_columns()
        resolved_config = resolver.get_resolved_config()

        # Display resolved configuration header
        self._display_config_header(resolved_config, date, market_context, data_date_summary)

        # Create table
        title = f"{screener_def.get('name', 'Screener')} - {screener_def.get('description', '')}"
        table = Table(title=title, show_header=True, header_style="bold cyan")

        # Add columns based on configuration
        for col_config in columns_config:
            if isinstance(col_config, dict):
                col_name = col_config.get("name", col_config.get("field", ""))
                col_width = col_config.get("width")
                table.add_column(col_name, width=col_width)
            else:
                # Simple column name
                table.add_column(str(col_config))

        # Add rows
        for i, result in enumerate(results):
            row = []
            for col_config in columns_config:
                if isinstance(col_config, dict):
                    field = col_config.get("field", "")
                    format_type = col_config.get("format", "")
                    value = self._get_field_value(result, field)
                    formatted = self._format_value(value, format_type)
                    row.append(formatted)
                else:
                    # Simple column name
                    value = result.get(col_config, "")
                    row.append(str(value))


            table.add_row(*row)

        # Display table
        self.console.print(table)

        # Show summary
        self.console.print(f"\n[dim]Showing {len(results)} results[/dim]")

    def _display_config_header(
        self,
        resolved_config: Dict[str, Any],
        date: Optional[str] = None,
        market_context: Optional[Any] = None,
        data_date_summary: Optional[Dict[str, Any]] = None
    ):
        """Display resolved configuration for current session.

        Args:
            resolved_config: Resolved configuration from TemplateResolver
            date: Date string (deprecated, use market_context)
            market_context: MarketContext with expected data date
            data_date_summary: Summary of actual data dates from database
        """
        session = resolved_config.get("session", "unknown")
        field_mapping = resolved_config.get("field_mapping", {})
        thresholds = resolved_config.get("thresholds", {})

        # Display session
        self.console.print(f"[bold cyan]Session:[/bold cyan] {session}")

        # Display data date validation if available
        if market_context and data_date_summary is not None:
            self._display_data_date_validation(market_context, data_date_summary)

        # Display field mappings if present
        if field_mapping:
            self.console.print("[bold cyan]Field Mappings:[/bold cyan]")
            for field_name, field_expr in field_mapping.items():
                self.console.print(f"  [dim]{field_name}:[/dim] {field_expr}")

        # Display thresholds if present
        if thresholds:
            self.console.print("[bold cyan]Thresholds:[/bold cyan]")
            for threshold_name, threshold_value in thresholds.items():
                self.console.print(f"  [dim]{threshold_name}:[/dim] {threshold_value}")

        self.console.print()  # Empty line after config

    def _display_data_date_validation(
        self,
        market_context: Any,
        data_date_summary: Dict[str, Any]
    ):
        """Display data date validation showing what data was actually used.

        Args:
            market_context: MarketContext with expected_data_date property
            data_date_summary: Summary from AssetPriceRepository.get_data_date_summary()
                Note: This shows ALL data in database, not just what screener used
        """
        expected_date = market_context.expected_data_date

        # Show what date the screener is querying for
        self.console.print(
            f"[bold cyan]Querying Data For:[/bold cyan] {expected_date}"
        )

    def _get_field_value(self, result: Dict, field: str) -> Any:
        """Get field value from result, handling computed fields.

        Args:
            result: Result dictionary
            field: Field name or expression

        Returns:
            Field value
        """
        # Handle simple field names
        if field in result:
            return result[field]

        # Handle expressions - basic evaluation
        # For complex expressions like "((min_close - day_close) / day_close * 100)"
        # Try to evaluate safely by substituting field values
        try:
            # Replace field names with their values in the expression
            # Only allow fields that exist in result
            expr = field
            for key, value in result.items():
                if key in expr and value is not None:
                    # Replace field name with its numeric value
                    expr = expr.replace(key, str(float(value)))

            # Replace SQL functions with Python equivalents
            expr = expr.replace("ABS(", "abs(")
            expr = expr.replace("MIN(", "min(")
            expr = expr.replace("MAX(", "max(")

            # If expression still contains letters (unknown fields), skip evaluation
            # Allow lowercase function names (abs, min, max) to pass through
            temp_expr = expr.replace("abs", "").replace("min", "").replace("max", "")
            if not any(c.isalpha() for c in temp_expr.replace("e", "").replace("E", "")):
                # Evaluate the expression (now only contains numbers and operators)
                # Note: eval is normally dangerous, but we've sanitized to only numbers/operators
                return eval(expr)
        except:
            pass

        # Fallback: Handle simple subtraction like "min_close - prevday_close"
        if " - " in field:
            parts = field.split(" - ")
            if len(parts) == 2:
                field1 = parts[0].strip()
                field2 = parts[1].strip()
                val1 = result.get(field1, 0)
                val2 = result.get(field2, 0)
                if val1 is not None and val2 is not None:
                    return val1 - val2

        # Handle simple multiplication (legacy)
        if "*" in field:
            # Simple multiplication like "min_volume * min_close"
            parts = field.split("*")
            if len(parts) == 2:
                field1 = parts[0].strip()
                field2 = parts[1].strip()
                val1 = result.get(field1, 0)
                val2 = result.get(field2, 0)
                if val1 and val2:
                    return val1 * val2

        # Handle CASE expressions (return placeholder for now)
        if field.startswith("CASE"):
            # TODO: change_percent doesn't exist - need context-aware calculation
            # change = result.get("change_percent", 0)
            # return "↑" if change > 0 else "↓" if change < 0 else "="
            return "FIX_ME"

        return ""

    def _format_value(self, value: Any, format_type: str) -> str:
        """Format value based on format type.

        Args:
            value: Value to format
            format_type: Format type (price, percent, volume, etc.)

        Returns:
            Formatted string
        """
        if value is None or value == "":
            return "N/A"

        try:
            if format_type == "price":
                return f"${float(value):.2f}"
            elif format_type == "price_change":
                val = float(value)
                sign = "+" if val > 0 else ""
                color = "green" if val > 0 else "red" if val < 0 else "white"
                return f"[{color}]{sign}${val:.2f}[/{color}]"
            elif format_type == "percent":
                val = float(value)
                sign = "+" if val > 0 else ""
                color = "green" if val > 0 else "red" if val < 0 else "white"
                return f"[{color}]{sign}{val:.2f}%[/{color}]"
            elif format_type == "volume":
                val = int(value)
                if val >= 1_000_000:
                    return f"{val/1_000_000:.1f}M"
                elif val >= 1_000:
                    return f"{val/1_000:.0f}K"
                else:
                    return str(val)
            elif format_type == "currency":
                val = float(value)
                if val >= 1_000_000:
                    return f"${val/1_000_000:.1f}M"
                elif val >= 1_000:
                    return f"${val/1_000:.0f}K"
                else:
                    return f"${val:.2f}"
            else:
                return str(value)
        except (ValueError, TypeError):
            return str(value)

    def display_screener_list(self, result):
        """Display list of available screeners.

        Args:
            result: ScreenerListResult containing list of screeners
        """
        from models.dataclass.screener_result import ScreenerListResult

        table = Table(title="Available Screeners", show_header=True)
        table.add_column("Screener", style="cyan", no_wrap=True)
        table.add_column("Description", style="white")

        for screener in result.screeners:
            table.add_row(screener.name, screener.description)

        self.console.print(table)
        self.console.print("\n[dim]Screeners are loaded from configs/screeners/*.yaml[/dim]")
