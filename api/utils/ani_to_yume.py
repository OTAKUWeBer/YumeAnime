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
from ..scrapers.hianime import HianimeScraper

HA = HianimeScraper()
ANILIST_GRAPHQL = "https://graphql.anilist.co"
CONCURRENT_REQUESTS = 500

_semaphore = None
def get_semaphore():
    global _semaphore
    loop = asyncio.get_running_loop()
    if _semaphore is None or _semaphore._loop is not loop:
        _semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
    return _semaphore

MAX_CACHE_SIZE = 10000
search_cache: Dict[str, Any] = {}
info_cache: Dict[str, Any] = {}
id_mapping_cache: Dict[int, str] = {}

NORMALIZE_PATTERN = re.compile(r"[^\w\s]")
WHITESPACE_PATTERN = re.compile(r"\s+")

@dataclass
class BatchConfig:
    batch_size: int = 2000
    delay_between_batches: float = 0.0
    max_retries: int = 2
    enable_caching: bool = True
    skip_failed_matches: bool = True
    max_search_candidates: int = 10
    max_anime_check: int = 10

class SyncProgress:
    def __init__(self, total: int, callback: Optional[Callable] = None):
        self.total = total
        self.processed = 0
        self.synced = 0
        self.failed = 0
        self.cached_hits = 0
        self.skipped = 0
        self.callback = callback
        self.start_time = time.time()# Key changes for reliability:
# 1. Better timeout handling for AniList API
# 2. Improved error detection for empty watchlists
# 3. More robust session management
# 4. Better retry logic with exponential backoff

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
from ..scrapers.hianime import HianimeScraper

HA = HianimeScraper()
ANILIST_GRAPHQL = "https://graphql.anilist.co"
CONCURRENT_REQUESTS = 500
semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)

MAX_CACHE_SIZE = 10000
search_cache: Dict[str, Any] = {}
info_cache: Dict[str, Any] = {}
id_mapping_cache: Dict[int, str] = {}

NORMALIZE_PATTERN = re.compile(r"[^\w\s]")
WHITESPACE_PATTERN = re.compile(r"\s+")

@dataclass
class BatchConfig:
    batch_size: int = 2000
    delay_between_batches: float = 0.0
    max_retries: int = 2  # Increased from 1
    enable_caching: bool = True
    skip_failed_matches: bool = True
    max_search_candidates: int = 10
    max_anime_check: int = 10

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
        self.lock = asyncio.Lock()
    
    async def update(self, synced: bool = False, failed: bool = False, cached: bool = False, skipped: bool = False):
        async with self.lock:
            self.processed += 1
            if synced:
                self.synced += 1
            if failed:
                self.failed += 1
            if cached:
                self.cached_hits += 1
            if skipped:
                self.skipped += 1
            
            if self.callback and (self.processed % 50 == 0 or self.processed == self.total):
                try:
                    self.callback(self)
                except Exception as e:
                    logger.warning(f"Progress callback error: {e}")

    async def update(self, synced: bool = False, failed: bool = False, cached: bool = False, skipped: bool = False):
        lock = asyncio.Lock()
        async with lock:
            self.processed += 1
            if synced:
                self.synced += 1
            if failed:
                self.failed += 1
            if cached:
                self.cached_hits += 1
            if skipped:
                self.skipped += 1

            if self.callback and (self.processed % 50 == 0 or self.processed == self.total):
                try:
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

_http_session: Optional[aiohttp.ClientSession] = None

async def get_http_session():
    global _http_session
    if _http_session is None or _http_session.closed:
        # FIX: Increased timeout for AniList API reliability
        timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=20)
        connector = aiohttp.TCPConnector(
            limit=CONCURRENT_REQUESTS,
            limit_per_host=50,  # Reduced to be more conservative
            ttl_dns_cache=600,
            use_dns_cache=True,
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )
        _http_session = aiohttp.ClientSession(timeout=timeout, connector=connector)
    return _http_session

async def close_http_session():
    global _http_session
    if _http_session and not _http_session.closed:
        await _http_session.close()

def _manage_cache_size(cache_dict: Dict, max_size: int):
    if len(cache_dict) > max_size:
        items_to_remove = len(cache_dict) - int(max_size * 0.8)
        keys_to_remove = list(cache_dict.keys())[:items_to_remove]
        for key in keys_to_remove:
            cache_dict.pop(key, None)

