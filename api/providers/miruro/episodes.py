"""
Episode fetching for Miruro API
Handles episode lists via the /episodes/{anilist_id} endpoint
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from .base import MiruroBaseClient
from ..animex import AnimexScraper
from ..kuudere import KuudereScraper

# Module-level singletons so caches survive across calls.
_animex_scraper: Optional[AnimexScraper] = None
_kuudere_scraper: Optional[KuudereScraper] = None


def _get_animex() -> AnimexScraper:
    global _animex_scraper
    if _animex_scraper is None:
        _animex_scraper = AnimexScraper()
    return _animex_scraper


def _get_kuudere() -> KuudereScraper:
    global _kuudere_scraper
    if _kuudere_scraper is None:
        _kuudere_scraper = KuudereScraper()
    return _kuudere_scraper


logger = logging.getLogger(__name__)

# Provider preference order (best quality/reliability first)
# Standard Miruro providers first, then anidap providers
PROVIDER_PRIORITY = [
    # Standard Miruro providers (best quality/reliability)
    "jet", "arc", "kiwi", "zoro", "bee", "wco", "KUUDERE",
    
    # Anidap / AnimeX shared HLS provider names
    "miru", "mochi", "nuri", "yuki", "kami", "wave", "shiro", "koto", "pahe", "maze",
    "gogo", "vee", "hop", "dune",
    # AnimeX-only sub-servers
    "uwu", "mimi", "zaza",
]


class MiruroEpisodesService:
    """Service for fetching episode information from Miruro API"""

    def __init__(self, client: MiruroBaseClient):
        self.client = client

    def _pick_best_provider(self, providers: Dict[str, Any]) -> Optional[str]:
        """Pick the best available provider based on priority"""
        if not providers:
            return None
        for name in PROVIDER_PRIORITY:
            if name in providers and providers[name]:
                provider_data = providers[name]
                # Check it has episodes
                if isinstance(provider_data, dict):
                    if provider_data.get("episodes") or provider_data.get("meta"):
                        return name
        # Fallback: first provider with data
        for name, data in providers.items():
            if isinstance(data, dict) and (data.get("episodes") or data.get("meta")):
                return name
        return None

    def _normalize_episodes(
        self, provider_data: Dict[str, Any], provider_name: str, anilist_id
    ) -> Dict[str, Any]:
        """Normalize episodes from a Miruro provider to standard format"""
        episodes_data = provider_data.get("episodes", {})
        
        sub_episodes = episodes_data.get("sub", []) or []
        dub_episodes = episodes_data.get("dub", []) or []

        # Build unified episode list from sub episodes
        episodes = []
        for ep in sub_episodes:
            episodes.append({
                "episodeId": ep.get("id", ""),
                "number": ep.get("number", 0),
                "title": ep.get("title") or f"Episode {ep.get('number', '?')}",
                "isFiller": ep.get("filler", False),
                "description": ep.get("description") or "",
                "image": ep.get("image") or "",
                "airDate": ep.get("airDate") or "",
            })

        # Deduplicate by episode number — keep first occurrence (API sometimes
        # returns the same episode number twice with different IDs or orderings).
        seen_numbers: set = set()
        unique_episodes = []
        for ep in episodes:
            num = ep["number"]
            if num in seen_numbers:
                logger.debug(
                    f"[MiruroEpisodes] Skipping duplicate episode {num} "
                    f"(provider={provider_name}, anilist_id={anilist_id})"
                )
                continue
            seen_numbers.add(num)
            unique_episodes.append(ep)
        episodes = unique_episodes

        # Build a dub episode ID map for quick lookup
        dub_episode_ids = {}
        for ep in dub_episodes:
            dub_episode_ids[ep.get("number")] = ep.get("id", "")

        return {
            "anime_id": str(anilist_id),
            "title": (provider_data.get("meta", {}) or {}).get("title", ""),
            "total_sub_episodes": len(sub_episodes),
            "total_dub_episodes": len(dub_episodes),
            "episodes": episodes,
            "total_episodes": len(episodes),
            "provider": provider_name,
            "dub_episode_ids": dub_episode_ids,
        }

    async def get_episodes(self, anilist_id, anime_slug: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetch episodes for an anime via Miruro /episodes/{anilist_id}
        Picks the best provider and normalizes episode data
        
        Args:
            anilist_id: AniList anime ID
            anime_slug: Optional anime slug for anidap provider discovery
        """
        params = {}
        if anime_slug:
            params["anime_slug"] = anime_slug
        
        resp = await self.client._get(f"episodes/{anilist_id}", params=params if params else None)
        if not resp:
            return {
                "anime_id": str(anilist_id),
                "title": "",
                "total_sub_episodes": 0,
                "total_dub_episodes": 0,
                "episodes": [],
                "total_episodes": 0,
            }

        providers = resp.get("providers", {}) or {}
        mappings = resp.get("mappings", {}) or {}



        # Inject AnimeX sub-servers as additional providers (independent HLS source).
        # Each AnimeX sub-server (uwu, mochi, kami, ...) appears as its own pill,
        # but we skip any name Miruro already owns to avoid clobbering it.
        try:
            anime_title = ""
            for _p in providers.values():
                if isinstance(_p, dict):
                    anime_title = (_p.get("meta", {}) or {}).get("title", "") or ""
                    if anime_title:
                        break
            ax_blocks = await _get_animex().build_provider_blocks(anilist_id, anime_title)
            added = []
            for srv_id, block in ax_blocks.items():
                if srv_id in providers:
                    # Miruro already exposes this server name — leave it alone.
                    continue
                if not block.get("episodes", {}).get("sub") and not block.get("episodes", {}).get("dub"):
                    continue
                providers[srv_id] = block
                added.append(srv_id)
            if added:
                logger.info(f"[MiruroEpisodes] Injected AnimeX servers: {added}")
        except Exception as e:
            logger.warning(f"[MiruroEpisodes] AnimeX injection failed for {anilist_id}: {e}")

        # Inject Kuudere episodes if KUUDERE provider is present but has no episodes.
        # Miruro returns KUUDERE with only provider_id — we fetch actual episodes from kuudere.to.
        try:
            kd_provider = mappings.get("providers", {}).get("KUUDERE", {})
            kd_pids = kd_provider.get("provider_id", []) if isinstance(kd_provider, dict) else []
            
            # Check if KUUDERE is already in the main providers dict with valid episodes
            kd_existing = providers.get("KUUDERE", {})
            kd_has_episodes = (
                isinstance(kd_existing, dict)
                and isinstance(kd_existing.get("episodes"), dict)
                and (kd_existing["episodes"].get("sub") or kd_existing["episodes"].get("dub"))
            )
            
            if kd_pids and not kd_has_episodes:
                kuudere_id = kd_pids[0] if isinstance(kd_pids, list) else kd_pids
                anime_title = ""
                for _p in providers.values():
                    if isinstance(_p, dict):
                        anime_title = (_p.get("meta", {}) or {}).get("title", "") or ""
                        if anime_title:
                            break
                kd_block = await _get_kuudere().build_provider_block(
                    kuudere_id, anilist_id, anime_title
                )
                if kd_block:
                    providers["KUUDERE"] = kd_block
                    logger.info(f"[MiruroEpisodes] Injected Kuudere episodes for {anilist_id}")
        except Exception as e:
            logger.warning(f"[MiruroEpisodes] Kuudere injection failed for {anilist_id}: {e}")


        best_provider = self._pick_best_provider(providers)

        if not best_provider:
            logger.warning(f"[MiruroEpisodes] No valid provider found for {anilist_id}")
            return {
                "anime_id": str(anilist_id),
                "title": "",
                "total_sub_episodes": 0,
                "total_dub_episodes": 0,
                "episodes": [],
                "total_episodes": 0,
            }

        provider_data = providers[best_provider]
        result = self._normalize_episodes(provider_data, best_provider, anilist_id)

        # Also store mappings for source fetching
        mappings = resp.get("mappings", {}) or {}
        result["mappings"] = mappings
        result["all_providers"] = list(providers.keys())
        result["providers_map"] = providers
        result["default_provider"] = best_provider

        logger.info(
            f"[MiruroEpisodes] anilist_id={anilist_id}, provider={best_provider}, "
            f"sub={result['total_sub_episodes']}, dub={result['total_dub_episodes']}"
        )
        return result

    async def episodes(self, anilist_id, anime_slug: Optional[str] = None) -> Dict[str, Any]:
        """Alias that returns just episode list data (standard compat) plus provider maps"""
        result = await self.get_episodes(anilist_id, anime_slug)
        return {
            "episodes": result.get("episodes", []),
            "totalEpisodes": result.get("total_episodes", 0),
            "providers_map": result.get("providers_map", {}),
            "default_provider": result.get("default_provider", "kiwi"),
        }

    async def is_dub_available(self, anilist_id, episode_id: str = None) -> bool:
        """Check if dub is available for an anime"""
        result = await self.get_episodes(anilist_id)
        return result.get("total_dub_episodes", 0) > 0

    async def next_episode_schedule(self, anilist_id) -> Dict[str, Any]:
        """Get next episode schedule — delegates to anime_info"""
        from .anime_info import MiruroAnimeInfoService
        info_service = MiruroAnimeInfoService(self.client)
        return await info_service.next_episode_schedule(anilist_id)