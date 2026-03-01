"""
Search functionality for Miruro API
Handles search queries and autocomplete suggestions
"""
import logging
from typing import Dict, Any, Optional
from .base import MiruroBaseClient

logger = logging.getLogger(__name__)


class MiruroSearchService:
    """Service for anime search operations via Miruro API"""

    def __init__(self, client: MiruroBaseClient):
        self.client = client

    def _normalize_search_result(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a Miruro search result to standard shape"""
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
        }

    async def search(
        self,
        q: str,
        page: int = 1,
        *,
        genres: Optional[str] = None,
        type_: Optional[str] = None,
        sort: Optional[str] = None,
        season: Optional[str] = None,
        language: Optional[str] = None,
        status: Optional[str] = None,
        rating: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        score: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search anime via Miruro /search endpoint
        Returns data in standard format
        """
        params = {"query": q, "page": page, "per_page": 20}

        resp = await self.client._get("search", params=params)
        if not resp:
            return {}

        results = resp.get("results", [])
        filtered_results = [
            item for item in results 
            if not item.get("isAdult", False) and "Hentai" not in item.get("genres", [])
        ]
        total = resp.get("total", 0)
        has_next = resp.get("hasNextPage", False)
        per_page = resp.get("perPage", 20)

        animes = [self._normalize_search_result(item) for item in filtered_results]

        total_pages = max(1, (total + per_page - 1) // per_page) if total else 1

        return {
            "animes": animes,
            "mostPopularAnimes": [],
            "totalPages": total_pages,
            "hasNextPage": has_next,
            "currentPage": page,
            "searchQuery": q,
        }

    async def search_suggestions(self, q: str) -> Dict[str, Any]:
        """
        Get search suggestions via Miruro /suggestions endpoint
        Returns data in standard format
        """
        resp = await self.client._get("suggestions", params={"query": q})
        if not resp:
            return {"suggestions": []}

        suggestions = resp.get("suggestions", [])
        filtered_suggestions = [
            s for s in suggestions 
            if not s.get("isAdult", False) and "Hentai" not in s.get("genres", [])
        ]

        # Normalize each suggestion to standard shape
        normalized = []
        for s in filtered_suggestions:
            normalized.append({
                "id": str(s.get("id", "")),
                "anilistId": s.get("id"),
                "name": s.get("title") or s.get("title_romaji") or "Unknown",
                "jname": s.get("title_romaji") or "",
                "poster": s.get("poster") or "",
                "moreInfo": [
                    s.get("format") or "",
                    s.get("status") or "",
                    str(s.get("year") or ""),
                ],
            })

        return {"suggestions": normalized}

    async def az_list(self, sort_option: str = "all", page: int = 1) -> Dict[str, Any]:
        """
        Miruro doesn't have a direct A-Z list endpoint.
        Use /filter with alphabet sorting as a workaround.
        """
        params = {"page": page, "per_page": 24, "sort": "TITLE_ROMAJI"}
        resp = await self.client._get("filter", params=params)
        if not resp:
            return {}

        results = resp.get("results", [])
        filtered_results = [
            item for item in results 
            if not item.get("isAdult", False) and "Hentai" not in item.get("genres", [])
        ]
        animes = [self._normalize_search_result(item) for item in filtered_results]
        
        return {
            "animes": animes,
            "totalPages": max(1, (resp.get("total", 0) + 24 - 1) // 24),
            "hasNextPage": resp.get("hasNextPage", False),
            "currentPage": page,
        }
