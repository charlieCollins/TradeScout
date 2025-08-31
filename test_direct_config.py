#!/usr/bin/env python3
"""
Test configuration manager directly without importing through __init__.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import directly to avoid __init__.py dependencies
from tradescout.config.data_sources_manager import DataSourcesManager, DataSourceType

try:
    print("✓ Configuration manager import successful")
    
    # Test data sources config loading
    manager = DataSourcesManager()
    extended_hours_providers = manager.get_providers_for_data_type(DataSourceType.EXTENDED_HOURS)
    print(f"✓ Found {len(extended_hours_providers)} providers for extended hours")
    
    # Check that web scrapers are included
    web_scrapers = []
    api_providers = []
    
    for provider_id, config in extended_hours_providers:
        provider_config = manager.config.providers[provider_id]
        if provider_config.type == "web_scraper":
            web_scrapers.append((provider_id, config))
        elif provider_config.type == "api":
            api_providers.append((provider_id, config))
    
    print(f"✓ Web scrapers: {len(web_scrapers)} ({[p[0] for p in web_scrapers]})")
    print(f"✓ API providers: {len(api_providers)} ({[p[0] for p in api_providers]})")
    
    # Test that reliability is properly configured
    print("\n📊 Web Scraper Configurations:")
    for provider_id, config in web_scrapers:
        provider_config = manager.config.providers[provider_id]
        print(f"  - {provider_id}: {provider_config.reliability} (priority: {provider_config.priority})")
    
    print("\n📊 API Provider Configurations:")
    for provider_id, config in api_providers:
        provider_config = manager.config.providers[provider_id]
        supports_extended = "✓" if provider_config.supports_extended_hours else "✗"
        print(f"  - {provider_id}: extended_hours={supports_extended} (priority: {provider_config.priority})")
    
    print("\n🎉 Configuration test successful!")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)