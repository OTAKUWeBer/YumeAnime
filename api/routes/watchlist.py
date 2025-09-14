from flask import Blueprint, render_template, request, session, jsonify, current_app
import logging
import time

from ..models.watchlist import (
    add_to_watchlist, get_watchlist_entry, update_watchlist_status,
    update_watched_episodes, remove_from_watchlist, get_user_watchlist,
    get_user_watchlist_paginated, get_watchlist_stats, warm_cache
)
from ..models.user import get_user_by_id
from ..utils.helpers import (
    sync_anilist_watchlist_blocking, store_sync_progress, 
    get_sync_progress, clear_sync_progress
)


watchlist_bp = Blueprint('watchlist', __name__)
logger = logging.getLogger(__name__)

@watchlist_bp.route('/', methods=['GET'])
def watchlist():
    if 'username' not in session:
        return render_template('404.html', error_message="Page not found"), 404
    return render_template('watchlist.html')
