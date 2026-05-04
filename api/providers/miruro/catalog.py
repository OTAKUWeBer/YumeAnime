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

        total_episodes = item.get("episodes") or 0
        next_ep = item.get("nextAiringEpisode") or {}
        # If currently airing, released = next episode - 1; otherwise released = total
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

    async def _fallback_anilist_query(self, query: str, variables: dict) -> Dict[str, Any]:
        """Execute a GraphQL query against AniList API as fallback"""
        url = "https://graphql.anilist.co"
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json={"query": query, "variables": variables}) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception as e:
            logger.error(f"AniList fallback query failed: {e}")
        return {}

    async def genre(self, name: str, page: int = 1) -> Dict[str, Any]:
        """Get anime by genre via AniList GraphQL"""
        resp = None
        if not resp:
            logger.info(f"Miruro /filter failed for genre '{name}'. Using AniList fallback.")
            query = '''
            query ($genre: String, $page: Int, $perPage: Int) {
              Page(page: $page, perPage: $perPage) {
                pageInfo {
                  total
                  hasNextPage
                  lastPage
                }
                media(type: ANIME, genre: $genre, sort: SCORE_DESC, isAdult: false) {
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
                }
              }
            }
            '''
            variables = {"genre": name.title(), "page": page, "perPage": 24}
            fallback_data = await self._fallback_anilist_query(query, variables)
            
            if fallback_data and "data" in fallback_data and "Page" in fallback_data["data"]:
                page_data = fallback_data["data"]["Page"]
                media_list = page_data.get("media", [])
                page_info = page_data.get("pageInfo", {})
                
                filtered_results = [
                    item for item in media_list 
                    if not item.get("isAdult", False) and "Hentai" not in item.get("genres", [])
                ]
                animes = [self._normalize_anime(item) for item in filtered_results]
                
                return {
                    "animes": animes,
                    "genreName": name.title(),
                    "totalPages": page_info.get("lastPage", max(1, page)),
                    "hasNextPage": page_info.get("hasNextPage", False),
                    "currentPage": page,
                }
            return {}



    async def category(self, name: str, page: int = 1) -> Dict[str, Any]:
        """Get anime by category via AniList API"""
        category_map = {
            "trending": {"sort": "TRENDING_DESC"},
            "popular": {"sort": "POPULARITY_DESC"},
            "most-popular": {"sort": "POPULARITY_DESC"},
            "recently-updated": {"sort": "UPDATED_AT_DESC"},
            "recently-added": {"sort": "UPDATED_AT_DESC"},
            "movie": {"format": "MOVIE", "sort": "SCORE_DESC"},
            "tv": {"format": "TV", "sort": "SCORE_DESC"},
            "ova": {"format": "OVA", "sort": "SCORE_DESC"},
            "ona": {"format": "ONA", "sort": "SCORE_DESC"},
            "special": {"format": "SPECIAL", "sort": "SCORE_DESC"},
            "most-favorite": {"sort": "FAVOURITES_DESC"},
            "top-airing": {"status": "RELEASING", "sort": "SCORE_DESC"},
            "completed": {"status": "FINISHED", "sort": "SCORE_DESC"},
            "upcoming": {"status": "NOT_YET_RELEASED", "sort": "POPULARITY_DESC"},
        }

        extra_params = category_map.get(name.lower(), {"sort": "SCORE_DESC"})

        graphql_format = extra_params.get("format")
        graphql_status = extra_params.get("status")
        graphql_sort = extra_params.get("sort")
        
        query = '''
        query ($page: Int, $perPage: Int, $format: MediaFormat, $status: MediaStatus, $sort: [MediaSort]) {
          Page(page: $page, perPage: $perPage) {
            pageInfo { total hasNextPage lastPage }
            media(type: ANIME, format: $format, status: $status, sort: $sort, isAdult: false) {
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
            }
          }
        }
        '''
        variables = {"page": page, "perPage": 24}
        if graphql_format:
            variables["format"] = graphql_format
        if graphql_status:
            variables["status"] = graphql_status
        if graphql_sort:
            variables["sort"] = [graphql_sort]
            
        fallback_data = await self._fallback_anilist_query(query, variables)
        
        if fallback_data and "data" in fallback_data and "Page" in fallback_data["data"]:
            page_data = fallback_data["data"]["Page"]
            media_list = page_data.get("media", [])
            page_info = page_data.get("pageInfo", {})
            
            filtered_results = [
                item for item in media_list 
                if not item.get("isAdult", False) and "Hentai" not in item.get("genres", [])
            ]
            animes = [self._normalize_anime(item) for item in filtered_results]
            
            return {
                "animes": animes,
                "category": name.replace("-", " ").title(),
                "totalPages": page_info.get("lastPage", max(1, page)),
                "hasNextPage": page_info.get("hasNextPage", False),
                "currentPage": page,
            }
        return {}

    async def producer(self, name: str, page: int = 1) -> Dict[str, Any]:
        """
        Get anime by producer/studio — Use AniList GraphQL
        """
        query = '''
        query ($search: String, $page: Int, $perPage: Int) {
          Page(page: $page, perPage: $perPage) {
            pageInfo { total hasNextPage lastPage }
            studios(search: $search) {
              id
              name
              media(isMain: true, sort: SCORE_DESC) {
                nodes {
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
                }
              }
            }
          }
        }
        '''
        variables = {"search": name.replace("-", " "), "page": page, "perPage": 24}
        fallback_data = await self._fallback_anilist_query(query, variables)
        
        animes = []
        page_info = {}
        if fallback_data and "data" in fallback_data and "Page" in fallback_data["data"]:
            page_data = fallback_data["data"]["Page"]
            studios = page_data.get("studios", [])
            page_info = page_data.get("pageInfo", {})
            if studios and "media" in studios[0]:
                media_list = studios[0]["media"].get("nodes", [])
                filtered_results = [
                    item for item in media_list 
                    if not item.get("isAdult", False) and "Hentai" not in item.get("genres", [])
                ]
                animes = [self._normalize_anime(item) for item in filtered_results]

        return {
            "animes": animes,
            "producerName": name.replace("-", " ").title(),
            "totalPages": page_info.get("lastPage", max(1, page)),
            "hasNextPage": page_info.get("hasNextPage", False),
            "currentPage": page,
        }

    async def schedule(self, date: str = None) -> Dict[str, Any]:
        """Get anime airing schedule via AniList GraphQL endpoint"""
        import time
        now = int(time.time())
        query = '''
        query ($page: Int, $perPage: Int, $airingAt_greater: Int, $airingAt_lesser: Int) {
          Page(page: $page, perPage: $perPage) {
            airingSchedules(airingAt_greater: $airingAt_greater, airingAt_lesser: $airingAt_lesser, sort: TIME) {
              id
              episode
              airingAt
              timeUntilAiring
              media {
                id
                title { romaji english native }
                coverImage { extraLarge large }
                episodes
                format
                duration
                averageScore
                genres
                isAdult
              }
            }
          }
        }
        '''
        # Next 7 days
        variables = {
            "page": 1,
            "perPage": 50,
            "airingAt_greater": now,
            "airingAt_lesser": now + 7 * 24 * 3600
        }
        fallback_data = await self._fallback_anilist_query(query, variables)
        
        scheduled = []
        if fallback_data and "data" in fallback_data and "Page" in fallback_data["data"]:
            schedules = fallback_data["data"]["Page"].get("airingSchedules", [])
            for sched in schedules:
                media = sched.get("media", {})
                if not media or media.get("isAdult", False) or "Hentai" in media.get("genres", []):
                    continue
                normalized = self._normalize_anime(media)
                normalized["next_episode"] = sched.get("episode")
                normalized["airingAt"] = sched.get("airingAt")
                normalized["timeUntilAiring"] = sched.get("timeUntilAiring")
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
