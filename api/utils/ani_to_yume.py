import re
import inspect
import aiohttp
import asyncio
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
import logging
from dataclasses import dataclass
import time

logger = logging.getLogger(__name__)

from ..models.user import get_user_by_id
from ..models.watchlist import (
    get_watchlist_entry, update_watchlist_status,
    update_watched_episodes, remove_from_watchlist, get_user_watchlist,
    get_user_watchlist_paginated, get_watchlist_stats, warm_cache, add_to_watchlist
)
from ..providers.hianime import HianimeScraper

HA = HianimeScraper()
ANILIST_GRAPHQL = "https://graphql.anilist.co"

MAX_CACHE_SIZE = 10000
search_cache: Dict[str, Any] = {}
info_cache: Dict[str, Any] = {}
id_mapping_cache: Dict[int, str] = {}

NORMALIZE_PATTERN = re.compile(r"[^\w\s]")
WHITESPACE_PATTERN = re.compile(r"\s+")

@dataclass
class BatchConfig:
    batch_size: int = 200
    concurrent_requests: int = 50
    delay_between_batches: float = 0.05
    max_retries: int = 3
    enable_caching: bool = True
    skip_failed_matches: bool = True
    max_search_candidates: int = 10
    max_anime_check: int = 5

class SyncProgress:
    def __init__(self, total: int, callback: Optional[Callable] = None):
        self.total = total
        self.processed = 0
        self.synced = 0
        self.failed = 0
        self.cached_hits = 0
        self.skipped = 0
        self.callback = callback
        self.start_time = time.time()
        self._lock = asyncio.Lock()
    
    async def update(self, synced: bool = False, failed: bool = False, cached: bool = False, skipped: bool = False):
        async with self._lock:
            self.processed += 1
            if synced:
                self.synced += 1
            if failed:
                self.failed += 1
            if cached:
                self.cached_hits += 1
            if skipped:
                self.skipped += 1
            
            if self.callback and (self.processed % 5 == 0 or self.processed == self.total):
                try:
                    if inspect.iscoroutinefunction(self.callback):
                        await self.callback(self)
                    else:
                        self.callback(self)
                except Exception as e:
                    logger.warning(f"Progress callback error: {e}")

    @property
    def percentage(self) -> float:
        return (self.processed / self.total * 100) if self.total > 0 else 0
    
    @property
    def elapsed_time(self) -> float:
        return time.time() - self.start_time
    
    @property
    def estimated_remaining(self) -> float:
        if self.processed == 0:
            return 0
        rate = self.processed / self.elapsed_time
        remaining = self.total - self.processed
        return remaining / rate if rate > 0 else 0

def _manage_cache_size(cache_dict: Dict, max_size: int):
    if len(cache_dict) > max_size:
        items_to_remove = int(max_size * 0.2)
        keys = list(cache_dict.keys())[:items_to_remove]
        for k in keys:
            cache_dict.pop(k, None)

async def _fetch_graphql(session: aiohttp.ClientSession, access_token: str, query: str, variables: Optional[dict] = None, retry_count: int = 0) -> Optional[dict]:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {"query": query, "variables": variables or {}}
    
    try:
        async with session.post(ANILIST_GRAPHQL, json=payload, headers=headers) as resp:
            if resp.status == 429:  # Rate limited
                if retry_count < 3:
                    wait_time = (2 ** retry_count) * 2
                    logger.info(f"Rate limited (429), waiting {wait_time}s before retry")
                    await asyncio.sleep(wait_time)
                    return await _fetch_graphql(session, access_token, query, variables, retry_count + 1)
                else:
                    logger.warning("Rate limited, max retries exceeded")
                    return {"error": "rate_limited"}
            
            if resp.status != 200:
                text = await resp.text()
                if resp.status >= 500 and retry_count < 3:
                    wait_time = (2 ** retry_count)
                    await asyncio.sleep(wait_time)
                    return await _fetch_graphql(session, access_token, query, variables, retry_count + 1)
                
                logger.warning(f"AniList API error {resp.status}: {text[:200]}")
                return {"error": f"status:{resp.status}", "body": text}
            
            return await resp.json()
    except asyncio.TimeoutError:
        if retry_count < 3:
            await asyncio.sleep(2 ** retry_count)
            return await _fetch_graphql(session, access_token, query, variables, retry_count + 1)
        return {"error": "timeout"}
    except Exception as e:
        if retry_count < 2: 
            await asyncio.sleep(1)
            return await _fetch_graphql(session, access_token, query, variables, retry_count + 1)
        logger.warning(f"AniList API error: {e}")
        return {"error": str(e)}

