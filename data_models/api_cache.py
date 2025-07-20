"""
TradeScout API Cache System

Intelligent caching for free-tier APIs with rate limits.
Always checks cache before making external API calls.
"""

import json
import os
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class CachePolicy(Enum):
    """Cache policies for different data types"""
    REAL_TIME = "real_time"      # 1-5 minutes
    INTRADAY = "intraday"        # 15-30 minutes  
    DAILY = "daily"              # 4-24 hours
    FUNDAMENTAL = "fundamental"   # 7-30 days
    HISTORICAL = "historical"    # 30+ days (rarely changes)


@dataclass
class CacheConfig:
    """Configuration for cache behavior"""
    base_dir: str = "data/cache"
    max_size_mb: int = 500           # 500MB cache limit
    default_ttl_minutes: int = 30    # Default 30 minutes
    compress_data: bool = True       # Compress JSON data
    enabled: bool = True             # Can disable for testing
    
    # TTL by data type
    ttl_policies: Dict[CachePolicy, int] = None
    
    def __post_init__(self):
        if self.ttl_policies is None:
            self.ttl_policies = {
                CachePolicy.REAL_TIME: 2,       # 2 minutes
                CachePolicy.INTRADAY: 15,       # 15 minutes
                CachePolicy.DAILY: 240,         # 4 hours
                CachePolicy.FUNDAMENTAL: 10080, # 1 week
                CachePolicy.HISTORICAL: 43200   # 30 days
            }


