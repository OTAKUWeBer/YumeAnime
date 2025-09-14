

from .ani_to_yume import *

# Re-export all functions so they can be imported from utils
__all__ = [
    'create_user', 
    'get_user', 
    'user_exists', 
    'get_user_by_id', 
    'email_exists',
    'update_user_avatar',
    'update_user_email', 
    'change_password',
    'delete_user',
    'get_all_users',
    'get_user_count',
    'search_users',
    'get_recent_users'
]

from .ani_to_yume import sync_anilist_watchlist_to_local

__all__ = [
    # User management
    'create_user', 'get_user', 'user_exists', 'get_user_by_id', 'email_exists',
    'update_user_email', 'update_user_avatar', 'get_user_by_anilist_id',
    'create_anilist_user', 'update_anilist_user', 'link_anilist_to_existing_user',
    'unlink_anilist_from_user',
    
    # Watchlist management
    'add_to_watchlist', 'get_watchlist_entry', 'update_watchlist_status',
    'update_watched_episodes', 'remove_from_watchlist', 'get_user_watchlist',
    'get_user_watchlist_paginated', 'get_watchlist_stats', 'warm_cache',
    
    # AniList sync
    'sync_anilist_watchlist_to_local'
]