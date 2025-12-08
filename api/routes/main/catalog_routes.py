"""
Catalog browsing routes (genre, profile, settings)
"""
import asyncio
from flask import Blueprint, request, session, redirect, url_for, render_template, flash, current_app
from markupsafe import escape

from ...models.user import get_user_by_id
from ...core.caching import cache_result, USER_DATA_CACHE_DURATION

catalog_routes_bp = Blueprint('catalog_routes', __name__)


@catalog_routes_bp.route('/genre/<genre_name>', methods=['GET'])
def genre(genre_name):
    """Display anime list for a specific genre"""
    genre_name = escape(genre_name)
    
    try:
        data = asyncio.run(current_app.ha_scraper.genre(genre_name))
        animes = data.get("animes", [])
        if not animes:
            return render_template('404.html', error_message=f"No animes found for genre: {genre_name}"), 404
        
        genre_data = {
            'genreName': f"{genre_name.title()} Anime",
            'animes': []
        }
        
        for anime in animes:
            anime_id = anime.get("id")
            if not anime_id:
                continue
                
            # Map all required fields for the template
            mapped_anime = {
                "id": anime_id,
                "name": anime.get("name") or anime.get("title") or anime_id,
                "jname": anime.get("jname") or anime.get("japanese_name") or "",
                "poster": anime.get("poster") or anime.get("image") or "",
                "duration": anime.get("duration") or "N/A",
                "type": anime.get("type") or "Unknown",
                "rating": anime.get("rating"),
                "episodes": {
                    "sub": anime.get("episodes", {}).get("sub") if anime.get("episodes") else None,
                    "dub": anime.get("episodes", {}).get("dub") if anime.get("episodes") else None
                }
            }
            genre_data['animes'].append(mapped_anime)
        
        return render_template('genre.html', **genre_data)
    
    except Exception as e:
        current_app.logger.exception(f"Error fetching genre {genre_name}")
        return render_template('404.html', error_message=f"Error fetching genre: {e}"), 500


@catalog_routes_bp.route('/profile', methods=['GET'])
def profile():
    """Display user profile page"""
    username = session.get('username')
    user_id = session.get('_id')
    
    if not username or not user_id:
        flash('Please log in to view your profile.', 'warning')
        return redirect('/home')
    
    try:
        user = get_user_by_id(user_id)
        if not user:
            session.clear()
            flash('User session expired. Please log in again.', 'error')
            return redirect('/home')
        
        # Prepare user data for template
        created = user.get('created_at')
        user_data = {
            'email': user.get('email', ''),
            'joined_date': created.strftime('%B %d, %Y') if created else 'Unknown',
            'avatar': user.get('avatar'),
            'anilist_authenticated': bool(user.get('anilist_id')),
            'anilist_id': user.get('anilist_id'),
            'anilist_stats': user.get('anilist_stats', {})
        }
        
        return render_template('profile.html', 
                             user=user_data, 
                             username=username, 
                             user_id=str(user_id))
        
    except Exception as e:
        current_app.logger.error(f"Error loading profile for user {username}: {e}")
        user_data = {
            'email': 'Error loading data',
            'joined_date': 'Error loading data',
            'avatar': None,
            'anilist_authenticated': False
        }
        return render_template('profile.html',
                               user=user_data,
                               username=username,
                               user_id=str(user_id),
                               error="Error loading profile data")


@catalog_routes_bp.route('/settings', methods=['GET'])
def settings():
    """Display user settings page"""
    username = session.get('username')
    user_id = session.get('_id')
    
    if not username or not user_id:
        flash('Please log in to access settings.', 'warning')
        return redirect('/home')
    
    try:
        user = get_user_by_id(user_id)
        if not user:
            session.clear()
            flash('User session expired. Please log in again.', 'error')
            return redirect('/home')
        
        # Prepare user data for template
        user_data = {
            'username': username,
            'email': user.get('email', ''),
            'anilist_authenticated': bool(user.get('anilist_id')),
            'anilist_id': user.get('anilist_id'),
            'avatar': user.get('avatar'),
            'created_at': user.get('created_at')
        }
        
        return render_template('settings.html', user=user_data)
        
    except Exception as e:
        current_app.logger.error(f"Error loading settings for user {username}: {e}")
        flash('Error loading settings. Please try again.', 'error')
        return redirect('/home')
