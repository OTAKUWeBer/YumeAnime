"""
Main Miruro scraper - unified interface
Delegates to specialized service modules for the Miruro Native API
"""
import os
import logging
from typing import Optional, Dict, Any, Union
from dotenv import load_dotenv

from .base import MiruroBaseClient
from .home import MiruroHomeService
from .anime_info import MiruroAnimeInfoService
from .episodes import MiruroEpisodesService
from .search import MiruroSearchService
from .catalog import MiruroCatalogService
from .sources import MiruroSourcesService

load_dotenv()
logger = logging.getLogger(__name__)


class MiruroScraper:
    """
    Unified async wrapper for the Miruro Native API
    API base: https://yumero-api.vercel.app/
    """

    api_url = os.getenv("MIRURO_API_URL", "https://yumero-api.vercel.app/")

    def __init__(self, base_url: Optional[str] = None, default_headers: Optional[Dict[str, str]] = None):
        url = base_url.rstrip("/") if base_url else self.api_url.rstrip("/")

        # Initialize base client
        self.client = MiruroBaseClient(url, default_headers)

        # Initialize services
        self.home_service = MiruroHomeService(self.client)
        self.anime_info_service = MiruroAnimeInfoService(self.client)
        self.episodes_service = MiruroEpisodesService(self.client)
        self.search_service = MiruroSearchService(self.client)
        self.catalog_service = MiruroCatalogService(self.client)
        self.sources_service = MiruroSourcesService(self.client)

    # === Home ===
    async def home(self) -> Dict[str, Any]:
        """Get unified home response with all sections"""
        return await self.home_service.home()

    def clear_home_cache(self) -> None:
        """Clear the home page cache"""
        self.home_service.clear_home_cache()

    # === Anime Info ===
    async def get_anime_info(self, anilist_id) -> dict:
        """Fetch detailed anime info by AniList ID"""
        return await self.anime_info_service.get_anime_info(anilist_id)

    # === Episodes ===
    async def get_episodes(self, anilist_id) -> Dict[str, Any]:
        """Fetch episodes and basic info"""
        return await self.episodes_service.get_episodes(anilist_id)

    async def episodes(self, anilist_id) -> Dict[str, Any]:
        """Get episodes list"""
        return await self.episodes_service.episodes(anilist_id)

    async def is_dub_available(self, anilist_id, episode_id: str = None) -> bool:
        """Check if dub is available"""
        return await self.episodes_service.is_dub_available(anilist_id, episode_id)

    async def next_episode_schedule(self, anilist_id) -> Dict[str, Any]:
        """Get next episode schedule"""
        return await self.episodes_service.next_episode_schedule(anilist_id)

    # === Sources / Video ===
    async def get_sources(
        self,
        episode_id: str,
        provider: str = "kiwi",
        anilist_id: Optional[int] = None,
        category: str = "sub",
    ) -> Dict[str, Any]:
        """Get streaming sources for an episode"""
        return await self.sources_service.get_sources(episode_id, provider, anilist_id, category)

    async def video(self, ep_id: Union[str, int], language: str = "sub", server: Optional[str] = None) -> Dict[str, Any]:
        """
        Get video streaming data — Miruro flow:
        This requires episode_id from the episodes() call, not the HiAnime ep param.
        The ep_id here is expected to be the Miruro episode ID (e.g. "animekai:9r5k:...")
        """
        # The unified scraper will handle mapping, but if called directly
        # we attempt to use the ep_id as-is
        return await self.sources_service.get_sources(
            episode_id=str(ep_id),
            provider=server or "kiwi",
            category=language,
        )

    # === Search ===
    async def search(self, q: str, page: int = 1, **kwargs) -> Dict[str, Any]:
        """Search anime with filters"""
        return await self.search_service.search(q, page, **kwargs)

    async def search_suggestions(self, q: str) -> Dict[str, Any]:
        """Get search suggestions"""
        return await self.search_service.search_suggestions(q)

    async def az_list(self, sort_option: str = "all", page: int = 1) -> Dict[str, Any]:
        """Get A-Z anime list"""
        return await self.search_service.az_list(sort_option, page)

    # === Catalog ===
    async def producer(self, name: str, page: int = 1) -> Dict[str, Any]:
        """Get anime by producer"""
        return await self.catalog_service.producer(name, page)

    async def genre(self, name: str, page: int = 1) -> Dict[str, Any]:
        """Get anime by genre"""
        return await self.catalog_service.genre(name, page)

    async def category(self, name: str, page: int = 1) -> Dict[str, Any]:
        """Get anime by category"""
        return await self.catalog_service.category(name, page)

    async def schedule(self, date: str = None) -> Dict[str, Any]:
        """Get anime schedule"""
        return await self.catalog_service.schedule(date)

    async def qtip(self, anime_id: str) -> Dict[str, Any]:
        """Get quick tooltip info"""
        return await self.catalog_service.qtip(anime_id)

    async def anime_about(self, anime_id: str) -> Dict[str, Any]:
        """Get detailed anime info"""
        return await self.catalog_service.anime_about(anime_id)

    # === Utility ===
    async def raw(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Fetch any arbitrary endpoint"""
        resp = await self.client._get(endpoint, params=params)
        return resp