class APICache:
    """
    Intelligent API cache that respects rate limits and data freshness.
    
    Features:
    - Automatic cache key generation
    - TTL-based expiration by data type
    - Size management (LRU eviction)
    - Cache statistics and monitoring
    - Easy cache clearing and management
    """
    
    def __init__(self, config: CacheConfig = None):
        self.config = config or CacheConfig()
        self.cache_dir = Path(self.config.base_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache subdirectories by provider
        self.providers = {
            'polygon': self.cache_dir / 'polygon',
            'yfinance': self.cache_dir / 'yfinance', 
            'newsapi': self.cache_dir / 'newsapi',
            'reddit': self.cache_dir / 'reddit',
            'general': self.cache_dir / 'general'
        }
        
        for provider_dir in self.providers.values():
            provider_dir.mkdir(exist_ok=True)
        
        self.stats = {
            'hits': 0,
            'misses': 0,
            'saves': 0,
            'evictions': 0
        }
    
    def get_cache_key(self, provider: str, endpoint: str, params: Dict[str, Any]) -> str:
        """Generate consistent cache key from API call parameters"""
        # Create deterministic key from provider + endpoint + sorted params
        param_str = json.dumps(params, sort_keys=True, default=str)
        combined = f"{provider}:{endpoint}:{param_str}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def get_cache_path(self, provider: str, cache_key: str) -> Path:
        """Get file path for cache entry"""
        provider_dir = self.providers.get(provider, self.providers['general'])
        return provider_dir / f"{cache_key}.json"
    
    def is_fresh(self, cache_path: Path, policy: CachePolicy) -> bool:
        """Check if cached data is still fresh based on policy"""
        if not cache_path.exists():
            return False
        
        file_time = datetime.fromtimestamp(cache_path.stat().st_mtime)
        ttl_minutes = self.config.ttl_policies[policy]
        expiry_time = file_time + timedelta(minutes=ttl_minutes)
        
        return datetime.now() < expiry_time
    
    def get(self, provider: str, endpoint: str, params: Dict[str, Any], 
            policy: CachePolicy = CachePolicy.INTRADAY) -> Optional[Dict[str, Any]]:
        """
        Get data from cache if available and fresh
        
        Args:
            provider: API provider name (polygon, yfinance, etc.)
            endpoint: API endpoint name
            params: API call parameters
            policy: Cache policy determining TTL
            
        Returns:
            Cached data if available and fresh, None otherwise
        """
        if not self.config.enabled:
            return None
        
        cache_key = self.get_cache_key(provider, endpoint, params)
        cache_path = self.get_cache_path(provider, cache_key)
        
        if self.is_fresh(cache_path, policy):
            try:
                with open(cache_path, 'r') as f:
                    cache_entry = json.load(f)
                
                self.stats['hits'] += 1
                logger.debug(f"Cache HIT: {provider}:{endpoint} (age: {self._get_age_minutes(cache_path):.1f}m)")
                
                return cache_entry['data']
                
            except (json.JSONDecodeError, KeyError, IOError) as e:
                logger.warning(f"Cache read error for {cache_key}: {e}")
                # Remove corrupted cache file
                cache_path.unlink(missing_ok=True)
        
        self.stats['misses'] += 1
        logger.debug(f"Cache MISS: {provider}:{endpoint}")
        return None
    
    def set(self, provider: str, endpoint: str, params: Dict[str, Any], 
            data: Any, policy: CachePolicy = CachePolicy.INTRADAY) -> bool:
        """
        Save data to cache
        
        Args:
            provider: API provider name
            endpoint: API endpoint name  
            params: API call parameters
            data: Data to cache
            policy: Cache policy for TTL
            
        Returns:
            True if successfully cached
        """
        if not self.config.enabled:
            return False
        
        try:
            cache_key = self.get_cache_key(provider, endpoint, params)
            cache_path = self.get_cache_path(provider, cache_key)
            
            cache_entry = {
                'provider': provider,
                'endpoint': endpoint,
                'params': params,
                'data': data,
                'policy': policy.value,
                'cached_at': datetime.now().isoformat(),
                'ttl_minutes': self.config.ttl_policies[policy]
            }
            
            with open(cache_path, 'w') as f:
                json.dump(cache_entry, f, indent=2, default=str)
            
            self.stats['saves'] += 1
            logger.debug(f"Cache SAVE: {provider}:{endpoint} (TTL: {self.config.ttl_policies[policy]}m)")
            
            # Check cache size and evict if needed
            self._maybe_evict_old_entries()
            
            return True
            
        except (IOError, TypeError) as e:
            logger.error(f"Cache save error: {e}")
            return False
    
    def cached_api_call(self, provider: str, endpoint: str, params: Dict[str, Any],
                       api_function: Callable, policy: CachePolicy = CachePolicy.INTRADAY) -> Any:
        """
        Wrapper for API calls with automatic caching
        
        Args:
            provider: API provider name
            endpoint: API endpoint name
            params: API call parameters
            api_function: Function to call if not in cache
            policy: Cache policy
            
        Returns:
            API response data (from cache or fresh API call)
        """
        # Try cache first
        cached_data = self.get(provider, endpoint, params, policy)
        if cached_data is not None:
            return cached_data
        
        # Cache miss - make API call
        logger.info(f"API CALL: {provider}:{endpoint} (cache miss)")
        fresh_data = api_function()
        
        # Save to cache
        self.set(provider, endpoint, params, fresh_data, policy)
        
        return fresh_data
    
    def invalidate(self, provider: str = None, endpoint: str = None, 
                  symbol: str = None) -> int:
        """
        Invalidate cache entries
        
        Args:
            provider: Specific provider to invalidate (optional)
            endpoint: Specific endpoint to invalidate (optional)  
            symbol: Specific symbol to invalidate (optional)
            
        Returns:
            Number of cache entries removed
        """
        removed_count = 0
        
        if provider and provider in self.providers:
            search_dirs = [self.providers[provider]]
        else:
            search_dirs = list(self.providers.values())
        
        for provider_dir in search_dirs:
            for cache_file in provider_dir.glob("*.json"):
                should_remove = False
                
                try:
                    with open(cache_file, 'r') as f:
                        cache_entry = json.load(f)
                    
                    # Check if matches invalidation criteria
                    if endpoint and cache_entry.get('endpoint') == endpoint:
                        should_remove = True
                    elif symbol and symbol.upper() in str(cache_entry.get('params', {})).upper():
                        should_remove = True
                    elif not endpoint and not symbol:  # Remove all for provider
                        should_remove = True
                    
                    if should_remove:
                        cache_file.unlink()
                        removed_count += 1
                        
                except (json.JSONDecodeError, IOError):
                    # Remove corrupted files
                    cache_file.unlink()
                    removed_count += 1
        
        logger.info(f"Cache invalidated: {removed_count} entries removed")
        return removed_count
    
    def clear_all(self) -> int:
        """Clear entire cache"""
        return self.invalidate()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        cache_size_mb = self._calculate_cache_size() / (1024 * 1024)
        file_count = sum(len(list(d.glob("*.json"))) for d in self.providers.values())
        hit_rate = self.stats['hits'] / (self.stats['hits'] + self.stats['misses']) if (self.stats['hits'] + self.stats['misses']) > 0 else 0
        
        return {
            'hit_rate': f"{hit_rate:.2%}",
            'cache_size_mb': f"{cache_size_mb:.1f}",
            'file_count': file_count,
            'max_size_mb': self.config.max_size_mb,
            'utilization': f"{(cache_size_mb / self.config.max_size_mb):.1%}",
            **self.stats
        }
    
    def cleanup_expired(self) -> int:
        """Remove expired cache entries"""
        removed_count = 0
        
        for provider_dir in self.providers.values():
            for cache_file in provider_dir.glob("*.json"):
                try:
                    with open(cache_file, 'r') as f:
                        cache_entry = json.load(f)
                    
                    policy = CachePolicy(cache_entry.get('policy', 'intraday'))
                    if not self.is_fresh(cache_file, policy):
                        cache_file.unlink()
                        removed_count += 1
                        
                except (json.JSONDecodeError, IOError):
                    cache_file.unlink()
                    removed_count += 1
        
        logger.info(f"Cache cleanup: {removed_count} expired entries removed")
        return removed_count
    
    def _get_age_minutes(self, cache_path: Path) -> float:
        """Get age of cache file in minutes"""
        file_time = datetime.fromtimestamp(cache_path.stat().st_mtime)
        return (datetime.now() - file_time).total_seconds() / 60
    
    def _calculate_cache_size(self) -> int:
        """Calculate total cache size in bytes"""
        total_size = 0
        for provider_dir in self.providers.values():
            for cache_file in provider_dir.glob("*.json"):
                total_size += cache_file.stat().st_size
        return total_size
    
    def _maybe_evict_old_entries(self):
        """Evict old entries if cache size exceeds limit"""
        current_size_mb = self._calculate_cache_size() / (1024 * 1024)
        
        if current_size_mb > self.config.max_size_mb:
            # Get all cache files with timestamps
            all_files = []
            for provider_dir in self.providers.values():
                for cache_file in provider_dir.glob("*.json"):
                    all_files.append((cache_file, cache_file.stat().st_mtime))
            
            # Sort by age (oldest first)
            all_files.sort(key=lambda x: x[1])
            
            # Remove oldest files until under limit
            for cache_file, _ in all_files:
                cache_file.unlink()
                self.stats['evictions'] += 1
                
                current_size_mb = self._calculate_cache_size() / (1024 * 1024)
                if current_size_mb <= self.config.max_size_mb * 0.8:  # Leave 20% buffer
                    break
            
            logger.info(f"Cache eviction completed. Size: {current_size_mb:.1f}MB")


# Global cache instance
_api_cache = None

def get_api_cache() -> APICache:
    """Get global API cache instance"""
    global _api_cache
    if _api_cache is None:
        _api_cache = APICache()
    return _api_cache


def cached_api_call(provider: str, endpoint: str, params: Dict[str, Any],
                   api_function: Callable, policy: CachePolicy = CachePolicy.INTRADAY):
    """Convenience function for cached API calls"""
    return get_api_cache().cached_api_call(provider, endpoint, params, api_function, policy)


# CLI-style functions for cache management
def clear_cache(provider: str = None):
    """Clear cache for provider or all"""
    return get_api_cache().invalidate(provider)

def cache_stats():
    """Print cache statistics"""
    stats = get_api_cache().get_stats()
    print("📊 API Cache Statistics")
    print("-" * 30)
    for key, value in stats.items():
        print(f"{key.replace('_', ' ').title()}: {value}")

def cleanup_cache():
    """Remove expired cache entries"""
    return get_api_cache().cleanup_expired()


if __name__ == "__main__":
    # Demo usage
    cache = APICache()
    
    print("🗂️ API Cache Demo")
    print(f"Cache directory: {cache.cache_dir}")
    print(f"Providers: {list(cache.providers.keys())}")
    
    # Example usage
    def mock_api_call():
        return {"price": 172.41, "volume": 146456416}
    
    # First call (cache miss)
    data1 = cache.cached_api_call(
        "yfinance", "get_quote", {"symbol": "NVDA"}, 
        mock_api_call, CachePolicy.REAL_TIME
    )
    
    # Second call (cache hit)
    data2 = cache.cached_api_call(
        "yfinance", "get_quote", {"symbol": "NVDA"},
        mock_api_call, CachePolicy.REAL_TIME
    )
    
    print("\nCache Stats:")
    stats = cache.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")