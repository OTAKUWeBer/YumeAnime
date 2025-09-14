"""
api/services/anilist_sync.py

Handles the logic for syncing a user's AniList watchlist with the local database.
Replaces the logic from ani_to_yume.py.
"""
import aiohttp
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

# Use the new model for database operations
from ..models import watchlist as watchlist_model
from ..scrapers.hianime import HianimeScraper

# --- Setup ---
logger = logging.getLogger(__name__)
HA = HianimeScraper()
ANILIST_GRAPHQL_URL = "https://graphql.anilist.co"
CONCURRENT_REQUESTS = 10
SEMAPHORE = asyncio.Semaphore(CONCURRENT_REQUESTS)

# --- AniList API Fetching ---

async def _fetch_graphql(access_token: str, query: str, variables: Optional[dict] = None) -> dict:
    """Helper to perform a GraphQL request to the AniList API."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {"query": query, "variables": variables or {}}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(ANILIST_GRAPHQL_URL, json=payload, headers=headers, timeout=30) as resp:
                if resp.status != 200:
                    logger.error(f"AniList API error ({resp.status}): {await resp.text()}")
                    return {"error": f"HTTP Status {resp.status}"}
                return await resp.json()
        except asyncio.TimeoutError:
            logger.error("AniList API request timed out.")
            return {"error": "Timeout"}
        except Exception as e:
            logger.error(f"AniList API request failed: {e}")
            return {"error": str(e)}

async def fetch_anilist_watchlist(access_token: str) -> List[Dict[str, Any]]:
    """Fetches the full watchlist for the authenticated user from AniList."""
    query = """
    query ($userId: Int) {
      MediaListCollection(userId: $userId, type: ANIME, forceSingleCompletedList: true) {
        lists {
          entries {
            status
            progress
            media {
              id
              idMal
              episodes
              title { romaji english native }
            }
          }
        }
      }
    }
    """
    # First, get the viewer's ID
    viewer_query = "query { Viewer { id } }"
    viewer_response = await _fetch_graphql(access_token, viewer_query)
    if "error" in viewer_response or not viewer_response.get("data"):
        return []
    
    user_id = viewer_response["data"]["Viewer"]["id"]
    
    # Then, fetch the watchlist
    response = await _fetch_graphql(access_token, query, {"userId": user_id})
    if "error" in response or not response.get("data"):
        return []

    all_entries = []
    if response["data"].get("MediaListCollection", {}).get("lists"):
        for list_data in response["data"]["MediaListCollection"]["lists"]:
            all_entries.extend(list_data.get("entries", []))
    
    return all_entries

# --- Sync Logic ---

async def _find_hianime_id(anilist_media: dict) -> Optional[str]:
    """Tries to find a matching hianime ID for an anilist media entry."""
    anilist_id = anilist_media.get("id")
    mal_id = anilist_media.get("idMal")
    
    # Create a list of titles to search for
    titles = anilist_media.get("title", {})
    search_titles = [titles.get(key) for key in ["english", "romaji", "native"] if titles.get(key)]

    for title in search_titles:
        try:
            search_results = await asyncio.to_thread(HA.search, title)
            if not search_results or not search_results.get("animes"):
                continue

            for anime in search_results["animes"][:5]: # Check top 5 results
                anime_id = anime.get("id")
                if not anime_id:
                    continue
                
                info = await asyncio.to_thread(HA.get_anime_info, anime_id)
                info_data = info.get("info", {})
                
                if info_data.get("anilistId") == anilist_id or (mal_id and info_data.get("malId") == mal_id):
                    return anime_id
        except Exception as e:
            logger.warning(f"Error searching for title '{title}': {e}")
            
    return None

async def _process_entry(user_id: int, entry: dict, progress_callback=None) -> dict:
    """Processes a single entry from the AniList watchlist."""
    async with SEMAPHORE:
        media = entry.get("media")
        if not media:
            return {"status": "failed", "reason": "No media data"}

        anilist_id = media.get("id")
        
        # 1. Check if this anime is already in the user's local watchlist
        # This is a simple check; a more robust version could use anilist_id stored locally
        titles = media.get("title", {})
        anime_title = titles.get("english") or titles.get("romaji")
        
        # 2. Find the corresponding anime on hianime
        hianime_id = await _find_hianime_id(media)
        if not hianime_id:
            return {"status": "failed", "reason": "Could not match on hianime", "title": anime_title}

        # 3. Map AniList status to local status
        status_mapping = {
            'CURRENT': 'watching', 'COMPLETED': 'completed', 'PAUSED': 'paused',
            'DROPPED': 'dropped', 'PLANNING': 'plan_to_watch', 'REPEATING': 'watching'
        }
        local_status = status_mapping.get(entry.get("status"), 'plan_to_watch')
        
        # 4. Prepare data and add to local watchlist
        watched_episodes = entry.get("progress", 0)
        total_episodes = media.get("episodes") or 0
        
        success = await asyncio.to_thread(
            watchlist_model.add_to_watchlist,
            user_id, hianime_id, anime_title, local_status, watched_episodes, total_episodes
        )
        
        if success:
            return {"status": "synced", "title": anime_title}
        else:
            return {"status": "failed", "reason": "Database error", "title": anime_title}


async def sync_watchlist(user_id: int, access_token: str, progress_callback=None):
    """Main function to sync a user's AniList watchlist."""
    logger.info(f"Starting AniList sync for user {user_id}")
    anilist_entries = await fetch_anilist_watchlist(access_token)
    
    if not anilist_entries:
        logger.warning(f"No entries found on AniList for user {user_id}")
        return {"error": "Could not fetch watchlist from AniList or watchlist is empty."}

    total_count = len(anilist_entries)
    tasks = [_process_entry(user_id, entry, progress_callback) for entry in anilist_entries]
    
    results = await asyncio.gather(*tasks)
    
    # Summarize results
    summary = {
        "total_count": total_count,
        "synced_count": results.count({"status": "synced"}),
        "failed_count": total_count - results.count({"status": "synced"}),
        "failed_entries": [r for r in results if r.get("status") == "failed"]
    }

    logger.info(f"Sync completed for user {user_id}: {summary}")
    return summary
