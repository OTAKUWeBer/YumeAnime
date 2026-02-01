"""
Home page data fetching and caching
Handles spotlight, trending, popular, and latest anime
"""
import time
import asyncio
from typing import Dict, Any, List
from .base import HianimeBaseClient


class HianimeHomeService:
    """Service for fetching and caching home page data"""
    
    def __init__(self, client: HianimeBaseClient):
        self.client = client
        self._home_cache = None
        self._home_cache_ts = 0.0
        self._home_cache_ttl = 5.0

    async def _fetch_home_cached(self) -> Dict[str, Any]:
        """Fetch home data with caching"""
        now = time.time()
        if self._home_cache and (now - self._home_cache_ts) < self._home_cache_ttl:
            return self._home_cache

        lock = asyncio.Lock()
        async with lock:
            now = time.time()
            if self._home_cache and (now - self._home_cache_ts) < self._home_cache_ttl:
                return self._home_cache

            for _ in range(3):
                resp = await self.client._get("home")
                if resp and isinstance(resp, dict):
                    data = resp.get("data") or {}
                    if any(data.get(k) for k in [
                        "latestEpisodeAnimes",
                        "mostPopularAnimes",
                        "spotlightAnimes",
                        "trendingAnimes"
                    ]):
                        normalized = {
                            k: self._annotate_episodes_count(data.get(k, [])) 
                            for k in [
                                "latestEpisodeAnimes",
                                "mostPopularAnimes",
                                "spotlightAnimes",
                                "trendingAnimes"
                            ]
                        }
                        self._home_cache = normalized
                        self._home_cache_ts = time.time()
                        return self._home_cache
                await asyncio.sleep(0.5)

            # fallback: return old cache or empty normalized dict
            if self._home_cache:
                return self._home_cache
            return {
                k: [] for k in [
                    "latestEpisodeAnimes",
                    "mostPopularAnimes",
                    "spotlightAnimes",
                    "trendingAnimes"
                ]
            }

    async def home(self) -> Dict[str, Any]:
        """Get unified home response with all sections + metadata"""
        data = await self._fetch_home_cached()
        return {
            "success": True,
            "data": {key: value for key, value in data.items()},
            "counts": {key: len(value) for key, value in data.items()},
        }

    def _annotate_episodes_count(self, animes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add episode count annotations to anime list"""
        out = []
        for a in animes:
            copy = dict(a)
            eps = copy.get("episodes") or {}
            try:
                sub = int(eps.get("sub", 0) or 0)
            except Exception:
                sub = 0
            try:
                dub = int(eps.get("dub", 0) or 0)
            except Exception:
                dub = 0
            copy["episodesSub"] = sub
            copy["episodesDub"] = dub
            copy["episodesCount"] = sub + dub
            out.append(copy)
        return out

    def clear_home_cache(self) -> None:
        """Clear the home page cache"""
        self._home_cache = None
        self._home_cache_ts = 0.0
