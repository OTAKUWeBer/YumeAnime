"""
Unified scraper - uses the Miruro Native API.
"""

import logging
from typing import Optional, Dict, Any, Union
from urllib.parse import parse_qs

from .miruro import MiruroScraper
# from .animex import AnimexScraper
# from .kuudere import KuudereScraper


logger = logging.getLogger(__name__)


class UnifiedScraper:
    """
    Unified scraper using the Miruro Native API.
    """

    def __init__(self):
        self.miruro = MiruroScraper()
        # self.animex = AnimexScraper()
        # self.kuudere = KuudereScraper()

        logger.info("[UnifiedScraper] Initialized with Miruro + AnimeX + Kuudere")


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

        # Fallback: Miruro search API is dead (returns 500), so we disable the search fallback
        # and just return empty if the ID wasn't numeric or if the info fetch failed.
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

        # Fallback removed since miruro.search is dead.
        return {
            "anime_id": anime_id,
            "title": "",
            "total_sub_episodes": 0,
            "total_dub_episodes": 0,
            "episodes": [],
            "total_episodes": 0,
        }

    async def episodes(self, anime_id: str, anime_slug: str = None) -> Dict[str, Any]:
        """Get episodes list — Miruro for numeric IDs, optionally with anime_slug for anidap discovery"""
        print(f"[UnifiedScraper] episodes() called with: {anime_id}, slug: {anime_slug}")

        if str(anime_id).isdigit():
            try:
                result = await self.miruro.episodes(anime_id, anime_slug)
                if result and result.get("episodes"):
                    return result
            except Exception:
                pass

        # Fallback removed since search API is dead.
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

        ep_id_str = str(ep_id)
        miruro_ep_id, parsed_anilist_id = self._parse_miruro_ep(ep_id_str)

        if parsed_anilist_id:
            anilist_id = parsed_anilist_id


        # Detect AnimeX-routed episodes by the `watch/ax/...` slug pattern.
        import re
        is_ax = "/ax/" in f"/{ep_id_str}/"

        if is_ax:
            ax_anilist_id = anilist_id
            ax_server_id = None
            ax_ep_num = None

            m = re.search(r"/ax/(\d+)/(sub|dub)/([^/]+)$", f"/{ep_id_str}")
            if m:
                try:
                    ax_anilist_id = int(m.group(1))
                except ValueError:
                    pass
                language = m.group(2) or language
                tail = m.group(3)
                # tail is "<server_id>-<ep_num>" (server id may itself contain
                # dashes; episode number is the trailing numeric chunk).
                num_match = re.search(r"(\d+(?:\.\d+)?)\s*$", tail)
                if num_match:
                    try:
                        raw_num = float(num_match.group(1))
                        ax_ep_num = int(raw_num) if raw_num.is_integer() else raw_num
                    except ValueError:
                        ax_ep_num = None
                    ax_server_id = tail[: num_match.start()].rstrip("-") or None

            # If the explicit `server` param looks like an AnimeX sub-server, prefer it.
            if server and server not in ("kiwi", "jet", "arc", "zoro", "bee", "wco"):
                ax_server_id = ax_server_id or server

            if not ax_anilist_id or ax_ep_num is None:
                return {
                    "error": "no_sources",
                    "message": "AnimeX: missing anilist_id or episode number.",
                }

            try:
                result = await self.animex.get_sources(
                    ax_anilist_id, ax_ep_num, language, preferred_server=ax_server_id
                )
                if result and not result.get("error"):
                    logger.info(
                        f"[UnifiedScraper] Video (AnimeX): OK anilist_id={ax_anilist_id} "
                        f"ep={ax_ep_num} server={ax_server_id}"
                    )
                    result["source_provider"] = ax_server_id or result.get("source_provider")
                    return result
                logger.warning(
                    f"[UnifiedScraper] AnimeX returned no sources for anilist_id={ax_anilist_id} "
                    f"ep={ax_ep_num} server={ax_server_id}: "
                    f"{result.get('message') if isinstance(result, dict) else result}"
                )
            except Exception as e:
                logger.warning(f"[UnifiedScraper] AnimeX video failed: {e}")
            return {
                "error": "no_sources",
                "message": "AnimeX has no playable streams for this episode.",
            }

        # ── Kuudere-routed episodes: watch/KUUDERE/{anilist_id}/{category}/{slug} ──
        is_kuudere = "/KUUDERE/" in f"/{ep_id_str}/"

        if is_kuudere:
            kd_anilist_id = anilist_id
            kd_ep_num = None

            m = re.search(r"/KUUDERE/(\d+)/(sub|dub)/([^/]+)$", f"/{ep_id_str}")
            if m:
                try:
                    kd_anilist_id = int(m.group(1))
                except ValueError:
                    pass
                language = m.group(2) or language
                tail = m.group(3)
                # slug is "kuudere-{ep_num}"
                num_match = re.search(r"(\d+(?:\.\d+)?)\s*$", tail)
                if num_match:
                    try:
                        raw_num = float(num_match.group(1))
                        kd_ep_num = int(raw_num) if raw_num.is_integer() else raw_num
                    except ValueError:
                        kd_ep_num = None

            if not kd_anilist_id or kd_ep_num is None:
                return {
                    "error": "no_sources",
                    "message": "Kuudere: missing anilist_id or episode number.",
                }

            # Resolve kuudere anime ID from Miruro episodes API
            kuudere_id = self.kuudere.get_cached_id(kd_anilist_id)
            if not kuudere_id:
                try:
                    ep_resp = await self.miruro.client._get(f"episodes/{kd_anilist_id}")
                    if ep_resp:
                        kd_provider = (ep_resp.get("providers") or {}).get("KUUDERE", {})
                        pids = kd_provider.get("provider_id", [])
                        if isinstance(pids, list) and pids:
                            kuudere_id = pids[0]
                        elif isinstance(pids, str) and pids:
                            kuudere_id = pids
                    if kuudere_id:
                        self.kuudere.cache_kuudere_id(kd_anilist_id, kuudere_id)
                except Exception as e:
                    logger.warning(f"[UnifiedScraper] Failed to resolve Kuudere ID: {e}")

            if not kuudere_id:
                return {
                    "error": "no_sources",
                    "message": "Could not resolve Kuudere anime ID from Miruro.",
                }

            try:
                result = await self.kuudere.get_sources(
                    kuudere_id, kd_ep_num, language
                )
                if result and not result.get("error"):
                    logger.info(
                        f"[UnifiedScraper] Video (Kuudere): OK anilist_id={kd_anilist_id} "
                        f"ep={kd_ep_num} kuudere_id={kuudere_id}"
                    )
                    return result
                logger.warning(
                    f"[UnifiedScraper] Kuudere returned no sources for ep={kd_ep_num}: "
                    f"{result.get('message') if isinstance(result, dict) else result}"
                )
            except Exception as e:
                logger.warning(f"[UnifiedScraper] Kuudere video failed: {e}")
            return {
                "error": "no_sources",
                "message": "Kuudere has no playable streams for this episode.",
            }

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