# FIX: Better error handling and retry logic for AniList API
async def _fetch_graphql(access_token: str, query: str, variables: Optional[dict] = None, retry_count: int = 0) -> Optional[dict]:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {"query": query, "variables": variables or {}}
    
    try:
        session = await get_http_session()
        async with session.post(ANILIST_GRAPHQL, json=payload, headers=headers) as resp:
            if resp.status == 429:  # Rate limited
                if retry_count < 2:
                    wait_time = (2 ** retry_count) * 2  # Exponential backoff: 2s, 4s
                    logger.info(f"Rate limited, waiting {wait_time}s before retry")
                    await asyncio.sleep(wait_time)
                    return await _fetch_graphql(access_token, query, variables, retry_count + 1)
                else:
                    logger.warning("Rate limited, max retries exceeded")
                    return {"error": "rate_limited"}
            
            if resp.status != 200:
                text = await resp.text()
                logger.warning(f"AniList API error {resp.status}: {text[:200]}")
                
                # Retry on server errors
                if resp.status >= 500 and retry_count < 2:
                    wait_time = (2 ** retry_count)
                    await asyncio.sleep(wait_time)
                    return await _fetch_graphql(access_token, query, variables, retry_count + 1)
                
                return {"error": f"status:{resp.status}", "body": text}
            
            return await resp.json()
    except asyncio.TimeoutError:
        logger.warning(f"AniList API timeout (attempt {retry_count + 1})")
        if retry_count < 2:
            await asyncio.sleep(2 ** retry_count)
            return await _fetch_graphql(access_token, query, variables, retry_count + 1)
        return {"error": "timeout"}
    except Exception as e:
        logger.warning(f"AniList API error: {e}")
        if retry_count < 1:  # One retry for other errors
            await asyncio.sleep(1)
            return await _fetch_graphql(access_token, query, variables, retry_count + 1)
        return {"error": str(e)}

async def fetch_anilist_viewer_id(access_token: str) -> Optional[int]:
    query = "query { Viewer { id } }"
    r = await _fetch_graphql(access_token, query)
    if not r or "data" not in r or "error" in r:
        logger.warning(f"Failed to fetch viewer ID: {r}")
        return None
    return r["data"]["Viewer"]["id"]

# FIX: Better validation for empty watchlist detection
async def fetch_anilist_watchlist(access_token: str) -> List[Dict[str, Any]]:
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
    viewer_id = await fetch_anilist_viewer_id(access_token)
    if not viewer_id:
        logger.error("Could not fetch viewer ID from AniList")
        return []
    
    r = await _fetch_graphql(access_token, query, {"userId": viewer_id})
    
    # FIX: Better error detection
    if not r:
        logger.error("No response from AniList API")
        return []
    
    if "error" in r:
        logger.error(f"AniList API error: {r['error']}")
        return []
    
    if "data" not in r:
        logger.error(f"No data in AniList response: {r}")
        return []
    
    media_collection = r["data"].get("MediaListCollection")
    if not media_collection:
        logger.warning("MediaListCollection is None - user may have private lists or no anime entries")
        return []
    
    lists = media_collection.get("lists", [])
    if not lists:
        logger.warning("No lists found in MediaListCollection")
        return []
    
    out = []
    total_entries = 0
    
    for lst in lists:
        list_name = lst.get("name", "Unknown")
        entries = lst.get("entries", [])
        total_entries += len(entries)
        
        logger.debug(f"Processing list '{list_name}' with {len(entries)} entries")
        
        for e in entries:
            if not e.get("media"):
                logger.warning(f"Entry {e.get('id')} has no media data")
                continue
                
            out.append({
                "list_name": list_name,
                "entry_id": e.get("id"),
                "status": e.get("status"),
                "progress": e.get("progress", 0),
                "score": e.get("score"),
                "media": e.get("media")
            })
    
    logger.info(f"Fetched {len(out)} entries from {len(lists)} lists (total raw entries: {total_entries})")
    
    # FIX: Better empty detection - if we have lists but no valid entries, that's suspicious
    if lists and total_entries > 0 and len(out) == 0:
        logger.warning("Found lists with entries but no valid media data - possible API issue")
    
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
            {"$project": {"anime_id": 1, "anime_title": 1}}
        ]
        
        existing_entries = await call_maybe_async(
            list, watchlist_collection.aggregate(pipeline)
        )
        
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
    except Exception as e:
        logger.warning(f"Error checking existing entry: {e}")
        return False

# FIX: Better retry logic with exponential backoff
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
                    # Exponential backoff
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
                logger.warning("Search failed for '%s': %s", title, e)
                if attempt < config.max_retries:
                    await asyncio.sleep(0.5)
                break
    return None

async def process_single_entry(user_id: str, entry: Dict[str, Any], 
                               progress: SyncProgress, config: BatchConfig) -> Optional[Dict[str, Any]]:
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
                "mal_id": mal_id
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
                "user_id": user_id,
                "anime_id": hianime["id"],
                "anime_title": hianime["name"],
                "anilist_id": media.get("id"),
                "mal_id": media.get("idMal"),
                "status": local_status,
                "progress": watched_episodes,
                "score": entry.get("score"),
                "hianime": hianime,
                "synced_at": datetime.utcnow(),
            }
        else:
            await progress.update(failed=True)
            return {
                "failed": True,
                "reason": "database_error",
                "anilist_id": anilist_id,
                "anime_title": hianime["name"]
            }
    except Exception as e:
        logger.warning(f"Failed entry {entry.get('entry_id', 'unknown')}: {e}")
        await progress.update(failed=True)
        return {
            "failed": True,
            "reason": "exception",
            "error": str(e),
            "anilist_id": entry.get("media", {}).get("id")
        }

