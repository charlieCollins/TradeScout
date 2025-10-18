"""Template resolver for context-aware screeners.

Resolves template variables like {{current_price}} and {{thresholds.min_gap}}
based on the current market session context.
"""

import re
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class TemplateResolver:
    """Resolve template variables in screener configurations based on market context."""

    TEMPLATE_PATTERN = re.compile(r'\{\{([^}]+)\}\}')

    def __init__(self, screener_def: Dict, session: str):
        """Initialize template resolver.

        Args:
            screener_def: Screener configuration dictionary from YAML
            session: Current market session (e.g., 'premarket', 'regular', 'afterhours', 'closed')
        """
        self.screener_def = screener_def
        self.session = session
        self.field_mapping = screener_def.get('field_mapping', {})
        self.thresholds = screener_def.get('thresholds', {})

    def is_context_aware(self) -> bool:
        """Check if this screener is context-aware.

        Returns:
            True if screener has field_mapping section
        """
        return 'field_mapping' in self.screener_def

    def resolve_value(self, value: Any) -> Any:
        """Resolve templates in a value (string, number, dict, list, etc.).

        Args:
            value: Value that may contain templates

        Returns:
            Resolved value with templates replaced
        """
        if isinstance(value, str):
            return self._resolve_string(value)
        elif isinstance(value, dict):
            return {k: self.resolve_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self.resolve_value(v) for v in value]
        else:
            # Numbers, booleans, None - return as-is
            return value

    def _resolve_string(self, text: str) -> Any:
        """Resolve template variables in a string.

        Args:
            text: String that may contain {{template}} variables

        Returns:
            Resolved string, or original type if entire string was a template resolving to non-string
        """
        # Find all template matches
        matches = list(self.TEMPLATE_PATTERN.finditer(text))

        if not matches:
            return text

        # If the entire string is a single template, return the resolved value directly
        # This preserves type (e.g., {{thresholds.min_value}} stays a number)
        if len(matches) == 1 and matches[0].group(0) == text:
            variable_path = matches[0].group(1).strip()
            return self._resolve_variable(variable_path)

        # Multiple templates or template embedded in text - string substitution
        result = text
        for match in matches:
            variable_path = match.group(1).strip()
            resolved = self._resolve_variable(variable_path)
            # Convert to string for substitution
            result = result.replace(match.group(0), str(resolved))

        return result

    def _resolve_variable(self, variable_path: str) -> Any:
        """Resolve a single variable path like 'current_price' or 'thresholds.min_gap'.

        Args:
            variable_path: Variable path to resolve

        Returns:
            Resolved value

        Raises:
            ValueError: If variable path cannot be resolved
        """
        parts = variable_path.split('.')

        # Top-level field mapping variables (e.g., {{current_price}})
        if len(parts) == 1:
            field_name = parts[0]
            if field_name in self.field_mapping:
                return self._resolve_field_mapping(field_name)
            else:
                raise ValueError(f"Unknown template variable: {variable_path}")

        # Nested variables (e.g., {{thresholds.min_gap}})
        elif len(parts) == 2:
            section, field_name = parts
            if section == 'thresholds':
                return self._resolve_threshold(field_name)
            else:
                raise ValueError(f"Unknown template section: {section}")

        else:
            raise ValueError(f"Invalid template variable path: {variable_path}")

    def _resolve_field_mapping(self, field_name: str) -> str:
        """Resolve a field mapping for the current session.

        Args:
            field_name: Field name like 'current_price', 'reference_price', 'volume_field'

        Returns:
            SQL field expression for current session

        Raises:
            ValueError: If field mapping doesn't exist for current session
        """
        if field_name not in self.field_mapping:
            raise ValueError(f"Field mapping not found: {field_name}")

        session_mapping = self.field_mapping[field_name]

        if self.session not in session_mapping:
            raise ValueError(
                f"Field mapping '{field_name}' not defined for session '{self.session}'. "
                f"Available sessions: {list(session_mapping.keys())}"
            )

        return session_mapping[self.session]

    def _resolve_threshold(self, threshold_name: str) -> Any:
        """Resolve a threshold value for the current session.

        Args:
            threshold_name: Threshold name like 'min_gap_percent', 'min_volume'

        Returns:
            Threshold value for current session

        Raises:
            ValueError: If threshold doesn't exist for current session
        """
        if threshold_name not in self.thresholds:
            raise ValueError(f"Threshold not found: {threshold_name}")

        session_threshold = self.thresholds[threshold_name]

        if isinstance(session_threshold, dict):
            # Session-specific thresholds
            if self.session not in session_threshold:
                raise ValueError(
                    f"Threshold '{threshold_name}' not defined for session '{self.session}'. "
                    f"Available sessions: {list(session_threshold.keys())}"
                )
            return session_threshold[self.session]
        else:
            # Global threshold (same for all sessions)
            return session_threshold

    def resolve_filters(self) -> list:
        """Resolve all filter definitions.

        Returns:
            List of resolved filter dictionaries
        """
        filters = self.screener_def.get('filters', [])
        return self.resolve_value(filters)

    def resolve_sort(self) -> list:
        """Resolve sort configuration.

        Returns:
            List of resolved sort dictionaries
        """
        sort = self.screener_def.get('sort', [])
        return self.resolve_value(sort)

    def resolve_display_columns(self) -> list:
        """Resolve display columns for current session.

        Merges base columns with context-specific columns for current session.

        Returns:
            List of column configurations for display
        """
        display = self.screener_def.get('display', {})
        columns = display.get('columns')

        if not columns:
            # No column config, return empty list
            return []

        # Check if using context-specific column structure
        if isinstance(columns, dict) and 'base' in columns:
            # Merge base + context_specific columns
            base_columns = columns.get('base', [])
            context_specific = columns.get('context_specific', {})
            session_columns = context_specific.get(self.session, [])

            # Combine base + session-specific
            return base_columns + session_columns
        else:
            # Simple column list (backward compatible)
            return columns

    def get_resolved_config(self) -> Dict[str, Any]:
        """Get the resolved configuration for the current session.

        Returns a dictionary showing what field mappings and thresholds
        are being used for this specific session.

        Returns:
            Dictionary with resolved field_mapping and thresholds
        """
        config = {
            "session": self.session,
            "field_mapping": {},
            "thresholds": {}
        }

        # Resolve field mappings for current session
        for field_name, session_values in self.field_mapping.items():
            if isinstance(session_values, dict):
                # Session-specific mapping
                config["field_mapping"][field_name] = session_values.get(self.session, "N/A")
            else:
                # Static value (same for all sessions)
                config["field_mapping"][field_name] = session_values

        # Resolve thresholds for current session
        for threshold_name, session_values in self.thresholds.items():
            if isinstance(session_values, dict):
                # Session-specific threshold
                config["thresholds"][threshold_name] = session_values.get(self.session, "N/A")
            else:
                # Static value (same for all sessions)
                config["thresholds"][threshold_name] = session_values

        return config
