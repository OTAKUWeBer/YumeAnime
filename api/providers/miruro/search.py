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

    @staticmethod
    def _is_valid_result(anime: Dict[str, Any]) -> bool:
        """Filter out empty/useless anime entries"""
        name = anime.get("name", "")
        if not name or name == "Unknown":
            return False
        eps = anime.get("episodes") or {}
        sub = eps.get("sub", 0) or 0
        released = eps.get("released", 0) or 0
        if sub == 0 and released == 0:
            return False
        return True

    def _normalize_search_result(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a Miruro search result to standard shape"""
        title = item.get("title", {}) or {}
        cover = item.get("coverImage", {}) or {}
        studios_nodes = (item.get("studios", {}) or {}).get("nodes", [])
        studio_name = studios_nodes[0].get("name") if studios_nodes else ""
        english_title = title.get("english") or title.get("romaji") or "Unknown"

        total_episodes = item.get("episodes") or 0
        next_ep = item.get("nextAiringEpisode") or {}
        if next_ep and next_ep.get("episode"):
            released = next_ep["episode"] - 1
        else:
            released = total_episodes

        return {
            "id": str(item.get("id", "")),
            "anilistId": item.get("id"),
            "name": english_title,
            "jname": title.get("native") or title.get("romaji") or "",
            "poster": cover.get("extraLarge") or cover.get("large") or "",
            "episodes": {
                "sub": total_episodes,
                "dub": 0,
                "released": released,
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
        query = '''
        query ($search: String, $page: Int, $perPage: Int) {
          Page(page: $page, perPage: $perPage) {
            pageInfo { total hasNextPage lastPage perPage }
            media(type: ANIME, search: $search, sort: SEARCH_MATCH) {
              id
              title { romaji english native }
              coverImage { extraLarge large }
              episodes
              nextAiringEpisode { episode }
              format
              duration
              averageScore
              genres
              isAdult
              studios { nodes { name } }
            }
          }
        }
        '''
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://graphql.anilist.co",
                    json={"query": query, "variables": {"search": q, "page": page, "perPage": 20}}
                ) as r:
                    data = await r.json()
                    page_data = data.get("data", {}).get("Page", {})
        except Exception as e:
            logger.error(f"Anilist search fetch failed: {e}")
            page_data = {}

        results = page_data.get("media", [])
        filtered_results = [
            item for item in results 
            if not item.get("isAdult", False) and "Hentai" not in item.get("genres", [])
        ]
        
        page_info = page_data.get("pageInfo", {})
        total = page_info.get("total", 0)
        has_next = page_info.get("hasNextPage", False)
        per_page = page_info.get("perPage", 20)

        animes = [
            a for a in (self._normalize_search_result(item) for item in filtered_results)
            if self._is_valid_result(a)
        ]

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
        query = '''
        query ($search: String) {
          Page(page: 1, perPage: 10) {
            media(type: ANIME, search: $search, sort: SEARCH_MATCH) {
              id
              title { romaji english native }
              coverImage { medium large }
              format
              episodes
              status
              seasonYear
              genres
              isAdult
            }
          }
        }
        '''
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://graphql.anilist.co",
                    json={"query": query, "variables": {"search": q}}
                ) as r:
                    data = await r.json()
                    suggestions = data.get("data", {}).get("Page", {}).get("media", [])
        except Exception as e:
            logger.error(f"Anilist suggestions fetch failed: {e}")
            suggestions = []

        filtered_suggestions = [
            s for s in suggestions 
            if not s.get("isAdult", False) and "Hentai" not in s.get("genres", [])
        ]

        normalized = []
        for s in filtered_suggestions:
            title = s.get("title", {})
            name = title.get("english") or title.get("romaji") or ""
            cover = s.get("coverImage", {})
            poster = cover.get("medium") or cover.get("large") or ""
            if not name or name == "Unknown":
                continue
            more_info = []
            fmt = s.get("format")
            if fmt:
                more_info.append(fmt)
            eps = s.get("episodes")
            status = s.get("status") or ""
            if eps:
                more_info.append(f"Ep {eps}")
            elif status == "NOT_YET_RELEASED":
                more_info.append("Upcoming")
            elif status == "RELEASING":
                more_info.append("Airing")
            year = s.get("seasonYear")
            if year:
                more_info.append(str(year))
            normalized.append({
                "id": str(s.get("id", "")),
                "anilistId": s.get("id"),
                "name": name,
                "jname": title.get("native") or title.get("romaji") or "",
                "poster": poster,
                "moreInfo": more_info,
            })

        return {"suggestions": normalized}

    async def az_list(self, sort_option: str = "all", page: int = 1) -> Dict[str, Any]:
        """
        Miruro doesn't have a direct A-Z list endpoint.
        Use /filter with alphabet sorting as a workaround.
        """
        query = '''
        query ($page: Int, $perPage: Int) {
          Page(page: $page, perPage: $perPage) {
            pageInfo { total hasNextPage lastPage perPage }
            media(type: ANIME, sort: TITLE_ROMAJI) {
              id
              title { romaji english native }
              coverImage { extraLarge large }
              episodes
              nextAiringEpisode { episode }
              format
              duration
              averageScore
              genres
              isAdult
              studios { nodes { name } }
            }
          }
        }
        '''
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://graphql.anilist.co",
                    json={"query": query, "variables": {"page": page, "perPage": 24}}
                ) as r:
                    data = await r.json()
                    page_data = data.get("data", {}).get("Page", {})
        except Exception as e:
            logger.error(f"Anilist az_list fetch failed: {e}")
            page_data = {}

        results = page_data.get("media", [])
        filtered_results = [
            item for item in results 
            if not item.get("isAdult", False) and "Hentai" not in item.get("genres", [])
        ]
        
        page_info = page_data.get("pageInfo", {})
        
        animes = [
            a for a in (self._normalize_search_result(item) for item in filtered_results)
            if self._is_valid_result(a)
        ]
        
        return {
            "animes": animes,
            "totalPages": page_info.get("lastPage", max(1, page)),
            "hasNextPage": page_info.get("hasNextPage", False),
            "currentPage": page,
        }
