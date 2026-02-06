"""
Episode fetching and management
Handles episode lists and episode server information
"""
from typing import Dict, Any, Optional
from .base import HianimeBaseClient
from .anime_info import HianimeAnimeInfoService


class HianimeEpisodesService:
    """Service for fetching episode information"""
    
    def __init__(self, client: HianimeBaseClient):
        self.client = client
    
    async def get_episodes(self, anime_id: str) -> Dict[str, Any]:
        """Fetch episodes and basic info for a given anime ID"""
        resp = await self.client._get(f"/anime/{anime_id}/episodes")

        info_service = HianimeAnimeInfoService(self.client)
        anime_info = await info_service.get_anime_info(anime_id)

        if resp.get("status") == 200 and resp.get("data"):
            data = resp["data"]
            episodes_list = data.get("episodes", [])
            return {
                "anime_id": anime_id,
                "title": data.get("title", ""),
                "total_sub_episodes": data.get("totalEpisodes", 0),
                "total_dub_episodes": anime_info.get("total_dub_episodes", 0),
                "episodes": episodes_list,
                "total_episodes": len(episodes_list)
            }

        return {
            "anime_id": anime_id,
            "title": "",
            "total_sub_episodes": 0,
            "total_dub_episodes": 0,
            "episodes": [],
            "total_episodes": 0
        }
    
    async def episodes(self, anime_id: str) -> Dict[str, Any]:
        """Alias for get_episodes for backward compatibility"""
        resp = await self.client._get(f"anime/{anime_id}/episodes")
        return resp.get("data") if resp else {}
    
    async def episode_servers(self, anime_episode_id: str) -> Dict[str, Any]:
        """
        Get available servers for an episode
        e.g. anime_episode_id = "steinsgate-0-92?ep=2055"
        """
        resp = await self.client._get("episode/servers", params={"animeEpisodeId": anime_episode_id})
        return resp.get("data") if resp else {}
    
    async def is_dub_available(self, eps_title: str, anime_episode_id: str) -> bool:
        """Check if dub servers are available for the given episode"""
        full_id = f"{eps_title}?ep={anime_episode_id}"
        servers = await self.episode_servers(full_id)
        dub_servers = servers.get("dub", [])
        return bool(dub_servers)
    
    async def episode_sources(
        self, 
        anime_episode_id: str, 
        server: Optional[str] = None,
        category: str = "sub"
    ) -> Dict[str, Any]:
        """
        Get HLS sources, subtitles and headers for an episode
        category: sub|dub|raw
        """
        params = {"animeEpisodeId": anime_episode_id, "category": category}
        if server:
            params["server"] = server
        resp = await self.client._get("episode/sources", params=params)
        return resp.get("data") if resp else {}
    
    async def next_episode_schedule(self, anime_id: str) -> Dict[str, Any]:
        """Get next episode schedule for an anime"""
        resp = await self.client._get(f"anime/{anime_id}/next-episode-schedule")
        return resp.get("data") if resp else {}
