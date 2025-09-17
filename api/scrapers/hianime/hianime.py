import aiohttp
import asyncio
from typing import Optional, Dict, Any, Union, List
from .video import get_and_play_m3u8_and_vtt
import time
import os
from dotenv import load_dotenv

load_dotenv()

class HianimeScraper:
    """
    Async wrapper for the Aniwatch / Hianime endpoints documented at:
    https://github.com/ghoshRitesh12/aniwatch-api (API base path: /api/v2/hianime).
    """

    api_url = os.getenv("HIANIME_API_URL")

    def __init__(self, base_url: Optional[str] = None, default_headers: Optional[Dict[str, str]] = None):
        """
        :param base_url: override the default API base URL (useful if you self-host).
        :param default_headers: headers that will be sent with every request (e.g. custom cache header).
        """
        self.base_url = base_url.rstrip("/") if base_url else self.api_url
        self.default_headers = default_headers or {}
        self._home_cache = None
        self._home_cache_ts = 0.0
        self._home_cache_ttl = 5.0
        self._home_lock = asyncio.Lock()

    async def _get(self, endpoint: str, params: Optional[Dict[str, Union[str, int]]] = None,
                headers: Optional[Dict[str, str]] = None, raise_for_status: bool = False) -> Optional[Dict[str, Any]]:
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
                            # log and retry (don't return a success dict)
                            # optionally parse JSON to get error detail for logs
                            # do not cache this result upstream (see fetch logic)
                            raise aiohttp.ClientResponseError(
                                status=resp.status, request_info=resp.request_info, history=resp.history
                            )
                        # try parse json
                        try:
                            return await resp.json()
                        except Exception:
                            # if parsing fails, log and treat as failure to allow retry
                            raise
            except Exception as exc:
                # log.warning(f"GET {url} attempt {attempt} failed: {exc}")
                if attempt == tries:
                    return None
                await asyncio.sleep(backoff * attempt)
        return None

    async def _fetch_home_cached(self) -> Dict[str, Any]:
        now = time.time()
        if self._home_cache and (now - self._home_cache_ts) < self._home_cache_ttl:
            return self._home_cache

        async with self._home_lock:
            for _ in range(3):  # retry 3 times
                resp = await self._get("home")
                if resp and isinstance(resp, dict):
                    data = resp.get("data") or {}
                    if any(data.get(k) for k in ["latestEpisodeAnimes","mostPopularAnimes","spotlightAnimes","trendingAnimes"]):
                        normalized = {k: self._annotate_episodes_count(data.get(k, [])) for k in ["latestEpisodeAnimes","mostPopularAnimes","spotlightAnimes","trendingAnimes"]}
                        self._home_cache = normalized
                        self._home_cache_ts = time.time()
                        return self._home_cache
                await asyncio.sleep(0.5)  # small backoff before retry

            # fallback: return old cache or empty normalized dict
            if self._home_cache:
                return self._home_cache
            return {k: [] for k in ["latestEpisodeAnimes","mostPopularAnimes","spotlightAnimes","trendingAnimes"]}



    async def home(self) -> Dict[str, Any]:
        """Unified home response with all sections + metadata."""
        data = await self._fetch_home_cached()
        return {
            "success": True,
            "data": {
                key: value for key, value in data.items()
            },
            "counts": {key: len(value) for key, value in data.items()},
        }

    def _annotate_episodes_count(self, animes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = []
        for a in animes:
            copy = dict(a)
            eps = copy.get("episodes") or {}
            try:
                sub = int(eps.get("sub", 0) or 0)
            except Exception:
                sub = 0
            try:
                dub = int(eps.get("dub", 0) or 0)
            except Exception:
                dub = 0
            copy["episodesSub"] = sub
            copy["episodesDub"] = dub
            copy["episodesCount"] = sub + dub
            out.append(copy)
        return out

    def clear_home_cache(self) -> None:
        self._home_cache = None
        self._home_cache_ts = 0.0
        
        
    async def get_anime_info(self, anime_id: str) -> dict:
        """Fetch detailed anime info including seasons, related, recommended, prequels, sequels, and characters.

        Robustly looks for lists in multiple response locations because the API sometimes
        returns `seasons`/`relatedAnimes` at different levels.
        """
        resp = await self._get(f"anime/{anime_id}")
        if not resp:
            return {}

        # Helpful aliases
        data = resp.get("data", {}) if isinstance(resp, dict) else {}
        anime_data = (data.get("anime") if isinstance(data, dict) else None) or (resp.get("anime") if isinstance(resp, dict) else None) or {}

        def find_list(key: str):
            """Look for list `key` in several places: anime_data -> data -> top-level resp."""
            for src in (anime_data, data, resp):
                if isinstance(src, dict):
                    val = src.get(key)
                    if isinstance(val, list):
                        return val
            return []

        def safe_int(val):
            try:
                return int(val)
            except (TypeError, ValueError):
                return 0

        info = anime_data.get("info", {}) if isinstance(anime_data, dict) else {}
        stats = info.get("stats", {}) if isinstance(info, dict) else {}
        episodes = stats.get("episodes", {}) if isinstance(stats, dict) else {}
        rating = stats.get("rating", "")
        more_info = anime_data.get("moreInfo", {}) if isinstance(anime_data, dict) else {}

        # Collect seasons, related, recommended from any place they might be
        raw_seasons = find_list("seasons")
        raw_related = find_list("relatedAnimes") or find_list("related")
        raw_recommended = find_list("recommendedAnimes") or find_list("recommended")

        # Normalize seasons
        seasons = [
            {
                "id": s.get("id"),
                "anilistId": s.get("anilistId") or info.get("anilistId"),
                "malId": s.get("malId"),
                "title": s.get("title") or s.get("name"),
                "name": s.get("name"),
                "poster": s.get("poster"),
                "isCurrent": bool(s.get("isCurrent", False)),
            }
            for s in raw_seasons
            if isinstance(s, dict)
        ]

        # Related + prequel/sequel detection
        related = []
        prequels = []
        sequels = []

        for r in raw_related:
            if not isinstance(r, dict):
                continue
            entry = {
                "id": r.get("id"),
                "name": r.get("name"),
                "anilistId": r.get("anilistId"),
                "malId": r.get("malId"),
                "jname": r.get("jname"),
                "poster": r.get("poster"),
                "type": r.get("type"),
                "rating": r.get("rating"),
                "episodes_sub": safe_int((r.get("episodes") or {}).get("sub")),
                "episodes_dub": safe_int((r.get("episodes") or {}).get("dub")),
                "relation": r.get("relation") or r.get("relationType") or r.get("relation_name") or ""
            }
            related.append(entry)

            rel = (entry["relation"] or "").strip().lower()
            if "prequel" in rel:
                prequels.append(entry)
            elif "sequel" in rel:
                sequels.append(entry)

        # Recommended
        recommended = []
        for r in raw_recommended:
            if not isinstance(r, dict):
                continue
            recommended.append({
                "id": r.get("id"),
                "name": r.get("name"),
                "jname": r.get("jname"),
                "poster": r.get("poster"),
                "type": r.get("type"),
                "duration": r.get("duration"),
                "rating": r.get("rating"),
                "episodes_sub": safe_int((r.get("episodes") or {}).get("sub")),
                "episodes_dub": safe_int((r.get("episodes") or {}).get("dub")),
            })

        # Characters and voice actors
        raw_characters = info.get("charactersVoiceActors", []) if isinstance(info, dict) else []
        characters = []
        for cva in raw_characters:
            character = cva.get("character", {})
            voice_actor = cva.get("voiceActor", {})
            if not character or not voice_actor:
                continue

            characters.append({
                "character": {
                    "id": character.get("id"),
                    "name": character.get("name"),
                    "poster": character.get("poster"),
                    "cast": character.get("cast", "Unknown"),
                },
                "voiceActor": {
                    "id": voice_actor.get("id"),
                    "name": voice_actor.get("name"),
                    "poster": voice_actor.get("poster"),
                    "cast": voice_actor.get("cast", "Unknown"),
                }
            })

        return {
            "anilistId": info.get("anilistId"),
            "malId": info.get("malId"),
            "title": info.get("name") or anime_data.get("name") or "Unknown Title",
            "poster": info.get("poster") or anime_data.get("poster"),
            "description": info.get("description", ""),
            "status": more_info.get("status", "") or anime_data.get("status", ""),
            "genres": more_info.get("genres", []) or anime_data.get("genres", []),
            "duration": stats.get("duration", "") or more_info.get("duration", ""),
            "type": stats.get("type", "") or anime_data.get("type", ""),
            "rating": stats.get("rating", ""),
            "quality": stats.get("quality", ""),
            "total_sub_episodes": safe_int((episodes or {}).get("sub")),
            "total_dub_episodes": safe_int((episodes or {}).get("dub")),
            "japanese": more_info.get("japanese"),
            "synonyms": more_info.get("synonyms"),
            "aired": more_info.get("aired"),
            "premiered": more_info.get("premiered"),
            "studios": more_info.get("studios"),
            "producers": more_info.get("producers", []),
            "malScore": more_info.get("malscore"),
            "promotionalVideos": info.get("promotionalVideos", []),
            "charactersVoiceActors": info.get("charactersVoiceActors", []),
            "characters": characters,
            "seasons": seasons,
            "relatedAnimes": related,
            "recommendedAnimes": recommended,
            "prequels": prequels,
            "sequels": sequels,
        }



    async def get_episodes(self, anime_id: str) -> Dict[str, Any]:
        """Fetch episodes and basic info for a given anime ID"""
        resp = await self._get(f"/anime/{anime_id}/episodes")

        if resp.get("status") == 200 and resp.get("data"):
            data = resp["data"]
            episodes_list = data.get("episodes", [])
            return {
                "anime_id": anime_id,
                "title": data.get("title", ""),
                "total_sub_episodes": data.get("totalEpisodes", 0),
                "total_dub_episodes": data.get("totalDubEpisodes", 0),  # adjust key if needed
                "episodes": episodes_list,
                "total_episodes": len(episodes_list)
            }

        return {
            "anime_id": anime_id,
            "title": "",
            "total_sub_episodes": 0,
            "total_dub_episodes": 0,
            "episodes": [],
            "total_episodes": 0
        }



    async def az_list(self, sort_option: str = "all", page: int = 1) -> Dict[str, Any]:
        """GET /api/v2/hianime/azlist/{sortOption}?page={page}"""
        endpoint = f"azlist/{sort_option}"
        resp = await self._get(endpoint, params={"page": page})
        return resp.get("data") if resp else {}

    async def qtip(self, anime_id: str) -> Dict[str, Any]:
        """GET /api/v2/hianime/qtip/{animeId}"""
        resp = await self._get(f"qtip/{anime_id}")
        return resp.get("data") if resp else {}

    async def anime_about(self, anime_id: str) -> Dict[str, Any]:
        """GET /api/v2/hianime/anime/{animeId} -> detailed about/info"""
        resp = await self._get(f"anime/{anime_id}")
        return resp.get("data") if resp else {}

    # --- Search endpoints ------------------------------------------------

    async def search(self, q: str, page: int = 1, *,
                     genres: Optional[str] = None,
                     type_: Optional[str] = None,
                     sort: Optional[str] = None,
                     season: Optional[str] = None,
                     language: Optional[str] = None,
                     status: Optional[str] = None,
                     rating: Optional[str] = None,
                     start_date: Optional[str] = None,
                     end_date: Optional[str] = None,
                     score: Optional[str] = None) -> Dict[str, Any]:
        """
        GET /api/v2/hianime/search?q={query}&page={page}&...advanced filters...
        Provide advanced params as keyword args (see README for allowed values).
        """
        params = {"q": q, "page": page}
        if genres:
            params["genres"] = genres
        if type_:
            params["type"] = type_
        if sort:
            params["sort"] = sort
        if season:
            params["season"] = season
        if language:
            params["language"] = language
        if status:
            params["status"] = status
        if rating:
            params["rating"] = rating
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if score:
            params["score"] = score

        resp = await self._get("search", params=params)
        return resp.get("data") if resp else {}

    async def search_suggestions(self, q: str) -> Dict[str, Any]:
        """GET /api/v2/hianime/search/suggestion?q={query}"""
        resp = await self._get("search/suggestion", params={"q": q})
        return resp.get("data") if resp else {}

    # --- Producer / Genre / Category ------------------------------------

    async def producer(self, name: str, page: int = 1) -> Dict[str, Any]:
        """GET /api/v2/hianime/producer/{name}?page={page}"""
        resp = await self._get(f"producer/{name}", params={"page": page})
        return resp.get("data") if resp else {}

    async def genre(self, name: str, page: int = 1) -> Dict[str, Any]:
        """GET /api/v2/hianime/genre/{name}?page={page}"""
        resp = await self._get(f"genre/{name}", params={"page": page})
        return resp.get("data") if resp else {}

    async def category(self, name: str, page: int = 1) -> Dict[str, Any]:
        """GET /api/v2/hianime/category/{name}?page={page}"""
        resp = await self._get(f"category/{name}", params={"page": page})
        return resp.get("data") if resp else {}

    # --- Schedule / Episodes --------------------------------------------

    async def schedule(self, date: str) -> Dict[str, Any]:
        """
        GET /api/v2/hianime/schedule?date={yyyy-mm-dd}
        :param date: format 'YYYY-MM-DD' (must include year)
        """
        resp = await self._get("schedule", params={"date": date})
        return resp.get("data") if resp else {}

    async def episodes(self, anime_id: str) -> Dict[str, Any]:
        """GET /api/v2/hianime/anime/{animeId}/episodes"""
        resp = await self._get(f"anime/{anime_id}/episodes")
        return resp.get("data") if resp else {}

    async def next_episode_schedule(self, anime_id: str) -> Dict[str, Any]:
        """GET /api/v2/hianime/anime/{animeId}/next-episode-schedule"""
        resp = await self._get(f"anime/{anime_id}/next-episode-schedule")
        return resp.get("data") if resp else {}

    # --- Episode servers & streaming sources ---------------------------

    async def episode_servers(self, anime_episode_id: str) -> Dict[str, Any]:
        """
        GET /api/v2/hianime/episode/servers?animeEpisodeId={id}
        e.g. anime_episode_id = "steinsgate-0-92?ep=2055"
        """
        resp = await self._get("episode/servers", params={"animeEpisodeId": anime_episode_id})
        return resp.get("data") if resp else {}

    async def is_dub_available(self, eps_title: str, anime_episode_id: str) -> bool:
        """
        Returns True if dub servers are available for the given episode.
        Requires both the anime slug and the episode id.
        """
        # Build full identifier like "lord-of-mysteries-19802?ep=141637"
        full_id = f"{eps_title}?ep={anime_episode_id}"
        
        servers = await self.episode_servers(full_id)
        dub_servers = servers.get("dub", [])
        return bool(dub_servers)


    async def episode_sources(self, anime_episode_id: str, server: Optional[str] = None,
                              category: str = "sub") -> Dict[str, Any]:
        """
        GET /api/v2/hianime/episode/sources?animeEpisodeId={id}?server={server}&category={sub|dub|raw}
        Returns the HLS (.m3u8) sources, subtitles and headers required.
        """
        params = {"animeEpisodeId": anime_episode_id, "category": category}
        if server:
            params["server"] = server
        resp = await self._get("episode/sources", params=params)
        return resp.get("data") if resp else {}

    # --- Utilities ------------------------------------------------------

    async def raw(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Fetch any arbitrary (non-method) endpoint under the base path.
        Use cautiousy if you need parts not covered by the wrapper.
        """
        resp = await self._get(endpoint, params=params)
        return resp

    # --- Video API ------------------------------------------------------

    async def video(self, ep_id: Union[str, int], language: str) -> Dict[str, Any]:
        result = await asyncio.to_thread(get_and_play_m3u8_and_vtt, ep_id, language)
        return result


# --- Example usage -----------------------------------------------------
# async def main():
#     scraper = HianimeScraper()
#     home = await scraper.home()
#     print(home.get("genres", [])[:10])
#
# if __name__ == "__main__":
#     asyncio.run(main())
