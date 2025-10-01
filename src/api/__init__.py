"""API layer for external data providers.

This package contains API providers that handle external API integrations.
API providers are responsible for authentication, HTTP requests, and response parsing.

They do NOT handle database operations or caching - that's the database layer's job.
"""