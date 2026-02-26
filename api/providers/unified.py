"""
Unified scraper that tries Miruro API first, falls back to HiAnime.
Drop-in replacement for HianimeScraper — same public interface.
"""
import logging
from typing import Optional, Dict, Any, Union
from urllib.parse import parse_qs

from .hianime import HianimeScraper
from .miruro import MiruroScraper

logger = logging.getLogger(__name__)


class UnifiedScraper:
    """
    Unified scraper with Miruro as primary and HiAnime as fallback.
    Maintains the same public API as HianimeScraper so routes don't need changes.
    """

    def __init__(self):
        self.miruro = MiruroScraper()
        self.hianime = HianimeScraper()
        logger.info("[UnifiedScraper] Initialized with Miruro (primary) + HiAnime (fallback)")

    # =========================================================================
    # HOME
    # =========================================================================
    async def home(self) -> Dict[str, Any]:
        """Get home page data — Miruro first, HiAnime fallback"""
        try:
            result = await self.miruro.home()
            if result and result.get("success") and any(
                result.get("data", {}).get(k)
                for k in ["trendingAnimes", "mostPopularAnimes", "latestEpisodeAnimes"]
            ):
                logger.debug("[UnifiedScraper] Home: Miruro succeeded")
                return result
        except Exception as e:
            logger.warning(f"[UnifiedScraper] Home: Miruro failed: {e}")

        logger.info("[UnifiedScraper] Home: falling back to HiAnime")
        return await self.hianime.home()

    def clear_home_cache(self) -> None:
        """Clear caches on both providers"""
        try:
            self.miruro.clear_home_cache()
        except Exception:
            pass
        try:
            self.hianime.clear_home_cache()
        except Exception:
            pass

    # =========================================================================
    # ANIME INFO
    # =========================================================================
    async def get_anime_info(self, anime_id: str) -> dict:
        """
        Get anime info. 
        - If anime_id is numeric → Miruro (AniList ID)
        - If slug → HiAnime first (to get AniList ID), then enrich from Miruro
        """
        # Check if this is an AniList ID (numeric)
        if str(anime_id).isdigit():
            try:
                result = await self.miruro.get_anime_info(anime_id)
                if result and result.get("title"):
                    logger.debug(f"[UnifiedScraper] AnimeInfo (Miruro, anilistId={anime_id}): OK")
                    return result
            except Exception as e:
                logger.warning(f"[UnifiedScraper] AnimeInfo Miruro failed for {anime_id}: {e}")

        # HiAnime slug-based lookup
        try:
            result = await self.hianime.get_anime_info(anime_id)
            if result and result.get("title"):
                # Try to enrich with Miruro data using AniList ID if available
                anilist_id = result.get("anilistId")
                if anilist_id:
                    try:
                        miruro_info = await self.miruro.get_anime_info(anilist_id)
                        if miruro_info and miruro_info.get("title"):
                            # Merge Miruro data into HiAnime result (HiAnime takes priority for existing fields)
                            for key in ["bannerImage", "nextAiringEpisode"]:
                                if miruro_info.get(key) and not result.get(key):
                                    result[key] = miruro_info[key]
                            # Use Miruro characters if HiAnime doesn't have them
                            if not result.get("characters") and miruro_info.get("characters"):
                                result["characters"] = miruro_info["characters"]
                    except Exception:
                        pass  # Enrichment is optional
                logger.debug(f"[UnifiedScraper] AnimeInfo (HiAnime, slug={anime_id}): OK")
                return result
        except Exception as e:
            logger.warning(f"[UnifiedScraper] AnimeInfo HiAnime failed for {anime_id}: {e}")

        return {}

    # =========================================================================
    # EPISODES
    # =========================================================================
    async def get_episodes(self, anime_id: str) -> Dict[str, Any]:
        """Get episodes — Miruro first for numeric IDs, HiAnime for slugs"""
        # If numeric (AniList ID), try Miruro first (faster, avoids failed HiAnime call)
        if str(anime_id).isdigit():
            try:
                result = await self.miruro.get_episodes(anime_id)
                if result and result.get("episodes"):
                    logger.debug(f"[UnifiedScraper] Episodes (Miruro, {anime_id}): {len(result.get('episodes', []))} eps")
                    return result
            except Exception as e:
                logger.warning(f"[UnifiedScraper] Episodes Miruro failed for {anime_id}: {e}")

        # HiAnime slug-based fallback
        try:
            result = await self.hianime.get_episodes(anime_id)
            if result and result.get("episodes"):
                logger.debug(f"[UnifiedScraper] Episodes (HiAnime, {anime_id}): {len(result.get('episodes', []))} eps")
                return result
        except Exception as e:
            logger.warning(f"[UnifiedScraper] Episodes HiAnime failed for {anime_id}: {e}")

        return {
            "anime_id": anime_id,
            "title": "",
            "total_sub_episodes": 0,
            "total_dub_episodes": 0,
            "episodes": [],
            "total_episodes": 0,
        }

    async def episodes(self, anime_id: str) -> Dict[str, Any]:
        """Get episodes list — Miruro first for numeric IDs"""
        if str(anime_id).isdigit():
            try:
                result = await self.miruro.episodes(anime_id)
                if result and result.get("episodes"):
                    return result
            except Exception:
                pass

        try:
            result = await self.hianime.episodes(anime_id)
            if result and result.get("episodes"):
                return result
        except Exception as e:
            logger.warning(f"[UnifiedScraper] episodes() HiAnime failed for {anime_id}: {e}")

        return {"episodes": [], "totalEpisodes": 0}

    async def episode_servers(self, anime_episode_id: str) -> Dict[str, Any]:
        """Get available servers — skip for Miruro IDs, HiAnime only"""
        # If the slug part is numeric (Miruro mode), skip — no server concept
        ep_str = str(anime_episode_id)
        if "?" in ep_str:
            slug_part = ep_str.split("?", 1)[0]
            if slug_part.strip().isdigit():
                return {}
        try:
            return await self.hianime.episode_servers(anime_episode_id)
        except Exception as e:
            logger.warning(f"[UnifiedScraper] episode_servers failed: {e}")
            return {}

    async def is_dub_available(self, eps_title: str, anime_episode_id: str) -> bool:
        """Check if dub is available — Miruro for numeric IDs, HiAnime for slugs"""
        if str(eps_title).strip().isdigit():
            try:
                return await self.miruro.is_dub_available(eps_title)
            except Exception:
                return False
        try:
            return await self.hianime.is_dub_available(eps_title, anime_episode_id)
        except Exception:
            return False

    async def episode_sources(
        self,
        anime_episode_id: str,
        server: Optional[str] = None,
        category: str = "sub"
    ) -> Dict[str, Any]:
        """Get episode streaming sources — HiAnime (used internally by video)"""
        try:
            return await self.hianime.episode_sources(anime_episode_id, server, category)
        except Exception:
            return {}

    # =========================================================================
    # VIDEO / STREAMING — 3-tier: Miruro → HiAnime → Megaplay
    # =========================================================================
    def _parse_miruro_ep(self, ep_id_str: str):
        """Extract Miruro episode ID and anilist_id from full_slug.
        full_slug format: '108465?ep=animepahe:4171:47277:1' or just 'animepahe:...'
        Returns (miruro_ep_id, anilist_id) or (None, None)
        """
        miruro_ep_id = None
        anilist_id = None

        if "?" in ep_id_str:
            slug_part, query_part = ep_id_str.split("?", 1)
            params = parse_qs(query_part)
            ep_values = params.get("ep", [])
            ep_value = ep_values[0] if ep_values else None

            if ep_value and ":" in ep_value:
                miruro_ep_id = ep_value.split("-")[0]  # strip lang suffix like '-sub'
                if slug_part.strip().isdigit():
                    anilist_id = int(slug_part.strip())
        elif ":" in ep_id_str and not ep_id_str.startswith("http"):
            miruro_ep_id = ep_id_str

        return miruro_ep_id, anilist_id

    async def video(self, ep_id: Union[str, int], language: str = "sub", server: Optional[str] = None) -> Dict[str, Any]:
        """
        Get video streaming data.
        3-tier fallback: Miruro sources → HiAnime → Megaplay
        """
        ep_id_str = str(ep_id)
        miruro_ep_id, anilist_id = self._parse_miruro_ep(ep_id_str)

        # === Source 1: Miruro (if we have a Miruro episode ID) ===
        if miruro_ep_id:
            try:
                provider = "kiwi"  # default
                if anilist_id:
                    try:
                        eps_data = await self.miruro.get_episodes(anilist_id)
                        provider = eps_data.get("provider", "kiwi")
                    except Exception:
                        pass

                result = await self.miruro.get_sources(
                    episode_id=miruro_ep_id,
                    provider=provider,
                    anilist_id=anilist_id,
                    category=language,
                )
                if result and not result.get("error") and result.get("video_link"):
                    logger.info(f"[UnifiedScraper] Video (Miruro): OK for {miruro_ep_id}")
                    result["source_provider"] = "miruro"
                    return result
                else:
                    logger.warning(f"[UnifiedScraper] Video Miruro: no video_link for {miruro_ep_id}")
            except Exception as e:
                logger.warning(f"[UnifiedScraper] Video Miruro failed: {e}")

        # === Source 2: HiAnime ===
        try:
            result = await self.hianime.video(ep_id_str, language, server)
            if result and result.get("video_link"):
                logger.info(f"[UnifiedScraper] Video (HiAnime): OK for {ep_id_str}")
                result["source_provider"] = "hianime"
                return result
        except Exception as e:
            logger.warning(f"[UnifiedScraper] Video HiAnime failed for {ep_id_str}: {e}")

        # === Source 3: Megaplay fallback ===
        try:
            from .hianime.megaplay_video import get_and_play_m3u8_and_vtt
            from .hianime.video_utils import extract_episode_id

            # Try to find a numeric episode ID for Megaplay
            numeric_ep_id = extract_episode_id(ep_id_str)
            if numeric_ep_id:
                megaplay_result = get_and_play_m3u8_and_vtt(numeric_ep_id, language)
                if megaplay_result and (megaplay_result.get("video_link") or megaplay_result.get("sources")):
                    logger.info(f"[UnifiedScraper] Video (Megaplay): OK for ep_id={numeric_ep_id}")
                    megaplay_result["source_provider"] = "megaplay"
                    return megaplay_result
        except Exception as e:
            logger.warning(f"[UnifiedScraper] Video Megaplay failed: {e}")

        logger.info(f"[UnifiedScraper] Video: all 3 sources failed for {ep_id_str}")
        return {"error": "no_sources", "message": "No video sources available from any provider."}

    # =========================================================================
    # SEARCH
    # =========================================================================
    async def search(self, q: str, page: int = 1, **kwargs) -> Dict[str, Any]:
        """Search anime — Miruro first, HiAnime fallback"""
        try:
            result = await self.miruro.search(q, page, **kwargs)
            if result and result.get("animes"):
                logger.debug(f"[UnifiedScraper] Search (Miruro): {len(result.get('animes', []))} results")
                return result
        except Exception as e:
            logger.warning(f"[UnifiedScraper] Search Miruro failed: {e}")

        try:
            return await self.hianime.search(q, page, **kwargs)
        except Exception as e:
            logger.warning(f"[UnifiedScraper] Search HiAnime failed: {e}")
            return {}

    async def search_suggestions(self, q: str) -> Dict[str, Any]:
        """Get search suggestions — Miruro first, HiAnime fallback"""
        try:
            result = await self.miruro.search_suggestions(q)
            if result and result.get("suggestions"):
                logger.debug(f"[UnifiedScraper] Suggestions (Miruro): {len(result.get('suggestions', []))} results")
                return result
        except Exception as e:
            logger.warning(f"[UnifiedScraper] Suggestions Miruro failed: {e}")

        try:
            return await self.hianime.search_suggestions(q)
        except Exception as e:
            logger.warning(f"[UnifiedScraper] Suggestions HiAnime failed: {e}")
            return {"suggestions": []}

    async def az_list(self, sort_option: str = "all", page: int = 1) -> Dict[str, Any]:
        """Get A-Z anime list"""
        try:
            result = await self.miruro.az_list(sort_option, page)
            if result and result.get("animes"):
                return result
        except Exception:
            pass
        return await self.hianime.az_list(sort_option, page)

    # =========================================================================
    # CATALOG
    # =========================================================================
    async def producer(self, name: str, page: int = 1) -> Dict[str, Any]:
        """Get anime by producer — HiAnime primary (better producer support)"""
        try:
            result = await self.hianime.producer(name, page)
            if result and result.get("animes"):
                return result
        except Exception:
            pass
        try:
            return await self.miruro.producer(name, page)
        except Exception:
            return {}

    async def genre(self, name: str, page: int = 1) -> Dict[str, Any]:
        """Get anime by genre — Miruro first, HiAnime fallback"""
        try:
            result = await self.miruro.genre(name, page)
            if result and result.get("animes"):
                logger.debug(f"[UnifiedScraper] Genre (Miruro, {name}): {len(result.get('animes', []))} results")
                return result
        except Exception as e:
            logger.warning(f"[UnifiedScraper] Genre Miruro failed for {name}: {e}")

        try:
            return await self.hianime.genre(name, page)
        except Exception:
            return {}

    async def category(self, name: str, page: int = 1) -> Dict[str, Any]:
        """Get anime by category — Miruro first, HiAnime fallback"""
        try:
            result = await self.miruro.category(name, page)
            if result and result.get("animes"):
                logger.debug(f"[UnifiedScraper] Category (Miruro, {name}): {len(result.get('animes', []))} results")
                return result
        except Exception as e:
            logger.warning(f"[UnifiedScraper] Category Miruro failed for {name}: {e}")

        try:
            return await self.hianime.category(name, page)
        except Exception:
            return {}

    async def schedule(self, date: str = None) -> Dict[str, Any]:
        """Get anime schedule — Miruro first, HiAnime fallback"""
        try:
            result = await self.miruro.schedule(date)
            if result and (result.get("scheduledAnimes") or result.get("animes")):
                return result
        except Exception:
            pass
        try:
            return await self.hianime.schedule(date)
        except Exception:
            return {}

    async def qtip(self, anime_id: str) -> Dict[str, Any]:
        """Quick tooltip info — HiAnime primary (slug-based)"""
        try:
            return await self.hianime.qtip(anime_id)
        except Exception:
            pass
        if str(anime_id).isdigit():
            try:
                return await self.miruro.qtip(anime_id)
            except Exception:
                pass
        return {}

    async def anime_about(self, anime_id: str) -> Dict[str, Any]:
        """Detailed anime about — HiAnime primary (slug-based)"""
        try:
            result = await self.hianime.anime_about(anime_id)
            if result:
                return result
        except Exception:
            pass
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
        """Get next episode schedule — try HiAnime first (slug), then Miruro"""
        try:
            result = await self.hianime.next_episode_schedule(anime_id)
            if result and result.get("airingTimestamp"):
                return result
        except Exception:
            pass
        
        # Try Miruro with AniList ID
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
    async def raw(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Fetch arbitrary endpoint — HiAnime"""
        return await self.hianime.raw(endpoint, params)
