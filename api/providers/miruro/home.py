"""
Home page data fetching and caching for Miruro API
Handles trending, popular, and recent anime via separate endpoints
"""
import time
import asyncio
import logging
from typing import Dict, Any, List
from .base import MiruroBaseClient

logger = logging.getLogger(__name__)


class MiruroHomeService:
    """Service for fetching and caching home page data from Miruro API"""

    def __init__(self, client: MiruroBaseClient):
        self.client = client
        self._home_cache = None
        self._home_cache_ts = 0.0
        self._home_cache_ttl = 30.0  # 30 seconds cache

    def _normalize_anime(self, item: Dict[str, Any], rank: int = 0) -> Dict[str, Any]:
        """Normalize a Miruro API anime result to HiAnime-compatible shape"""
        title = item.get("title", {}) or {}
        cover = item.get("coverImage", {}) or {}
        studios_nodes = (item.get("studios", {}) or {}).get("nodes", [])
        studio_name = studios_nodes[0].get("name") if studios_nodes else ""

        english_title = title.get("english") or title.get("romaji") or "Unknown"
        
        return {
            "id": str(item.get("id", "")),
            "anilistId": item.get("id"),
            "name": english_title,
            "jname": title.get("native") or title.get("romaji") or "",
            "poster": cover.get("extraLarge") or cover.get("large") or "",
            "episodes": {
                "sub": item.get("episodes") or 0,
                "dub": 0,
            },
            "type": item.get("format") or "",
            "duration": f"{item.get('duration', '')} min" if item.get("duration") else "",
            "rating": item.get("averageScore") or None,
            "rank": rank,
            "description": "",
            "otherInfo": [
                item.get("format") or "",
                f"{item.get('duration', '')}m" if item.get("duration") else "",
                studio_name,
            ],
        }

    def _normalize_spotlight(self, item: Dict[str, Any], rank: int = 0) -> Dict[str, Any]:
        """Normalize a Miruro API result into spotlight shape"""
        base = self._normalize_anime(item, rank)
        base["description"] = ""  # Miruro list endpoints don't include descriptions
        return base

    async def _fetch_home_data(self) -> Dict[str, Any]:
        """Fetch trending, popular, and recent from Miruro API in parallel"""
        now = time.time()
        if self._home_cache and (now - self._home_cache_ts) < self._home_cache_ttl:
            return self._home_cache

        try:
            trending_task = self.client._get("trending", params={"per_page": 24})
            popular_task = self.client._get("popular", params={"per_page": 24})
            recent_task = self.client._get("recent", params={"per_page": 24})

            trending_resp, popular_resp, recent_resp = await asyncio.gather(
                trending_task, popular_task, recent_task,
                return_exceptions=True
            )

            def safe_results(resp):
                if isinstance(resp, Exception) or not resp:
                    return []
                return resp.get("results", [])

            trending_items = safe_results(trending_resp)
            popular_items = safe_results(popular_resp)
            recent_items = safe_results(recent_resp)

            # spotlightAnimes = top trending (up to 10)
            spotlight = [
                self._normalize_spotlight(item, i + 1) 
                for i, item in enumerate(trending_items[:10])
            ]

            # trendingAnimes = all trending
            trending = [
                self._normalize_anime(item, i + 1) 
                for i, item in enumerate(trending_items)
            ]

            # mostPopularAnimes = popular
            popular = [
                self._normalize_anime(item, i + 1)
                for i, item in enumerate(popular_items)
            ]

            # latestEpisodeAnimes = recent
            latest = [
                self._normalize_anime(item, i + 1)
                for i, item in enumerate(recent_items)
            ]

            # Add episode count annotations (same as HiAnime home service)
            normalized = {
                "spotlightAnimes": self._annotate_episodes_count(spotlight),
                "trendingAnimes": self._annotate_episodes_count(trending),
                "mostPopularAnimes": self._annotate_episodes_count(popular),
                "latestEpisodeAnimes": self._annotate_episodes_count(latest),
            }

            self._home_cache = normalized
            self._home_cache_ts = time.time()
            logger.info(
                f"[MiruroHome] Fetched: spotlight={len(spotlight)}, "
                f"trending={len(trending)}, popular={len(popular)}, latest={len(latest)}"
            )
            return normalized

        except Exception as e:
            logger.error(f"[MiruroHome] Error fetching home data: {e}")
            if self._home_cache:
                return self._home_cache
            return {
                "spotlightAnimes": [],
                "trendingAnimes": [],
                "mostPopularAnimes": [],
                "latestEpisodeAnimes": [],
            }

    async def home(self) -> Dict[str, Any]:
        """Get unified home response with all sections + metadata"""
        data = await self._fetch_home_data()
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
