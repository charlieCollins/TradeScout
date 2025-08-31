#!/usr/bin/env python3
"""
Test just the configuration system without external dependencies
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from tradescout.config.data_sources_manager import DataSourcesManager, DataSourceType
    print("✓ Configuration manager import successful")
    
    # Test data sources config loading
    manager = DataSourcesManager()
    extended_hours_providers = manager.get_providers_for_data_type(DataSourceType.EXTENDED_HOURS)
    print(f"✓ Found {len(extended_hours_providers)} providers for extended hours")
    
    # Check that web scrapers are included
    web_scrapers = [p for p in extended_hours_providers if manager.config.providers[p[0]].type == "web_scraper"]
    api_providers = [p for p in extended_hours_providers if manager.config.providers[p[0]].type == "api"]
    
    print(f"✓ Web scrapers: {len(web_scrapers)} ({[p[0] for p in web_scrapers]})")
    print(f"✓ API providers: {len(api_providers)} ({[p[0] for p in api_providers]})")
    
    # Test that reliability is properly configured
    for provider_id, config in web_scrapers:
        reliability = manager.config.providers[provider_id].reliability
        print(f"  - {provider_id}: {reliability}")
    
    print("🎉 Configuration test successful!")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)