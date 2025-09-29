"""
Catalog browsing functionality
Handles genre, producer, category, and schedule queries
"""
from typing import Dict, Any
from .base import HianimeBaseClient


class HianimeCatalogService:
    """Service for browsing anime catalogs"""
    
    def __init__(self, client: HianimeBaseClient):
        self.client = client
    
    async def producer(self, name: str, page: int = 1) -> Dict[str, Any]:
        """Get anime by producer"""
        resp = await self.client._get(f"producer/{name}", params={"page": page})
        return resp.get("data") if resp else {}
    
    async def genre(self, name: str, page: int = 1) -> Dict[str, Any]:
        """Get anime by genre"""
        resp = await self.client._get(f"genre/{name}", params={"page": page})
        return resp.get("data") if resp else {}
    
    async def category(self, name: str, page: int = 1) -> Dict[str, Any]:
        """Get anime by category"""
        resp = await self.client._get(f"category/{name}", params={"page": page})
        return resp.get("data") if resp else {}
    
    async def schedule(self, date: str) -> Dict[str, Any]:
        """
        Get anime schedule for a date
        date format: 'YYYY-MM-DD' (must include year)
        """
        resp = await self.client._get("schedule", params={"date": date})
        return resp.get("data") if resp else {}
    
    async def qtip(self, anime_id: str) -> Dict[str, Any]:
        """Get quick tooltip info for an anime"""
        resp = await self.client._get(f"qtip/{anime_id}")
        return resp.get("data") if resp else {}
    
    async def anime_about(self, anime_id: str) -> Dict[str, Any]:
        """Get detailed about/info for an anime"""
        resp = await self.client._get(f"anime/{anime_id}")
        return resp.get("data") if resp else {}
