"""
Video source fetching for Miruro API
Uses the new /watch/{provider}/{anilistId}/{category}/{slug} endpoint
"""

import logging
import re
from typing import Dict, Any, Optional, List
from .base import MiruroBaseClient
from ..video_utils import encode_proxy, encode_kiwi_proxy

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
        For the 'zoro' provider, constructs a megaplay.buzz embed URL directly.
        """
        parsed = self._parse_episode_id(episode_id)

        if parsed:
            provider = parsed["provider"]
            anilist_id = parsed["anilist_id"]
            category = parsed["category"]
            slug = parsed["slug"]

            # --- Zoro provider: direct megaplay.buzz embed ---
            if provider == "zoro":
                ep_num_match = re.search(r"(\d+)$", slug)
                ep_number = int(ep_num_match.group(1)) if ep_num_match else None

                embed_ep_id = None
                if ep_number is not None and anilist_id:
                    try:
                        episodes_resp = await self.client._get(f"episodes/{anilist_id}")
                        if episodes_resp:
                            zoro_data = episodes_resp.get("providers", {}).get("zoro", {})
                            zoro_eps = zoro_data.get("episodes", {}).get(category, []) or []
                            for ep in zoro_eps:
                                try:
                                    api_num = float(ep.get("number", -1))
                                    target_num = float(ep_number)
                                except (TypeError, ValueError):
                                    api_num, target_num = -1, -2

                                if api_num == target_num:
                                    ep_url = ep.get("url", "")
                                    if "?ep=" in ep_url:
                                        embed_ep_id = ep_url.split("?ep=")[1]
                                    break
                    except Exception as e:
                        logger.warning(f"[MiruroSources] Failed to fetch zoro ep ID: {e}")

                if not embed_ep_id:
                    logger.warning(
                        f"[MiruroSources] Could not resolve zoro ep ID for slug={slug}, ep_number={ep_number}"
                    )
                    return {
                        "error": "no_sources",
                        "message": "Could not resolve zoro episode ID for embed",
                    }

                embed_url = f"https://megaplay.buzz/stream/s-2/{embed_ep_id}/{category}"
                logger.info(f"[MiruroSources] Zoro embed: {embed_url}")
                embed_sources = [
                    {
                        "url": embed_url,
                        "quality": "default",
                        "label": "Megaplay (Embed)",
                        "type": "embed",
                    }
                ]
                return {
                    "sources": [],
                    "tracks": [],
                    "intro": None,
                    "outro": None,
                    "headers": {},
                    "provider": "zoro",
                    "download": "",
                    "embed_sources": embed_sources,
                    "hls_sources": [],
                    "source_type": "embed",
                    "available_qualities": [],
                    "video_link": embed_url,
                }

            # Use new /watch endpoint for other providers
            endpoint = f"watch/{provider}/{anilist_id}/{category}/{slug}"
            resp = await self.client._get(endpoint)
        else:
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

        # Handle subtitles — always use the default proxy (not kiwi proxy)
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

            # Megaplay domain mapping fix
            if "megaup.nl" in url:
                url = url.replace("megaup.nl", "megaplay.buzz")

            stream_type = stream.get("type", "").lower()
            quality = stream.get("quality") or "default"
            resolution = stream.get("resolution") or {}

            # Extract referer from stream if available
            referer = stream.get("referer")
            headers = {"referer": referer} if referer else None

            if stream_type == "hls" or url.endswith(".m3u8"):
                # ── Kiwi provider: use dedicated kiwi proxy ──────────────────
                if provider == "kiwi":
                    kiwi_referer = (headers or {}).get("referer", "https://kwik.cx/")
                    proxied_url = encode_kiwi_proxy(url, referer=kiwi_referer)
                else:
                    proxied_url = encode_proxy(url, headers)

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

        # Filter sources: only show streams > 700p
        hls_sources = [
            s for s in hls_sources
            if s.get("height", 0) > 700 or (
                s.get("height", 0) == 0
                and "480" not in s.get("quality", "").lower()
                and "360" not in s.get("quality", "").lower()
            )
        ]

        embed_sources = [
            s for s in embed_sources
            if not any(low_res in s.get("quality", "").lower() for low_res in ["480", "360", "240", "144"])
        ]

        def quality_sort_key(s):
            q = s.get("quality", "").lower()
            if "1080" in q:
                return 0
            if "720" in q:
                return 1
            return 4

        hls_sources.sort(key=quality_sort_key)

        print(
            f"[MiruroSources] hls_sources: {len(hls_sources)}, embed_sources: {len(embed_sources)}"
        )

        source_type = "embed" if embed_sources else ("hls" if hls_sources else None)

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
            "available_qualities": [s.get("quality") for s in hls_sources],
        }

        if source_type == "embed" and embed_sources:
            result["video_link"] = embed_sources[0].get("url", "")
            print(
                f"[MiruroSources] video_link (embed): {result['video_link'][:100] if result['video_link'] else 'EMPTY'}"
            )
        elif source_type == "hls" and default_hls_source:
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