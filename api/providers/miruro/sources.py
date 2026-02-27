"""
Video source fetching for Miruro API
Uses the new /watch/{provider}/{anilistId}/{category}/{slug} endpoint
"""

import logging
import re
from typing import Dict, Any, Optional, List
from .base import MiruroBaseClient
from ..hianime.video_utils import encode_proxy

logger = logging.getLogger(__name__)


class MiruroSourcesService:
    """Service for fetching video streaming sources from Miruro API"""

    def __init__(self, client: MiruroBaseClient):
        self.client = client

    def _parse_episode_id(self, episode_id: str) -> Optional[Dict[str, Any]]:
        """
        Parse episode ID in format 'watch/kiwi/178005/sub/animepahe-1'
        Returns dict with provider, anilist_id, category, slug
        """
        # Format: watch/{provider}/{anilist_id}/{category}/{slug}
        pattern = r"watch/([^/]+)/(\d+)/([^/]+)/(.+)"
        match = re.match(pattern, episode_id)
        if match:
            return {
                "provider": match.group(1),
                "anilist_id": int(match.group(2)),
                "category": match.group(3),
                "slug": match.group(4),
            }
        return None

    async def get_sources(
        self,
        episode_id: str,
        provider: str = "kiwi",
        anilist_id: Optional[int] = None,
        category: str = "sub",
    ) -> Dict[str, Any]:
        """
        Fetch streaming sources from Miruro /watch/{provider}/{anilistId}/{category}/{slug} endpoint.
        Returns ALL quality options for the frontend quality selector.
        """
        # Try to parse the new episode ID format first
        parsed = self._parse_episode_id(episode_id)

        if parsed:
            provider = parsed["provider"]
            anilist_id = parsed["anilist_id"]
            category = parsed["category"]
            slug = parsed["slug"]

            # Use new /watch endpoint
            endpoint = f"watch/{provider}/{anilist_id}/{category}/{slug}"
            resp = await self.client._get(endpoint)
        else:
            # Fallback to old /sources endpoint
            params = {
                "episodeId": episode_id,
                "provider": provider,
                "category": category,
            }
            if anilist_id:
                params["anilistId"] = str(anilist_id)
            resp = await self.client._get("sources", params=params)

        if not resp:
            return {
                "error": "no_sources",
                "message": "Failed to fetch sources from Miruro API",
            }

        raw_streams = resp.get("streams", []) or resp.get("sources", []) or []

        # Handle new API format - subtitles in resp.get("subtitles", [])
        subtitles = resp.get("subtitles", []) or []
        tracks = []
        for sub in subtitles:
            if isinstance(sub, dict):
                track_file = sub.get("file") or sub.get("url") or ""
                if track_file:
                    tracks.append(
                        {
                            "file": encode_proxy(track_file)
                            if track_file.startswith("http")
                            else track_file,
                            "url": encode_proxy(track_file)
                            if track_file.startswith("http")
                            else track_file,
                            "label": sub.get("label", "Unknown"),
                            "kind": "subtitles",
                            "lang": sub.get("label", "Unknown"),
                        }
                    )

        intro = resp.get("intro") or {}
        outro = resp.get("outro") or {}
        download = resp.get("download") or ""

        # Separate HLS and embed streams
        hls_sources = []
        embed_sources = []

        for stream in raw_streams:
            if not isinstance(stream, dict):
                continue
            url = stream.get("url") or ""
            if not url:
                continue
            stream_type = stream.get("type", "").lower()
            quality = stream.get("quality") or "default"
            resolution = stream.get("resolution") or {}

            if stream_type == "hls" or url.endswith(".m3u8"):
                proxied_url = encode_proxy(url)
                hls_sources.append(
                    {
                        "url": proxied_url,
                        "file": proxied_url,
                        "isM3U8": True,
                        "quality": quality,
                        "label": quality,
                        "width": resolution.get("width", 0),
                        "height": resolution.get("height", 0),
                        "codec": stream.get("codec", ""),
                        "fansub": stream.get("fansub", ""),
                        "isActive": stream.get("isActive", False),
                    }
                )
            elif stream_type == "embed":
                embed_sources.append(
                    {
                        "url": url,
                        "quality": quality,
                        "label": f"{quality} (Embed)",
                        "type": "embed",
                    }
                )

        # Sort HLS by quality: 1080p > 720p > 480p > 360p
        def quality_sort_key(s):
            q = s.get("quality", "").lower()
            if "1080" in q:
                return 0
            if "720" in q:
                return 1
            if "480" in q:
                return 2
            if "360" in q:
                return 3
            return 4

        hls_sources.sort(key=quality_sort_key)

        print(
            f"[MiruroSources] hls_sources: {len(hls_sources)}, embed_sources: {len(embed_sources)}"
        )

        # Priority: embed first (default), HLS as fallback/alternative
        # Determine source_type and default source
        source_type = "embed" if embed_sources else ("hls" if hls_sources else None)

        # Default HLS source (highest quality or first active)
        default_hls_source = None
        for s in hls_sources:
            if s.get("isActive"):
                default_hls_source = s
                break
        if not default_hls_source and hls_sources:
            default_hls_source = hls_sources[0]

        result = {
            "sources": hls_sources,
            "tracks": tracks,
            "intro": intro if intro.get("start") is not None else None,
            "outro": outro if outro.get("start") is not None else None,
            "headers": {},
            "provider": provider,
            "download": download,
            "embed_sources": embed_sources,
            "hls_sources": hls_sources,
            "source_type": source_type,
            # Quality info for frontend
            "available_qualities": [s.get("quality") for s in hls_sources],
        }

        # Set video_link based on source_type
        if source_type == "embed" and embed_sources:
            # Embed is default — video_link is the embed URL (for iframe)
            result["video_link"] = embed_sources[0].get("url", "")
            print(
                f"[MiruroSources] video_link (embed): {result['video_link'][:100] if result['video_link'] else 'EMPTY'}"
            )
        elif source_type == "hls" and default_hls_source:
            # HLS fallback — video_link is proxied m3u8
            result["video_link"] = (
                default_hls_source.get("file") or default_hls_source.get("url") or ""
            )
            print(
                f"[MiruroSources] video_link (hls): {result['video_link'][:100] if result['video_link'] else 'EMPTY'}"
            )

        logger.info(
            f"[MiruroSources] episode_id={episode_id}, provider={provider}, "
            f"category={category}, hls={len(hls_sources)}, embeds={len(embed_sources)}, "
            f"source_type={source_type}, qualities={result['available_qualities']}"
        )
        return result
