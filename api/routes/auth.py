from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, current_app
from urllib.parse import urlencode
import secrets
import requests

from ..utils.helpers import verify_turnstile, get_anilist_user_info
from ..models.user import (
    get_user, user_exists, email_exists, create_user, get_user_by_id,
    get_user_by_anilist_id, create_anilist_user, update_anilist_user,
    link_anilist_to_existing_user, unlink_anilist_from_user
)
from ..core.config import Config

auth_bp = Blueprint('auth', __name__)

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
                return redirect(url_for('auth.profile'))
            
            # Link AniList account to existing user
            result = link_anilist_to_existing_user(current_user_id, user_info, access_token)
            if result:
                session['anilist_authenticated'] = True
                current_app.logger.info(f"AniList account linked to user {current_username}")
                flash('AniList account successfully linked to your account!', 'success')
            else:
                flash('Failed to link AniList account. Please try again.', 'error')
            
            return redirect(url_for('auth.profile'))
        
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
            session.permanent = True
            
            current_app.logger.info(f"User {username} logged in via AniList successfully")
            flash(f'Welcome, {username}!', 'success')
            
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
        result = unlink_anilist_from_user(user_id)
        
        if result:
            session['anilist_authenticated'] = False
            return jsonify({'success': True, 'message': 'AniList account unlinked successfully.'})
        else:
            return jsonify({'success': False, 'message': 'Failed to unlink AniList account.'})
            
    except Exception as e:
        current_app.logger.error(f"Error unlinking AniList account: {e}")
        return jsonify({'success': False, 'message': 'An error occurred.'})
