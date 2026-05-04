"""
AniList GraphQL service for home page data
Direct replacement for Miruro API calls
"""
import asyncio
import logging
import time
from typing import Dict, Any, List
import aiohttp

logger = logging.getLogger(__name__)

ANILIST_GRAPHQL = "https://graphql.anilist.co"


class AnilistHomeService:
    """Service for fetching home page data directly from AniList GraphQL API"""

    def __init__(self):
        self._home_cache = None
        self._home_cache_ts = 0.0
        self._home_cache_ttl = 300.0  # 5 minutes cache for blazing speed

    def _normalize_anime(self, item: Dict[str, Any], rank: int = 0) -> Dict[str, Any]:
        """Normalize AniList GraphQL result into unified anime format"""
        title = item.get("title", {}) or {}
        cover = item.get("coverImage", {}) or {}
        studios_nodes = (item.get("studios", {}).get("nodes", []))
        studio_name = studios_nodes[0].get("name") if studios_nodes else ""

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
            "banner": item.get("bannerImage") or "",
            "episodes": {
                "sub": total_episodes,
                "dub": 0,
                "released": released,
            },
            "type": item.get("format") or "",
            "duration": f"{item.get('duration', '')} min" if item.get("duration") else "",
            "rating": item.get("averageScore") or None,
            "isAdult": item.get("isAdult", False),
            "rank": rank,
            "description": "",
            "otherInfo": [
                item.get("format") or "",
                f"{item.get('duration', '')}m" if item.get("duration") else "",
                studio_name,
            ],
        }

    def _normalize_spotlight(self, item: Dict[str, Any], rank: int = 0) -> Dict[str, Any]:
        """Normalize a AniList result into spotlight shape"""
        base = self._normalize_anime(item, rank)
        # Spotlight-specific enrichment
        desc = item.get("description") or ""
        # Strip HTML tags from AniList descriptions
        if desc and "<" in desc:
            import re
            desc = re.sub(r"<[^>]+>", "", desc)
        base["description"] = desc
        base["genres"] = item.get("genres") or []
        studios_nodes = (item.get("studios", {}).get("nodes", []))
        base["studio"] = studios_nodes[0].get("name") if studios_nodes else ""
        base["totalEpisodes"] = item.get("episodes") or None
        # released episode count for spotlight
        released_count = base["episodes"].get("released")
        base["releasedEpisodes"] = released_count if released_count is not None else base.get("totalEpisodes")
        base["season"] = item.get("season") or ""
        base["seasonYear"] = item.get("seasonYear") or ""
        next_ep = item.get("nextAiringEpisode") or {}
        base["nextEpisode"] = next_ep.get("episode") or None
        return base

    async def _fetch_anilist_data(self, query: str, variables: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make a GraphQL request to AniList"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    ANILIST_GRAPHQL,
                    json={'query': query, 'variables': variables or {}},
                    headers={'Content-Type': 'application/json'}
                ) as resp:
                    if resp.status != 200:
                        logger.error(f"AniList API error {resp.status}")
                        return {}
                    data = await resp.json()
                    if 'errors' in data:
                        logger.error(f"AniList GraphQL errors: {data['errors']}")
                        return {}
                    return data.get('data', {})
        except Exception as e:
            logger.error(f"AniList request failed: {e}")
            return {}

    async def _fetch_home_data(self) -> Dict[str, Any]:
        """Fetch trending, popular, and recent from AniList GraphQL API using a single combined query"""
        now = time.time()
        if self._home_cache and (now - self._home_cache_ts) < self._home_cache_ttl:
            return self._home_cache

        combined_query = '''
        fragment mediaFields on Media {
          id
          title { romaji english native }
          coverImage { large extraLarge }
          bannerImage
          episodes
          duration
          averageScore
          isAdult
          format
          studios { nodes { name } }
          nextAiringEpisode { episode }
        }
        query ($perPage: Int) {
          trending: Page(perPage: $perPage) {
            media(type: ANIME, sort: TRENDING_DESC, status_in: [RELEASING, FINISHED]) {
              ...mediaFields
            }
          }
          popular: Page(perPage: $perPage) {
            media(type: ANIME, sort: POPULARITY_DESC, status_in: [RELEASING, FINISHED]) {
              ...mediaFields
            }
          }
          recent: Page(perPage: $perPage) {
            media(type: ANIME, sort: UPDATED_AT_DESC, status_in: [RELEASING, FINISHED]) {
              ...mediaFields
            }
          }
          spotlight: Page(perPage: 10) {
            media(type: ANIME, sort: TRENDING_DESC, status_in: [RELEASING]) {
              ...mediaFields
              description
              genres
              season
              seasonYear
            }
          }
        }
        '''

        try:
            data = await self._fetch_anilist_data(combined_query, {"perPage": 24})

            def safe_results(key):
                if not data:
                    return []
                return data.get(key, {}).get("media", [])

            def filter_adult(items):
                return [
                    item for item in items
                    if not item.get("isAdult", False) and "Hentai" not in item.get("genres", [])
                ]

            def is_valid_entry(anime):
                """Filter out empty/useless anime entries"""
                name = anime.get("name", "")
                if not name or name == "Unknown":
                    return False
                eps = anime.get("episodes") or {}
                sub = eps.get("sub", 0) or 0
                released = eps.get("released", 0) or 0
                # Keep if it has episodes OR is upcoming
                if sub == 0 and released == 0:
                    return False
                return True

            spotlight_items = filter_adult(safe_results("spotlight"))
            trending_items = filter_adult(safe_results("trending"))
            popular_items = filter_adult(safe_results("popular"))
            recent_items = filter_adult(safe_results("recent"))

            # spotlightAnimes = top trending (up to 10)
            spotlight = [
                a for a in (
                    self._normalize_spotlight(item, i + 1)
                    for i, item in enumerate(spotlight_items)
                ) if is_valid_entry(a)
            ]

            # trendingAnimes = all trending
            trending = [
                a for a in (
                    self._normalize_anime(item, i + 1)
                    for i, item in enumerate(trending_items)
                ) if is_valid_entry(a)
            ]

            # mostPopularAnimes = popular
            popular = [
                a for a in (
                    self._normalize_anime(item, i + 1)
                    for i, item in enumerate(popular_items)
                ) if is_valid_entry(a)
            ]

            # latestEpisodeAnimes = recent
            latest = [
                a for a in (
                    self._normalize_anime(item, i + 1)
                    for i, item in enumerate(recent_items)
                ) if is_valid_entry(a)
            ]

            # Add episode count annotations
            normalized = {
                "spotlightAnimes": self._annotate_episodes_count(spotlight),
                "trendingAnimes": self._annotate_episodes_count(trending),
                "mostPopularAnimes": self._annotate_episodes_count(popular),
                "latestEpisodeAnimes": self._annotate_episodes_count(latest),
            }

            self._home_cache = normalized
            self._home_cache_ts = time.time()
            logger.info(
                f"[AniListHome] Fetched: spotlight={len(spotlight)}, "
                f"trending={len(trending)}, popular={len(popular)}, latest={len(latest)}"
            )
            return normalized

        except Exception as e:
            logger.error(f"[AniListHome] Error fetching home data: {e}")
            if self._home_cache:
                return self._home_cache
            return {
                "spotlightAnimes": [],
                "trendingAnimes": [],
                "mostPopularAnimes": [],
                "latestEpisodeAnimes": [],
            }

    def _annotate_episodes_count(self, animes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add episode count annotations for display"""
        for anime in animes:
            episodes = anime.get("episodes", {})
            sub_count = episodes.get("sub", 0)
            released_count = episodes.get("released", 0)

            if sub_count > 0:
                if released_count > 0 and released_count != sub_count:
                    anime["episodeCount"] = f"{released_count}/{sub_count}"
                else:
                    anime["episodeCount"] = str(sub_count)
            else:
                anime["episodeCount"] = "?"

        return animes

    async def home(self) -> Dict[str, Any]:
        """Get unified home response with all sections + metadata"""
        data = await self._fetch_home_data()
        return {
            "success": True,
            "data": {key: value for key, value in data.items()},
            "counts": {key: len(value) for key, value in data.items()},
        }