#!/usr/bin/env python3
"""
Quick test of import structure for SmartCoordinator changes
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    # Test basic imports without external dependencies
    from tradescout.config.data_sources_manager import DataSourcesManager, DataSourceType
    from tradescout.data_models.domain_models_core import Asset, MarketStatus, ExtendedHoursData
    print("✓ Core imports successful")
    
    # Test data sources config loading
    manager = DataSourcesManager()
    extended_hours_providers = manager.get_providers_for_data_type(DataSourceType.EXTENDED_HOURS)
    print(f"✓ Found {len(extended_hours_providers)} providers for extended hours")
    
    # Check that web scrapers are included
    web_scrapers = [p for p in extended_hours_providers if manager.config.providers[p[0]].type == "web_scraper"]
    api_providers = [p for p in extended_hours_providers if manager.config.providers[p[0]].type == "api"]
    
    print(f"✓ Web scrapers: {len(web_scrapers)} ({[p[0] for p in web_scrapers]})")
    print(f"✓ API providers: {len(api_providers)} ({[p[0] for p in api_providers]})")
    
    print("🎉 Import structure test successful!")

except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Configuration error: {e}")
    sys.exit(1)