async def process_single_entry_safe(user_id: str, entry: Dict[str, Any], 
                                    progress: SyncProgress, config: BatchConfig):
    async with semaphore:
        return await process_single_entry(user_id, entry, progress, config)

async def process_batch(user_id: str, batch: List[Dict], progress: SyncProgress, config: BatchConfig) -> List[Any]:
    tasks = [process_single_entry_safe(user_id, entry, progress, config) for entry in batch]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.warning(f"Batch entry {i} exception: {result}")
            processed_results.append({
                "failed": True,
                "reason": "batch_exception",
                "error": str(result)
            })
        else:
            processed_results.append(result)
    
    return processed_results

# FIX: Better error reporting and validation
async def sync_anilist_watchlist_to_local(user_id: str, access_token: str, 
                                          progress_callback=None, config: BatchConfig = None):
    if config is None:
        config = BatchConfig()
    
    try:
        user = await call_maybe_async(get_user_by_id, user_id)
        if not user:
            return {"error": "User not found", "synced_count": 0, "failed_count": 0, "total_count": 0}

        logger.info(f"Starting AniList sync for user {user_id}")
        watchlist = await fetch_anilist_watchlist(access_token)
        
        # FIX: Better empty watchlist detection and reporting
        if not watchlist:
            # Try to determine if it's really empty or an API issue
            viewer_id = await fetch_anilist_viewer_id(access_token)
            if viewer_id:
                logger.warning(f"Empty watchlist for user {user_id} (AniList ID: {viewer_id}) - may have private lists or no anime entries")
                return {
                    "error": "AniList watchlist appears to be empty or private. Please check your AniList privacy settings.",
                    "synced_count": 0,
                    "failed_count": 0,
                    "total_count": 0,
                    "success_rate": "0%",
                    "anilist_user_id": viewer_id
                }
            else:
                return {
                    "error": "Failed to access AniList account. Please check your connection and try again.",
                    "synced_count": 0,
                    "failed_count": 0,
                    "total_count": 0,
                    "success_rate": "0%"
                }

        logger.info(f"Retrieved {len(watchlist)} entries from AniList")
        progress = SyncProgress(total=len(watchlist), callback=progress_callback)
        
        batch_size = min(config.batch_size, 500)
        all_results = []
        
        for i in range(0, len(watchlist), batch_size):
            batch = watchlist[i:i + batch_size]
            logger.debug(f"Processing batch {i//batch_size + 1}: entries {i+1}-{min(i+batch_size, len(watchlist))}")
            
            batch_results = await process_batch(user_id, batch, progress, config)
            all_results.extend(batch_results)
            
            if i + batch_size < len(watchlist):
                await asyncio.sleep(0.1)
        
        synced = []
        skipped = []
        failed = []
        
        for result in all_results:
            if not result:
                failed.append({"failed": True, "reason": "no_result"})
            elif result.get("success"):
                synced.append(result)
            elif result.get("skipped"):
                skipped.append(result)
            elif result.get("failed"):
                failed.append(result)
            else:
                failed.append({"failed": True, "reason": "unknown_result", "result": result})

        success_count = len(synced) + len(skipped)
        success_rate = (success_count / len(watchlist) * 100) if watchlist else 0

        logger.info(f"Sync completed for user {user_id}: {len(synced)} synced, {len(skipped)} skipped, {len(failed)} failed")

        return {
            "synced_count": len(synced),
            "skipped_count": len(skipped),
            "failed_count": len(failed),
            "total_count": len(watchlist),
            "success_rate": f"{success_rate:.1f}%",
            "cache_hits": progress.cached_hits,
            "elapsed_time": f"{progress.elapsed_time:.1f}s",
            "synced": synced[:10],
            "skipped": skipped[:10],
            "failed_sample": failed[:10]
        }
    
    except Exception as e:
        logger.error(f"Sync process failed for user {user_id}: {e}", exc_info=True)
        return {
            "error": f"Sync process failed: {str(e)}",
            "synced_count": 0,
            "failed_count": 0,
            "total_count": 0,
            "success_rate": "0%"
        }
    finally:
        await close_http_session()

def clear_caches():
    global search_cache, info_cache, id_mapping_cache
    search_cache.clear()
    info_cache.clear()
    id_mapping_cache.clear()

async def fast_sync_example(user_id: str, access_token: str):
    config = BatchConfig(
        batch_size=1000,
        delay_between_batches=0.1,
        max_retries=2,  # Increased
        max_search_candidates=6,
        max_anime_check=3
    )
    
    def progress_callback(progress: SyncProgress):
        print(f"Progress: {progress.percentage:.1f}% ({progress.processed}/{progress.total}) "
              f"Synced: {progress.synced}, Skipped: {progress.skipped}, Failed: {progress.failed}, "
              f"Cached: {progress.cached_hits}, ETA: {progress.estimated_remaining:.1f}s")
    
    result = await sync_anilist_watchlist_to_local(user_id, access_token, progress_callback, config)
    return result
