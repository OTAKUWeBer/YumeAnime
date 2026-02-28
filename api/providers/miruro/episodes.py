"""
Episode fetching for Miruro API
Handles episode lists via the /episodes/{anilist_id} endpoint
"""
import logging
from typing import Dict, Any, Optional, List
from .base import MiruroBaseClient

logger = logging.getLogger(__name__)

# Provider preference order (best quality/reliability first)
PROVIDER_PRIORITY = ["kiwi", "arc", "zoro", "bee", "jet", "wco"]


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
        """Normalize episodes from a Miruro provider to HiAnime-compatible format"""
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

    async def get_episodes(self, anilist_id) -> Dict[str, Any]:
        """
        Fetch episodes for an anime via Miruro /episodes/{anilist_id}
        Picks the best provider and normalizes episode data
        """
        resp = await self.client._get(f"episodes/{anilist_id}")
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

    async def episodes(self, anilist_id) -> Dict[str, Any]:
        """Alias that returns just episode list data (HiAnime compat) plus provider maps"""
        result = await self.get_episodes(anilist_id)
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
