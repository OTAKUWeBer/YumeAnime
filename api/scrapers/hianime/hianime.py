"""
Main Hianime scraper - unified interface
Delegates to specialized service modules
"""
import os
import asyncio
from typing import Optional, Dict, Any, Union
from dotenv import load_dotenv

from .base import HianimeBaseClient
from .home import HianimeHomeService
from .anime_info import HianimeAnimeInfoService
from .episodes import HianimeEpisodesService
from .search import HianimeSearchService
from .catalog import HianimeCatalogService
from .video import HianimeVideoService

load_dotenv()


class HianimeScraper:
    """
    Unified async wrapper for the Aniwatch / Hianime API
    Documentation: https://github.com/ghoshRitesh12/aniwatch-api
    """

    api_url = os.getenv("HIANIME_API_URL")

    def __init__(self, base_url: Optional[str] = None, default_headers: Optional[Dict[str, str]] = None):
        """
        Initialize the Hianime scraper
        
        Args:
            base_url: Override default API base URL
            default_headers: Headers sent with every request
        """
        url = base_url.rstrip("/") if base_url else self.api_url
        
        # Initialize base client
        self.client = HianimeBaseClient(url, default_headers)
        
        # Initialize services
        self.home_service = HianimeHomeService(self.client)
        self.anime_info_service = HianimeAnimeInfoService(self.client)
        self.episodes_service = HianimeEpisodesService(self.client)
        self.search_service = HianimeSearchService(self.client)
        self.catalog_service = HianimeCatalogService(self.client)
    
    async def home(self) -> Dict[str, Any]:
        """Get unified home response with all sections"""
        return await self.home_service.home()
    
    def clear_home_cache(self) -> None:
        """Clear the home page cache"""
        self.home_service.clear_home_cache()
    
    async def get_anime_info(self, anime_id: str) -> dict:
        """Fetch detailed anime info"""
        return await self.anime_info_service.get_anime_info(anime_id)
    
    async def get_episodes(self, anime_id: str) -> Dict[str, Any]:
        """Fetch episodes and basic info"""
        return await self.episodes_service.get_episodes(anime_id)
    
    async def episodes(self, anime_id: str) -> Dict[str, Any]:
        """Get episodes list"""
        return await self.episodes_service.episodes(anime_id)
    
    async def episode_servers(self, anime_episode_id: str) -> Dict[str, Any]:
        """Get available servers for an episode"""
        return await self.episodes_service.episode_servers(anime_episode_id)
    
    async def is_dub_available(self, eps_title: str, anime_episode_id: str) -> bool:
        """Check if dub is available"""
        return await self.episodes_service.is_dub_available(eps_title, anime_episode_id)
    
    async def episode_sources(
        self, 
        anime_episode_id: str, 
        server: Optional[str] = None,
        category: str = "sub"
    ) -> Dict[str, Any]:
        """Get episode streaming sources"""
        return await self.episodes_service.episode_sources(anime_episode_id, server, category)
    
    async def next_episode_schedule(self, anime_id: str) -> Dict[str, Any]:
        """Get next episode schedule"""
        return await self.episodes_service.next_episode_schedule(anime_id)
    
    async def search(self, q: str, page: int = 1, **kwargs) -> Dict[str, Any]:
        """Search anime with filters"""
        return await self.search_service.search(q, page, **kwargs)
    
    async def search_suggestions(self, q: str) -> Dict[str, Any]:
        """Get search suggestions"""
        return await self.search_service.search_suggestions(q)
    
    async def az_list(self, sort_option: str = "all", page: int = 1) -> Dict[str, Any]:
        """Get A-Z anime list"""
        return await self.search_service.az_list(sort_option, page)
    
    async def producer(self, name: str, page: int = 1) -> Dict[str, Any]:
        """Get anime by producer"""
        return await self.catalog_service.producer(name, page)
    
    async def genre(self, name: str, page: int = 1) -> Dict[str, Any]:
        """Get anime by genre"""
        return await self.catalog_service.genre(name, page)
    
    async def category(self, name: str, page: int = 1) -> Dict[str, Any]:
        """Get anime by category"""
        return await self.catalog_service.category(name, page)
    
    async def schedule(self, date: str) -> Dict[str, Any]:
        """Get anime schedule"""
        return await self.catalog_service.schedule(date)
    
    async def qtip(self, anime_id: str) -> Dict[str, Any]:
        """Get quick tooltip info"""
        return await self.catalog_service.qtip(anime_id)
    
    async def anime_about(self, anime_id: str) -> Dict[str, Any]:
        """Get detailed anime info"""
        return await self.catalog_service.anime_about(anime_id)
    
    async def video(self, ep_id: Union[str, int], language: str = "sub", server: Optional[str] = None) -> Dict[str, Any]:
        """
        Get video streaming data for an episode

        Args:
            ep_id: Episode ID (string or int)
            language: "sub" or "dub"
            server: Optional specific server name

        Returns:
            Dict containing streaming links, qualities, and metadata
        """
        video_service = HianimeVideoService(self.client)
        return await video_service.get_video(ep_id, language, server)

    
    # Utility method
    async def raw(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Fetch any arbitrary endpoint"""
        resp = await self.client._get(endpoint, params=params)
        return resp
