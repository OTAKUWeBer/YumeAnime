from flask import Blueprint, request, session, jsonify, current_app
import re
import logging
import time
from typing import Dict
import asyncio

from ..utils.helpers import verify_turnstile
from ..models.user import (
    create_user, get_user, user_exists, email_exists, get_user_by_id,
    get_anilist_connection_info
)
from ..core.config import Config
from ..utils.helpers import (
    sync_anilist_watchlist_blocking, store_sync_progress, 
    get_sync_progress, clear_sync_progress, enrich_watchlist_item
)
from ..models.watchlist import (
    add_to_watchlist, get_watchlist_entry, update_watchlist_status,
    update_watched_episodes, remove_from_watchlist, get_user_watchlist,
    get_user_watchlist_paginated, get_watchlist_stats, warm_cache
)

from ..scrapers.hianime import HianimeScraper

HA = HianimeScraper()

anime_cache: Dict[str, dict] = {}
CACHE_TTL = 60 * 60 * 24  # 24 hours

api_bp = Blueprint('api', __name__)
logger = logging.getLogger(__name__)

@api_bp.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    turnstile_token = data.get('cf_turnstile_response')
    
    if not verify_turnstile(turnstile_token, Config.CLOUDFLARE_SECRET, request.remote_addr):
        return jsonify({'success': False, 'message': 'Please verify you are not a robot.'}), 403

    # Validation
    if not username or not email or not password:
        return jsonify({'success': False, 'message': 'All fields are required.'}), 400
    
    if len(username) < 3:
        return jsonify({'success': False, 'message': 'Username must be at least 3 characters long.'}), 400
        
    if len(password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters long.'}), 400
    
    # Check for existing username
    if user_exists(username):
        return jsonify({'success': False, 'message': 'Username already exists. Please choose a different one.'}), 409
    
    # Check for existing email
    if email_exists(email):
        return jsonify({'success': False, 'message': 'Email already registered. Please use a different email or try logging in.'}), 409
    
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    if not re.match(email_pattern, email):
        return jsonify({'success': False, 'message': 'Please enter a valid email address.'}), 400
    
    try:
        # Create user
        user_id = create_user(username, password, email)
        
        # Set session - IMPORTANT: Make sure session is properly set
        session.clear()  # Clear any existing session data
        session['username'] = username
        session['_id'] = user_id
        session.permanent = True
        
        current_app.logger.info(f"User {username} signed up successfully with ID {user_id}")
        
        return jsonify({
            'success': True, 
            'message': 'Account created successfully!',
            'user': {
                'username': username,
                '_id': str(user_id)
            }
        }), 201
        
    except Exception as e:
        current_app.logger.error(f"Error creating user: {e}")
        return jsonify({'success': False, 'message': 'Failed to create account. Please try again.'}), 500

@api_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    turnstile_token = data.get('cf_turnstile_response')

    if not verify_turnstile(turnstile_token, Config.CLOUDFLARE_SECRET, request.remote_addr):
        return jsonify({'success': False, 'message': 'Please verify you are not a robot.'}), 403

    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password are required.'}), 400
    
    if len(password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters long.'}), 400
    
    try:
        user = get_user(username, password)
        if user:
            # Set session - IMPORTANT: Make sure session is properly set
            session.clear()  # Clear any existing session data
            session['username'] = username
            session['_id'] = user['_id']
            session.permanent = True
            
            current_app.logger.info(f"User {username} logged in successfully")
            
            return jsonify({
                'success': True,
                'message': 'Login successful!',
                'user': {
                    'username': username,
                    '_id': str(user['_id'])
                }
            }), 200
        else:
            return jsonify({'success': False, 'message': 'Invalid username or password.'}), 401
            
    except Exception as e:
        current_app.logger.error(f"Error during login: {e}")
        return jsonify({'success': False, 'message': 'Login failed. Please try again.'}), 500

@api_bp.route('/logout', methods=['POST'])
def logout():
    try:
        username = session.get('username', 'Unknown')
        session.clear()
        current_app.logger.info(f"User {username} logged out successfully")
        return jsonify({'success': True, 'message': 'Logged out successfully.'}), 200
    except Exception as e:
        current_app.logger.error(f"Error during logout: {e}")
        return jsonify({'success': True, 'message': 'Logged out successfully.'}), 200  # Still return success

@api_bp.route('/me', methods=['GET'])
def me():
    try:
        username = session.get('username')
        user_id = session.get('_id')
        
        current_app.logger.debug(f"Checking session: username={username}, user_id={user_id}")
        
        if username and user_id:
            user = get_user_by_id(user_id)
            if user:
                # Get comprehensive AniList connection info
                anilist_info = get_anilist_connection_info(user_id)
                
                return jsonify({
                    'username': username,
                    '_id': str(user['_id']),
                    'anilist_authenticated': anilist_info.get('connected', False),
                    'avatar': user.get('avatar'),
                    'anilist_id': user.get('anilist_id'),
                    'anilist_stats': user.get('anilist_stats', {}),
                    'auth_method': user.get('auth_method', 'local')
                }), 200
        
        # No valid session
        return jsonify(None), 401
        
    except Exception as e:
        current_app.logger.error(f"Error checking session: {e}")
        return jsonify(None), 401

@api_bp.route('/anilist/status', methods=['GET'])
def get_anilist_status():
    """Get detailed AniList connection status for the current user."""
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

@api_bp.route('/anilist/disconnect', methods=['POST'])
def disconnect_anilist():
    """API endpoint to disconnect AniList account."""
    if 'username' not in session or '_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in.'}), 401
    
    # Import the auth blueprint function
    from ..routes.auth import unlink_anilist_account
    return unlink_anilist_account()

