"""
Simple Configuration for DataProvider

Since we only need to load DataProviderPolygon, we can simplify the configuration
to just handle API key loading and basic provider creation.
"""

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SimpleDataProviderConfig:
    """
    Simple configuration that just loads the Polygon provider
    
    This replaces the complex DataSourcesManager with something minimal
    that just handles API key loading for the single Polygon provider.
    """
    
    def __init__(self):
        """Initialize simple config"""
        self.api_key = self._load_polygon_api_key()
        
    def _load_polygon_api_key(self) -> Optional[str]:
        """Load Polygon API key from environment or .env file"""
        # Try environment variable first
        api_key = os.getenv("POLYGON_API_KEY")
        if api_key and not api_key.startswith("your_"):
            return api_key
            
        # Try to load from .env file in project root
        project_root = Path(__file__).parent.parent.parent.parent
        env_file = project_root / ".env"
        
        if env_file.exists():
            try:
                with open(env_file, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("POLYGON_API_KEY=") and not line.startswith("POLYGON_API_KEY=your_"):
                            api_key = line.split("=", 1)[1]
                            logger.debug("Loaded Polygon API key from .env file")
                            return api_key
            except Exception as e:
                logger.debug(f"Error reading .env file: {e}")
                
        return None
        
    def has_polygon_key(self) -> bool:
        """Check if we have a valid Polygon API key"""
        return self.api_key is not None and len(self.api_key) > 0
        
    def get_polygon_key(self) -> Optional[str]:
        """Get the Polygon API key"""
        return self.api_key


# Global instance
_simple_config = None


def get_simple_config() -> SimpleDataProviderConfig:
    """Get the global simple config instance"""
    global _simple_config
    if _simple_config is None:
        _simple_config = SimpleDataProviderConfig()
    return _simple_config


if __name__ == "__main__":
    # Test the simple config
    print("🧪 Testing Simple Data Provider Config...")
    
    config = get_simple_config()
    
    if config.has_polygon_key():
        print("✅ Polygon API key loaded successfully")
        print(f"   Key starts with: {config.get_polygon_key()[:8]}...")
    else:
        print("❌ No Polygon API key found")
        print("   Check POLYGON_API_KEY environment variable or .env file")
        
    print("\n✅ Simple config test completed!")