"""
Search functionality for anime
Handles search queries, suggestions, and filters
"""
from typing import Dict, Any, Optional
from .base import HianimeBaseClient


class HianimeSearchService:
    """Service for anime search operations"""
    
    def __init__(self, client: HianimeBaseClient):
        self.client = client
    
    async def search(
        self, 
        q: str, 
        page: int = 1, 
        *,
        genres: Optional[str] = None,
        type_: Optional[str] = None,
        sort: Optional[str] = None,
        season: Optional[str] = None,
        language: Optional[str] = None,
        status: Optional[str] = None,
        rating: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        score: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search anime with advanced filters
        Provide advanced params as keyword args
        """
        params = {"q": q, "page": page}
        if genres:
            params["genres"] = genres
        if type_:
            params["type"] = type_
        if sort:
            params["sort"] = sort
        if season:
            params["season"] = season
        if language:
            params["language"] = language
        if status:
            params["status"] = status
        if rating:
            params["rating"] = rating
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if score:
            params["score"] = score

        resp = await self.client._get("search", params=params)
        return resp.get("data") if resp else {}
    
    async def search_suggestions(self, q: str) -> Dict[str, Any]:
        """Get search suggestions for a query"""
        resp = await self.client._get("search/suggestion", params={"q": q})
        return resp.get("data") if resp else {}
    
    async def az_list(self, sort_option: str = "all", page: int = 1) -> Dict[str, Any]:
        """Get A-Z list of anime"""
        endpoint = f"azlist/{sort_option}"
        resp = await self.client._get(endpoint, params={"page": page})
        return resp.get("data") if resp else {}
