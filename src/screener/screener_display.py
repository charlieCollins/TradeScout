"""Display formatter for screener results."""

import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.table import Table
from rich.text import Text

from screener.template_resolver import TemplateResolver


class ScreenerDisplay:
    """Format and display screener results."""

    def __init__(self):
        """Initialize display formatter."""
        self.console = Console()

    def display_results(
        self,
        results: List[Dict[str, Any]],
        screener_def: Dict,
        session: str,
        snapshot_time: Optional[str] = None,
        sessions_text: Optional[str] = None,
        warnings: Optional[List[str]] = None
    ):
        """Display screener results in a formatted table.

        Args:
            results: List of stock results
            screener_def: Screener configuration with display settings
            session: Current market session for context-aware columns
            snapshot_time: Optional snapshot time string to display
            sessions_text: Optional sessions info to display
            warnings: Optional list of warning messages to display
        """
        # Show last snapshot time first
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

        # Get display columns using template resolver for context-aware screeners
        resolver = TemplateResolver(screener_def, session)
        columns_config = resolver.resolve_display_columns()

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