async def fetch_anilist_viewer_id(session: aiohttp.ClientSession, access_token: str) -> Optional[int]:
    query = "query { Viewer { id } }"
    r = await _fetch_graphql(session, access_token, query)
    if not r or "data" not in r or "error" in r:
        return None
    return r["data"]["Viewer"]["id"]

async def fetch_anilist_watchlist(session: aiohttp.ClientSession, access_token: str) -> List[Dict[str, Any]]:
    query = """
    query ($userId:Int) {
      MediaListCollection(userId: $userId, type: ANIME) {
        lists {
          name
          entries {
            id
            status
            progress
            score
            media {
              id
              idMal
              episodes
              siteUrl
              title { romaji english native userPreferred }
              synonyms
            }
          }
        }
      }
    }
    """
    viewer_id = await fetch_anilist_viewer_id(session, access_token)
    if not viewer_id:
        logger.error("Could not fetch viewer ID from AniList")
        return []
    
    r = await _fetch_graphql(session, access_token, query, {"userId": viewer_id})
    
    if not r or "error" in r or "data" not in r:
        logger.error(f"AniList API error or no data: {r}")
        return []
    
    media_collection = r["data"].get("MediaListCollection")
    if not media_collection:
        return []
    
    lists = media_collection.get("lists", [])
    out = []
    
    for lst in lists:
        list_name = lst.get("name", "Unknown")
        entries = lst.get("entries", [])
        for e in entries:
            if not e.get("media"):
                continue
            out.append({
                "list_name": list_name,
                "entry_id": e.get("id"),
                "status": e.get("status"),
                "progress": e.get("progress", 0),
                "score": e.get("score"),
                "media": e.get("media")
            })
    
    return out

def _normalize_name(s: Optional[str]) -> str:
    if not s:
        return ""
    s = s.lower()
    s = NORMALIZE_PATTERN.sub(" ", s)
    s = WHITESPACE_PATTERN.sub(" ", s).strip()
    return s

def _generate_title_candidates(media: Dict[str, Any], max_candidates: int = 8) -> List[str]:
    titles = []
    t = media.get("title") or {}
    priority_titles = []
    if t.get("userPreferred"):
        priority_titles.append(t["userPreferred"])
    if t.get("english") and t.get("english") != t.get("userPreferred"):
        priority_titles.append(t["english"])
    for k in ("romaji", "native"):
        v = t.get(k)
        if v and v not in priority_titles:
            titles.append(v)
    
    synonyms = media.get("synonyms") or []
    titles.extend(synonyms[:2])
    all_titles = priority_titles + titles
    
    seen = set()
    result = []
    for title in all_titles:
        if title and title not in seen:
            seen.add(title)
            result.append(title)
            if len(result) >= max_candidates:
                break
    return result

async def call_maybe_async(func: Callable, *args, **kwargs) -> Any:
    try:
        if inspect.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        return await asyncio.to_thread(func, *args, **kwargs)
    except Exception as e:
        logger.warning(f"call_maybe_async error: {e}")
        return None

async def check_existing_watchlist_entry(user_id: str, anilist_id: int, mal_id: Optional[int] = None) -> bool:
    try:
        from ..models.watchlist import watchlist_collection
        
        if anilist_id in id_mapping_cache:
            hianime_id = id_mapping_cache[anilist_id]
            existing = await call_maybe_async(
                watchlist_collection.find_one,
                {"user_id": user_id, "anime_id": hianime_id}
            )
            if existing:
                return True

        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$project": {"anime_id": 1}}
        ]
        existing_entries = await call_maybe_async(list, watchlist_collection.aggregate(pipeline))
        
        if not existing_entries:
            return False
        
        for entry in existing_entries:
            anime_id = entry.get("anime_id")
            if anime_id and anime_id in info_cache:
                cached_info = info_cache[anime_id]
                if (cached_info.get("anilistId") == anilist_id or 
                    (mal_id and cached_info.get("malId") == mal_id)):
                    id_mapping_cache[anilist_id] = anime_id
                    return True
        return False
    except Exception:
        return False

