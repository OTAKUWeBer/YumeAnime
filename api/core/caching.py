# core/caching.py
import time
from functools import wraps
from typing import Dict, Any

_cache: Dict[str, Any] = {}
CACHE_DURATION = 300  # Default 5 minutes

def cache_result(duration: int = CACHE_DURATION):
    """Decorator to cache function results."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
            
            if cache_key in _cache:
                cached_data, timestamp = _cache[cache_key]
                if time.time() - timestamp < duration:
                    return cached_data
            
            result = func(*args, **kwargs)
            _cache[cache_key] = (result, time.time())
            return result
        return wrapper
    return decorator

def clear_user_cache(user_id: int):
    """Clear all cache entries related to a specific user_id."""
    global _cache
    user_id_str = str(user_id)
    keys_to_remove = [key for key in _cache if user_id_str in key]
    for key in keys_to_remove:
        del _cache[key]
