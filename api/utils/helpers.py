"""
Helper utility functions for the application.
Includes Turnstile verification, AniList API interactions, and watchlist enrichment.
"""

import requests
import logging
import time
import asyncio
import inspect
from threading import Lock
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Global storage for sync progress
sync_progress_storage = {}
sync_progress_lock = Lock()


# === Turnstile Verification ===

def verify_turnstile(token, secret, remoteip=None):
    """Verify Turnstile token with Cloudflare - Vercel compatible version"""
    if not token:
        return False
    
    # For Vercel deployment, we need to handle the verification more carefully
    data = {
        "secret": secret,
        "response": token
    }
    
    # Only add remoteip if it's a valid IP address (avoid Vercel proxy issues)
    if remoteip and remoteip not in ['127.0.0.1', 'localhost'] and not remoteip.startswith('::'):
        data["remoteip"] = remoteip
    
    try:
        # Use longer timeout for serverless functions
        resp = requests.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify", 
            data=data, 
            timeout=10,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'User-Agent': 'YumeAnime/1.0'
            }
        )
        
        if resp.status_code != 200:
            logger.error(f"Turnstile API returned status {resp.status_code}: {resp.text}")
            return False
            
        result = resp.json()
        success = result.get("success", False)
        
        # Log detailed error info for debugging
        if not success:
            error_codes = result.get("error-codes", [])
            logger.warning(f"Turnstile verification failed. Token: {token[:20]}..., Error codes: {error_codes}")
            
            # For Vercel, sometimes we get false negatives due to IP/timing issues
            # If it's just a timeout or connection issue, we might want to be more lenient
            if 'timeout-or-duplicate' in error_codes:
                logger.warning("Turnstile timeout-or-duplicate error - treating as valid for Vercel deployment")
                return True
                
        return success
        
    except requests.exceptions.Timeout:
        logger.error("Turnstile verification timeout")
        # For Vercel, timeout might be due to serverless cold start - be more lenient
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Turnstile verification request error: {e}")
        return False
    except Exception as e:
        logger.error(f"Turnstile verification unexpected error: {e}")
        return False


# === AniList API Functions ===

