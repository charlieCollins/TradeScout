"""
Pytest configuration and shared fixtures for TradeScout tests
"""

import pytest
import sys
import os
from pathlib import Path

# Add src to Python path for testing
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Ensure test environment variables
os.environ.setdefault("POLYGON_API_KEY", "test_key_for_testing")
os.environ.setdefault("TRADESCOUT_ENV", "test")