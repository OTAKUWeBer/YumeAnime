"""
Base HTTP client for Hianime API requests
Handles retries, timeouts, and error handling
"""
import aiohttp
import asyncio
from typing import Optional, Dict, Any, Union


class HianimeBaseClient:
    """Base HTTP client with retry logic and error handling"""
    
    def __init__(self, base_url: str, default_headers: Optional[Dict[str, str]] = None):
        self.base_url = base_url.rstrip("/")
        self.default_headers = default_headers or {}
    
    async def _get(
        self, 
        endpoint: str, 
        params: Optional[Dict[str, Union[str, int]]] = None,
        headers: Optional[Dict[str, str]] = None, 
        raise_for_status: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Make GET request with retry logic
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            headers: Additional headers
            raise_for_status: Whether to raise on HTTP errors
            
        Returns:
            JSON response dict or None on failure
        """
        params = params or {}
        headers = {**self.default_headers, **(headers or {})}
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        tries = 3
        backoff = 0.4
        timeout = aiohttp.ClientTimeout(total=8)

        for attempt in range(1, tries + 1):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url, params=params, headers=headers) as resp:
                        text = await resp.text()
                        if resp.status >= 400:
                            raise aiohttp.ClientResponseError(
                                status=resp.status, 
                                request_info=resp.request_info, 
                                history=resp.history
                            )
                        try:
                            return await resp.json()
                        except Exception:
                            raise
            except Exception as exc:
                if attempt == tries:
                    return None
                await asyncio.sleep(backoff * attempt)
        return None