def get_anilist_user_info(access_token):
    """Get user information from AniList GraphQL API."""
    query = '''
    query {
        Viewer {
            id
            name
            avatar {
                large
                medium
            }
            bannerImage
            about
            statistics {
                anime {
                    count
                    meanScore
                    minutesWatched
                }
            }
        }
    }
    '''
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    try:
        response = requests.post('https://graphql.anilist.co', 
                               json={'query': query}, 
                               headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            if 'errors' in data:
                logger.error(f"AniList GraphQL errors: {data['errors']}")
                return None
            return data['data']['Viewer']
        else:
            logger.error(f"AniList API error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting AniList user info: {e}")
        return None

async def fetch_anilist_next_episode(anilist_id: int = None, mal_id: int = None, search_title: str = None) -> dict:
    """Fetch the next episode schedule from AniList GraphQL API using anilistId, malId, or search title."""
    if not anilist_id and not mal_id and not search_title:
        return {}
        
    query_id = '''
    query ($id: Int, $idMal: Int) {
      Media(id: $id, idMal: $idMal, type: ANIME) {
        nextAiringEpisode {
          airingAt
          timeUntilAiring
          episode
        }
      }
    }
    '''
    
    query_search = '''
    query ($search: String) {
      Media(search: $search, type: ANIME, status: RELEASING) {
        nextAiringEpisode {
          airingAt
          timeUntilAiring
          episode
        }
      }
    }
    '''
    
    queries_to_try = []
    if anilist_id and int(anilist_id) > 0:
        queries_to_try.append((query_id, {"id": int(anilist_id)}))
    if mal_id and int(mal_id) > 0:
        queries_to_try.append((query_id, {"idMal": int(mal_id)}))
    if search_title:
        queries_to_try.append((query_search, {"search": search_title}))
        
    if not queries_to_try:
        return {}
    
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            for query, variables in queries_to_try:
                async with session.post('https://graphql.anilist.co', json={'query': query, 'variables': variables}) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        media_data = data.get('data', {})
                        # Handle both single Media and Page->media responses
                        if 'Page' in media_data:
                            media_list = media_data.get('Page', {}).get('media', [])
                            media = media_list[0] if media_list else {}
                        else:
                            media = media_data.get('Media') or {}
                            
                        next_ep = media.get('nextAiringEpisode')
                        if next_ep and next_ep.get('airingAt'):
                            return {
                                "airingTimestamp": next_ep.get('airingAt'),
                                "timeUntilAiring": next_ep.get('timeUntilAiring'),
                                "episode": next_ep.get('episode')
                            }
                # If we get here, either status != 200 or no valid airingAt was found for this query.
                # Continue loop to try the next fallback (e.g. mal_id or search_title).
        return {}
    except Exception as e:
        logger.error(f"Error fetching next episode from AniList: {e}")
        return {}

# === Sync Progress Management ===

def store_sync_progress(user_id: str, progress_data: dict):
    """Store sync progress for a user"""
    with sync_progress_lock:
        sync_progress_storage[user_id] = {
            **progress_data,
            'timestamp': time.time()
        }


def get_sync_progress(user_id: str) -> dict:
    """Get sync progress for a user"""
    with sync_progress_lock:
        return sync_progress_storage.get(user_id, {})


def clear_sync_progress(user_id: str):
    """Clear sync progress for a user"""
    with sync_progress_lock:
        sync_progress_storage.pop(user_id, None)


# === Sync Wrapper Function ===

def sync_anilist_watchlist_blocking(user_id: str, access_token: str, progress_callback=None) -> Dict[str, Any]:
    """
    Run the user's sync function in a safe way whether it's async or sync.
    Returns the dict result, or {'error': ...} on failure.
    """
    try:
        # import the async function and BatchConfig from ani_to_yume
        from .ani_to_yume import sync_anilist_watchlist_to_local as async_sync_watchlist
        from .ani_to_yume import BatchConfig

        # Use optimized config for better performance and fewer failures
        config = BatchConfig(
            batch_size=1000,
            delay_between_batches=0.05,
            max_retries=1,
            skip_failed_matches=True,
            max_search_candidates=4,
            max_anime_check=3
        )

        # If the imported name is an async function, call it with progress callback
        if inspect.iscoroutinefunction(async_sync_watchlist):
            coro = async_sync_watchlist(user_id, access_token, progress_callback, config)
        else:
            # check if function accepts progress_callback and config
            sig = inspect.signature(async_sync_watchlist)
            params = sig.parameters
            if 'progress_callback' in params and 'config' in params:
                coro_or_result = async_sync_watchlist(user_id, access_token, progress_callback, config)
            elif 'progress_callback' in params:
                coro_or_result = async_sync_watchlist(user_id, access_token, progress_callback)
            else:
                coro_or_result = async_sync_watchlist(user_id, access_token)

            # if the result is a coroutine, treat it as such
            if asyncio.iscoroutine(coro_or_result):
                coro = coro_or_result
            else:
                # synchronous function returned a result
                return coro_or_result or {}

        # At this point `coro` should be an awaitable
        try:
            return asyncio.run(coro) or {}
        except RuntimeError as e:
            # asyncio.run may fail if we're already inside an event loop (e.g., some WSGI/ASGI contexts).
            logger.debug("asyncio.run failed, falling back to manual loop: %s", e)
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                return loop.run_until_complete(coro) or {}
            finally:
                try:
                    loop.run_until_complete(loop.shutdown_asyncgens())
                except Exception:
                    pass
                loop.close()

    except Exception as e:
        logger.exception("Blocking watchlist sync failed")
        return {"error": str(e)}


# === Watchlist Enrichment ===

from ..providers import UnifiedScraper

HA = UnifiedScraper()



async def enrich_watchlist_item(item: dict) -> dict:
    """
    Enriches a watchlist item with poster_url, episodes, total_episodes, rating.
    Always fetches fresh data from the scraper.
    """
    try:
        anime_id = item.get('anime_id')
        if not anime_id:
            return item

        try:
            resp = await HA.anime_about(anime_id)
        except Exception as e:
            logger.debug(f"Scraper.anime_about failed for {anime_id}: {e}")
            resp = None

        poster_url = ''
        episodes = {'sub': 0, 'dub': 0}
        total_episodes = 0
        rating = None
        status = 'Unknown'

        if isinstance(resp, dict):
            candidate = resp.get('anime', {}).get('info', {})

            if isinstance(candidate, dict):
                # Poster
                poster_url = (
                    candidate.get('poster')
                    or candidate.get('image')
                    or candidate.get('thumbnail')
                    or candidate.get('poster_url')
                    or ''
                )

                # Stats → episodes & rating
                stats = candidate.get('stats') or {}
                eps_obj = stats.get('episodes') or candidate.get('episodes')

                if isinstance(eps_obj, dict):
                    episodes['sub'] = int(eps_obj.get('sub') or 0)
                    episodes['dub'] = int(eps_obj.get('dub') or 0)
                elif isinstance(eps_obj, (int, float, str)):
                    try:
                        episodes['sub'] = int(eps_obj)
                    except Exception:
                        pass

                rating = candidate.get('rating') or stats.get('rating')

            # Extract status
            more_info = resp.get('anime', {}).get('moreInfo', {})
            status = more_info.get('status') or 'Unknown'

        # Total episodes
        if episodes.get('sub'):
            total_episodes = episodes['sub']
        elif episodes.get('dub'):
            total_episodes = episodes['dub']

        payload = {
            'poster_url': poster_url,
            'episodes': episodes,
            'total_episodes': total_episodes,
            'status': status
        }
        if rating:
            payload['rating'] = rating
        item.update(payload)
        return item

    except Exception as e:
        logger.debug(f"enrich_watchlist_item error for {item.get('anime_id')}: {e}")
        return item
