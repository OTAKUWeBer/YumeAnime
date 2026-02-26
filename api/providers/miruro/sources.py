"""
Video source fetching for Miruro API
Handles the /sources endpoint to get streaming URLs
"""
import base64
import logging
import os
from typing import Dict, Any, Optional
from .base import MiruroBaseClient

logger = logging.getLogger(__name__)

proxy_url = os.getenv("PROXY_URL", "")
if proxy_url and proxy_url.startswith("http://"):
    proxy_url = proxy_url.replace("http://", "https://", 1)


def encode_proxy_with_referer(url: str, referer: str = "") -> str:
    """Proxy a URL with optional referer header forwarding.
    Format: PROXY_URL + base64(url) + ?referer=base64(referer)
    """
    if not url:
        return url
    try:
        encoded_url = base64.b64encode(url.encode()).decode()
        result = f"{proxy_url}{encoded_url}"
        if referer:
            encoded_referer = base64.b64encode(referer.encode()).decode()
            result = f"{result}?referer={encoded_referer}"
        if result.startswith("http://"):
            result = result.replace("http://", "https://", 1)
        return result
    except Exception:
        return url


class MiruroSourcesService:
    """Service for fetching video streaming sources from Miruro API"""

    def __init__(self, client: MiruroBaseClient):
        self.client = client

    async def get_sources(
        self,
        episode_id: str,
        provider: str = "kiwi",
        anilist_id: Optional[int] = None,
        category: str = "sub",
    ) -> Dict[str, Any]:
        """
        Fetch streaming sources from Miruro /sources endpoint

        Actual API response format:
        {
            "streams": [
                {"url": "...", "type": "hls", "quality": "1080p", "referer": "...", ...},
            ],
            "download": "..."
        }
        """
        params = {
            "episodeId": episode_id,
            "provider": provider,
            "category": category,
        }
        if anilist_id:
            params["anilistId"] = str(anilist_id)

        resp = await self.client._get("sources", params=params)
        if not resp:
            return {"error": "no_sources", "message": "Failed to fetch sources from Miruro API"}

        # Parse: "streams" array (not "sources")
        raw_streams = resp.get("streams", []) or resp.get("sources", []) or []
        intro = resp.get("intro") or {}
        outro = resp.get("outro") or {}

        # Filter HLS streams, skip embed-only
        sources = []
        for stream in raw_streams:
            if not isinstance(stream, dict):
                continue
            url = stream.get("url") or ""
            stream_type = stream.get("type", "").lower()
            referer = stream.get("referer") or ""

            if stream_type == "hls" or url.endswith(".m3u8"):
                # Proxy the URL with referer header
                proxied_url = encode_proxy_with_referer(url, referer)
                sources.append({
                    "url": proxied_url,
                    "file": proxied_url,
                    "isM3U8": True,
                    "quality": stream.get("quality") or "default",
                })

        # If no HLS streams, try embed as fallback
        if not sources:
            for stream in raw_streams:
                if not isinstance(stream, dict):
                    continue
                url = stream.get("url") or ""
                referer = stream.get("referer") or ""
                proxied_url = encode_proxy_with_referer(url, referer)
                sources.append({
                    "url": proxied_url,
                    "file": proxied_url,
                    "isM3U8": ".m3u8" in url,
                    "quality": stream.get("quality") or "default",
                })

        # Sort: highest quality first
        def quality_sort_key(s):
            q = s.get("quality", "").lower()
            if "1080" in q:
                return 0
            if "720" in q:
                return 1
            if "480" in q:
                return 2
            return 3
        sources.sort(key=quality_sort_key)

        result = {
            "sources": sources,
            "tracks": [],  # hardsubs, no VTT
            "intro": intro if intro.get("start") is not None else None,
            "outro": outro if outro.get("start") is not None else None,
            "headers": {},
            "provider": provider,
        }

        # video_link = first (best quality) proxied source
        if sources:
            result["video_link"] = sources[0].get("file") or sources[0].get("url") or ""

        logger.info(
            f"[MiruroSources] episode_id={episode_id}, provider={provider}, "
            f"category={category}, streams={len(raw_streams)}, hls_sources={len(sources)}"
        )
        return result
