"""
Comments & Episode Reactions API endpoints.
All routes live under /api/ (registered with no extra prefix).
"""
from flask import Blueprint, request, session, jsonify
from ...core.extensions import limiter
from ...models.comments import (
    get_comments, create_comment, toggle_comment_reaction,
    edit_comment, delete_comment,
    get_episode_reaction, toggle_episode_reaction,
)
from ...core.db_connector import comments_collection
from bson import ObjectId
from datetime import datetime, timezone
import re

comments_api_bp = Blueprint("comments_api", __name__)

import re

BANNED_WORDS = {
    # English (strong)
    "nigger", "nigga", "faggot", "fag", "retard",
    "cunt", "slut", "whore", "fuck", "motherfucker",
    "kys", "kill yourself", "go die", "end yourself",
    # Hindi / Urdu
    "madarchod", "bhenchod", "chutiya", "randi", "gandu", "lund",
    # Bengali (Bangla)
    "chod", "choda", "khanki", "bhoda", "chudi", "bainchod", "magir pola", "shuwor", "kuttar baccha",
    # Arabic
    "sharmuta", "ibn sharmuta", "ya kalb", "ya ibn al kalb",
    # Spanish
    "puta", "hijo de puta", "maricon", "cabron",
    # French
    "pute", "salope", "connard",
    # German
    "hurensohn", "fotze",
    # Filipino
    "putang ina", "gago",
    # Indonesian / Malay
    "anjing", "bangsat",
    # Turkish
    "orospu", "orospu cocugu",
}

# Words too short/ambiguous for word-boundary matching — require surrounding context
_CONTEXT_BANNED = {"bc", "mc"}

_PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(w) for w in BANNED_WORDS) + r')\b',
    re.IGNORECASE
)

# bc/mc only flagged when used as standalone insults, e.g. "bc teri" / "mc sala"
# Matches: bc or mc followed or preceded by a Hindi/Urdu word or another slur
_CONTEXT_PATTERN = re.compile(
    r'\b(bc|mc)\b(?=\s+\w)|\b\w+\s+(bc|mc)\b',
    re.IGNORECASE
)

def contains_banned_words(text: str) -> bool:
    if not text:
        return False
    if _PATTERN.search(text):
        return True
    if _CONTEXT_PATTERN.search(text):
        return True
    return False

def _require_auth():
    """Return (user_id, username, avatar) if logged in, else None."""
    if "username" in session and "_id" in session:
        return str(session["_id"]), session["username"], session.get("avatar")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Comments
# ─────────────────────────────────────────────────────────────────────────────

@comments_api_bp.route("/comments", methods=["GET"])
def list_comments():
    """GET /api/comments?anime_id=&ep=<number>"""
    anime_id = request.args.get("anime_id", "").strip()
    ep = request.args.get("ep", "")
    if not anime_id or not ep:
        return jsonify({"success": False, "message": "Missing anime_id or ep"}), 400
    try:
        ep_num = int(ep)
    except ValueError:
        return jsonify({"success": False, "message": "ep must be an integer"}), 400

    comments = get_comments(anime_id, ep_num)
    return jsonify({"success": True, "comments": comments, "count": len(comments)})


@comments_api_bp.route("/comments", methods=["POST"])
@limiter.limit("4 per minute")
def post_comment():
    """POST /api/comments — create a new top-level comment."""
    auth = _require_auth()
    if not auth:
        return jsonify({"success": False, "message": "Login required"}), 401

    user_id, username, avatar = auth
    data = request.get_json() or {}
    anime_id = data.get("anime_id", "").strip()
    ep = data.get("episode_number")
    body = data.get("body", "")
    if isinstance(body, str): body = body.strip()
    
    gif_url = data.get("gif_url")
    if isinstance(gif_url, str):
        gif_url = gif_url.strip() or None
    else:
        gif_url = None

    if not anime_id or ep is None:
        return jsonify({"success": False, "message": "Missing anime_id or episode_number"}), 400
    if not body and not gif_url:
        return jsonify({"success": False, "message": "Comment cannot be empty"}), 400
    if body and len(body) > 2000:
        return jsonify({"success": False, "message": "Comment too long (max 2000 chars)"}), 400
    if contains_banned_words(body):
        return jsonify({"success": False, "message": "Comment contains inappropriate language"}), 400

    comment = create_comment(
        anime_id=anime_id,
        episode_number=int(ep),
        author=username,
        avatar=avatar,
        body=body,
        gif_url=gif_url,
        author_id=user_id,
    )
    if not comment:
        return jsonify({"success": False, "message": "Failed to post comment"}), 500
    return jsonify({"success": True, "comment": comment}), 201


