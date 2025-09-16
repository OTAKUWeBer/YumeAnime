from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, current_app
from urllib.parse import urlencode
import secrets
import requests
import logging

from ..utils.helpers import verify_turnstile, get_anilist_user_info
from ..models.user import (
    get_user, user_exists, email_exists, create_user, get_user_by_id,
    get_user_by_anilist_id, create_anilist_user, update_anilist_user,
    link_anilist_to_existing_user, unlink_anilist_from_user, delete_anilist_data,
    connect_anilist_to_user
)
from ..utils.auto_sync import trigger_auto_sync
from ..core.config import Config

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

@auth_bp.route('/anilist/link')
def link_anilist_account():
    """Link AniList account to existing logged-in user."""
    # Check if user is already logged in
    if 'username' not in session or '_id' not in session:
        flash('Please log in first to link your AniList account.', 'warning')
        return redirect(url_for('main.home'))
    
    # Generate a random state parameter for security
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    session['linking_account'] = True  # Flag to indicate we're linking, not creating new
    
    # Build the authorization URL
    params = {
        'client_id': Config.ANILIST_CLIENT_ID,
        'redirect_uri': Config.ANILIST_REDIRECT_URI,
        'response_type': 'code',
        'state': state
    }
    
    auth_url = f"https://anilist.co/api/v2/oauth/authorize?{urlencode(params)}"
    return redirect(auth_url)

@auth_bp.route('/anilist/callback')
def anilist_callback():
    """Handle AniList OAuth callback with account linking support."""
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    
    # Check for errors
    if error:
        current_app.logger.error(f"AniList OAuth error: {error}")
        flash('Login failed. Please try again.', 'error')
        return redirect(url_for('main.home'))
    
    # Check if we're linking to existing account (only if user is logged in)
    is_linking = 'username' in session and '_id' in session
    current_user_id = session.get('_id') if is_linking else None
    current_username = session.get('username') if is_linking else None
    
    if not code:
        flash('Login cancelled or failed.', 'error')
        return redirect(url_for('main.home'))
    
    try:
        # Exchange code for access token
        token_data = {
            'grant_type': 'authorization_code',
            'client_id': Config.ANILIST_CLIENT_ID,
            'client_secret': Config.ANILIST_CLIENT_SECRET,
            'redirect_uri': Config.ANILIST_REDIRECT_URI,
            'code': code
        }
        
        token_response = requests.post('https://anilist.co/api/v2/oauth/token', json=token_data)
        
        if token_response.status_code != 200:
            current_app.logger.error(f"Token exchange failed: {token_response.text}")
            flash('Login failed. Unable to get access token.', 'error')
            return redirect(url_for('main.home'))
        
        token_info = token_response.json()
        access_token = token_info.get('access_token')
        
        if not access_token:
            flash('Login failed. No access token received.', 'error')
            return redirect(url_for('main.home'))
        
        # Get user info from AniList
        user_info = get_anilist_user_info(access_token)
        
        if not user_info:
            flash('Login failed. Unable to get user information.', 'error')
            return redirect(url_for('main.home'))
        
        # Check if this AniList account is already linked to another user
        existing_anilist_user = get_user_by_anilist_id(user_info['id'])
        
        if is_linking and current_user_id:
            # ACCOUNT LINKING MODE (user is already logged in)
            if existing_anilist_user:
                if existing_anilist_user['_id'] == current_user_id:
                    flash('This AniList account is already linked to your account.', 'info')
                else:
                    flash('This AniList account is already linked to another user account.', 'error')
                return redirect(url_for('main.settings'))
            
            # Connect AniList account to existing user
            result = connect_anilist_to_user(current_user_id, user_info, access_token)
            if result:
                session['anilist_authenticated'] = True
                session['anilist_id'] = user_info['id']
                current_app.logger.info(f"AniList account linked to user {current_username}")
                flash('AniList account successfully connected! You can now sync your watchlist.', 'success')
                
                # Trigger auto-sync in background
                try:
                    trigger_auto_sync(current_user_id)
                    current_app.logger.info(f"Auto-sync triggered for user {current_username}")
                except Exception as e:
                    current_app.logger.warning(f"Failed to trigger auto-sync for user {current_username}: {e}")
            else:
                flash('Failed to connect AniList account. It may already be linked to another account.', 'error')
            
            return redirect(url_for('main.settings'))
        
        else:
            # NORMAL LOGIN/SIGNUP MODE (user is not logged in)
            if existing_anilist_user:
                # Update existing user with latest AniList info
                update_anilist_user(existing_anilist_user['_id'], user_info, access_token)
                user_id = existing_anilist_user['_id']
                username = existing_anilist_user['username']
            else:
                # Create new user
                user_id = create_anilist_user(user_info, access_token)
                username = user_info['name']
            
            # Set session
            session.clear()
            session['username'] = username
            session['_id'] = user_id
            session['anilist_authenticated'] = True
            session['anilist_id'] = user_info['id']
            session.permanent = True
            
            current_app.logger.info(f"User {username} logged in via AniList successfully")
            flash(f'Welcome, {username}!', 'success')
            
            # Trigger auto-sync for new AniList users
            try:
                trigger_auto_sync(user_id)
                current_app.logger.info(f"Auto-sync triggered for new AniList user {username}")
            except Exception as e:
                current_app.logger.warning(f"Failed to trigger auto-sync for new user {username}: {e}")
            
            return redirect(url_for('main.home'))
        
    except Exception as e:
        current_app.logger.error(f"AniList OAuth error: {e}")
        flash('Login failed. Please try again.', 'error')
        return redirect(url_for('main.home'))

