"""
Watchlist API endpoints — powered entirely by AniList GraphQL.
No local database storage; every read/write hits AniList directly.
"""
from flask import Blueprint, request, session, jsonify, current_app
import logging
import requests

from ...models.user import get_user_by_id

watchlist_api_bp = Blueprint('watchlist_api', __name__)
logger = logging.getLogger(__name__)

ANILIST_GRAPHQL = "https://graphql.anilist.co"

# ── viewer ID cache ─────────────────────────────────────────────
# Viewer ID never changes for a given access token, so we cache it
# to avoid a redundant API call on every request.
import time as _time

_viewer_id_cache = {}          # {access_token_hash: (viewer_id, expires_at)}
_VIEWER_CACHE_TTL = 6 * 3600   # 6 hours

# ── helpers ──────────────────────────────────────────────────────

STATUS_MAP_TO_LOCAL = {
    'CURRENT': 'watching',
    'COMPLETED': 'completed',
    'PAUSED': 'paused',
    'DROPPED': 'dropped',
    'PLANNING': 'plan_to_watch',
    'REPEATING': 'watching',
}

STATUS_MAP_TO_ANILIST = {v: k for k, v in STATUS_MAP_TO_LOCAL.items()}
STATUS_MAP_TO_ANILIST['plan_to_watch'] = 'PLANNING'
STATUS_MAP_TO_ANILIST['on_hold'] = 'PAUSED'


def _get_access_token():
    """Return the user's AniList access_token or None."""
    user_id = session.get('_id')
    if not user_id:
        return None
    user = get_user_by_id(user_id)
    if not user:
        return None
    return user.get('anilist_access_token')


def _anilist_request(access_token, query, variables=None):
    """Fire a GraphQL request against AniList and return the parsed JSON."""
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    try:
        resp = requests.post(
            ANILIST_GRAPHQL,
            json={'query': query, 'variables': variables or {}},
            headers=headers,
            timeout=15,
        )
        if resp.status_code != 200:
            logger.error(f"AniList API error {resp.status_code}: {resp.text[:300]}")
            return None
        data = resp.json()
        if 'errors' in data:
            logger.error(f"AniList GraphQL errors: {data['errors']}")
            return None
        return data
    except Exception as e:
        logger.error(f"AniList request failed: {e}")
        return None


def _token_hash(access_token):
    """Short hash of the token for cache key (avoids storing raw tokens)."""
    import hashlib
    return hashlib.sha256(access_token.encode()).hexdigest()[:16]


def _fetch_viewer_id(access_token):
    """Get the authenticated viewer's AniList user ID (cached)."""
    now = _time.time()
    th = _token_hash(access_token)

    # Check cache
    cached = _viewer_id_cache.get(th)
    if cached and cached[1] > now:
        return cached[0]

    # Fetch from AniList
    data = _anilist_request(access_token, "query { Viewer { id } }")
    if not data:
        return None
    viewer_id = data.get('data', {}).get('Viewer', {}).get('id')

    if viewer_id:
        _viewer_id_cache[th] = (viewer_id, now + _VIEWER_CACHE_TTL)

        # Lazy cleanup: remove expired entries if cache is growing
        if len(_viewer_id_cache) > 100:
            expired = [k for k, v in _viewer_id_cache.items() if v[1] <= now]
            for k in expired:
                del _viewer_id_cache[k]

    return viewer_id


def get_anilist_watchlist_entry(anilist_id):
    """Utility to quickly fetch the progress of a single anime from AniList."""
    if not anilist_id or 'username' not in session:
        return None
    try:
        anilist_id = int(anilist_id)
    except (ValueError, TypeError):
        return None

    access_token = _get_access_token()
    if not access_token:
        return None

    viewer_id = _fetch_viewer_id(access_token)
    if not viewer_id:
        return None

    query = """
    query ($userId: Int, $mediaId: Int) {
      MediaList(userId: $userId, mediaId: $mediaId) {
        progress
      }
    }
    """
    data = _anilist_request(access_token, query, {'userId': viewer_id, 'mediaId': anilist_id})
    if data and 'data' in data and data['data'].get('MediaList'):
        return data['data']['MediaList']
    return None