@api_bp.route('/sync-progress', methods=['GET'])
def sync_progress():
    """Get current sync progress for the logged-in user."""
    if 'username' not in session or '_id' not in session:
        return jsonify({'error': 'Not logged in.'}), 401
    
    try:
        user_id = session.get('_id')
        progress = get_sync_progress(user_id)
        
        if not progress:
            return jsonify({'status': 'none', 'message': 'No sync in progress'})
        
        # Clean up old progress (older than 1 hour)
        if time.time() - progress.get('timestamp', 0) > 3600:
            clear_sync_progress(user_id)
            return jsonify({'status': 'none', 'message': 'No sync in progress'})
        
        return jsonify(progress)
        
    except Exception as e:
        logger.error(f"Error getting sync progress: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to get progress'})

@api_bp.route('/sync-progress/clear', methods=['POST'])
def clear_sync_progress_route():
    """Clear sync progress for the current user."""
    if 'username' not in session or '_id' not in session:
        return jsonify({'error': 'Not logged in.'}), 401
    
    try:
        user_id = session.get('_id')
        clear_sync_progress(user_id)
        return jsonify({'success': True, 'message': 'Progress cleared'})
    except Exception as e:
        logger.error(f"Error clearing sync progress: {e}")
        return jsonify({'success': False, 'message': 'Failed to clear progress'})

@api_bp.route('/sync-anilist', methods=['POST'])
def sync_anilist():
    """Sync AniList watchlist to local database."""
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
        
        def progress_callback(progress):
            """Progress callback to update UI"""
            try:
                store_sync_progress(user_id, {
                    'status': 'syncing',
                    'processed': progress.processed,
                    'total': progress.total,
                    'synced': progress.synced,
                    'skipped': progress.skipped,
                    'failed': progress.failed,
                    'percentage': progress.percentage,
                    'estimated_remaining': getattr(progress, 'estimated_remaining', 0),
                    'message': f'Syncing... {progress.processed}/{progress.total} processed'
                })
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")
        
        # Run the sync function with progress callback
        result = sync_anilist_watchlist_blocking(user_id, access_token, progress_callback)
        
        # Update final progress
        if 'error' in result:
            store_sync_progress(user_id, {
                'status': 'error',
                'message': f'Sync failed: {result["error"]}',
                'error': result['error']
            })
            return jsonify({'success': False, 'message': f'Sync failed: {result["error"]}'}), 500
        
        # Calculate success metrics
        synced_count = result.get('synced_count', 0)
        skipped_count = result.get('skipped_count', 0)
        failed_count = result.get('failed_count', 0)
        total_count = result.get('total_count', 0)
        
        success_count = synced_count + skipped_count
        success_rate = (success_count / total_count * 100) if total_count > 0 else 0
        
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
            'message': f'Sync completed! {success_count}/{total_count} entries processed successfully.'
        })
        
        # Determine if sync should be considered successful
        # Consider it successful if we processed at least 70% successfully
        is_success = success_rate >= 70.0
        
        if is_success:
            message = f'Sync completed successfully! Added {synced_count} new entries, skipped {skipped_count} duplicates.'
            if failed_count > 0:
                message += f' {failed_count} entries could not be matched.'
        else:
            message = f'Sync partially completed. Only {success_count}/{total_count} entries were processed successfully.'
        
        return jsonify({
            'success': is_success,
            'message': message,
            'synced_count': synced_count,
            'skipped_count': skipped_count,
            'failed_count': failed_count,
            'total_count': total_count,
            'success_rate': f'{success_rate:.1f}%',
            'elapsed_time': result.get('elapsed_time', 'N/A')
        })
        
    except Exception as e:
        user_id = session.get('_id', 'unknown')
        logger.error(f"Error syncing AniList watchlist for user {user_id}: {e}")
        
        store_sync_progress(user_id, {
            'status': 'error',
            'message': f'Unexpected error: {str(e)}',
            'error': str(e)
        })
        
        return jsonify({'success': False, 'message': 'Sync failed due to unexpected error. Please try again.'}), 500



