"""
Base HTTP client for Miruro Native API requests
Handles retries, timeouts, and error handling
"""
import aiohttp
import asyncio
import logging
from typing import Optional, Dict, Any, Union

logger = logging.getLogger(__name__)


class MiruroBaseClient:
    """Base HTTP client with retry logic for Miruro API"""

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
        backoff = 0.5
        timeout = aiohttp.ClientTimeout(total=12)

        for attempt in range(1, tries + 1):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url, params=params, headers=headers) as resp:
                        if resp.status >= 400:
                            logger.warning(
                                f"[MiruroAPI] {url} returned {resp.status} (attempt {attempt}/{tries})"
                            )
                            if raise_for_status:
                                raise aiohttp.ClientResponseError(
                                    status=resp.status,
                                    request_info=resp.request_info,
                                    history=resp.history
                                )
                            if attempt == tries:
                                return None
                            await asyncio.sleep(backoff * attempt)
                            continue
                        try:
                            return await resp.json()
                        except Exception:
                            text = await resp.text()
                            logger.error(f"[MiruroAPI] Failed to parse JSON from {url}: {text[:200]}")
                            return None
            except asyncio.TimeoutError:
                logger.warning(f"[MiruroAPI] Timeout for {url} (attempt {attempt}/{tries})")
                if attempt == tries:
                    return None
                await asyncio.sleep(backoff * attempt)
            except Exception as exc:
                logger.warning(f"[MiruroAPI] Error for {url}: {exc} (attempt {attempt}/{tries})")
                if attempt == tries:
                    return None
                await asyncio.sleep(backoff * attempt)
        return None
