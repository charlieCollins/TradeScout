#!/usr/bin/env python3
"""
Migrate asset universe from YAML to database

This script imports the existing screening_universe.yaml into the new
SQLite database structure for dynamic asset management.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.tradescout.storage.asset_universe_manager import AssetUniverseManager
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    """Main migration function"""
    
    # Initialize manager
    manager = AssetUniverseManager()
    
    # Path to YAML file
    yaml_path = project_root / "src/tradescout/config/screening_universe.yaml"
    
    if not yaml_path.exists():
        logger.error(f"YAML file not found: {yaml_path}")
        return 1
    
    logger.info(f"Importing universe from {yaml_path}")
    
    try:
        assets_imported, memberships_added = manager.import_from_yaml(str(yaml_path))
        
        logger.info(f"Successfully imported {assets_imported} assets")
        logger.info(f"Added {memberships_added} universe memberships")
        
        # Verify import
        liquid_symbols = manager.get_universe_symbols('default_liquid_universe')
        logger.info(f"Liquid universe now contains {len(liquid_symbols)} symbols")
        
        if liquid_symbols:
            logger.info(f"First 10 symbols: {liquid_symbols[:10]}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())