@comments_api_bp.route("/comments/<comment_id>/reply", methods=["POST"])
@limiter.limit("4 per minute")
def post_reply(comment_id):
    """POST /api/comments/<id>/reply — create a reply to an existing comment."""
    auth = _require_auth()
    if not auth:
        return jsonify({"success": False, "message": "Login required"}), 401

    user_id, username, avatar = auth
    data = request.get_json() or {}
    anime_id = data.get("anime_id", "").strip()
    ep = data.get("episode_number")
    body = data.get("body", "")
    if isinstance(body, str): body = body.strip()
    
    gif_url = data.get("gif_url")
    if isinstance(gif_url, str):
        gif_url = gif_url.strip() or None
    else:
        gif_url = None

    if not anime_id or ep is None:
        return jsonify({"success": False, "message": "Missing anime_id or episode_number"}), 400
    if not body and not gif_url:
        return jsonify({"success": False, "message": "Reply cannot be empty"}), 400
    if body and len(body) > 2000:
        return jsonify({"success": False, "message": "Reply too long (max 2000 chars)"}), 400
    if contains_banned_words(body):
        return jsonify({"success": False, "message": "Reply contains inappropriate language"}), 400

    reply = create_comment(
        anime_id=anime_id,
        episode_number=int(ep),
        author=username,
        avatar=avatar,
        body=body,
        gif_url=gif_url,
        parent_id=comment_id,
        author_id=user_id,
    )
    if not reply:
        return jsonify({"success": False, "message": "Failed to post reply"}), 500
    return jsonify({"success": True, "comment": reply}), 201


@comments_api_bp.route("/comments/<comment_id>/react", methods=["POST"])
@limiter.limit("30 per minute")
def react_to_comment(comment_id):
    """POST /api/comments/<id>/react  body: { type: 'like'|'dislike' }"""
    auth = _require_auth()
    if not auth:
        return jsonify({"success": False, "message": "Login required"}), 401

    user_id, _, _ = auth
    data = request.get_json() or {}
    reaction_type = data.get("type", "")
    if reaction_type not in ("like", "dislike"):
        return jsonify({"success": False, "message": "Invalid reaction type"}), 400

    result = toggle_comment_reaction(comment_id, user_id, reaction_type)
    if result is None:
        return jsonify({"success": False, "message": "Comment not found"}), 404
    return jsonify({"success": True, **result})


