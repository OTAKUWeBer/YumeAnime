from flask import Blueprint, render_template, session, redirect, flash
import logging
from ..models.user import get_user_by_id

watchlist_bp = Blueprint('watchlist', __name__)
logger = logging.getLogger(__name__)

@watchlist_bp.route('/', methods=['GET'])
def watchlist():
    username = session.get('username')
    user_id = session.get('_id')
    
    if not username or not user_id:
        return redirect('/home')
        
    try:
        user = get_user_by_id(user_id)
        if not user:
            session.clear()
            return redirect('/home')
            
        user_data = {
            'username': username,
            'email': user.get('email', ''),
            'avatar': user.get('avatar'),
            'anilist_authenticated': bool(user.get('anilist_id')),
            'anilist_id': user.get('anilist_id'),
            'anilist_stats': user.get('anilist_stats', {})
        }
        
        return render_template('watchlist.html', user=user_data, username=username)
    except Exception as e:
        logger.error(f"Error loading watchlist profile for user {username}: {e}")
        return render_template('watchlist.html', error="Error loading profile data", user={'username': username}, username=username)
