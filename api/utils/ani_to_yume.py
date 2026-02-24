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
from .id_cache import (
    lookup_hianime_id, save_id_mapping, preload_to_memory,
    get_ids_for_hianime,
)

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
        # Call sync functions directly instead of asyncio.to_thread
        # PyMongo operations are fast blocking I/O and NOT thread-safe
        # (cursors can't be consumed across threads), so wrapping them
        # in to_thread causes hangs / deadlocks when we are already
        # running inside a background thread via threading.Thread.
        return func(*args, **kwargs)
    except Exception as e:
        logger.warning(f"call_maybe_async error: {e}")
        return None

async def check_existing_watchlist_entry(existing_anime_ids: set, anilist_id: int, mal_id: Optional[int] = None) -> bool:
    """Check if an AniList entry already exists in the user's local watchlist.
    Uses a pre-built set of existing anime_ids for O(1) lookup."""
    try:
        # Check by anilist_id mapping
        if anilist_id in id_mapping_cache:
            hianime_id = id_mapping_cache[anilist_id]
            if hianime_id in existing_anime_ids:
                return True

        # Check by persistent cache (local JSON → MongoDB)
        persistent_hid = lookup_hianime_id(anilist_id or 0, mal_id or 0)
        if persistent_hid and persistent_hid in existing_anime_ids:
            # Also populate in-memory cache for future lookups
            if anilist_id:
                id_mapping_cache[anilist_id] = persistent_hid
            return True

        return False
    except Exception:
        return False

