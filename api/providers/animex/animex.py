"""
AnimeX provider - fetches episodes and HLS streams from animex.one
GraphQL maps AniList ID -> AnimeX slug; REST gives episodes/servers/sources.
"""

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

from ..video_utils import encode_proxy

logger = logging.getLogger(__name__)


GRAPHQL_URL = "https://graphql.animex.one/graphql"
REST_BASE = "https://pp.animex.one/rest/api"

UPSTREAM_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://animex.one",
    "Referer": "https://animex.one/",
}


class AnimexScraper:
    """Async scraper for the AnimeX API (animex.one)."""

    def __init__(self, timeout: int = 20):
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        # Cache anilist_id -> animex slug to avoid repeated graphql calls
        self._slug_cache: Dict[int, Optional[str]] = {}
        # Cache anilist_id -> episodes list
        self._episodes_cache: Dict[int, List[Dict[str, Any]]] = {}

    # ──────────────────────────────────────────────────────────
    #  Internal helpers
    # ──────────────────────────────────────────────────────────
    async def _post_json(
        self, session: aiohttp.ClientSession, url: str, payload: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        try:
            async with session.post(
                url,
                json=payload,
                headers={**UPSTREAM_HEADERS, "Content-Type": "application/json"},
            ) as r:
                if r.status != 200:
                    logger.warning(f"[AnimeX] POST {url} -> {r.status}")
                    return None
                return await r.json(content_type=None)
        except Exception as e:
            logger.warning(f"[AnimeX] POST {url} failed: {e}")
            return None

    async def _get_json(
        self,
        session: aiohttp.ClientSession,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        retries: int = 3,
    ) -> Optional[Any]:
        backoff = 0.7
        for attempt in range(retries):
            try:
                async with session.get(url, params=params, headers=UPSTREAM_HEADERS) as r:
                    if r.status == 429:
                        # Honour Retry-After if provided, otherwise back off.
                        retry_after = r.headers.get("Retry-After")
                        delay = backoff
                        if retry_after:
                            try:
                                delay = max(delay, float(retry_after))
                            except ValueError:
                                pass
                        logger.warning(
                            f"[AnimeX] GET {url} -> 429, retry {attempt + 1}/{retries} in {delay:.1f}s"
                        )
                        if attempt + 1 < retries:
                            await asyncio.sleep(delay)
                            backoff *= 2
                            continue
                        return None
                    if r.status != 200:
                        logger.warning(f"[AnimeX] GET {url} -> {r.status}")
                        return None
                    return await r.json(content_type=None)
            except Exception as e:
                logger.warning(f"[AnimeX] GET {url} failed (attempt {attempt + 1}): {e}")
                if attempt + 1 < retries:
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    continue
                return None
        return None

    # ──────────────────────────────────────────────────────────
    #  Slug mapping (AniList ID -> AnimeX slug)
    # ──────────────────────────────────────────────────────────
    async def map_anilist(self, anilist_id: int) -> Optional[str]:
        """Resolve an AniList ID to the matching AnimeX slug."""
        try:
            anilist_id = int(anilist_id)
        except (TypeError, ValueError):
            return None

        if anilist_id in self._slug_cache:
            return self._slug_cache[anilist_id]

        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            data = await self._post_json(
                session,
                GRAPHQL_URL,
                {
                    "query": "query($id:Int){anime(anilistId:$id){id anilistId titleEnglish titleRomaji}}",
                    "variables": {"id": anilist_id},
                },
            )

        slug = None
        if isinstance(data, dict):
            anime = ((data.get("data") or {}).get("anime")) or {}
            slug = anime.get("id")

        self._slug_cache[anilist_id] = slug
        if not slug:
            logger.info(f"[AnimeX] No slug found for anilist_id={anilist_id}")
        return slug

    # ──────────────────────────────────────────────────────────
    #  Episodes
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def _episode_title(ep: Dict[str, Any]) -> str:
        titles = ep.get("titles") or {}
        if isinstance(titles, dict):
            for key in ("en", "x-jat", "ja", "romaji"):
                t = titles.get(key)
                if isinstance(t, str) and t.strip():
                    return t.strip()
        t = ep.get("title")
        if isinstance(t, str) and t.strip():
            return t.strip()
        return f"Episode {ep.get('number', '?')}"

    async def fetch_raw_episodes(self, anilist_id: int) -> List[Dict[str, Any]]:
        """Return AnimeX raw episode list for the given AniList ID."""
        try:
            anilist_id = int(anilist_id)
        except (TypeError, ValueError):
            return []

        if anilist_id in self._episodes_cache:
            return self._episodes_cache[anilist_id]

        slug = await self.map_anilist(anilist_id)
        if not slug:
            return []

        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            data = await self._get_json(
                session, f"{REST_BASE}/episodes", params={"id": slug}
            )

        episodes: List[Dict[str, Any]] = []
        if isinstance(data, list):
            episodes = [ep for ep in data if isinstance(ep, dict)]
        elif isinstance(data, dict):
            raw = data.get("episodes") or data.get("data") or []
            if isinstance(raw, list):
                episodes = [ep for ep in raw if isinstance(ep, dict)]

        # Only cache non-empty results so transient errors (429, network)
        # don't poison the cache for the rest of the process lifetime.
        if episodes:
            self._episodes_cache[anilist_id] = episodes
        logger.info(
            f"[AnimeX] anilist_id={anilist_id} slug={slug} -> {len(episodes)} eps"
        )
        return episodes

    async def build_provider_blocks(
        self, anilist_id: int, anime_title: str = ""
    ) -> Dict[str, Dict[str, Any]]:
        """
        Build providers_map entries for AnimeX — one entry per sub-server
        (uwu, mochi, kami, ...) so each shows up as its own selectable
        provider in the watch UI, matching how miruro exposes jet/arc/kiwi.

        Returns a dict keyed by `animex-<sub_provider_id>`. Empty dict if
        AnimeX has nothing for this anilist_id.
        """
        episodes = await self.fetch_raw_episodes(anilist_id)
        if not episodes:
            return {}

        slug = await self.map_anilist(anilist_id)
        if not slug:
            return {}

        # Pick a representative episode (prefer ep 1) to discover sub-servers.
        first_ep_num = None
        for ep in episodes:
            n = ep.get("number")
            if n is not None:
                try:
                    first_ep_num = int(n) if float(n).is_integer() else n
                except (TypeError, ValueError):
                    first_ep_num = n
                break
        if first_ep_num is None:
            return {}

        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            sub_servers, dub_servers = await self._list_servers(session, slug, first_ep_num)

        # Build episode lists keyed by sub-server id.
        # We need a union of sub+dub server ids; per-language episode lists
        # only include languages that server supports.
        sub_ids = [p.get("id") for p in sub_servers if isinstance(p, dict) and p.get("id")]
        dub_ids = [p.get("id") for p in dub_servers if isinstance(p, dict) and p.get("id")]

        if not sub_ids and not dub_ids:
            return {}

        # Build raw (number, title) once.
        ep_meta: List[Tuple[Any, Any, str]] = []
        for ep in episodes:
            number = ep.get("number")
            if number is None:
                continue
            try:
                num_for_slug = int(number) if float(number).is_integer() else number
            except (TypeError, ValueError):
                num_for_slug = number
            ep_meta.append((number, num_for_slug, self._episode_title(ep)))

        all_server_ids = list(dict.fromkeys(sub_ids + dub_ids))
        blocks: Dict[str, Dict[str, Any]] = {}

        for server_id in all_server_ids:
            sub_eps: List[Dict[str, Any]] = []
            dub_eps: List[Dict[str, Any]] = []

            for number, num_for_slug, title in ep_meta:
                ep_entry_sub = {
                    "id": f"watch/ax/{anilist_id}/sub/{server_id}-{num_for_slug}",
                    "number": number,
                    "title": title,
                    "filler": False,
                }
                ep_entry_dub = {
                    "id": f"watch/ax/{anilist_id}/dub/{server_id}-{num_for_slug}",
                    "number": number,
                    "title": title,
                    "filler": False,
                }
                if server_id in sub_ids:
                    sub_eps.append(ep_entry_sub)
                if server_id in dub_ids:
                    dub_eps.append(ep_entry_dub)

            blocks[server_id] = {
                "meta": {"title": anime_title or ""},
                "episodes": {"sub": sub_eps, "dub": dub_eps},
                "_ax": True,
                "_ax_server_id": server_id,
            }

        return blocks

    # ──────────────────────────────────────────────────────────
    #  Sources
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def _parse_ep_num_from_slug(slug: str) -> Optional[float]:
        """Pull the trailing number out of slugs like 'animex-1' or '12'."""
        if not slug:
            return None
        m = re.search(r"(\d+(?:\.\d+)?)\s*$", str(slug))
        if not m:
            return None
        try:
            return float(m.group(1))
        except ValueError:
            return None

    async def _list_servers(
        self, session: aiohttp.ClientSession, slug: str, ep_num
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        data = await self._get_json(
            session, f"{REST_BASE}/servers", params={"id": slug, "epNum": ep_num}
        )
        if not isinstance(data, dict):
            return [], []
        sub_p = data.get("subProviders") or []
        dub_p = data.get("dubProviders") or []
        return (
            sub_p if isinstance(sub_p, list) else [],
            dub_p if isinstance(dub_p, list) else [],
        )

    @staticmethod
    def _ordered_provider_ids(providers: List[Dict[str, Any]]) -> List[str]:
        """Return server IDs ordered by 'default' first, then declared order."""
        if not providers:
            return []
        default_ids = [p.get("id") for p in providers if isinstance(p, dict) and p.get("default") and p.get("id")]
        rest = [p.get("id") for p in providers if isinstance(p, dict) and not p.get("default") and p.get("id")]
        return [pid for pid in (default_ids + rest) if pid]

    @staticmethod
    def _quality_to_int(q: Any) -> int:
        if not q:
            return 0
        m = re.search(r"(\d+)", str(q))
        return int(m.group(1)) if m else 0

    async def _try_provider(
        self,
        session: aiohttp.ClientSession,
        slug: str,
        ep_num,
        type_: str,
        provider_id: str,
    ) -> Optional[Dict[str, Any]]:
        data = await self._get_json(
            session,
            f"{REST_BASE}/sources",
            params={
                "id": slug,
                "epNum": ep_num,
                "type": type_,
                "providerId": provider_id,
            },
        )
        if not isinstance(data, dict):
            return None
        sources = data.get("sources") or []
        if not (isinstance(sources, list) and sources):
            return None
        return data

    async def get_sources(
        self,
        anilist_id: int,
        ep_num,
        category: str = "sub",
        preferred_server: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch HLS sources from AnimeX. If `preferred_server` is given, tries
        that sub-server first; otherwise falls back to the AnimeX-declared
        default order. Returns the same shape the rest of the unified
        scraper consumes (hls_sources + video_link, all proxied).
        """
        slug = await self.map_anilist(anilist_id)
        if not slug:
            return {"error": "no_sources", "message": "AnimeX has no slug for this title."}

        try:
            ep_num_clean = (
                int(ep_num) if isinstance(ep_num, (int, float)) and float(ep_num).is_integer() else ep_num
            )
        except (TypeError, ValueError):
            ep_num_clean = ep_num

        category = category if category in ("sub", "dub") else "sub"

        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            sub_providers, dub_providers = await self._list_servers(session, slug, ep_num_clean)
            providers = dub_providers if category == "dub" else sub_providers
            ordered_ids = self._ordered_provider_ids(providers)

            if not ordered_ids:
                return {
                    "error": "no_sources",
                    "message": f"AnimeX has no {category} providers for episode {ep_num_clean}.",
                }

            if preferred_server and preferred_server in ordered_ids:
                ordered_ids = [preferred_server] + [p for p in ordered_ids if p != preferred_server]

            chosen = None
            for pid in ordered_ids:
                result = await self._try_provider(session, slug, ep_num_clean, category, pid)
                if result:
                    chosen = (pid, result)
                    break

        if not chosen:
            return {
                "error": "no_sources",
                "message": "AnimeX returned no playable streams.",
            }

        provider_id, raw = chosen
        upstream_sources = raw.get("sources") or []
        upstream_headers = raw.get("headers") or {}
        # Normalise referer header (proxy expects lowercase keys)
        proxy_headers = None
        ref = upstream_headers.get("Referer") or upstream_headers.get("referer")
        if ref:
            proxy_headers = {"referer": ref}

        hls_sources: List[Dict[str, Any]] = []
        available_qualities: List[str] = []

        for stream in upstream_sources:
            if not isinstance(stream, dict):
                continue
            url = stream.get("url") or stream.get("file")
            if not url:
                continue
            quality = stream.get("quality") or "default"
            proxied = encode_proxy(url, proxy_headers)
            hls_sources.append(
                {
                    "url": proxied,
                    "file": proxied,
                    "isM3U8": True,
                    "quality": quality,
                    "label": quality,
                }
            )
            if quality and quality not in available_qualities:
                available_qualities.append(quality)

        if not hls_sources:
            return {
                "error": "no_sources",
                "message": "AnimeX stream list was empty.",
            }

        # Sort by numeric quality (desc) so the highest-res is first / default
        hls_sources.sort(key=lambda s: self._quality_to_int(s.get("quality")), reverse=True)
        available_qualities = [q for q in available_qualities]
        available_qualities.sort(key=self._quality_to_int, reverse=True)

        # Subtitles
        tracks: List[Dict[str, Any]] = []
        upstream_tracks = raw.get("tracks") or []
        if isinstance(upstream_tracks, list):
            for sub in upstream_tracks:
                if not isinstance(sub, dict):
                    continue
                file_url = sub.get("file") or sub.get("url")
                if not file_url:
                    continue
                proxied_sub = (
                    encode_proxy(file_url, proxy_headers)
                    if file_url.startswith("http")
                    else file_url
                )
                tracks.append(
                    {
                        "file": proxied_sub,
                        "url": proxied_sub,
                        "label": sub.get("label") or sub.get("lang") or "Unknown",
                        "kind": sub.get("kind") or "subtitles",
                        "lang": sub.get("label") or sub.get("lang") or "Unknown",
                    }
                )

        primary_url = hls_sources[0]["url"]
        return {
            "sources": [{"file": s["url"], "url": s["url"], "quality": s["quality"]} for s in hls_sources],
            "tracks": tracks,
            "intro": None,
            "outro": None,
            "headers": upstream_headers or {},
            "provider": "animex",
            "download": "",
            "embed_sources": [],
            "hls_sources": hls_sources,
            "source_type": "hls",
            "available_qualities": available_qualities,
            "video_link": primary_url,
            "source_provider": "animex",
            "selected_server_id": provider_id,
        }
