import time
from functools import wraps
from typing import Dict, Any, Callable

_cache: Dict[str, Any] = {}

CACHE_DURATION = 900  # 15 minutes - default
LOGIN_CACHE_DURATION = 3600  # 1 hour - user login sessions and auth data
USER_DATA_CACHE_DURATION = 1800  # 30 minutes - user profile data
WATCHLIST_STATS_CACHE_DURATION = 600  # 10 minutes - watchlist statistics


def cache_result(duration: int = CACHE_DURATION) -> Callable:
    """
    Decorator to cache function results with configurable duration.
    
    Args:
        duration: Cache duration in seconds (default: 15 minutes)
    
    Returns:
        Decorated function with caching capability
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{func.__module__}.{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
            
            # Check if cached result exists and is still valid
            if cache_key in _cache:
                cached_data, timestamp = _cache[cache_key]
                if time.time() - timestamp < duration:
                    return cached_data
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            _cache[cache_key] = (result, time.time())
            return result
        return wrapper
    return decorator


def cache_user_data(duration: int = USER_DATA_CACHE_DURATION) -> Callable:
    """Cache user profile data with longer TTL."""
    return cache_result(duration)


def cache_login_data(duration: int = LOGIN_CACHE_DURATION) -> Callable:
    """Cache login session data with even longer TTL."""
    return cache_result(duration)


def cache_watchlist_stats(duration: int = WATCHLIST_STATS_CACHE_DURATION) -> Callable:
    """Cache watchlist statistics with moderate TTL."""
    return cache_result(duration)


def clear_user_cache(user_id: int) -> None:
    """
    Clear all cache entries related to a specific user_id.
    
    Args:
        user_id: The user ID whose cache entries should be cleared
    """
    global _cache
    user_id_str = str(user_id)
    keys_to_remove = [key for key in _cache if user_id_str in key]
    for key in keys_to_remove:
        del _cache[key]


def clear_old_cache(max_age: int = 1800) -> int:
    """
    Clear cache entries older than the specified age.
    
    Args:
        max_age: Maximum age in seconds (default: 30 minutes)
    
    Returns:
        Number of cache entries cleared
    """
    global _cache
    current_time = time.time()
    keys_to_remove = []
    
    for key, (data, timestamp) in _cache.items():
        if current_time - timestamp > max_age:
            keys_to_remove.append(key)
    
    for key in keys_to_remove:
        del _cache[key]
    
    return len(keys_to_remove)


def get_cache_stats() -> Dict[str, Any]:
    """
    Get statistics about the current cache state.
    
    Returns:
        Dictionary containing cache statistics
    """
    current_time = time.time()
    total_entries = len(_cache)
    
    if total_entries == 0:
        return {
            "total_entries": 0,
            "oldest_entry_age": 0,
            "newest_entry_age": 0,
            "average_age": 0
        }
    
    ages = [current_time - timestamp for _, timestamp in _cache.values()]
    
    return {
        "total_entries": total_entries,
        "oldest_entry_age": max(ages),
        "newest_entry_age": min(ages),
        "average_age": sum(ages) / len(ages)
    }
