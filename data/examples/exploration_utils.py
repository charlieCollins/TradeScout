#!/usr/bin/env python3
"""
Simple API Exploration Utilities

Save and load API results as text files to avoid repeated API calls
during command-line exploration and development.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

def save_api_result(filename: str, data: Dict[str, Any], description: str = ""):
    """
    Save API result as a JSON file in data/examples/
    
    Args:
        filename: Name for the file (without .json extension)
        data: API response data to save
        description: Optional description of what this data represents
    """
    filepath = Path(__file__).parent / f"{filename}.json"
    
    # Add metadata
    save_data = {
        "saved_at": datetime.now().isoformat(),
        "description": description,
        "data": data
    }
    
    with open(filepath, 'w') as f:
        json.dump(save_data, f, indent=2, default=str)
    
    print(f"📁 Saved API result to {filepath.name}")

def load_api_result(filename: str) -> Optional[Dict[str, Any]]:
    """
    Load previously saved API result
    
    Args:
        filename: Name of the file (without .json extension)
        
    Returns:
        The saved data, or None if file doesn't exist
    """
    filepath = Path(__file__).parent / f"{filename}.json"
    
    if not filepath.exists():
        return None
    
    with open(filepath, 'r') as f:
        saved_data = json.load(f)
    
    print(f"📂 Loaded API result from {filepath.name} (saved: {saved_data.get('saved_at', 'unknown')})")
    return saved_data.get('data')

def get_or_fetch_api_data(filename: str, fetch_function, description: str = "", force_refresh: bool = False):
    """
    Get data from saved file, or fetch from API and save if not exists
    
    Args:
        filename: Name for the saved file
        fetch_function: Function to call to fetch fresh data
        description: Description of the data
        force_refresh: If True, always fetch fresh data
        
    Returns:
        The API data (from cache or fresh)
    """
    if not force_refresh:
        cached_data = load_api_result(filename)
        if cached_data is not None:
            return cached_data
    
    # Fetch fresh data
    print(f"🌐 Fetching fresh data from API...")
    fresh_data = fetch_function()
    
    # Save for next time
    save_api_result(filename, fresh_data, description)
    
    return fresh_data

def list_saved_results():
    """List all saved API results"""
    examples_dir = Path(__file__).parent
    json_files = list(examples_dir.glob("*.json"))
    
    if not json_files:
        print("📭 No saved API results found")
        return
    
    print("📚 Saved API Results:")
    print("-" * 30)
    
    for filepath in sorted(json_files):
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            saved_at = data.get('saved_at', 'unknown')
            description = data.get('description', 'No description')
            size_kb = filepath.stat().st_size / 1024
            
            print(f"{filepath.name}")
            print(f"  📅 Saved: {saved_at}")
            print(f"  📝 Description: {description}")
            print(f"  📏 Size: {size_kb:.1f} KB")
            print()
            
        except Exception as e:
            print(f"{filepath.name} (error reading: {e})")


if __name__ == "__main__":
    print("🛠️ API Exploration Utilities")
    print("=" * 40)
    
    list_saved_results()
    
    print("\nExample usage:")
    print("  from exploration_utils import get_or_fetch_api_data")
    print("  data = get_or_fetch_api_data('nvda_quote', lambda: fetch_nvidia_quote())")
    print("  # First time: fetches from API and saves")
    print("  # Next time: loads from saved file")