# ── READ endpoints ──────────────────────────────────────────────

WATCHLIST_QUERY = """
query ($userId: Int, $type: MediaType) {
  MediaListCollection(userId: $userId, type: $type) {
    lists {
      name
      entries {
        id
        mediaId
        status
        progress
        score(format: POINT_10_DECIMAL)
        repeat
        notes
        startedAt { year month day }
        completedAt { year month day }
        media {
          id
          title { userPreferred english romaji }
          episodes
          nextAiringEpisode { episode }
          coverImage { large medium }
          bannerImage
          format
          status
        }
      }
    }
  }
}
"""


@watchlist_api_bp.route('/paginated', methods=['GET'])
def watchlist_paginated():
    """Fetch watchlist directly from AniList, apply local pagination/filter."""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    access_token = _get_access_token()
    if not access_token:
        return jsonify({'data': [], 'pagination': {}, 'error': 'AniList not connected'}), 200

    page = max(1, int(request.args.get('page', 1)))
    limit = max(1, min(50, int(request.args.get('limit', 20))))
    status_filter = request.args.get('status', '').strip()

    viewer_id = _fetch_viewer_id(access_token)
    if not viewer_id:
        return jsonify({'data': [], 'pagination': {}, 'error': 'Could not verify AniList identity'}), 200

    data = _anilist_request(access_token, WATCHLIST_QUERY, {'userId': viewer_id, 'type': 'ANIME'})
    if not data:
        return jsonify({'data': [], 'pagination': {}, 'error': 'Failed to fetch from AniList'}), 200

    # Flatten all lists into one array, deduplicating by media ID
    # (AniList custom lists can cause the same anime to appear in multiple lists)
    all_entries = []
    seen_media_ids = set()
    collection = data.get('data', {}).get('MediaListCollection', {})
    for lst in collection.get('lists', []):
        for entry in lst.get('entries', []):
            media = entry.get('media') or {}
            media_id = media.get('id')
            if media_id in seen_media_ids:
                continue
            seen_media_ids.add(media_id)

            title_obj = media.get('title', {})
            cover = media.get('coverImage', {})
            local_status = STATUS_MAP_TO_LOCAL.get(entry.get('status'), 'watching')

            item = {
                'anime_id': str(media_id or ''),
                'anilist_entry_id': entry.get('id'),
                'anime_title': title_obj.get('userPreferred') or title_obj.get('english') or title_obj.get('romaji') or 'Unknown',
                'status': local_status,
                'watched_episodes': entry.get('progress', 0),
                'total_episodes': media.get('episodes') or 0,
                'next_airing_episode': (media.get('nextAiringEpisode') or {}).get('episode'),
                'score': entry.get('score', 0),
                'repeat': entry.get('repeat', 0),
                'notes': entry.get('notes', ''),
                'poster_url': cover.get('large') or cover.get('medium') or '',
                'banner_image': media.get('bannerImage', ''),
                'startedAt': entry.get('startedAt'),
                'completedAt': entry.get('completedAt'),
                'media_format': media.get('format', ''),
                'media_status': media.get('status', ''),
            }
            all_entries.append(item)

    # Apply status filter
    if status_filter:
        all_entries = [e for e in all_entries if e['status'] == status_filter]

    # Sort by title
    all_entries.sort(key=lambda x: (x.get('anime_title') or '').lower())

    total_count = len(all_entries)
    total_pages = max(1, (total_count + limit - 1) // limit)
    start = (page - 1) * limit
    paginated = all_entries[start:start + limit]

    return jsonify({
        'data': paginated,
        'pagination': {
            'current_page': page,
            'page_size': limit,
            'total_pages': total_pages,
            'total_count': total_count,
            'has_next': page < total_pages,
            'has_prev': page > 1,
        }
    })


@watchlist_api_bp.route('/stats', methods=['GET'])
def watchlist_stats():
    """Return stats from AniList Viewer query."""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    access_token = _get_access_token()
    if not access_token:
        return jsonify({}), 200

    viewer_id = _fetch_viewer_id(access_token)
    if not viewer_id:
        return jsonify({}), 200

    # Fetch both stats and list counts
    query = """
    query ($userId: Int) {
      User(id: $userId) {
        statistics {
          anime {
            count
            meanScore
            minutesWatched
            episodesWatched
          }
        }
      }
      MediaListCollection(userId: $userId, type: ANIME) {
        lists {
          name
          status
          entries { id }
        }
      }
    }
    """
    data = _anilist_request(access_token, query, {'userId': viewer_id})
    if not data:
        return jsonify({}), 200

    stats = data.get('data', {}).get('User', {}).get('statistics', {}).get('anime', {})
    lists = data.get('data', {}).get('MediaListCollection', {}).get('lists', [])

    status_counts = {
        'watching': 0, 'completed': 0, 'paused': 0,
        'dropped': 0, 'plan_to_watch': 0,
    }
    for lst in lists:
        al_status = lst.get('status')
        local = STATUS_MAP_TO_LOCAL.get(al_status)
        if local:
            status_counts[local] += len(lst.get('entries', []))

    return jsonify({
        'total_anime': stats.get('count', 0),
        'total': stats.get('count', 0),
        'minutes_watched': stats.get('minutesWatched', 0),
        'episodes_watched': stats.get('episodesWatched', 0),
        'mean_score': stats.get('meanScore', 0),
        **status_counts,
    })


# ── WRITE endpoints (mutate AniList) ────────────────────────────

SAVE_ENTRY_MUTATION = """
mutation ($mediaId: Int, $status: MediaListStatus, $progress: Int,
          $score: Int, $repeat: Int, $notes: String,
          $startedAt: FuzzyDateInput, $completedAt: FuzzyDateInput) {
  SaveMediaListEntry(mediaId: $mediaId, status: $status, progress: $progress,
                     scoreRaw: $score, repeat: $repeat, notes: $notes,
                     startedAt: $startedAt, completedAt: $completedAt) {
    id
    status
    progress
    score(format: POINT_10_DECIMAL)
  }
}
"""

DELETE_ENTRY_MUTATION = """
mutation ($id: Int) {
  DeleteMediaListEntry(id: $id) {
    deleted
  }
}
"""


@watchlist_api_bp.route('/add', methods=['POST'])
def add_to_watchlist_route():
    """Add an anime to AniList watchlist."""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    access_token = _get_access_token()
    if not access_token:
        return jsonify({'success': False, 'message': 'AniList not connected'}), 400

    body = request.get_json()
    anime_id = body.get('anime_id')
    status = body.get('status', 'watching')

    if not anime_id:
        return jsonify({'success': False, 'message': 'Missing anime ID'}), 400

    al_status = STATUS_MAP_TO_ANILIST.get(status, 'CURRENT')

    variables = {
        'mediaId': int(anime_id),
        'status': al_status,
        'progress': int(body.get('watched_episodes', 0)),
    }

    data = _anilist_request(access_token, SAVE_ENTRY_MUTATION, variables)
    if data and data.get('data', {}).get('SaveMediaListEntry'):
        return jsonify({'success': True, 'message': f'Added to {status} list on AniList!'})
    return jsonify({'success': False, 'message': 'AniList mutation failed'}), 500


@watchlist_api_bp.route('/update', methods=['POST'])
def update_watchlist():
    """Update status or episodes on AniList."""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    access_token = _get_access_token()
    if not access_token:
        return jsonify({'success': False, 'message': 'AniList not connected'}), 400

    body = request.get_json()
    anime_id = body.get('anime_id')
    action = body.get('action')

    if not anime_id or not action:
        return jsonify({'success': False, 'message': 'Missing parameters'}), 400

    variables = {'mediaId': int(anime_id)}

    if action == 'status':
        status = body.get('status', 'watching')
        variables['status'] = STATUS_MAP_TO_ANILIST.get(status, 'CURRENT')
    elif action == 'episodes':
        new_progress = int(body.get('watched_episodes', 0))

        # Guard: only increase progress, never decrease (prevents rewatch regression)
        viewer_id = _fetch_viewer_id(access_token)
        if viewer_id:
            check_query = """
            query ($userId: Int, $mediaId: Int) {
              MediaList(userId: $userId, mediaId: $mediaId) {
                progress
              }
            }
            """
            current = _anilist_request(access_token, check_query, {'userId': viewer_id, 'mediaId': int(anime_id)})
            if current:
                current_progress = (current.get('data', {}).get('MediaList') or {}).get('progress', 0) or 0
                if new_progress <= current_progress:
                    return jsonify({'success': True, 'message': 'Progress already up to date'})

        variables['progress'] = new_progress
    else:
        return jsonify({'success': False, 'message': 'Invalid action'}), 400

    data = _anilist_request(access_token, SAVE_ENTRY_MUTATION, variables)
    if data and data.get('data', {}).get('SaveMediaListEntry'):
        return jsonify({'success': True, 'message': 'Updated on AniList!'})
    return jsonify({'success': False, 'message': 'AniList mutation failed'}), 500


@watchlist_api_bp.route('/advanced_update', methods=['POST'])
def advanced_update():
    """Full edit modal save → mutates AniList with all fields."""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    access_token = _get_access_token()
    if not access_token:
        return jsonify({'success': False, 'message': 'AniList not connected'}), 400

    body = request.get_json()
    anime_id = body.get('anime_id')
    if not anime_id:
        return jsonify({'success': False, 'message': 'Missing anime ID'}), 400

    # Build variables
    variables = {'mediaId': int(anime_id)}

    if body.get('status'):
        # Accept both AniList-native and local status strings
        raw = body['status']
        variables['status'] = raw if raw in ('CURRENT', 'COMPLETED', 'PAUSED', 'DROPPED', 'PLANNING', 'REPEATING') \
            else STATUS_MAP_TO_ANILIST.get(raw, 'CURRENT')

    if 'progress' in body:
        variables['progress'] = int(body['progress'])
    if 'score' in body and body['score']:
        # AniList scoreRaw expects an int 0-100 (POINT_100 format)
        # Our UI uses 0-10 decimal, so multiply by 10
        variables['score'] = int(float(body['score']) * 10)
    if 'repeat' in body:
        variables['repeat'] = int(body['repeat'])
    if 'notes' in body:
        variables['notes'] = body['notes']

    # Dates
    def _clean_date(d):
        if not d or not isinstance(d, dict):
            return None
        if not d.get('year') and not d.get('month') and not d.get('day'):
            return None
        return {k: v for k, v in d.items() if v is not None}

    started = _clean_date(body.get('startedAt'))
    completed = _clean_date(body.get('completedAt'))
    if started:
        variables['startedAt'] = started
    if completed:
        variables['completedAt'] = completed

    data = _anilist_request(access_token, SAVE_ENTRY_MUTATION, variables)
    if data and data.get('data', {}).get('SaveMediaListEntry'):
        return jsonify({'success': True, 'message': 'Saved to AniList!'})
    return jsonify({'success': False, 'message': 'AniList mutation failed'}), 500


@watchlist_api_bp.route('/remove', methods=['POST'])
def remove_from_watchlist_route():
    """Delete entry from AniList. Requires the anilist entry id."""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    access_token = _get_access_token()
    if not access_token:
        return jsonify({'success': False, 'message': 'AniList not connected'}), 400

    body = request.get_json()
    anime_id = body.get('anime_id')  # This is the AniList media ID
    if not anime_id:
        return jsonify({'success': False, 'message': 'Missing anime ID'}), 400

    # First we need to find the list entry ID for this media
    viewer_id = _fetch_viewer_id(access_token)
    if not viewer_id:
        return jsonify({'success': False, 'message': 'Could not verify AniList identity'}), 500

    find_query = """
    query ($userId: Int, $mediaId: Int) {
      MediaList(userId: $userId, mediaId: $mediaId) {
        id
      }
    }
    """
    find_data = _anilist_request(access_token, find_query, {'userId': viewer_id, 'mediaId': int(anime_id)})
    if not find_data:
        return jsonify({'success': False, 'message': 'Could not find entry on AniList'}), 404

    entry_id = find_data.get('data', {}).get('MediaList', {}).get('id')
    if not entry_id:
        return jsonify({'success': False, 'message': 'Entry not found on AniList'}), 404

    del_data = _anilist_request(access_token, DELETE_ENTRY_MUTATION, {'id': entry_id})
    if del_data and del_data.get('data', {}).get('DeleteMediaListEntry', {}).get('deleted'):
        return jsonify({'success': True, 'message': 'Removed from AniList!'})
    return jsonify({'success': False, 'message': 'Failed to delete from AniList'}), 500


@watchlist_api_bp.route('/status', methods=['GET'])
def get_watchlist_status():
    """Check if an anime is in the user's AniList list."""
    if 'username' not in session:
        return jsonify({'in_watchlist': False}), 200

    access_token = _get_access_token()
    anime_id = request.args.get('anime_id')
    if not access_token or not anime_id:
        return jsonify({'in_watchlist': False}), 200

    viewer_id = _fetch_viewer_id(access_token)
    if not viewer_id:
        return jsonify({'in_watchlist': False}), 200

    query = """
    query ($userId: Int, $mediaId: Int) {
      MediaList(userId: $userId, mediaId: $mediaId) {
        id status progress
        media { episodes }
      }
    }
    """
    data = _anilist_request(access_token, query, {'userId': viewer_id, 'mediaId': int(anime_id)})
    if not data:
        return jsonify({'in_watchlist': False}), 200

    entry = data.get('data', {}).get('MediaList')
    if entry:
        return jsonify({
            'in_watchlist': True,
            'status': STATUS_MAP_TO_LOCAL.get(entry.get('status'), 'watching'),
            'watched_episodes': entry.get('progress', 0),
            'total_episodes': (entry.get('media') or {}).get('episodes', 0),
        })
    return jsonify({'in_watchlist': False})


@watchlist_api_bp.route('/progress', methods=['POST'])
def save_progress():
    """Save episode progress → updates AniList progress."""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    access_token = _get_access_token()
    if not access_token:
        return jsonify({'success': False, 'message': 'AniList not connected'}), 400

    body = request.get_json()
    anime_id = body.get('anime_id')
    episode_number = body.get('episode_number')
    is_completed = bool(body.get('is_completed', False))

    if not anime_id or episode_number is None:
        return jsonify({'success': False, 'message': 'Missing parameters'}), 400

    try:
        ep = int(float(episode_number))
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'Invalid episode number'}), 400

    if is_completed:
        variables = {'mediaId': int(anime_id), 'progress': ep}
        data = _anilist_request(access_token, SAVE_ENTRY_MUTATION, variables)
        if data and data.get('data', {}).get('SaveMediaListEntry'):
            return jsonify({'success': True, 'message': 'Progress saved to AniList!'})
        return jsonify({'success': False, 'message': 'AniList update failed'}), 500

    # If not completed, just acknowledge — we don't need to push partial progress to AniList
    return jsonify({'success': True, 'message': 'Progress noted'})


