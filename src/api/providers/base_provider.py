"""Base API provider for external API integrations."""

import logging
import requests
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from utils.config_loader import ConfigLoader

logger = logging.getLogger(__name__)


class BaseAPIProvider(ABC):
    """Abstract base class for all API providers.

    API providers handle:
    - External API authentication
    - HTTP request/response handling
    - Rate limiting and retry logic
    - Response parsing into model objects

    API providers do NOT:
    - Store data to database (that's database manager responsibility)
    - Handle TTL logic (that's database manager responsibility)
    - Manage caching (that's database manager responsibility)
    """

    def __init__(self, api_key: str, base_url: str):
        """Initialize API provider with authentication.

        Args:
            api_key: API authentication key
            base_url: Base URL for API endpoints
        """
        if not api_key:
            raise ValueError(f"{self.__class__.__name__} requires an API key")

        self.api_key = api_key
        self.base_url = base_url

    # ============================================================================
    # PROTECTED METHODS - HTTP Request Handling
    # ============================================================================

    def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET"
    ) -> Dict[str, Any]:
        """Make authenticated request to API.

        Args:
            endpoint: API endpoint path (e.g., "/v2/snapshot/...")
            params: Query parameters
            method: HTTP method (default: GET)

        Returns:
            Parsed JSON response

        Raises:
            Exception: If API request fails
        """
        if params is None:
            params = {}

        # Add API key to request
        params = self.add_authentication(params)

        url = f"{self.base_url}{endpoint}"
        logger.debug(f"Making {method} request to {endpoint}")

        max_retries = 3

        for attempt in range(1, max_retries + 1):
            try:
                response = requests.request(method, url, params=params)

                # Handle rate limiting with exponential backoff
                if response.status_code == 429:
                    if attempt < max_retries:
                        self._handle_rate_limit(response, attempt)
                        continue  # Retry
                    else:
                        logger.error(f"Rate limit exceeded after {max_retries} retries")
                        raise Exception(f"Rate limit exceeded after {max_retries} retries")

                # Handle errors
                if response.status_code != 200:
                    self._handle_error_response(response)

                return response.json()

            except requests.RequestException as e:
                if attempt < max_retries:
                    logger.warning(f"Request failed (attempt {attempt}): {e}, retrying...")
                    time.sleep(2 ** attempt)  # Exponential backoff for network errors
                    continue
                logger.error(f"Request failed for {endpoint} after {max_retries} attempts: {e}")
                raise Exception(f"API request failed: {e}")

        # Should not reach here, but just in case
        raise Exception(f"API request failed after {max_retries} retries")

    @abstractmethod
    def add_authentication(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add authentication to request parameters.

        Each provider implements their own authentication method
        (API key in params, headers, etc.)

        Args:
            params: Request parameters

        Returns:
            Parameters with authentication added
        """
        pass

    def _handle_rate_limit(self, response: requests.Response, attempt: int = 1) -> None:
        """Handle rate limit response with exponential backoff.

        Uses exponential backoff: base_wait * 2^(attempt-1), capped at max_wait.

        Args:
            response: HTTP response with 429 status
            attempt: Current retry attempt number (1-based)
        """
        config = ConfigLoader().load_yaml("api.yaml")
        base_wait = config["api"]["polygon"]["rate_limiting"]["default_wait_seconds"]
        max_wait = config["api"]["polygon"]["rate_limiting"].get("max_wait_seconds", 60)

        # Exponential backoff: base_wait * 2^(attempt-1)
        wait_seconds = min(base_wait * (2 ** (attempt - 1)), max_wait)
        logger.warning(f"Rate limited (attempt {attempt}), waiting {wait_seconds} seconds...")
        time.sleep(wait_seconds)

    def _handle_error_response(self, response: requests.Response) -> None:
        """Handle error response.

        Args:
            response: HTTP error response

        Raises:
            Exception: With error details
        """
        error_message = f"API error: {response.status_code}"

        try:
            error_data = response.json()
            if "error" in error_data:
                error_message += f" - {error_data['error']}"
            elif "message" in error_data:
                error_message += f" - {error_data['message']}"
        except (ValueError, KeyError) as e:
            logger.debug(f"Could not parse error response as JSON: {e}")
            error_message += f" - {response.text}"

        logger.error(error_message)
        raise Exception(error_message)

    # ============================================================================
    # PUBLIC INTERFACE - Health Check
    # ============================================================================

    def health_check(self) -> bool:
        """Check if API is accessible and authenticated.

        Returns:
            True if API is healthy, False otherwise
        """
        try:
            self._make_request(self.get_health_endpoint())
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    @abstractmethod
    def get_health_endpoint(self) -> str:
        """Get endpoint for health check.

        Returns:
            Endpoint path for health checking
        """
        pass