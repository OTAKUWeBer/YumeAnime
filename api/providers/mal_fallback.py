"""
Jikan (MyAnimeList) API v4 fallback service.

Used as a third-tier fallback when both AniList GraphQL and Miruro API are
down or rate-limited.  Provides home page data and anime info using the
free Jikan REST API (https://api.jikan.moe/v4).

The anime-lists mapping file is used to convert MAL IDs ↔ AniList IDs so
that cards rendered from Jikan data still link to /watch/<anilist_id>.
"""

import asyncio
import logging
import re
import time
from typing import Dict, Any, List, Optional

import aiohttp

logger = logging.getLogger(__name__)

JIKAN_BASE = "https://api.jikan.moe/v4"
MAPPING_URL = (
    "https://raw.githubusercontent.com/Fribb/anime-lists/master/anime-list-full.json"
)

# ---------------------------------------------------------------------------
# Rate-limit guard — Jikan allows ~3 req/s
# ---------------------------------------------------------------------------
_JIKAN_SEMAPHORE = asyncio.Semaphore(3)
_JIKAN_MIN_INTERVAL = 0.35  # seconds between calls
_jikan_last_call: float = 0.0


class MalFallbackService:
    """Jikan-based fallback for home page data and anime info."""

    def __init__(self):
        # ID mapping caches
        self._mapping: Optional[List[Dict]] = None
        self._mapping_ts: float = 0.0
        self._mapping_ttl: float = 86400.0  # 24 h

        self._mal_to_al: Dict[int, int] = {}
        self._al_to_mal: Dict[int, int] = {}

        # Home data cache
        self._home_cache: Optional[Dict[str, Any]] = None
        self._home_cache_ts: float = 0.0
        self._home_cache_ttl: float = 600.0  # 10 min

        logger.info("[MalFallback] Service initialised")

    # ======================================================================
    # Internal HTTP helpers
    # ======================================================================

    async def _jikan_get(self, path: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Rate-limited GET to Jikan. Returns parsed JSON or {}."""
        global _jikan_last_call

        async with _JIKAN_SEMAPHORE:
            now = time.monotonic()
            wait = _JIKAN_MIN_INTERVAL - (now - _jikan_last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            _jikan_last_call = time.monotonic()

            url = f"{JIKAN_BASE}/{path.lstrip('/')}"
            timeout = aiohttp.ClientTimeout(total=10)
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url, params=params) as resp:
                        if resp.status == 429:
                            logger.warning("[MalFallback] Jikan rate-limited, dropping request")
                            return {}
                        if resp.status != 200:
                            logger.error(f"[MalFallback] Jikan {resp.status} for {url}")
                            return {}
                        return await resp.json()
            except Exception as e:
                logger.error(f"[MalFallback] Jikan request failed for {url}: {e}")
                return {}

    # ======================================================================
    # ID mapping
    # ======================================================================

    async def _ensure_mapping(self) -> None:
        """Load or refresh the MAL ↔ AniList mapping file."""
        now = time.time()
        if self._mapping and (now - self._mapping_ts) < self._mapping_ttl:
            return

        timeout = aiohttp.ClientTimeout(total=30)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(MAPPING_URL) as resp:
                    if resp.status != 200:
                        logger.error(f"[MalFallback] Mapping fetch failed: {resp.status}")
                        return
                    data = await resp.json(content_type=None)

            self._mapping = data
            self._mapping_ts = time.time()

            # Build bidirectional lookup dicts
            mal_to_al: Dict[int, int] = {}
            al_to_mal: Dict[int, int] = {}
            for entry in data:
                mal_id = entry.get("mal_id")
                al_id = entry.get("anilist_id")
                if mal_id and al_id:
                    try:
                        m = int(mal_id)
                        a = int(al_id)
                        mal_to_al[m] = a
                        al_to_mal[a] = m
                    except (ValueError, TypeError):
                        continue

            self._mal_to_al = mal_to_al
            self._al_to_mal = al_to_mal
            logger.info(
                f"[MalFallback] Mapping loaded: {len(mal_to_al)} entries"
            )
        except Exception as e:
            logger.error(f"[MalFallback] Mapping load failed: {e}")

    def mal_to_anilist(self, mal_id: int) -> Optional[int]:
        return self._mal_to_al.get(int(mal_id))

    def anilist_to_mal(self, anilist_id: int) -> Optional[int]:
        return self._al_to_mal.get(int(anilist_id))

    # ======================================================================
    # Normalizers — output matches AnilistHomeService / MiruroAnimeInfoService
    # ======================================================================

    def _normalize_jikan_anime(
        self, item: Dict[str, Any], rank: int = 0
    ) -> Dict[str, Any]:
        """Convert a Jikan anime object into the unified card format."""
        mal_id = item.get("mal_id")
        anilist_id = self.mal_to_anilist(mal_id) if mal_id else None
        display_id = str(anilist_id) if anilist_id else str(mal_id or "")

        images = item.get("images", {})
        poster = (
            images.get("webp", {}).get("large_image_url")
            or images.get("jpg", {}).get("large_image_url")
            or images.get("jpg", {}).get("image_url")
            or ""
        )

        english_title = item.get("title_english") or item.get("title") or "Unknown"

        total_episodes = item.get("episodes") or 0
        # Jikan doesn't directly give "released episodes" for airing shows,
        # but if airing==True and episodes is set, use a reasonable estimate.
        airing = item.get("airing", False)
        released = total_episodes if not airing else max(total_episodes - 1, 1) if total_episodes else 0

        # Studios
        studios = item.get("studios", [])
        studio_name = studios[0].get("name") if studios else ""

        # Duration (e.g. "23 min per ep" → "23 min")
        raw_duration = item.get("duration") or ""
        duration = raw_duration.replace(" per ep", "").strip() if raw_duration else ""

        # Rating: Jikan score is 0-10, AniList is 0-100
        score = item.get("score")
        rating = int(score * 10) if score else None

        genres = [g.get("name") for g in (item.get("genres") or []) if g.get("name")]

        return {
            "id": display_id,
            "anilistId": anilist_id,
            "malId": mal_id,
            "name": english_title,
            "jname": item.get("title_japanese") or "",
            "poster": poster,
            "banner": "",  # Jikan doesn't provide banner images
            "episodes": {
                "sub": total_episodes,
                "dub": 0,
                "released": released,
            },
            "type": item.get("type") or "",
            "duration": duration,
            "rating": rating,
            "isAdult": (item.get("rating") or "").startswith("Rx"),
            "rank": rank,
            "description": "",
            "genres": genres,
            "otherInfo": [
                item.get("type") or "",
                duration,
                studio_name,
            ],
        }

    def _normalize_jikan_spotlight(
        self, item: Dict[str, Any], rank: int = 0
    ) -> Dict[str, Any]:
        """Convert a Jikan anime object into the spotlight card format."""
        base = self._normalize_jikan_anime(item, rank)

        # Synopsis
        synopsis = item.get("synopsis") or ""
        # Strip MAL source notes
        if synopsis and "[Written by MAL" in synopsis:
            synopsis = synopsis[: synopsis.index("[Written by MAL")].strip()

        studios = item.get("studios", [])
        studio_name = studios[0].get("name") if studios else ""

        total_episodes = item.get("episodes") or 0
        released = base["episodes"].get("released", 0)

        base["description"] = synopsis
        base["studio"] = studio_name
        base["totalEpisodes"] = total_episodes or None
        base["releasedEpisodes"] = released if released else total_episodes
        base["season"] = (item.get("season") or "").upper()
        base["seasonYear"] = item.get("year") or ""
        base["nextEpisode"] = None
        return base

    def _normalize_jikan_info(self, item: Dict[str, Any], chars_list: Optional[List[Dict[str, Any]]] = None, recs_list: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Convert a Jikan /anime/{id}/full response into the same shape as
        MiruroAnimeInfoService.get_anime_info().
        """
        mal_id = item.get("mal_id")
        anilist_id = self.mal_to_anilist(mal_id) if mal_id else None

        images = item.get("images", {})
        poster = (
            images.get("webp", {}).get("large_image_url")
            or images.get("jpg", {}).get("large_image_url")
            or ""
        )

        english_title = item.get("title_english") or item.get("title") or "Unknown"

        # Status mapping
        status_map = {
            "Currently Airing": "Currently Airing",
            "Finished Airing": "Finished Airing",
            "Not yet aired": "Not yet aired",
        }
        status = status_map.get(item.get("status", ""), item.get("status", ""))

        total_episodes = item.get("episodes") or 0
        airing = item.get("airing", False)
        released_episodes = total_episodes if not airing else max(total_episodes - 1, 1) if total_episodes else 0

        genres = [g.get("name") for g in (item.get("genres") or []) if g.get("name")]
        themes = [t.get("name") for t in (item.get("themes") or []) if t.get("name")]
        all_genres = genres + themes

        studios = item.get("studios", [])
        studios_list = [
            {"id": s.get("mal_id"), "name": s.get("name")} for s in studios
        ]

        # Duration
        raw_duration = item.get("duration") or ""
        duration = raw_duration.replace(" per ep", "").strip() if raw_duration else ""

        # Score → AniList scale (0-100)
        score = item.get("score")
        rating_str = str(int(score * 10)) if score else ""

        # Dates
        aired = item.get("aired", {}) or {}
        aired_string = aired.get("string") or ""
        prop = aired.get("prop", {}) or {}
        from_d = prop.get("from", {}) or {}
        to_d = prop.get("to", {}) or {}

        def fmt_date(d):
            if not d or not d.get("year"):
                return ""
            months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            m = months[d["month"] - 1] if d.get("month") and 1 <= d["month"] <= 12 else ""
            day = d.get("day", "")
            return f"{m} {day}, {d['year']}".strip(", ")

        aired_start = fmt_date(from_d)
        aired_end = fmt_date(to_d)

        season = (item.get("season") or "").upper()
        season_year = item.get("year") or ""
        premiered = f"{season} {season_year}".strip() if season else ""

        # Synopsis
        synopsis = item.get("synopsis") or ""
        if synopsis and "[Written by MAL" in synopsis:
            synopsis = synopsis[: synopsis.index("[Written by MAL")].strip()

        # Source
        source = (item.get("source") or "").replace("_", " ").title()

        # Characters (from characters endpoint)
        characters = []
        for char_entry in (chars_list or []):
            char = char_entry.get("character", {}) or {}
            char_images = char.get("images", {}) or {}
            role = char_entry.get("role") or "Supporting"

            # Pick first Japanese VA
            va = None
            for v in (char_entry.get("voice_actors") or []):
                if v.get("language", "").lower() == "japanese":
                    va = v
                    break
            if not va and (char_entry.get("voice_actors") or []):
                va = char_entry["voice_actors"][0]

            va_person = (va or {}).get("person", {}) or {}
            va_images = va_person.get("images", {}) or {}

            characters.append({
                "character": {
                    "id": str(char.get("mal_id", "")),
                    "name": char.get("name", ""),
                    "poster": char_images.get("webp", {}).get("image_url") or char_images.get("jpg", {}).get("image_url") or "",
                    "cast": role.title(),
                },
                "voiceActor": {
                    "id": str(va_person.get("mal_id", "")),
                    "name": va_person.get("name", ""),
                    "poster": va_images.get("jpg", {}).get("image_url") or "",
                    "cast": (va or {}).get("language", "Japanese"),
                } if va else None,
            })

        # Relations
        related = []
        prequels = []
        sequels = []
        for rel in (item.get("relations") or []):
            rel_type = rel.get("relation", "")
            for entry in (rel.get("entry") or []):
                if entry.get("type") != "anime":
                    continue
                rel_mal_id = entry.get("mal_id")
                rel_al_id = self.mal_to_anilist(rel_mal_id) if rel_mal_id else None
                rel_entry = {
                    "id": str(rel_al_id or rel_mal_id or ""),
                    "anilistId": rel_al_id,
                    "malId": rel_mal_id,
                    "name": entry.get("name") or "",
                    "jname": "",
                    "poster": "",  # Jikan relations don't include images
                    "type": "",
                    "rating": None,
                    "episodes_sub": 0,
                    "episodes_dub": 0,
                    "relation": rel_type.replace("_", " ").title(),
                    "badge": rel_type.upper(),
                }

                if rel_type.lower() == "prequel":
                    prequels.append(rel_entry)
                elif rel_type.lower() == "sequel":
                    sequels.append(rel_entry)
                related.append(rel_entry)

        # Recommendations (from recommendations endpoint)
        recommended = []
        for rec in (recs_list or [])[:6]:
            rec_entry = rec.get("entry", {}) or {}
            rec_mal_id = rec_entry.get("mal_id")
            rec_al_id = self.mal_to_anilist(rec_mal_id) if rec_mal_id else None
            rec_images = rec_entry.get("images", {}) or {}
            recommended.append({
                "id": str(rec_al_id or rec_mal_id or ""),
                "anilistId": rec_al_id,
                "name": rec_entry.get("title") or "",
                "jname": "",
                "poster": rec_images.get("webp", {}).get("large_image_url") or rec_images.get("jpg", {}).get("large_image_url") or "",
                "type": "",
                "duration": "",
                "rating": None,
                "episodes_sub": 0,
                "episodes_dub": 0,
            })

        # Trailer
        promotional_videos = []
        trailer = item.get("trailer", {}) or {}
        if trailer.get("youtube_id") or trailer.get("embed_url"):
            yt_id = trailer.get("youtube_id")
            url = f"https://www.youtube.com/watch?v={yt_id}" if yt_id else (trailer.get("url") or "")
            thumb = (trailer.get("images") or {}).get("maximum_image_url") or ""
            if url:
                promotional_videos.append({
                    "title": "Trailer",
                    "source": url,
                    "thumbnail": thumb,
                })

        return {
            "anilistId": anilist_id,
            "malId": mal_id,
            "title": english_title,
            "poster": poster,
            "banner": "",
            "description": synopsis,
            "status": status,
            "genres": all_genres,
            "duration": duration,
            "isAdult": (item.get("rating") or "").startswith("Rx"),
            "type": item.get("type") or "",
            "source": source,
            "rating": rating_str,
            "quality": "",
            "total_sub_episodes": total_episodes,
            "total_dub_episodes": total_episodes,
            "released_episodes": released_episodes,
            "japanese": item.get("title_japanese") or "",
            "synonyms": ", ".join(item.get("title_synonyms") or []),
            "aired": aired_string,
            "aired_start": aired_start,
            "aired_end": aired_end,
            "premiered": premiered,
            "studios": studios_list,
            "producers": [
                {"id": p.get("mal_id"), "name": p.get("name")}
                for p in (item.get("producers") or [])
            ],
            "malScore": str(score) if score else None,
            "promotionalVideos": promotional_videos,
            "charactersVoiceActors": [],
            "characters": characters,
            "seasons": [],
            "relatedAnimes": related,
            "recommendedAnimes": recommended,
            "prequels": prequels,
            "sequels": sequels,
            "stats": {
                "rating": rating_str,
                "episodes": {
                    "sub": released_episodes,
                    "dub": released_episodes,
                },
                "type": item.get("type") or "",
                "duration": duration,
                "source": source,
            },
            "bannerImage": "",
            "nextAiringEpisode": None,
        }

    # ======================================================================
    # Episode annotation (same helper as AnilistHomeService)
    # ======================================================================

    def _annotate_episodes_count(
        self, animes: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        for anime in animes:
            episodes = anime.get("episodes", {})
            sub_count = episodes.get("sub", 0)
            released_count = episodes.get("released", 0)

            if sub_count > 0:
                if released_count > 0 and released_count != sub_count:
                    anime["episodeCount"] = f"{released_count}/{sub_count}"
                else:
                    anime["episodeCount"] = str(sub_count)
            else:
                anime["episodeCount"] = "?"
        return animes

    # ======================================================================
    # HOME
    # ======================================================================

    async def home(self) -> Dict[str, Any]:
        """Fetch home page data from Jikan as fallback."""
        now = time.time()
        if self._home_cache and (now - self._home_cache_ts) < self._home_cache_ttl:
            return self._home_cache

        await self._ensure_mapping()

        try:
            # Fire requests concurrently (within rate-limit)
            airing_task = self._jikan_get("top/anime", {"filter": "airing", "limit": 24})
            popular_task = self._jikan_get("top/anime", {"filter": "bypopularity", "limit": 24, "type": "tv"})
            seasonal_task = self._jikan_get("seasons/now", {"limit": 24})

            airing_resp, popular_resp, seasonal_resp = await asyncio.gather(
                airing_task, popular_task, seasonal_task,
                return_exceptions=True,
            )

            def safe_data(resp):
                if isinstance(resp, Exception) or not resp:
                    return []
                return resp.get("data", [])

            def filter_adult(items):
                return [
                    item for item in items
                    if not (item.get("rating") or "").startswith("Rx")
                    and "Hentai" not in [g.get("name") for g in (item.get("genres") or [])]
                ]

            def is_valid(anime):
                name = anime.get("name", "")
                if not name or name == "Unknown":
                    return False
                # Must have an AniList ID to be useful for navigation
                if not anime.get("anilistId") and not anime.get("id"):
                    return False
                return True

            airing_items = filter_adult(safe_data(airing_resp))
            popular_items = filter_adult(safe_data(popular_resp))
            seasonal_items = filter_adult(safe_data(seasonal_resp))

            # Spotlight = top 10 airing
            spotlight = [
                a for a in (
                    self._normalize_jikan_spotlight(item, i + 1)
                    for i, item in enumerate(airing_items[:10])
                ) if is_valid(a)
            ]

            # Trending = airing
            trending = [
                a for a in (
                    self._normalize_jikan_anime(item, i + 1)
                    for i, item in enumerate(airing_items)
                ) if is_valid(a)
            ]

            # Popular
            popular = [
                a for a in (
                    self._normalize_jikan_anime(item, i + 1)
                    for i, item in enumerate(popular_items)
                ) if is_valid(a)
            ]

            # Latest = seasonal
            latest = [
                a for a in (
                    self._normalize_jikan_anime(item, i + 1)
                    for i, item in enumerate(seasonal_items)
                ) if is_valid(a)
            ]

            normalized = {
                "spotlightAnimes": self._annotate_episodes_count(spotlight),
                "trendingAnimes": self._annotate_episodes_count(trending),
                "mostPopularAnimes": self._annotate_episodes_count(popular),
                "latestEpisodeAnimes": self._annotate_episodes_count(latest),
            }

            result = {
                "success": True,
                "data": normalized,
                "counts": {k: len(v) for k, v in normalized.items()},
            }

            self._home_cache = result
            self._home_cache_ts = time.time()
            logger.info(
                f"[MalFallback] Home fetched: spotlight={len(spotlight)}, "
                f"trending={len(trending)}, popular={len(popular)}, latest={len(latest)}"
            )
            return result

        except Exception as e:
            logger.error(f"[MalFallback] Home fetch error: {e}")
            if self._home_cache:
                return self._home_cache
            return {
                "success": False,
                "data": {
                    "spotlightAnimes": [],
                    "trendingAnimes": [],
                    "mostPopularAnimes": [],
                    "latestEpisodeAnimes": [],
                },
                "counts": {},
            }

    # ======================================================================
    # ANIME INFO
    # ======================================================================

    async def get_anime_info_by_anilist_id(self, anilist_id: int) -> Dict[str, Any]:
        """
        Fetch anime info from Jikan using an AniList ID.
        Requires the mapping file to convert AniList → MAL ID first.
        """
        await self._ensure_mapping()

        mal_id = self.anilist_to_mal(anilist_id)
        if not mal_id:
            logger.debug(
                f"[MalFallback] No AniList → MAL mapping for ID {anilist_id}. Treating as MAL ID directly."
            )
            mal_id = anilist_id

        return await self.get_anime_info_by_mal_id(mal_id)

    async def get_anime_info_by_mal_id(self, mal_id: int) -> Dict[str, Any]:
        """Fetch full anime info from Jikan by MAL ID."""
        await self._ensure_mapping()

        # Fetch full details, characters, and recommendations in parallel
        full_task = self._jikan_get(f"anime/{mal_id}/full")
        chars_task = self._jikan_get(f"anime/{mal_id}/characters")
        recs_task = self._jikan_get(f"anime/{mal_id}/recommendations")

        full_resp, chars_resp, recs_resp = await asyncio.gather(
            full_task, chars_task, recs_task,
            return_exceptions=True
        )

        if isinstance(full_resp, Exception) or not full_resp or not full_resp.get("data"):
            return {}

        # Safely extract lists
        chars_list = []
        if not isinstance(chars_resp, Exception) and chars_resp and isinstance(chars_resp.get("data"), list):
            chars_list = chars_resp["data"]

        recs_list = []
        if not isinstance(recs_resp, Exception) and recs_resp and isinstance(recs_resp.get("data"), list):
            recs_list = recs_resp["data"]

        info = self._normalize_jikan_info(full_resp["data"], chars_list, recs_list)
        logger.info(
            f"[MalFallback] Anime info fetched for MAL ID {mal_id} → "
            f"title={info.get('title')}"
        )
        return info