async def get_hianime_link_with_retry(media: Dict[str, Any], config: BatchConfig) -> Optional[Dict[str, Any]]:
    anilist_id = media.get("id")
    mal_id = media.get("idMal")
    
    if config.enable_caching and anilist_id in id_mapping_cache:
        hianime_id = id_mapping_cache[anilist_id]
        if hianime_id in info_cache:
            cached_info = info_cache[hianime_id]
            return {
                "id": hianime_id,
                "name": cached_info.get("title"),
                "poster": cached_info.get("poster"),
                "link": f"/anime/{hianime_id}"
            }
    
    candidates = _generate_title_candidates(media, config.max_search_candidates)
    
    for attempt in range(config.max_retries + 1):
        for title in candidates:
            try:
                if attempt > 0:
                    wait_time = (2 ** (attempt - 1)) * 0.5
                    await asyncio.sleep(wait_time)
                
                cache_key = _normalize_name(title)
                if config.enable_caching and cache_key in search_cache:
                    results = search_cache[cache_key]
                else:
                    results = await call_maybe_async(HA.search, title)
                    if config.enable_caching and results:
                        search_cache[cache_key] = results
                        _manage_cache_size(search_cache, MAX_CACHE_SIZE)
                
                if not results:
                    continue
                
                animes = results.get("animes") if isinstance(results, dict) else results
                if not animes:
                    continue
                
                for anime in animes[:config.max_anime_check]:
                    anime_id = anime.get("id")
                    if not anime_id:
                        continue
                        
                    if config.enable_caching and anime_id in info_cache:
                        info_data = info_cache[anime_id]
                    else:
                        info = await call_maybe_async(HA.get_anime_info, anime_id)
                        if not info:
                            continue
                        info_data = info.get("info") if isinstance(info, dict) and "info" in info else info
                        if config.enable_caching and info_data:
                            info_cache[anime_id] = info_data
                            _manage_cache_size(info_cache, MAX_CACHE_SIZE)
                    
                    if not info_data:
                        continue
                     
                    if (info_data.get("anilistId") == anilist_id or 
                        (mal_id and info_data.get("malId") == mal_id)):
                        if config.enable_caching:
                            id_mapping_cache[anilist_id] = anime_id
                        return {
                            "id": anime_id,
                            "name": info_data.get("title") or anime.get("name"),
                            "poster": info_data.get("poster") or anime.get("poster"),
                            "link": f"/anime/{anime_id}"
                        }
            except Exception as e:
                logger.debug("Search attempt failed for '%s': %s", title, e)
                if attempt < config.max_retries:
                    await asyncio.sleep(0.5)
                break
    return None

