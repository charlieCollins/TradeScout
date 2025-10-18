"""Web output adapter for fed results.

Formats Federal Reserve data operation results for web/JSON display.
Returns dictionaries suitable for FastAPI JSON serialization.
"""

from typing import Dict, Any

from models.result.fed_result import FedUpdateResult, FedInfoResult


class WebFedOutputAdapter:
    """Format and display Fed results for web/JSON API."""

    def display_fed_update_result(self, result: FedUpdateResult) -> Dict[str, Any]:
        """Display fed update result as JSON-ready dict.

        Args:
            result: FedUpdateResult containing update statistics

        Returns:
            Dictionary ready for FastAPI JSON serialization
        """
        return {
            "data_by_type": result.data_by_type,
            "total_stored": result.total_stored,
            "elapsed_seconds": result.elapsed_seconds,
        }

    def display_fed_info_result(self, result: FedInfoResult) -> Dict[str, Any]:
        """Display fed info result as JSON-ready dict.

        Args:
            result: FedInfoResult containing Fed data sections

        Returns:
            Dictionary ready for FastAPI JSON serialization
        """
        sections = []
        for section in result.sections:
            section_data = {
                "data_type_key": section.data_type_key,
                "display_name": section.display_name,
                "latest": None,
                "recent": []
            }

            if section.latest:
                section_data["latest"] = {
                    "date": str(section.latest.date),
                    "value": section.latest.value,
                    "data_type": section.latest.data_type,
                }

            section_data["recent"] = [
                {
                    "date": str(item.date),
                    "value": item.value,
                    "data_type": item.data_type,
                }
                for item in section.recent
            ]

            sections.append(section_data)

        return {
            "sections": sections,
        }