@api_bp.route('/watchlist/paginated', methods=['GET'])
async def watchlist_paginated():
    """
    Returns paginated watchlist data for current user.
    Expected query params: page (default 1), limit (default 20), status (optional).
    Each returned watchlist item will include poster_url and total_episodes (enriched from Hianime scraper).
    """
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    try:
        user_id = session.get('_id')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        status_filter = request.args.get('status', '').strip()

        # sanitize inputs
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

        # Use asyncio.gather for concurrent enrichment
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
                result['data'][i] = {} # Return a blank item instead of crashing

        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in watchlist_paginated: {e}")
        return jsonify({'data': [], 'pagination': {}, 'error': str(e)}), 500


@api_bp.route('/watchlist/update', methods=['POST'])
def update_watchlist():
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    anime_id = data.get('anime_id')
    action = data.get('action')  # 'status' or 'episodes'
    
    # Add debugging
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

@api_bp.route('/watchlist/remove', methods=['POST'])
def remove_from_watchlist_route():
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

@api_bp.route('/watchlist/get', methods=['GET'])
def get_watchlist_route():
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

@api_bp.route('/watchlist/add', methods=['POST'])
def add_to_watchlist_route():
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    anime_id = data.get('anime_id')
    anime_title = data.get('anime_title')
    status = data.get('status', 'watching')
    total_episodes = data.get('total_episodes', 0)
    
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

@api_bp.route('/watchlist/status', methods=['GET'])
def get_watchlist_status():
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

@api_bp.route('/watchlist/stats', methods=['GET'])
def get_watchlist_stats_route():
    """Get user's watchlist statistics."""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        user_id = session.get('_id')
        
        # Use the optimized stats function from watchlist_manager
        stats = get_watchlist_stats(user_id)
        return jsonify(stats or {})
        
    except Exception as e:
        current_app.logger.error(f"Error getting watchlist stats: {e}")
        return jsonify({}), 500

@api_bp.route('/watchlist/warm-cache', methods=['POST'])
def warm_watchlist_cache():
    """Pre-warm cache for user's watchlist."""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        user_id = session.get('_id')
        warm_cache(user_id)
        
        return jsonify({'success': True, 'message': 'Cache warmed successfully'})
        
    except Exception as e:
        current_app.logger.error(f"Error warming cache: {e}")
        return jsonify({'success': False, 'message': 'Failed to warm cache'}), 500

@api_bp.route('/change-password', methods=['POST'])
def change_password_route():
    """Change user password."""
    if 'username' not in session or '_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in.'}), 401
    
    data = request.get_json()
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')
    
    if not current_password or not new_password:
        return jsonify({'success': False, 'message': 'Current and new passwords are required.'}), 400
    
    if len(new_password) < 6:
        return jsonify({'success': False, 'message': 'New password must be at least 6 characters long.'}), 400
    
    try:
        from ..models.user import change_password
        user_id = session.get('_id')
        
        result = change_password(user_id, current_password, new_password)
        
        if result:
            current_app.logger.info(f"Password changed successfully for user {session.get('username')}")
            return jsonify({'success': True, 'message': 'Password changed successfully!'})
        else:
            return jsonify({'success': False, 'message': 'Current password is incorrect.'}), 400
            
    except Exception as e:
        current_app.logger.error(f"Error changing password: {e}")
        return jsonify({'success': False, 'message': 'Failed to change password. Please try again.'}), 500