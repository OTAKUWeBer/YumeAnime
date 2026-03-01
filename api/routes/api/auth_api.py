"""
Authentication API endpoints
Handles signup, login, logout, and session management
"""
from flask import Blueprint, request, session, jsonify, current_app, make_response
import re
import logging

from ...utils.helpers import verify_turnstile
from ...models.user import (
    create_user, get_user, user_exists, email_exists, get_user_by_id, change_password
)
from ...core.caching import clear_user_cache
from ...core.config import Config
from ...core.extensions import limiter

auth_api_bp = Blueprint('auth_api', __name__)
logger = logging.getLogger(__name__)


@auth_api_bp.route('/signup', methods=['POST'])
@limiter.limit("3 per minute")
def signup():
    """User registration endpoint"""
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
    
    if user_exists(username):
        return jsonify({'success': False, 'message': 'Username already exists. Please choose a different one.'}), 409
    
    if email_exists(email):
        return jsonify({'success': False, 'message': 'Email already registered. Please use a different email or try logging in.'}), 409
    
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    if not re.match(email_pattern, email):
        return jsonify({'success': False, 'message': 'Please enter a valid email address.'}), 400
    
    try:
        user_id = create_user(username, password, email)
        
        session.clear()
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


@auth_api_bp.route('/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    """User login endpoint"""
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    turnstile_token = data.get('cf_turnstile_response')
    client_ip = request.remote_addr

    current_app.logger.info(f"Login attempt for user '{username}' from IP: {client_ip}")

    if not verify_turnstile(turnstile_token, Config.CLOUDFLARE_SECRET, client_ip):
        current_app.logger.warning(f"Failed captcha for user '{username}' from IP: {client_ip}")
        return jsonify({'success': False, 'message': 'Please verify you are not a robot.'}), 403

    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password are required.'}), 400
    
    if len(password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters long.'}), 400
    
    try:
        user = get_user(username, password)
        if user:
            session.clear()
            session['username'] = username
            session['_id'] = user['_id']
            session.permanent = True
            
            current_app.logger.info(f"User {username} logged in successfully from IP: {client_ip}")
            
            return jsonify({
                'success': True,
                'message': 'Login successful!',
                'user': {
                    'username': username,
                    '_id': str(user['_id'])
                }
            }), 200
        else:
            current_app.logger.warning(f"Failed login for user '{username}' from IP: {client_ip} (Invalid credentials)")
            return jsonify({'success': False, 'message': 'Invalid username or password.'}), 401
            
    except Exception as e:
        current_app.logger.error(f"Error during login: {e}")
        return jsonify({'success': False, 'message': 'Login failed. Please try again.'}), 500


@auth_api_bp.route('/logout', methods=['POST'])
def logout():
    """User logout endpoint"""
    try:
        user_id = session.get('_id')
        if user_id:
            clear_user_cache(int(user_id))
        
        username = session.get('username', 'Unknown')
        session.clear()
        
        # Create response and explicitly delete the session cookie
        response = make_response(jsonify({'success': True, 'message': 'Logged out successfully.'}))
        response.delete_cookie('session')
        
        current_app.logger.info(f"User {username} logged out successfully via API")
        return response, 200
    except Exception as e:
        current_app.logger.error(f"Error during logout: {e}")
        # Always return success on logout to prevent client issues
        session.clear()
        response = make_response(jsonify({'success': True, 'message': 'Logged out successfully.'}))
        response.delete_cookie('session')
        return response, 200


@auth_api_bp.route('/me', methods=['GET'])
def me():
    """Get current user session info"""
    try:
        username = session.get('username')
        user_id = session.get('_id')
        
        current_app.logger.debug(f"Checking session: username={username}, user_id={user_id}")
        
        if username and user_id:
            user = get_user_by_id(user_id)
            if user:
                from ...models.user import get_anilist_connection_info
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
        
        return jsonify(None), 401
        
    except Exception as e:
        current_app.logger.error(f"Error checking session: {e}")
        return jsonify(None), 401


@auth_api_bp.route('/change-password', methods=['POST'])
def change_password_route():
    """Change user password"""
    if 'username' not in session or '_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in.'}), 401
    
    data = request.get_json()
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')
    turnstile_token = data.get('cf_turnstile_response')
    
    if not verify_turnstile(turnstile_token, Config.CLOUDFLARE_SECRET, request.remote_addr):
        return jsonify({'success': False, 'message': 'Please verify you are not a robot.'}), 403
    
    if not current_password or not new_password:
        return jsonify({'success': False, 'message': 'Current and new passwords are required.'}), 400
    
    if len(new_password) < 6:
        return jsonify({'success': False, 'message': 'New password must be at least 6 characters long.'}), 400
    
    try:
        user_id = session.get('_id')
        
        result = change_password(user_id, current_password, new_password)
        
        if result:
            current_app.logger.info(f"Password changed successfully for user {session.get('username')}")
            return jsonify({'success': True, 'message': 'Password changed successfully!'}), 200
        else:
            return jsonify({'success': False, 'message': 'Current password is incorrect.'}), 400
            
    except Exception as e:
        current_app.logger.error(f"Error changing password: {e}")
        return jsonify({'success': False, 'message': 'Failed to change password. Please try again.'}), 500
