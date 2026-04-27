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
    get_user_watchlist, watchlist_collection
)

ANILIST_GRAPHQL = "https://graphql.anilist.co"

@dataclass
class BatchConfig:
    batch_size: int = 200
    concurrent_requests: int = 50
    delay_between_batches: float = 0.05
    max_retries: int = 3
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

async def call_maybe_async(func: Callable, *args, **kwargs) -> Any:
    try:
        if inspect.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        return func(*args, **kwargs)
    except Exception as e:
        logger.warning(f"call_maybe_async error: {e}")
        return None

async def sync_anilist_watchlist_to_local(user_id: str, access_token: str, 
                                          progress_callback=None, config: BatchConfig = None):
    if config is None:
        config = BatchConfig()
    
    timeout = aiohttp.ClientTimeout(total=45, connect=10)
    connector = aiohttp.TCPConnector(limit=20, ttl_dns_cache=300)
    session = aiohttp.ClientSession(timeout=timeout, connector=connector)
    
    try:
        user = await call_maybe_async(get_user_by_id, user_id)
        if not user:
            return {"error": "User not found"}

        logger.info(f"Starting AniList sync for user {user_id}")
        
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
        
        _send_phase("Fetching your AniList watchlist...", pct=10)
        
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
        
        _send_phase(f"Found {total} anime on AniList. Updating local watchlist...", total=total, pct=40)
        
        # Pre-fetch user's existing watchlist
        existing_map = {}
        try:
            user_watchlist = await call_maybe_async(get_user_watchlist, user_id)
            if user_watchlist:
                for wl_entry in user_watchlist:
                    aid = wl_entry.get("anime_id")
                    if aid:
                        existing_map[aid] = wl_entry
        except Exception as e:
             logger.warning("Failed to pre-fetch watchlist: %s", e)
             
        status_mapping = {
            'CURRENT': 'watching', 'COMPLETED': 'completed',
            'PAUSED': 'paused', 'DROPPED': 'dropped',
            'PLANNING': 'plan_to_watch'
        }
        
        now = datetime.utcnow()
        updates_count = 0
        
        for entry in watchlist:
            media = entry.get("media", {})
            anilist_id = media.get("id")
            if not anilist_id:
                continue
                
            anime_id = str(anilist_id)
            title = media.get("title", {}).get("userPreferred") or media.get("title", {}).get("english") or media.get("title", {}).get("romaji", "Unknown")
            local_status = status_mapping.get(entry.get("status", "CURRENT"), "watching")
            watched_episodes = entry.get("progress", 0)
            
            existing_entry = existing_map.get(anime_id, {})
            existing_map[anime_id] = {
                "anime_id": anime_id,
                "anime_title": title or existing_entry.get("anime_title", ""),
                "status": local_status,
                "watched_episodes": watched_episodes,
                "updated_at": now,
            }
            updates_count += 1
            
        merged_watchlist = list(existing_map.values())
        
        _send_phase(f"Saving {updates_count} anime to your YumeAnime watchlist...", total=total, pct=80)
        
        try:
            watchlist_collection.update_one(
                {"_id": user_id},
                {
                    "$set": {"watchlist": merged_watchlist},
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
            )
            progress.synced = updates_count
            progress.processed = updates_count
            
        except Exception as e:
            logger.error("Bulk watchlist write failed: %s", e)
            return {"error": f"Database write failed: {e}"}

        success_rate = 100.0 if watchlist else 0

        logger.info(f"Sync completed for user {user_id}: {updates_count} synced")
        
        return {
            "synced_count": updates_count,
            "skipped_count": 0,
            "failed_count": 0,
            "total_count": len(watchlist),
            "cached_hits": updates_count,
            "success_rate": f"{success_rate:.1f}%",
            "elapsed_time": f"{progress.elapsed_time:.1f}s"
        }
    
    except Exception as e:
        logger.exception(f"Sync failed: {e}")
        return {"error": str(e)}
    finally:
        if not session.closed:
            await session.close()
