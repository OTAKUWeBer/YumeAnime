"""
Kuudere provider - fetches embed streaming sources from kuudere.to
Maps AniList ID -> Kuudere ID (via Miruro) -> kuudere.to API for episode embed links.
"""

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)

KUUDERE_API = "https://kuudere.to/api"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://kuudere.to/",
}


class KuudereScraper:
    """Async scraper for the Kuudere API (kuudere.to)."""

    # def __init__(self, timeout: int = 15):
    #     self._timeout = aiohttp.ClientTimeout(total=timeout)
    #     self._session: Optional[aiohttp.ClientSession] = None
    #     self._session_lock = asyncio.Lock()
    #     # Cache: anilist_id -> kuudere anime id
    #     self._id_cache: Dict[int, Optional[str]] = {}

    # # ──────────────────────────────────────────────────────────
    # #  Session management
    # # ──────────────────────────────────────────────────────────
    # async def _get_session(self) -> aiohttp.ClientSession:
    #     async with self._session_lock:
    #         if self._session is None or self._session.closed:
    #             self._session = aiohttp.ClientSession(timeout=self._timeout)
    #         return self._session

    # async def close(self) -> None:
    #     async with self._session_lock:
    #         if self._session and not self._session.closed:
    #             await self._session.close()
    #             self._session = None

    # async def __aenter__(self):
    #     return self

    # async def __aexit__(self, *_):
    #     await self.close()

    # # ──────────────────────────────────────────────────────────
    # #  HTTP helpers
    # # ──────────────────────────────────────────────────────────
    # async def _get_json(self, url: str, params: Optional[Dict] = None) -> Optional[Any]:
    #     session = await self._get_session()
    #     try:
    #         async with session.get(url, headers=HEADERS, params=params) as r:
    #             if r.status == 200:
    #                 return await r.json(content_type=None)
    #             logger.warning(f"[Kuudere] GET {url} -> {r.status}")
    #             return None
    #     except asyncio.TimeoutError:
    #         logger.warning(f"[Kuudere] Timeout for {url}")
    #         return None
    #     except aiohttp.ClientError as e:
    #         logger.warning(f"[Kuudere] ClientError: {e}")
    #         return None

    # # ──────────────────────────────────────────────────────────
    # #  ID resolution
    # # ──────────────────────────────────────────────────────────
    # def cache_kuudere_id(self, anilist_id: int, kuudere_id: str) -> None:
    #     """Cache a known anilist_id -> kuudere_id mapping (called by unified scraper)."""
    #     self._id_cache[int(anilist_id)] = kuudere_id

    # def get_cached_id(self, anilist_id: int) -> Optional[str]:
    #     return self._id_cache.get(int(anilist_id))

    # # ──────────────────────────────────────────────────────────
    # #  Episode block builder (injected into providers_map)
    # # ──────────────────────────────────────────────────────────
    # async def build_provider_block(
    #     self,
    #     kuudere_id: str,
    #     anilist_id: int,
    #     anime_title: str = "",
    # ) -> Optional[Dict[str, Any]]:
    #     """
    #     Fetch episode list from kuudere.to and build a providers_map-compatible
    #     block so KUUDERE appears as a selectable server pill.

    #     Args:
    #         kuudere_id: Kuudere anime ID (from Miruro provider_id)
    #         anilist_id: AniList anime ID
    #         anime_title: Optional anime title for metadata

    #     Returns:
    #         Provider block dict or None if no episodes found.
    #     """
    #     # Fetch episode 1 to get the full episode list (all_episodes)
    #     url = f"{KUUDERE_API}/watch/{kuudere_id}/1"
    #     data = await self._get_json(url)

    #     if not data or not data.get("success"):
    #         logger.warning(f"[Kuudere] No episode data for kuudere_id={kuudere_id}")
    #         return None

    #     all_episodes: List[Dict] = data.get("all_episodes", [])
    #     episode_links: List[Dict] = data.get("episode_links", [])

    #     if not all_episodes:
    #         return None

    #     # Determine sub/dub availability from the first episode's links
    #     has_sub = any(
    #         (link.get("dataType") or "").lower() == "sub"
    #         for link in episode_links
    #         if isinstance(link, dict)
    #     )
    #     has_dub = any(
    #         (link.get("dataType") or "").lower() == "dub"
    #         for link in episode_links
    #         if isinstance(link, dict)
    #     )

    #     sub_eps: List[Dict[str, Any]] = []
    #     dub_eps: List[Dict[str, Any]] = []

    #     for ep in all_episodes:
    #         if not isinstance(ep, dict):
    #             continue
    #         ep_num = ep.get("number")
    #         if ep_num is None:
    #             continue

    #         titles = ep.get("titles", [])
    #         title = titles[0] if isinstance(titles, list) and titles else f"Episode {ep_num}"

    #         if has_sub:
    #             sub_eps.append({
    #                 "id": f"watch/KUUDERE/{anilist_id}/sub/kuudere-{ep_num}",
    #                 "number": ep_num,
    #                 "title": title,
    #                 "filler": ep.get("filler") or False,
    #             })
    #         if has_dub:
    #             dub_eps.append({
    #                 "id": f"watch/KUUDERE/{anilist_id}/dub/kuudere-{ep_num}",
    #                 "number": ep_num,
    #                 "title": title,
    #                 "filler": ep.get("filler") or False,
    #             })

    #     if not sub_eps and not dub_eps:
    #         return None

    #     # Cache the kuudere_id for later source fetching
    #     self.cache_kuudere_id(anilist_id, kuudere_id)

    #     logger.info(
    #         f"[Kuudere] Built provider block: kuudere_id={kuudere_id} "
    #         f"anilist_id={anilist_id} sub={len(sub_eps)} dub={len(dub_eps)}"
    #     )

    #     return {
    #         "meta": {"title": anime_title},
    #         "episodes": {"sub": sub_eps, "dub": dub_eps},
    #     }

    # # ──────────────────────────────────────────────────────────
    # #  Sources
    # # ──────────────────────────────────────────────────────────
    # async def get_sources(
    #     self,
    #     kuudere_id: str,
    #     ep_num: int,
    #     category: str = "sub",
    # ) -> Dict[str, Any]:
    #     """
    #     Fetch embed streaming URLs from kuudere.to.

    #     Args:
    #         kuudere_id: The Kuudere anime ID (e.g. "6932fcb90002e0d03e13")
    #         ep_num: Episode number
    #         category: "sub" or "dub"

    #     Returns:
    #         Standardised result dict compatible with the watch page frontend.
    #     """
    #     url = f"{KUUDERE_API}/watch/{kuudere_id}/{ep_num}"
    #     data = await self._get_json(url)

    #     if not data or not data.get("success"):
    #         logger.warning(f"[Kuudere] API returned no data for {kuudere_id} ep {ep_num}")
    #         return {
    #             "error": "no_sources",
    #             "message": "Kuudere API returned no data for this episode.",
    #         }

    #     # ── Extract embed URLs from episode_links ──
    #     episode_links: List[Dict] = data.get("episode_links", [])
    #     embed_sources: List[Dict[str, Any]] = []

    #     for link in episode_links:
    #         if not isinstance(link, dict):
    #             continue
    #         link_type = (link.get("dataType") or "").lower()
    #         if link_type != category:
    #             continue
    #         embed_url = link.get("dataLink", "")
    #         server_name = link.get("serverName") or "Kuudere"
    #         if embed_url:
    #             embed_sources.append({
    #                 "url": embed_url,
    #                 "quality": "default",
    #                 "label": f"{server_name} (Embed)",
    #                 "type": "embed",
    #             })

    #     if not embed_sources:
    #         logger.warning(
    #             f"[Kuudere] No {category} embed links for {kuudere_id} ep {ep_num}"
    #         )
    #         return {
    #             "error": "no_sources",
    #             "message": f"Kuudere has no {category} sources for episode {ep_num}.",
    #         }

    #     # ── Intro / Outro skip data ──
    #     intro = None
    #     outro = None
    #     intro_start = data.get("intro_start", 0)
    #     intro_end = data.get("intro_end", 0)
    #     outro_start = data.get("outro_start", 0)
    #     outro_end = data.get("outro_end", 0)
    #     if intro_end:
    #         intro = {"start": intro_start, "end": intro_end}
    #     if outro_end:
    #         outro = {"start": outro_start, "end": outro_end}

    #     primary_url = embed_sources[0]["url"]
    #     logger.info(
    #         f"[Kuudere] OK kuudere_id={kuudere_id} ep={ep_num} "
    #         f"category={category} embeds={len(embed_sources)}"
    #     )

    #     return {
    #         "sources": [],
    #         "tracks": [],
    #         "intro": intro,
    #         "outro": outro,
    #         "headers": {},
    #         "provider": "KUUDERE",
    #         "download": "",
    #         "embed_sources": embed_sources,
    #         "hls_sources": [],
    #         "source_type": "embed",
    #         "available_qualities": [],
    #         "video_link": primary_url,
    #         "source_provider": "KUUDERE",
    #     }
