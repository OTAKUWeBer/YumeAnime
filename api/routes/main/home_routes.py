"""
Home and index routes
"""
from flask import Blueprint, redirect, render_template, current_app

home_routes_bp = Blueprint('home_routes', __name__)


@home_routes_bp.route('/', methods=["GET"])
async def index():
    """Redirect to home page"""
    return redirect("/home")


@home_routes_bp.route("/home", methods=["GET"])
async def home():
    """Display home page with anime sections"""
    info = "Home"
    try:
        data = await current_app.ha_scraper.home()
        current_app.logger.debug("home counts: %s", data.get("counts"))
        return render_template("index.html", suggestions=data, info=info)
    except Exception as e:
        current_app.logger.exception("Unhandled error in /home")
        empty = {
            k: [] for k in [
                "latestEpisodeAnimes",
                "mostPopularAnimes",
                "spotlightAnimes",
                "trendingAnimes"
            ]
        }
        return render_template(
            "index.html",
            suggestions={"success": False, "data": empty, "counts": {}},
            error=f"Error fetching home page data: {e}",
            info=info
        )