@auth_bp.route('/anilist/unlink', methods=['POST'])
def unlink_anilist_account():
    """Unlink AniList account from current user."""
    if 'username' not in session or '_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in.'}), 401
    
    try:
        user_id = session.get('_id')
        
        # Get user data before unlinking to log the action
        user = get_user_by_id(user_id)
        if not user:
            return jsonify({'success': False, 'message': 'User not found.'}), 404
        
        anilist_id = user.get('anilist_id')
        username = user.get('username', 'Unknown')
        
        # Delete all AniList-related data from the user
        result = delete_anilist_data(user_id)
        
        if result:
            # Update session to reflect the change
            session['anilist_authenticated'] = False
            if 'anilist_id' in session:
                del session['anilist_id']
            
            logger.info(f"AniList account (ID: {anilist_id}) disconnected from user {username} (ID: {user_id})")
            return jsonify({
                'success': True, 
                'message': 'AniList account disconnected successfully. All AniList data has been removed from your account.'
            })
        else:
            logger.error(f"Failed to disconnect AniList account for user {username} (ID: {user_id})")
            return jsonify({'success': False, 'message': 'Failed to disconnect AniList account. Please try again.'})
            
    except Exception as e:
        logger.error(f"Error disconnecting AniList account for user {session.get('username', 'Unknown')}: {e}")
        return jsonify({'success': False, 'message': 'An unexpected error occurred. Please try again.'})

@auth_bp.route('/anilist/connect', methods=['GET'])
def connect_anilist_account():
    """Connect AniList account - same as link but with different messaging."""
    # Check if user is already logged in
    if 'username' not in session or '_id' not in session:
        flash('Please log in first to connect your AniList account.', 'warning')
        return redirect(url_for('main.home'))
    
    # Check if already connected
    user_id = session.get('_id')
    user = get_user_by_id(user_id)
    if user and user.get('anilist_id'):
        flash('Your AniList account is already connected.', 'info')
        return redirect(url_for('main.settings'))
    
    # Generate a random state parameter for security
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    session['connecting_account'] = True  # Flag to indicate we're connecting
    
    # Build the authorization URL
    params = {
        'client_id': Config.ANILIST_CLIENT_ID,
        'redirect_uri': Config.ANILIST_REDIRECT_URI,
        'response_type': 'code',
        'state': state
    }
    
    auth_url = f"https://anilist.co/api/v2/oauth/authorize?{urlencode(params)}"
    return redirect(auth_url)

@auth_bp.route('/anilist/disconnect', methods=['POST'])
def disconnect_anilist_account():
    """Disconnect AniList account from current user (alternative endpoint)."""
    return unlink_anilist_account()

@auth_bp.route('/anilist/status', methods=['GET'])
def anilist_status():
    """Get current AniList connection status for the user."""
    if 'username' not in session or '_id' not in session:
        return jsonify({'connected': False, 'message': 'Not logged in.'}), 401
    
    try:
        user_id = session.get('_id')
        user = get_user_by_id(user_id)
        
        if not user:
            return jsonify({'connected': False, 'message': 'User not found.'}), 404
        
        is_connected = bool(user.get('anilist_id'))
        anilist_data = {}
        
        if is_connected:
            anilist_data = {
                'anilist_id': user.get('anilist_id'),
                'avatar': user.get('avatar'),
                'anilist_stats': user.get('anilist_stats', {}),
                'connected_at': user.get('updated_at')
            }
        
        return jsonify({
            'connected': is_connected,
            'anilist_data': anilist_data if is_connected else None,
            'message': 'Connected to AniList' if is_connected else 'Not connected to AniList'
        })
        
    except Exception as e:
        logger.error(f"Error checking AniList status for user {session.get('username', 'Unknown')}: {e}")
        return jsonify({'connected': False, 'message': 'Error checking connection status.'}), 500