@comments_api_bp.route("/comments/<comment_id>", methods=["PUT"])
@limiter.limit("4 per minute")
def update_comment(comment_id):
    """PUT /api/comments/<id> — edit an existing comment body/gif."""
    auth = _require_auth()
    if not auth:
        return jsonify({"success": False, "message": "Login required"}), 401

    user_id, username, _ = auth
    data = request.get_json() or {}
    new_body = data.get("body")
    new_gif_url = data.get("gif_url")

    if new_body is None and new_gif_url is None:
        return jsonify({"success": False, "message": "Nothing to update"}), 400
    
    if new_body and len(new_body) > 2000:
        return jsonify({"success": False, "message": "Comment too long (max 2000 chars)"}), 400
        
    if contains_banned_words(new_body):
        return jsonify({"success": False, "message": "Comment contains inappropriate language"}), 400

    try:
        oid = ObjectId(comment_id)
    except Exception:
        return jsonify({"success": False, "message": "Invalid comment ID"}), 400

    doc = comments_collection.find_one({"_id": oid, "deleted": False})
    if not doc:
        return jsonify({"success": False, "message": "Comment not found"}), 404

    # Authorship check (fallback to username for legacy comments without author_id)
    db_author_id = doc.get("author_id")
    is_owner = (db_author_id is not None and str(db_author_id) == str(user_id)) or (not db_author_id and doc.get("author") == username)
    if not is_owner:
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    # 5-minute Edit Rule
    created_at = doc.get("created_at")
    if created_at:
        now = datetime.now(timezone.utc)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        time_diff = (now - created_at).total_seconds()
        if time_diff > 300: # 5 minutes = 300 seconds
            return jsonify({"success": False, "message": "Comments can only be edited within 5 minutes of posting"}), 403

    updated_comment = edit_comment(comment_id, new_body, new_gif_url)
    if not updated_comment:
        return jsonify({"success": False, "message": "Update failed"}), 500

    return jsonify({"success": True, "comment": updated_comment})


@comments_api_bp.route("/comments/<comment_id>", methods=["DELETE"])
@limiter.limit("10 per minute")
def remove_comment(comment_id):
    """DELETE /api/comments/<id> — soft/hard delete a comment."""
    auth = _require_auth()
    if not auth:
        return jsonify({"success": False, "message": "Login required"}), 401

    user_id, username, _ = auth

    try:
        oid = ObjectId(comment_id)
    except Exception:
        return jsonify({"success": False, "message": "Invalid comment ID"}), 400

    doc = comments_collection.find_one({"_id": oid, "deleted": False})
    if not doc:
        return jsonify({"success": False, "message": "Comment not found or already deleted"}), 404

    # Authorship check
    db_author_id = doc.get("author_id")
    is_owner = (db_author_id is not None and str(db_author_id) == str(user_id)) or (not db_author_id and doc.get("author") == username)
    if not is_owner:
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    success = delete_comment(comment_id)
    if not success:
        return jsonify({"success": False, "message": "Delete failed"}), 500

    return jsonify({"success": True})


# ─────────────────────────────────────────────────────────────────────────────
# Episode reactions
# ─────────────────────────────────────────────────────────────────────────────

@comments_api_bp.route("/episodes/reaction", methods=["GET"])
def get_episode_reaction_counts():
    """GET /api/episodes/reaction?anime_id=&ep="""
    anime_id = request.args.get("anime_id", "").strip()
    ep = request.args.get("ep", "")
    if not anime_id or not ep:
        return jsonify({"success": False, "message": "Missing params"}), 400
    try:
        ep_num = int(ep)
    except ValueError:
        return jsonify({"success": False, "message": "ep must be an integer"}), 400

    auth = _require_auth()
    user_id = auth[0] if auth else None
    data = get_episode_reaction(anime_id, ep_num, user_id)
    return jsonify({"success": True, **data})


@comments_api_bp.route("/episodes/reaction", methods=["POST"])
@limiter.limit("30 per minute")
def react_to_episode():
    """POST /api/episodes/reaction  body: { anime_id, episode_number, type }"""
    auth = _require_auth()
    if not auth:
        return jsonify({"success": False, "message": "Login required"}), 401

    user_id, _, _ = auth
    data = request.get_json() or {}
    anime_id = data.get("anime_id", "").strip()
    ep = data.get("episode_number")
    reaction_type = data.get("type", "")

    if not anime_id or ep is None:
        return jsonify({"success": False, "message": "Missing params"}), 400
    if reaction_type not in ("like", "dislike"):
        return jsonify({"success": False, "message": "Invalid reaction type"}), 400

    result = toggle_episode_reaction(anime_id, int(ep), user_id, reaction_type)
    return jsonify({"success": True, **result})
