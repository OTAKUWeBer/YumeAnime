from flask import Blueprint, render_template, session
import logging


watchlist_bp = Blueprint('watchlist', __name__)
logger = logging.getLogger(__name__)

@watchlist_bp.route('/', methods=['GET'])
def watchlist():
    if 'username' not in session:
        return render_template('404.html', error_message="Page not found"), 404
    return render_template('watchlist.html')
