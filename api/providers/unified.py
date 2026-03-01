"""
Unified scraper - uses the Miruro Native API.
"""

import logging
from typing import Optional, Dict, Any, Union
from urllib.parse import parse_qs

from .miruro import MiruroScraper

logger = logging.getLogger(__name__)


class UnifiedScraper:
    """
    Unified scraper using the Miruro Native API.
    """

    def __init__(self):
        self.miruro = MiruroScraper()
        logger.info("[UnifiedScraper] Initialized with Miruro only")

    # =========================================================================
    # HOME
    # =========================================================================
    async def home(self) -> Dict[str, Any]:
        """Get home page data from Miruro"""
        try:
            result = await self.miruro.home()
            if (
                result
                and result.get("success")
                and any(
                    result.get("data", {}).get(k)
                    for k in [
                        "trendingAnimes",
                        "mostPopularAnimes",
                        "latestEpisodeAnimes",
                    ]
                )
            ):
                logger.debug("[UnifiedScraper] Home: Miruro succeeded")
                return result
        except Exception as e:
            logger.warning(f"[UnifiedScraper] Home: Miruro failed: {e}")

        return {"success": False, "data": {}}

    def clear_home_cache(self) -> None:
        """Clear caches on Miruro"""
        try:
            self.miruro.clear_home_cache()
        except Exception:
            pass

    # =========================================================================
    # ANIME INFO
    # =========================================================================
    async def get_anime_info(self, anime_id: str) -> dict:
        """
        Get anime info.
        - If anime_id is numeric → Miruro (AniList ID)
        - If slug → Try to resolve to AniList ID using cache, then search Miruro
        """
        print(f"[UnifiedScraper] get_anime_info() called with: {anime_id}")

        # Check if this is an AniList ID (numeric)
        if str(anime_id).isdigit():
            try:
                result = await self.miruro.get_anime_info(anime_id)
                if result and result.get("title"):
                    logger.debug(
                        f"[UnifiedScraper] AnimeInfo (Miruro, anilistId={anime_id}): OK"
                    )
                    return result
            except Exception as e:
                logger.warning(
                    f"[UnifiedScraper] AnimeInfo Miruro failed for {anime_id}: {e}"
                )

        # Fallback: search Miruro using the slug
        try:
            search_result = await self.miruro.search(anime_id, 1)
            if search_result and search_result.get("animes"):
                first_match = search_result["animes"][0]
                anilist_id = first_match.get("id") or first_match.get("anilistId")
                if anilist_id:
                    result = await self.miruro.get_anime_info(str(anilist_id))
                    if result and result.get("title"):
                        logger.debug(
                            f"[UnifiedScraper] AnimeInfo (Miruro, search anilistId={anilist_id}): OK"
                        )
                        return result
        except Exception as e:
            logger.warning(
                f"[UnifiedScraper] Search fallback failed for {anime_id}: {e}"
            )

        return {}

    # =========================================================================
    # EPISODES
    # =========================================================================
    async def get_episodes(self, anime_id: str) -> Dict[str, Any]:
        """Get episodes — Miruro for numeric IDs, or resolve slug first"""
        # If numeric (AniList ID), try Miruro
        if str(anime_id).isdigit():
            try:
                result = await self.miruro.get_episodes(anime_id)
                if result and result.get("episodes"):
                    logger.debug(
                        f"[UnifiedScraper] Episodes (Miruro, {anime_id}): {len(result.get('episodes', []))} eps"
                    )
                    return result
            except Exception as e:
                logger.warning(
                    f"[UnifiedScraper] Episodes Miruro failed for {anime_id}: {e}"
                )

        # Fallback: search Miruro using the slug
        try:
            search_result = await self.miruro.search(anime_id, 1)
            if search_result and search_result.get("animes"):
                first_match = search_result["animes"][0]
                anilist_id = first_match.get("id") or first_match.get("anilistId")
                if anilist_id:
                    anilist_id_str = str(anilist_id)
                    try:
                        result = await self.miruro.get_episodes(anilist_id_str)
                        if result and result.get("episodes"):
                            logger.debug(
                                f"[UnifiedScraper] Episodes (Miruro, search fallback {anilist_id_str}): {len(result.get('episodes', []))} eps"
                            )
                            return result
                    except Exception as e:
                        logger.warning(
                            f"[UnifiedScraper] Episodes Miruro failed for search fallback {anilist_id_str}: {e}"
                        )
        except Exception:
            pass

        return {
            "anime_id": anime_id,
            "title": "",
            "total_sub_episodes": 0,
            "total_dub_episodes": 0,
            "episodes": [],
            "total_episodes": 0,
        }

    async def episodes(self, anime_id: str) -> Dict[str, Any]:
        """Get episodes list — Miruro for numeric IDs, or resolve slug first"""
        print(f"[UnifiedScraper] episodes() called with: {anime_id}")

        if str(anime_id).isdigit():
            try:
                result = await self.miruro.episodes(anime_id)
                if result and result.get("episodes"):
                    return result
            except Exception:
                pass

        # Fallback: search Miruro using the slug
        try:
            search_result = await self.miruro.search(anime_id, 1)
            if search_result and search_result.get("animes"):
                first_match = search_result["animes"][0]
                anilist_id = first_match.get("id") or first_match.get("anilistId")
                if anilist_id:
                    anilist_id_str = str(anilist_id)
                    try:
                        result = await self.miruro.episodes(anilist_id_str)
                        if result and result.get("episodes"):
                            return result
                    except Exception:
                        pass
        except Exception as e:
            print(f"[UnifiedScraper] Error in search fallback: {e}")

        return {"episodes": [], "totalEpisodes": 0}

    async def episode_servers(self, anime_episode_id: str) -> Dict[str, Any]:
        """Get available servers — Miruro doesn't have server concept"""
        return {}

    async def is_dub_available(
        self, eps_title: str, anime_episode_id: str = None
    ) -> bool:
        """Check if dub is available — Miruro for numeric IDs"""
        if str(eps_title).strip().isdigit():
            try:
                return await self.miruro.is_dub_available(eps_title)
            except Exception:
                return False
        return False

    async def episode_sources(
        self, anime_episode_id: str, server: Optional[str] = None, category: str = "sub"
    ) -> Dict[str, Any]:
        """Get episode streaming sources"""
        return {}

    # =========================================================================
    # VIDEO / STREAMING — Miruro only
    # =========================================================================
    def _parse_miruro_ep(self, ep_id_str: str):
        """
        Extract Miruro episode ID components from full_slug.
        Supports new format: 'watch/kiwi/178005/sub/animepahe-1'
        Also supports: 'anime_slug?ep=watch/kiwi/178005/sub/animepahe-1'
        Also supports: '108465?ep=animepahe:4171:47277:1'
        Returns (miruro_ep_id, anilist_id) or (None, None)
        """
        import re

        print(f"[UnifiedScraper] _parse_miruro_ep input: {ep_id_str}")

        # First, extract episode ID from query string if present
        # Format: "anime_slug?ep=watch/kiwi/178005/sub/animepahe-1"
        if "?" in ep_id_str:
            slug_part, query_part = ep_id_str.split("?", 1)
            params = parse_qs(query_part)
            ep_values = params.get("ep", [])
            ep_value = ep_values[0] if ep_values else None
            if ep_value:
                ep_id_str = ep_value
                print(f"[UnifiedScraper] After query extract: {ep_id_str}")

        # New format: watch/{provider}/{anilist_id}/{category}/{slug}
        pattern = r"watch/([^/]+)/(\d+)/([^/]+)/(.+)"
        match = re.match(pattern, ep_id_str)
        if match:
            print(
                f"[UnifiedScraper] Matched new format: provider={match.group(1)}, anilist_id={match.group(2)}, category={match.group(3)}, slug={match.group(4)}"
            )
            return (ep_id_str, int(match.group(2)))

        # Old format with colons (animepahe:4171:47277:1)
        miruro_ep_id = None
        anilist_id = None

        if ":" in ep_id_str and not ep_id_str.startswith("http"):
            miruro_ep_id = ep_id_str

        print(
            f"[UnifiedScraper] Returning: miruro_ep_id={miruro_ep_id}, anilist_id={anilist_id}"
        )
        return miruro_ep_id, anilist_id

    async def video(
        self,
        ep_id: Union[str, int],
        language: str = "sub",
        server: Optional[str] = None,
        anilist_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Get video streaming data using Miruro only.
        """
        ep_id_str = str(ep_id)
        miruro_ep_id, parsed_anilist_id = self._parse_miruro_ep(ep_id_str)

        if parsed_anilist_id:
            anilist_id = parsed_anilist_id

        if miruro_ep_id:
            try:
                provider = server or "kiwi"
                result = await self.miruro.get_sources(
                    episode_id=miruro_ep_id,
                    provider=provider,
                    anilist_id=anilist_id,
                    category=language,
                )
                if result and not result.get("error") and (result.get("video_link") or result.get("embed_sources")):
                    logger.info(
                        f"[UnifiedScraper] Video (Miruro): OK for {miruro_ep_id}"
                    )
                    result["source_provider"] = "miruro"
                    return result
                else:
                    logger.warning(
                        f"[UnifiedScraper] Video Miruro: no video_link for {miruro_ep_id}"
                    )
            except Exception as e:
                logger.warning(f"[UnifiedScraper] Video Miruro failed: {e}")

        logger.info(f"[UnifiedScraper] Video: Miruro failed for {ep_id_str}")
        return {
            "error": "no_sources",
            "message": "No video sources available from Miruro.",
        }

    # =========================================================================
    # SEARCH
    # =========================================================================
    async def search(self, q: str, page: int = 1, **kwargs) -> Dict[str, Any]:
        """Search anime — Miruro"""
        try:
            result = await self.miruro.search(q, page, **kwargs)
            if result and result.get("animes"):
                logger.debug(
                    f"[UnifiedScraper] Search (Miruro): {len(result.get('animes', []))} results"
                )
                return result
        except Exception as e:
            logger.warning(f"[UnifiedScraper] Search Miruro failed: {e}")

        return {}

    async def search_suggestions(self, q: str) -> Dict[str, Any]:
        """Get search suggestions — Miruro"""
        try:
            result = await self.miruro.search_suggestions(q)
            if result and result.get("suggestions"):
                logger.debug(
                    f"[UnifiedScraper] Suggestions (Miruro): {len(result.get('suggestions', []))} results"
                )
                return result
        except Exception as e:
            logger.warning(f"[UnifiedScraper] Suggestions Miruro failed: {e}")

        return {"suggestions": []}

    async def az_list(self, sort_option: str = "all", page: int = 1) -> Dict[str, Any]:
        """Get A-Z anime list"""
        try:
            result = await self.miruro.az_list(sort_option, page)
            if result and result.get("animes"):
                return result
        except Exception:
            pass
        return {"animes": []}

    # =========================================================================
    # CATALOG
    # =========================================================================
    async def producer(self, name: str, page: int = 1) -> Dict[str, Any]:
        """Get anime by producer"""
        try:
            result = await self.miruro.producer(name, page)
            if result and result.get("animes"):
                return result
        except Exception:
            pass
        return {}

    async def genre(self, name: str, page: int = 1) -> Dict[str, Any]:
        """Get anime by genre"""
        try:
            result = await self.miruro.genre(name, page)
            if result and result.get("animes"):
                logger.debug(
                    f"[UnifiedScraper] Genre (Miruro, {name}): {len(result.get('animes', []))} results"
                )
                return result
        except Exception as e:
            logger.warning(f"[UnifiedScraper] Genre Miruro failed for {name}: {e}")

        return {}

    async def category(self, name: str, page: int = 1) -> Dict[str, Any]:
        """Get anime by category"""
        try:
            result = await self.miruro.category(name, page)
            if result and result.get("animes"):
                logger.debug(
                    f"[UnifiedScraper] Category (Miruro, {name}): {len(result.get('animes', []))} results"
                )
                return result
        except Exception as e:
            logger.warning(f"[UnifiedScraper] Category Miruro failed for {name}: {e}")

        return {}

    async def schedule(self, date: str = None) -> Dict[str, Any]:
        """Get anime schedule"""
        try:
            result = await self.miruro.schedule(date)
            if result and (result.get("scheduledAnimes") or result.get("animes")):
                return result
        except Exception:
            pass
        return {}

    async def qtip(self, anime_id: str) -> Dict[str, Any]:
        """Quick tooltip info"""
        if str(anime_id).isdigit():
            try:
                return await self.miruro.qtip(anime_id)
            except Exception:
                pass
        return {}

    async def anime_about(self, anime_id: str) -> Dict[str, Any]:
        """Detailed anime about"""
        if str(anime_id).isdigit():
            try:
                return await self.miruro.anime_about(anime_id)
            except Exception:
                pass
        return {}

    # =========================================================================
    # SCHEDULE
    # =========================================================================
    async def next_episode_schedule(self, anime_id: str) -> Dict[str, Any]:
        """Get next episode schedule"""
        if str(anime_id).isdigit():
            try:
                result = await self.miruro.next_episode_schedule(anime_id)
                if result and result.get("airingTimestamp"):
                    return result
            except Exception:
                pass
        return {}

    # =========================================================================
    # UTILITY
    # =========================================================================
    async def raw(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Fetch arbitrary endpoint"""
        return {}