async def process_single_entry(user_id: str, entry: Dict[str, Any], 
                               progress: SyncProgress, config: BatchConfig, 
                               semaphore: asyncio.Semaphore) -> Optional[Dict[str, Any]]:
    # Acquire semaphore for this specific entry processing task
    async with semaphore:
        try:
            media = entry["media"]
            anilist_id = media.get("id")
            mal_id = media.get("idMal")
            
            if anilist_id and await check_existing_watchlist_entry(user_id, anilist_id, mal_id):
                await progress.update(skipped=True)
                return {
                    "skipped": True,
                    "reason": "already_exists",
                    "anilist_id": anilist_id,
                    "anime_title": media.get("title", {}).get("userPreferred")
                }
            
            hianime = await get_hianime_link_with_retry(media, config)
            if not hianime:
                await progress.update(failed=True)
                return {
                    "failed": True,
                    "reason": "no_match_found",
                    "anilist_id": anilist_id,
                    "titles": _generate_title_candidates(media, 3)
                }
            
            status_mapping = {
                'CURRENT': 'watching',
                'COMPLETED': 'completed',
                'PAUSED': 'paused',
                'DROPPED': 'dropped',
                'PLANNING': 'plan_to_watch'
            }
            
            anilist_status = entry.get("status", "CURRENT")
            local_status = status_mapping.get(anilist_status, 'watching')
            watched_episodes = entry.get("progress", 0)
            
            result = await call_maybe_async(add_to_watchlist,
                user_id=user_id,
                anime_id=hianime["id"],
                anime_title=hianime["name"],
                status=local_status,
                watched_episodes=watched_episodes,
            )
            
            if result:
                await progress.update(synced=True)
                return {
                    "success": True,
                    "anime_id": hianime["id"],
                    "anime_title": hianime["name"],
                    "status": local_status
                }
            else:
                await progress.update(failed=True)
                return {
                    "failed": True,
                    "reason": "database_error",
                    "anilist_id": anilist_id
                }
        except Exception as e:
            logger.warning(f"Failed entry {entry.get('entry_id')}: {e}")
            await progress.update(failed=True)
            return {"failed": True, "reason": "exception", "error": str(e)}

async def sync_anilist_watchlist_to_local(user_id: str, access_token: str, 
                                          progress_callback=None, config: BatchConfig = None):
    if config is None:
        config = BatchConfig()
    
    timeout = aiohttp.ClientTimeout(total=45, connect=10)
    connector = aiohttp.TCPConnector(limit=20, ttl_dns_cache=300)
    session = aiohttp.ClientSession(timeout=timeout, connector=connector)
    
    concurrency = getattr(config, 'concurrent_requests', 5)
    sem = asyncio.Semaphore(concurrency)
    
    try:
        user = await call_maybe_async(get_user_by_id, user_id)
        if not user:
            return {"error": "User not found"}

        logger.info(f"Starting AniList sync for user {user_id}")
        
        watchlist = await fetch_anilist_watchlist(session, access_token)
        
        if not watchlist:
            viewer_id = await fetch_anilist_viewer_id(session, access_token)
            if viewer_id:
                 return {
                    "error": "AniList watchlist is empty or private.",
                    "synced_count": 0, "failed_count": 0, "total_count": 0
                }
            return {"error": "Failed to connect to AniList"}

        progress = SyncProgress(total=len(watchlist), callback=progress_callback)
        
        all_results = []
        chunk_size = config.batch_size
        
        for i in range(0, len(watchlist), chunk_size):
            chunk = watchlist[i:i + chunk_size]
            
            tasks = []
            for entry in chunk:
                tasks.append(process_single_entry(user_id, entry, progress, config, sem))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for res in results:
                if isinstance(res, Exception):
                    logger.error(f"Task exception: {res}")
                    all_results.append({"failed": True, "reason": "task_exception", "error": str(res)})
                else:
                    all_results.append(res)
            
            if i + chunk_size < len(watchlist):
                await asyncio.sleep(config.delay_between_batches)
        
        synced = [r for r in all_results if r and r.get("success")]
        skipped = [r for r in all_results if r and r.get("skipped")]
        failed = [r for r in all_results if r and r.get("failed")]
        
        success_count = len(synced) + len(skipped)
        success_rate = (success_count / len(watchlist) * 100) if watchlist else 0

        logger.info(f"Sync completed for user {user_id}: {len(synced)} synced, {len(skipped)} skipped, {len(failed)} failed")
        
        return {
            "synced_count": len(synced),
            "skipped_count": len(skipped),
            "failed_count": len(failed),
            "total_count": len(watchlist),
            "success_rate": f"{success_rate:.1f}%",
            "elapsed_time": f"{progress.elapsed_time:.1f}s"
        }
    
    except Exception as e:
        logger.exception(f"Sync failed: {e}")
        return {"error": str(e)}
    finally:
        if not session.closed:
            await session.close()

def clear_caches():
    global search_cache, info_cache, id_mapping_cache
    search_cache.clear()
    info_cache.clear()
    id_mapping_cache.clear()
