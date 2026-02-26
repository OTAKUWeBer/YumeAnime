"""
Video source fetching for Miruro API
Handles the /sources endpoint to get streaming URLs
"""
import logging
from typing import Dict, Any, Optional
from .base import MiruroBaseClient
from ..hianime.video_utils import encode_proxy

logger = logging.getLogger(__name__)


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

            if stream_type == "hls" or url.endswith(".m3u8"):
                # Use same proxy encoding as HiAnime
                proxied_url = encode_proxy(url)
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
                proxied_url = encode_proxy(url)
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