async def get_hianime_link_with_retry(media: Dict[str, Any], config: BatchConfig) -> Optional[Dict[str, Any]]:
    anilist_id = media.get("id")
    mal_id = media.get("idMal")
    
    # 1) Check in-memory cache first (fastest)
    if config.enable_caching and anilist_id in id_mapping_cache:
        hianime_id = id_mapping_cache[anilist_id]
        # Return from cache — use info_cache for title/poster if available,
        # otherwise fall back to AniList media title
        cached_info = info_cache.get(hianime_id, {}) if config.enable_caching else {}
        return {
            "id": hianime_id,
            "name": cached_info.get("title") or media.get("title", {}).get("userPreferred", ""),
            "poster": cached_info.get("poster", ""),
            "link": f"/anime/{hianime_id}"
        }

    # 2) Check persistent MongoDB/JSON ID cache
    persistent_hid = lookup_hianime_id(anilist_id or 0, mal_id or 0)
    if persistent_hid:
        # Found in persistent cache — populate in-memory cache too
        if config.enable_caching and anilist_id:
            id_mapping_cache[anilist_id] = persistent_hid
        cached = get_ids_for_hianime(persistent_hid)
        title = cached.get("title", "") if cached else ""
        return {
            "id": persistent_hid,
            "name": title or media.get("title", {}).get("userPreferred", ""),
            "poster": "",
            "link": f"/anime/{persistent_hid}"
        }
    
    candidates = _generate_title_candidates(media, config.max_search_candidates)
    
    for attempt in range(config.max_retries + 1):
        for title in candidates:
            try:
                if attempt > 0:
                    await asyncio.sleep(0.3)
                
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
                        # Save to persistent cache for future syncs
                        save_id_mapping(
                            hianime_id=anime_id,
                            anilist_id=info_data.get("anilistId") or 0,
                            mal_id=info_data.get("malId") or 0,
                            title=info_data.get("title") or anime.get("name") or "",
                        )
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
                               semaphore: asyncio.Semaphore,
                               existing_anime_ids: set = None) -> Optional[Dict[str, Any]]:
    # Acquire semaphore for this specific entry processing task
    async with semaphore:
        try:
            media = entry["media"]
            anilist_id = media.get("id")
            mal_id = media.get("idMal")
            
            # Timeout per entry so one slow search doesn't block everything
            try:
                hianime = await asyncio.wait_for(
                    get_hianime_link_with_retry(media, config),
                    timeout=15.0
                )
            except asyncio.TimeoutError:
                logger.warning("Timeout searching for anilist_id=%s", anilist_id)
                hianime = None
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
        
        # --- Helper to send phase updates directly ---
        def _send_phase(message, processed=0, total=0, pct=0, **extra):
            if progress_callback:
                class _P:
                    pass
                p = _P()
                p.processed = processed
                p.total = total
                p.synced = extra.get("synced", 0)
                p.skipped = extra.get("skipped", 0)
                p.failed = extra.get("failed", 0)
                p.percentage = pct
                p.message = message
                p.cached_hits = extra.get("cached_hits", 0)
                try:
                    progress_callback(p)
                except Exception:
                    pass
        
        _send_phase("Fetching your AniList watchlist...", pct=2)
        
        watchlist = await fetch_anilist_watchlist(session, access_token)
        
        if not watchlist:
            viewer_id = await fetch_anilist_viewer_id(session, access_token)
            if viewer_id:
                 return {
                    "error": "AniList watchlist is empty or private.",
                    "synced_count": 0, "failed_count": 0, "total_count": 0
                }
            return {"error": "Failed to connect to AniList"}

        total = len(watchlist)
        progress = SyncProgress(total=total, callback=progress_callback)
        
        _send_phase(f"Found {total} anime on AniList. Loading cache...", total=total, pct=5)
        
        # Preload persistent ID cache into memory for fast lookups
        try:
            anilist_ids, _ = preload_to_memory()
            id_mapping_cache.update(anilist_ids)
            logger.info("Preloaded %d AniList ID mappings", len(anilist_ids))
            _send_phase(f"Loaded {len(anilist_ids)} cached IDs. Matching anime...", total=total, pct=10)
        except Exception as e:
            logger.warning("Failed to preload ID cache: %s", e)
        
        # Pre-fetch user's existing watchlist ONCE
        existing_anime_ids = set()
        try:
            user_watchlist = await call_maybe_async(get_user_watchlist, user_id)
            if user_watchlist:
                for wl_entry in user_watchlist:
                    aid = wl_entry.get("anime_id")
                    if aid:
                        existing_anime_ids.add(aid)
        except Exception as e:
            logger.warning("Failed to pre-fetch watchlist: %s", e)
        
        all_results = []
        needs_api = []
        
        # === FAST PATH: resolve cache hits in memory ===
        from ..models.watchlist import watchlist_collection
        from ..models.watchlist import clear_user_cache
        
        status_mapping = {
            'CURRENT': 'watching', 'COMPLETED': 'completed',
            'PAUSED': 'paused', 'DROPPED': 'dropped',
            'PLANNING': 'plan_to_watch'
        }
        
        cached_updates = {}
        for i, entry in enumerate(watchlist):
            media = entry.get("media", {})
            anilist_id = media.get("id")
            mal_id = media.get("idMal")
            
            hianime_id = None
            if config.enable_caching and anilist_id and anilist_id in id_mapping_cache:
                hianime_id = id_mapping_cache[anilist_id]
            if not hianime_id:
                hianime_id = lookup_hianime_id(anilist_id or 0, mal_id or 0)
            
            if hianime_id:
                cached = get_ids_for_hianime(hianime_id)
                title = (cached.get("title", "") if cached else "") or media.get("title", {}).get("userPreferred", "")
                local_status = status_mapping.get(entry.get("status", "CURRENT"), "watching")
                watched_episodes = entry.get("progress", 0)
                
                cached_updates[hianime_id] = {
                    "anime_id": hianime_id,
                    "anime_title": title,
                    "status": local_status,
                    "watched_episodes": watched_episodes,
                }
                all_results.append({"success": True, "anime_id": hianime_id, "anime_title": title, "status": local_status})
            else:
                needs_api.append(entry)
            
            # Send progress every 50 entries during resolution
            if (i + 1) % 50 == 0 or i == total - 1:
                pct = 10 + int((i + 1) / total * 40)  # 10% to 50%
                _send_phase(
                    f"Matching: {i+1}/{total} — {len(cached_updates)} found in cache, {len(needs_api)} needs search",
                    processed=i+1, total=total, pct=pct,
                    cached_hits=len(cached_updates)
                )
        
        logger.info("Cache resolved: %d hits, %d need API search", len(cached_updates), len(needs_api))
        
        # Step 2: merge with existing watchlist and write ONCE
        if cached_updates:
            _send_phase(
                f"Writing {len(cached_updates)} anime to your watchlist...",
                processed=len(cached_updates), total=total, pct=55,
                synced=len(cached_updates), cached_hits=len(cached_updates)
            )
            
            now = datetime.utcnow()
            existing_map = {}
            for wl_entry in (user_watchlist or []):
                aid = wl_entry.get("anime_id")
                if aid:
                    existing_map[aid] = wl_entry
            
            for anime_id, update in cached_updates.items():
                existing_entry = existing_map.get(anime_id, {})
                existing_map[anime_id] = {
                    "anime_id": anime_id,
                    "anime_title": update["anime_title"] or existing_entry.get("anime_title", ""),
                    "status": update["status"],
                    "watched_episodes": update["watched_episodes"],
                    "updated_at": now,
                }
            
            merged_watchlist = list(existing_map.values())
            try:
                watchlist_collection.update_one(
                    {"_id": user_id},
                    {
                        "$set": {"watchlist": merged_watchlist},
                        "$setOnInsert": {"created_at": now},
                    },
                    upsert=True,
                )
                clear_user_cache(user_id)
                
                # Update SyncProgress counts for final report
                progress.synced = len(cached_updates)
                progress.cached_hits = len(cached_updates)
                progress.processed = len(cached_updates)
                    
                logger.info("Bulk wrote %d entries to watchlist in 1 DB operation", len(cached_updates))
                
                _send_phase(
                    f"✓ {len(cached_updates)} anime synced from cache!" + 
                    (f" Searching for {len(needs_api)} remaining..." if needs_api else ""),
                    processed=len(cached_updates), total=total, pct=60,
                    synced=len(cached_updates), cached_hits=len(cached_updates)
                )
            except Exception as e:
                logger.error("Bulk watchlist write failed: %s", e)
                progress.failed = len(cached_updates)
                _send_phase(f"Error writing to database: {e}", pct=55)
        
        # === SLOW PATH: process cache misses via API search ===
        if needs_api:
            _send_phase(
                f"Searching HiAnime for {len(needs_api)} anime not in cache...",
                processed=len(cached_updates), total=total, pct=60,
                synced=progress.synced
            )
            chunk_size = config.batch_size
            for i in range(0, len(needs_api), chunk_size):
                chunk = needs_api[i:i + chunk_size]
                tasks = [process_single_entry(user_id, entry, progress, config, sem, existing_anime_ids) for entry in chunk]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for res in results:
                    if isinstance(res, Exception):
                        logger.error(f"Task exception: {res}")
                        all_results.append({"failed": True, "reason": "task_exception", "error": str(res)})
                    else:
                        all_results.append(res)
                
                # Progress update during API search
                api_done = min(i + chunk_size, len(needs_api))
                api_pct = 60 + int(api_done / len(needs_api) * 35)  # 60% to 95%
                _send_phase(
                    f"Searching: {api_done}/{len(needs_api)} remaining anime...",
                    processed=len(cached_updates) + api_done, total=total, pct=api_pct,
                    synced=progress.synced, failed=progress.failed
                )
                
                if i + chunk_size < len(needs_api):
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
            "cached_hits": progress.cached_hits,
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
