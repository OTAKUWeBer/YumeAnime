"""
Catalog browsing functionality for Miruro API
Handles genre, category, and schedule queries
"""
import logging
from typing import Dict, Any
from .base import MiruroBaseClient

logger = logging.getLogger(__name__)


class MiruroCatalogService:
    """Service for browsing anime catalogs via Miruro API"""

    def __init__(self, client: MiruroBaseClient):
        self.client = client

    def _normalize_anime(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a Miruro API result to standard catalog shape"""
        title = item.get("title", {}) or {}
        cover = item.get("coverImage", {}) or {}
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
        }

    async def genre(self, name: str, page: int = 1) -> Dict[str, Any]:
        """Get anime by genre via Miruro /filter endpoint"""
        params = {
            "genre": name.title(),
            "page": page,
            "per_page": 24,
            "sort": "SCORE_DESC",
        }
        resp = await self.client._get("filter", params=params)
        if not resp:
            return {}

        results = resp.get("results", [])
        filtered_results = [
            item for item in results 
            if not item.get("isAdult", False) and "Hentai" not in item.get("genres", [])
        ]
        animes = [self._normalize_anime(item) for item in filtered_results]
        total = resp.get("total", 0)

        return {
            "animes": animes,
            "genreName": name.title(),
            "totalPages": max(1, (total + 24 - 1) // 24),
            "hasNextPage": resp.get("hasNextPage", False),
            "currentPage": page,
        }

    async def category(self, name: str, page: int = 1) -> Dict[str, Any]:
        """Get anime by category via Miruro API"""
        # Map category names to Miruro endpoints/filters
        category_map = {
            "trending": ("trending", {}),
            "popular": ("popular", {}),
            "most-popular": ("popular", {}),
            "recently-updated": ("recent", {}),
            "recently-added": ("recent", {}),
            "movie": ("filter", {"format": "MOVIE", "sort": "SCORE_DESC"}),
            "tv": ("filter", {"format": "TV", "sort": "SCORE_DESC"}),
            "ova": ("filter", {"format": "OVA", "sort": "SCORE_DESC"}),
            "ona": ("filter", {"format": "ONA", "sort": "SCORE_DESC"}),
            "special": ("filter", {"format": "SPECIAL", "sort": "SCORE_DESC"}),
            "most-favorite": ("filter", {"sort": "FAVOURITES_DESC"}),
            "top-airing": ("filter", {"status": "RELEASING", "sort": "SCORE_DESC"}),
            "completed": ("filter", {"status": "FINISHED", "sort": "SCORE_DESC"}),
            "upcoming": ("upcoming", {}),
        }

        endpoint, extra_params = category_map.get(name.lower(), ("filter", {}))

        params = {"page": page, "per_page": 24, **extra_params}
        resp = await self.client._get(endpoint, params=params)
        if not resp:
            return {}

        results = resp.get("results", [])
        filtered_results = [
            item for item in results 
            if not item.get("isAdult", False) and "Hentai" not in item.get("genres", [])
        ]
        animes = [self._normalize_anime(item) for item in filtered_results]
        total = resp.get("total", 0)

        return {
            "animes": animes,
            "category": name.replace("-", " ").title(),
            "totalPages": max(1, (total + 24 - 1) // 24) if total else 1,
            "hasNextPage": resp.get("hasNextPage", False),
            "currentPage": page,
        }

    async def producer(self, name: str, page: int = 1) -> Dict[str, Any]:
        """
        Get anime by producer/studio — Miruro doesn't have a direct endpoint,
        so we use /filter with a search approach
        """
        params = {"page": page, "per_page": 24}
        resp = await self.client._get("filter", params=params)
        if not resp:
            return {}

        results = resp.get("results", [])
        filtered_results = [
            item for item in results 
            if not item.get("isAdult", False) and "Hentai" not in item.get("genres", [])
        ]
        animes = [self._normalize_anime(item) for item in filtered_results]

        return {
            "animes": animes,
            "producerName": name.replace("-", " ").title(),
            "totalPages": max(1, (resp.get("total", 0) + 24 - 1) // 24),
            "hasNextPage": resp.get("hasNextPage", False),
            "currentPage": page,
        }

    async def schedule(self, date: str = None) -> Dict[str, Any]:
        """Get anime airing schedule via Miruro /schedule endpoint"""
        params = {"per_page": 50}
        resp = await self.client._get("schedule", params=params)
        if not resp:
            return {}

        results = resp.get("results", [])
        
        # Normalize schedule items
        scheduled = []
        for item in results:
            if item.get("isAdult", False) or "Hentai" in item.get("genres", []):
                continue
            normalized = self._normalize_anime(item)
            # Add schedule-specific fields
            next_ep = item.get("nextAiringEpisode") or {}
            normalized["next_episode"] = item.get("next_episode") or next_ep.get("episode")
            normalized["airingAt"] = item.get("airingAt") or next_ep.get("airingAt")
            normalized["timeUntilAiring"] = item.get("timeUntilAiring") or next_ep.get("timeUntilAiring")
            scheduled.append(normalized)

        return {
            "scheduledAnimes": scheduled,
            "totalCount": len(scheduled),
        }

    async def qtip(self, anime_id: str) -> Dict[str, Any]:
        """Quick tooltip info — use /info for Miruro"""
        from .anime_info import MiruroAnimeInfoService
        info_service = MiruroAnimeInfoService(self.client)
        return await info_service.get_anime_info(anime_id)

    async def anime_about(self, anime_id: str) -> Dict[str, Any]:
        """Detailed about/info — maps to /info for Miruro"""
        from .anime_info import MiruroAnimeInfoService
        info_service = MiruroAnimeInfoService(self.client)
        info = await info_service.get_anime_info(anime_id)
        
        # Wrap in standard structure for watchlist enrichment
        if info:
            return {
                "anime": {
                    "info": {
                        "poster": info.get("poster"),
                        "stats": {
                            "episodes": {
                                "sub": info.get("total_sub_episodes", 0),
                                "dub": info.get("total_dub_episodes", 0),
                            },
                            "rating": info.get("rating"),
                        },
                    },
                    "moreInfo": {
                        "status": info.get("status"),
                    },
                }
            }
        return {}
