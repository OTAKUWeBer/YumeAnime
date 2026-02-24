"""
AniList integration API endpoints
Handles AniList connection status, sync, and disconnection
"""
from flask import Blueprint, request, session, jsonify, current_app
import logging
import time
import threading

from ...models.user import get_user_by_id, get_anilist_connection_info
from ...utils.helpers import (
    sync_anilist_watchlist_blocking, store_sync_progress, 
    get_sync_progress, clear_sync_progress
)

anilist_api_bp = Blueprint('anilist_api', __name__)
logger = logging.getLogger(__name__)


@anilist_api_bp.route('/status', methods=['GET'])
def get_anilist_status():
    """Get detailed AniList connection status"""
    if 'username' not in session or '_id' not in session:
        return jsonify({'connected': False, 'message': 'Not logged in.'}), 401
    
    try:
        user_id = session.get('_id')
        connection_info = get_anilist_connection_info(user_id)
        return jsonify(connection_info), 200
        
    except Exception as e:
        logger.error(f"Error getting AniList status: {e}")
        return jsonify({
            'connected': False, 
            'error': 'Failed to check AniList connection status'
        }), 500


@anilist_api_bp.route('/disconnect', methods=['POST'])
def disconnect_anilist():
    """Disconnect AniList account"""
    if 'username' not in session or '_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in.'}), 401
    
    from ...routes.auth import unlink_anilist_account
    return unlink_anilist_account()


@anilist_api_bp.route('/sync-anilist', methods=['POST'])
def sync_anilist():
    """Sync AniList watchlist to local database (Background Task)"""
    if 'username' not in session or '_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in.'}), 401
    
    try:
        user_id = session.get('_id')
        user = get_user_by_id(user_id)
        
        if not user or not user.get('anilist_access_token'):
            return jsonify({'success': False, 'message': 'AniList account not linked.'}), 400
        
        access_token = user['anilist_access_token']
        
        # Initialize progress
        store_sync_progress(user_id, {
            'status': 'starting',
            'processed': 0,
            'total': 0,
            'synced': 0,
            'skipped': 0,
            'failed': 0,
            'percentage': 0,
            'message': 'Starting sync...'
        })
        
        # Define background task with app context
        app = current_app._get_current_object()
        
        def background_sync(app, user_id, access_token):
            with app.app_context():
                try:
                    def progress_callback(progress):
                        try:
                            store_sync_progress(user_id, {
                                'status': 'syncing',
                                'processed': progress.processed,
                                'total': progress.total,
                                'synced': progress.synced,
                                'skipped': progress.skipped,
                                'failed': progress.failed,
                                'percentage': progress.percentage,
                                'cached_hits': getattr(progress, 'cached_hits', 0),
                                'estimated_remaining': getattr(progress, 'estimated_remaining', 0),
                                'message': getattr(progress, 'message', f'Syncing... {progress.processed}/{progress.total}')
                            })
                        except Exception as e:
                            logger.warning(f"Progress callback error: {e}")
                    
                    # Run the sync function
                    result = sync_anilist_watchlist_blocking(user_id, access_token, progress_callback)
                    
                    # Handle errors
                    if 'error' in result:
                        store_sync_progress(user_id, {
                            'status': 'error',
                            'message': f'Sync failed: {result["error"]}',
                            'error': result['error']
                        })
                        return
                    
                    # Calculate success metrics
                    synced_count = result.get('synced_count', 0)
                    skipped_count = result.get('skipped_count', 0)
                    failed_count = result.get('failed_count', 0)
                    total_count = result.get('total_count', 0)
                    cached_hits = result.get('cached_hits', 0)
                    
                    success_count = synced_count + skipped_count
                    success_rate = (success_count / total_count * 100) if total_count > 0 else 0
                    
                    is_success = success_rate >= 70.0
                    
                    if is_success:
                        parts = [f'✓ Sync completed! {synced_count} anime synced']
                        if cached_hits:
                            parts.append(f'{cached_hits} from cache')
                        if failed_count:
                            parts.append(f'{failed_count} not found')
                        message = ' — '.join(parts)
                    else:
                        message = f'Sync partially completed. {success_count}/{total_count} successful, {failed_count} not found.'
                    
                    # Store final progress
                    store_sync_progress(user_id, {
                        'status': 'completed',
                        'processed': total_count,
                        'total': total_count,
                        'synced': synced_count,
                        'skipped': skipped_count,
                        'failed': failed_count,
                        'percentage': 100,
                        'success_rate': success_rate,
                        'message': message,
                        'result': {
                            'success': is_success,
                            'synced_count': synced_count,
                            'skipped_count': skipped_count,
                            'failed_count': failed_count
                        }
                    })
                    
                except Exception as e:
                    logger.error(f"Background sync error for user {user_id}: {e}")
                    store_sync_progress(user_id, {
                        'status': 'error',
                        'message': f'Unexpected error: {str(e)}',
                        'error': str(e)
                    })

        # Start background thread
        thread = threading.Thread(target=background_sync, args=(app, user_id, access_token))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True, 
            'message': 'Sync started in background',
            'status': 'started'
        }), 202
        
    except Exception as e:
        logger.error(f"Error starting AniList sync: {e}")
        return jsonify({'success': False, 'message': 'Failed to start sync.'}), 500


@anilist_api_bp.route('/sync-progress', methods=['GET'])
def get_sync_progress_route():
    """Get current sync progress"""
    if 'username' not in session or '_id' not in session:
        return jsonify({'error': 'Not logged in.'}), 401
        
    user_id = session.get('_id')
    progress = get_sync_progress(user_id)
    
    # If no progress found, return empty/idle status
    if not progress:
        return jsonify({'status': 'idle'}), 200
        
    return jsonify(progress), 200


@anilist_api_bp.route('/sync-progress/clear', methods=['POST'])
def clear_sync_progress_route():
    """Clear sync progress"""
    if 'username' not in session or '_id' not in session:
        return jsonify({'error': 'Not logged in.'}), 401
    
    try:
        user_id = session.get('_id')
        clear_sync_progress(user_id)
        return jsonify({'success': True, 'message': 'Progress cleared'})
    except Exception as e:
        logger.error(f"Error clearing sync progress: {e}")
        return jsonify({'success': False, 'message': 'Failed to clear progress'})