@watchlist_api_bp.route('/get', methods=['GET'])
def get_watchlist_route():
    """Get full watchlist from AniList (non-paginated, for compatibility)."""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    access_token = _get_access_token()
    if not access_token:
        return jsonify({'watchlist': []}), 200

    viewer_id = _fetch_viewer_id(access_token)
    if not viewer_id:
        return jsonify({'watchlist': []}), 200

    data = _anilist_request(access_token, WATCHLIST_QUERY, {'userId': viewer_id, 'type': 'ANIME'})
    if not data:
        return jsonify({'watchlist': []}), 200

    entries = []
    seen_media_ids = set()
    collection = data.get('data', {}).get('MediaListCollection', {})
    for lst in collection.get('lists', []):
        for entry in lst.get('entries', []):
            media = entry.get('media') or {}
            media_id = media.get('id')
            if media_id in seen_media_ids:
                continue
            seen_media_ids.add(media_id)

            title_obj = media.get('title', {})
            entries.append({
                'anime_id': str(media_id or ''),
                'anime_title': title_obj.get('userPreferred') or title_obj.get('english') or title_obj.get('romaji') or 'Unknown',
                'status': STATUS_MAP_TO_LOCAL.get(entry.get('status'), 'watching'),
                'watched_episodes': entry.get('progress', 0),
            })

    return jsonify({'watchlist': entries})
