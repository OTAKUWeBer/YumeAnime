"""
Video source fetching for Miruro API
Uses the new /watch/{provider}/{anilistId}/{category}/{slug} endpoint
"""

import logging
import re
from typing import Any, Dict, Optional, List

from .base import MiruroBaseClient
from ..video_utils import encode_proxy, encode_kiwi_proxy, encode_payload, WORKER_BASE

logger = logging.getLogger(__name__)

# Providers that must use the kiwi worker (/p/ Base64 route)
_WORKER_PROVIDERS = {
    "kiwi",
    "animex",
    "ax",
    "ax-uwu",
    "ax-mochi",
    "ax-wave",
    "ax-zaza",
    "ax-yuki",
    "ax-zen",
    "uwu",
    "mochi",
    "wave",
    "zaza",
    "yuki",
    "zen",
}

# Providers that must always use cdn-eu (never kiwi worker)
_CDN_ONLY_PROVIDERS = {
    "arc",
    "jet",
    "zoro",
    "miruro",
}


def _normalize_provider(provider: Optional[str]) -> str:
    return (provider or "").strip().lower()


def _is_already_proxied(url: str) -> bool:
    if not url:
        return False
    return url.startswith(WORKER_BASE + "/p/") or "cdn-eu.1ani.me/proxy/m3u8" in url


def _route_stream_proxy(
    url: str,
    provider: Optional[str],
    headers: Optional[Dict[str, str]] = None,
    subtitles: bool = False,
) -> str:
    """
    Route stream URLs to the correct proxy.

    Rules:
      - kiwi / animex / ax-* / AnimeX sub-servers -> kiwi worker (/p/)
      - arc / jet / zoro / miruro -> cdn-eu only
      - subtitles -> cdn-eu only
      - everything else -> cdn-eu only
    """
    if not url or _is_already_proxied(url):
        return url

    provider_norm = _normalize_provider(provider)

    # Subtitles always go through cdn-eu, never kiwi worker
    if subtitles:
        return encode_proxy(url, headers) or url

    # Hard-force CDN for Arc/Miruro-style providers
    if provider_norm in _CDN_ONLY_PROVIDERS:
        return encode_proxy(url, headers) or url

    # Kiwi / AnimeX family -> kiwi worker
    is_worker_provider = (
        provider_norm in _WORKER_PROVIDERS
        or provider_norm.startswith("ax-")
        or provider_norm.startswith("animex")
    )

    if is_worker_provider:
        referer = (headers or {}).get("referer") or (headers or {}).get("Referer") or ""
        if not referer and provider_norm == "kiwi":
            referer = "https://kwik.cx/"
        return encode_payload(url, referer)

    # Default: cdn-eu only
    return encode_proxy(url, headers) or url


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
        provider: Optional[str] = None,
        anilist_id: Optional[int] = None,
        category: str = "sub",
    ) -> Dict[str, Any]:
        """
        Fetch streaming sources from Miruro /watch/{provider}/{anilistId}/{category}/{slug} endpoint.
        Returns all quality options for the frontend quality selector.

        Routing rules:
          - kiwi / AnimeX -> kiwi worker
          - arc / jet / zoro / miruro -> cdn-eu only
          - subtitles -> cdn-eu only
        """
        parsed = self._parse_episode_id(episode_id)

        if parsed:
            # Use requested provider if it's not set or is default kiwi, otherwise use provider from ID
            if not provider or provider == "kiwi":
                provider = parsed["provider"]

            anilist_id = parsed["anilist_id"]
            category = parsed["category"]
            slug = parsed["slug"]

            # --- Zoro provider: direct megaplay.buzz embed ---
            if _normalize_provider(provider) == "zoro":
                ep_number = None
                if slug:
                    ep_num_match = re.search(r"(\d+)$", slug)
                    ep_number = int(ep_num_match.group(1)) if ep_num_match else None
                
                # If no slug, try extracting from the end of episode_id if it's numeric
                if ep_number is None and str(episode_id).isdigit():
                    ep_number = int(episode_id)
                
                # If still no ep_number but it's in the watch/ format
                if ep_number is None and parsed:
                    ep_num_match = re.search(r"(\d+)$", parsed["slug"])
                    ep_number = int(ep_num_match.group(1)) if ep_num_match else None
                
                embed_url = None
                
                # Method 1: Use AniList ID + Episode Number (Documented primary method)
                if anilist_id and ep_number is not None:
                    # language must be 'sub' or 'dub'
                    lang = category.lower() if category.lower() in ["sub", "dub"] else "sub"
                    embed_url = f"https://megaplay.buzz/stream/ani/{anilist_id}/{ep_number}/{lang}"
                    logger.info(f"[MiruroSources] Megaplay (AniList) embed: {embed_url}")

                # Method 2: Fallback to internal episode ID resolution if AniList fails
                if not embed_url and ep_number is not None and anilist_id:
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
                                        embed_url = f"https://megaplay.buzz/stream/s-2/{embed_ep_id}/{category}"
                                        break
                    except Exception as e:
                        logger.warning(f"[MiruroSources] Failed to fetch zoro ep ID fallback: {e}")

                if not embed_url:
                    logger.warning(
                        f"[MiruroSources] Could not resolve Megaplay embed for slug={slug}, ep_number={ep_number}"
                    )
                    return {
                        "error": "no_sources",
                        "message": "Could not resolve Megaplay (Zoro) embed",
                    }
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
            if not provider:
                provider = "kiwi"
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

        raw_streams = (
            resp.get("streams", [])
            or resp.get("sources", [])
            or resp.get("ssub", {}).get("streams", [])
            or resp.get("ddub", {}).get("streams", [])
            or resp.get("sub", {}).get("streams", [])
            or resp.get("dub", {}).get("streams", [])
            or []
        )

        # Subtitles: always use cdn-eu, never kiwi worker
        subtitles = (
            resp.get("subtitles", [])
            or resp.get("ssub", {}).get("subtitles", [])
            or resp.get("ddub", {}).get("subtitles", [])
            or resp.get("sub", {}).get("subtitles", [])
            or resp.get("dub", {}).get("subtitles", [])
            or []
        )
        tracks = []
        for sub in subtitles:
            if isinstance(sub, dict):
                track_file = sub.get("file") or sub.get("url") or ""
                if track_file:
                    proxied_track = _route_stream_proxy(
                        track_file,
                        provider,
                        headers={"referer": sub.get("referer")} if sub.get("referer") else None,
                        subtitles=True,
                    )
                    tracks.append(
                        {
                            "file": proxied_track,
                            "url": proxied_track,
                            "label": sub.get("label", "Unknown"),
                            "kind": "subtitles",
                            "lang": sub.get("label", "Unknown"),
                        }
                    )

        intro = (
            resp.get("intro")
            or resp.get("ssub", {}).get("intro")
            or resp.get("ddub", {}).get("intro")
            or {}
        )
        outro = (
            resp.get("outro")
            or resp.get("ssub", {}).get("outro")
            or resp.get("ddub", {}).get("outro")
            or {}
        )
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

            stream_type = (stream.get("type") or "").lower()
            quality = stream.get("quality") or "default"
            resolution = stream.get("resolution") or {}

            referer = stream.get("referer")
            headers = {"referer": referer} if referer else None

            if stream_type == "hls" or url.endswith(".m3u8"):
                # Provider-aware routing:
                # arc/jet/zoro/miruro -> cdn-eu only
                # kiwi/animex -> kiwi worker
                proxied_url = _route_stream_proxy(url, provider, headers=headers)

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
                        "_provider": provider,
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