"""
Watchlist API endpoints
Handles watchlist CRUD operations and statistics
"""
from flask import Blueprint, request, session, jsonify, current_app
import logging
import asyncio

from ...models.watchlist import (
    add_to_watchlist, get_watchlist_entry, update_watchlist_status,
    update_watched_episodes, remove_from_watchlist, get_user_watchlist,
    get_user_watchlist_paginated, get_watchlist_stats, warm_cache
)
from ...utils.helpers import enrich_watchlist_item

watchlist_api_bp = Blueprint('watchlist_api', __name__)
logger = logging.getLogger(__name__)


@watchlist_api_bp.route('/paginated', methods=['GET'])
async def watchlist_paginated():
    """Get paginated watchlist data"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    try:
        user_id = session.get('_id')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        status_filter = request.args.get('status', '').strip()

        # Sanitize inputs
        page = max(1, page)
        limit = max(1, min(50, limit))

        result = get_user_watchlist_paginated(
            user_id=user_id,
            page=page,
            page_size=limit,
            status=status_filter if status_filter else None
        )

        if not isinstance(result, dict):
            result = {'data': [], 'pagination': {}}

        # Enrich items concurrently
        items_to_enrich = []
        for item in result.get('data', []):
            try:
                if item.get('_id') is not None:
                    item['_id'] = str(item['_id'])
            except Exception:
                pass
            items_to_enrich.append(enrich_watchlist_item(item))

        enriched_items = await asyncio.gather(*items_to_enrich, return_exceptions=True)
        result['data'] = enriched_items

        # Handle exceptions from enrichment
        for i, item in enumerate(result['data']):
            if isinstance(item, Exception):
                logger.error(f"Failed to enrich item at index {i}: {item}")
                result['data'][i] = {}

        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in watchlist_paginated: {e}")
        return jsonify({'data': [], 'pagination': {}, 'error': str(e)}), 500


@watchlist_api_bp.route('/update', methods=['POST'])
def update_watchlist():
    """Update watchlist entry"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    anime_id = data.get('anime_id')
    action = data.get('action')  # 'status' or 'episodes'
    
    current_app.logger.info(f"Update request - anime_id: {anime_id}, action: {action}, data: {data}")
    
    if not anime_id or not action:
        return jsonify({'success': False, 'message': 'Missing parameters.'}), 400
    
    try:
        user_id = session.get('_id')
        
        if action == 'status':
            status = data.get('status')
            current_app.logger.info(f"Updating status to: {status}")
            result = update_watchlist_status(user_id, anime_id, status)
        elif action == 'episodes':
            watched_episodes = data.get('watched_episodes', 0)
            current_app.logger.info(f"Updating episodes: watched={watched_episodes}")
            result = update_watched_episodes(user_id, anime_id, watched_episodes)
        else:
            return jsonify({'success': False, 'message': 'Invalid action.'}), 400
        
        current_app.logger.info(f"Update result: {result}")
        
        if result:
            return jsonify({'success': True, 'message': 'Updated successfully!'})
        else:
            return jsonify({'success': False, 'message': 'Failed to update.'}), 500
    except Exception as e:
        current_app.logger.error(f"Error updating watchlist: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@watchlist_api_bp.route('/remove', methods=['POST'])
def remove_from_watchlist_route():
    """Remove from watchlist"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    anime_id = data.get('anime_id')
    
    if not anime_id:
        return jsonify({'success': False, 'message': 'Missing anime ID.'}), 400
    
    try:
        user_id = session.get('_id')
        result = remove_from_watchlist(user_id, anime_id)
        
        if result:
            return jsonify({'success': True, 'message': 'Removed from watchlist!'})
        else:
            return jsonify({'success': False, 'message': 'Failed to remove.'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@watchlist_api_bp.route('/get', methods=['GET'])
def get_watchlist_route():
    """Get user watchlist"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        user_id = session.get('_id')
        status_filter = request.args.get('status')
        watchlist = get_user_watchlist(user_id, status_filter)
        
        for item in watchlist:
            item['_id'] = str(item['_id'])
        
        return jsonify({'watchlist': watchlist})
    except Exception:
        return jsonify({'watchlist': []}), 500


@watchlist_api_bp.route('/add', methods=['POST'])
def add_to_watchlist_route():
    """Add to watchlist"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    anime_id = data.get('anime_id')
    anime_title = data.get('anime_title')
    status = data.get('status', 'watching')
    
    if not anime_id or not anime_title:
        return jsonify({'success': False, 'message': 'Missing anime information.'}), 400
    
    try:
        user_id = session.get('_id')
        watched_episodes = data.get('watched_episodes', 0)
        result = add_to_watchlist(user_id, anime_id, anime_title, status, watched_episodes)
        
        if result:
            return jsonify({'success': True, 'message': f'Added to {status} list!'})
        else:
            return jsonify({'success': False, 'message': 'Failed to add to watchlist.'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@watchlist_api_bp.route('/status', methods=['GET'])
def get_watchlist_status():
    """Get watchlist status for an anime"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    anime_id = request.args.get('anime_id')
    if not anime_id:
        return jsonify({'in_watchlist': False}), 200
    
    try:
        user_id = session.get('_id')
        entry = get_watchlist_entry(user_id, anime_id)
        
        if entry:
            return jsonify({
                'in_watchlist': True,
                'status': entry['status'],
                'watched_episodes': entry.get('watched_episodes', 0),
                'total_episodes': entry.get('total_episodes', 0)
            })
        else:
            return jsonify({'in_watchlist': False})
    except Exception:
        return jsonify({'in_watchlist': False}), 500


@watchlist_api_bp.route('/stats', methods=['GET'])
def get_watchlist_stats_route():
    """Get watchlist statistics"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        user_id = session.get('_id')
        stats = get_watchlist_stats(user_id)
        return jsonify(stats or {})
        
    except Exception as e:
        current_app.logger.error(f"Error getting watchlist stats: {e}")
        return jsonify({}), 500


@watchlist_api_bp.route('/warm-cache', methods=['POST'])
def warm_watchlist_cache():
    """Pre-warm cache for watchlist"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        user_id = session.get('_id')
        warm_cache(user_id)
        return jsonify({'success': True, 'message': 'Cache warmed successfully'})
        
    except Exception as e:
        current_app.logger.error(f"Error warming cache: {e}")
        return jsonify({'success': False, 'message': 'Failed to warm cache'}), 500
