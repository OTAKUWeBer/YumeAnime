"""
Comments & Episode Reactions model layer.
Handles all MongoDB operations for the comment system.
"""
from datetime import datetime, timezone
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING

from ..core.db_connector import comments_collection, episode_reactions_collection


# ─────────────────────────────────────────────────────────────────────────────
# Index setup (run once on import — idempotent)
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_indexes():
    try:
        comments_collection.create_index(
            [("anime_id", ASCENDING), ("episode_number", ASCENDING), ("created_at", DESCENDING)]
        )
        comments_collection.create_index([("parent_id", ASCENDING)])
        episode_reactions_collection.create_index(
            [("anime_id", ASCENDING), ("episode_number", ASCENDING)],
            unique=True
        )
    except Exception:
        pass  # Don't crash the app if index creation fails


_ensure_indexes()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _serialize_comment(doc):
    """Convert a MongoDB comment document into a JSON-serialisable dict."""
    if not doc:
        return None
    return {
        "_id": str(doc["_id"]),
        "anime_id": doc.get("anime_id", ""),
        "episode_number": doc.get("episode_number", 0),
        "parent_id": str(doc["parent_id"]) if doc.get("parent_id") else None,
        "author": doc.get("author", "Anonymous"),
        "author_id": doc.get("author_id"),
        "avatar": doc.get("avatar"),
        "body": doc.get("body", ""),
        "gif_url": doc.get("gif_url"),
        "likes": [str(u) for u in doc.get("likes", [])],
        "dislikes": [str(u) for u in doc.get("dislikes", [])],
        "like_count": len(doc.get("likes", [])),
        "dislike_count": len(doc.get("dislikes", [])),
        "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None,
        "edited_at": doc["edited_at"].isoformat() if doc.get("edited_at") else None,
        "deleted": doc.get("deleted", False),
        "replies": [],  # populated by get_comments()
    }


# ─────────────────────────────────────────────────────────────────────────────
# Comments
# ─────────────────────────────────────────────────────────────────────────────

def get_comments(anime_id: str, episode_number: int) -> list:
    """
    Return all top-level comments for an episode, each with nested replies.
    Replies are sorted oldest-first; top-level comments are sorted newest-first.
    """
    raw = list(
        comments_collection.find(
            {"anime_id": anime_id, "episode_number": episode_number, "deleted": False},
            sort=[("created_at", ASCENDING)],
        )
    )

    top_level = []
    reply_map: dict[str, list] = {}

    for doc in raw:
        serialized = _serialize_comment(doc)
        pid = serialized["parent_id"]
        if pid is None:
            top_level.append(serialized)
        else:
            reply_map.setdefault(pid, []).append(serialized)

    # Attach replies
    for comment in top_level:
        comment["replies"] = reply_map.get(comment["_id"], [])

    # Sort top-level newest first
    top_level.sort(key=lambda c: c["created_at"] or "", reverse=True)
    return top_level


def create_comment(
    anime_id: str,
    episode_number: int,
    author: str,
    avatar,
    body: str,
    gif_url=None,
    parent_id=None,
    author_id=None,
) -> dict | None:
    """Insert a new comment and return the serialised document."""
    if not body and not gif_url:
        return None  # Must have content

    doc = {
        "anime_id": anime_id,
        "episode_number": int(episode_number),
        "parent_id": ObjectId(parent_id) if parent_id else None,
        "author": author,
        "author_id": author_id,
        "avatar": avatar,
        "body": body.strip() if body else "",
        "gif_url": gif_url,
        "likes": [],
        "dislikes": [],
        "created_at": datetime.now(timezone.utc),
        "edited_at": None,
        "deleted": False,
    }

    result = comments_collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _serialize_comment(doc)


def toggle_comment_reaction(comment_id: str, user_id: str, reaction_type: str) -> dict | None:
    """
    Toggle like or dislike on a comment.
    - Adding a like removes any existing dislike, and vice-versa.
    - Reacting again to the same type removes it (toggle off).
    Returns updated like/dislike counts, or None if comment not found.
    """
    try:
        oid = ObjectId(comment_id)
    except Exception:
        return None

    doc = comments_collection.find_one({"_id": oid, "deleted": False})
    if not doc:
        return None

    likes = [str(u) for u in doc.get("likes", [])]
    dislikes = [str(u) for u in doc.get("dislikes", [])]

    if reaction_type == "like":
        if user_id in likes:
            likes.remove(user_id)          # toggle off
        else:
            likes.append(user_id)
            if user_id in dislikes:
                dislikes.remove(user_id)   # remove opposite
    elif reaction_type == "dislike":
        if user_id in dislikes:
            dislikes.remove(user_id)       # toggle off
        else:
            dislikes.append(user_id)
            if user_id in likes:
                likes.remove(user_id)      # remove opposite
    else:
        return None

    comments_collection.update_one(
        {"_id": oid},
        {"$set": {"likes": likes, "dislikes": dislikes}},
    )
    return {"like_count": len(likes), "dislike_count": len(dislikes),
            "user_liked": user_id in likes, "user_disliked": user_id in dislikes}


def edit_comment(comment_id: str, new_body: str, new_gif_url: str | None) -> dict | None:
    """Updates a comment's body/gif_url and sets edited_at timestamp."""
    try:
        oid = ObjectId(comment_id)
    except Exception:
        return None

    update_fields = {"edited_at": datetime.now(timezone.utc)}
    if new_body is not None: update_fields["body"] = new_body.strip()
    if new_gif_url is not None: update_fields["gif_url"] = new_gif_url

    comments_collection.update_one({"_id": oid}, {"$set": update_fields})
    doc = comments_collection.find_one({"_id": oid})
    return _serialize_comment(doc)


def delete_comment(comment_id: str) -> bool:
    """
    Soft-deletes a comment (sets body/author to '[deleted]') if it has replies.
    Otherwise, hard-deletes it completely.
    """
    try:
        oid = ObjectId(comment_id)
    except Exception:
        return False

    has_replies = comments_collection.find_one({"parent_id": oid}) is not None
    if has_replies:
        comments_collection.update_one(
            {"_id": oid},
            {"$set": {
                "body": "[deleted]",
                "gif_url": None,
                "author": "[deleted]",
                "avatar": None,
                "deleted": True # mark as formally deleted in UI state while preserving replies
            }}
        )
    else:
        comments_collection.delete_one({"_id": oid})
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Episode reactions
# ─────────────────────────────────────────────────────────────────────────────

def get_episode_reaction(anime_id: str, episode_number: int, user_id: str | None = None) -> dict:
    """Return episode like/dislike counts (and optionally the user's vote)."""
    doc = episode_reactions_collection.find_one(
        {"anime_id": anime_id, "episode_number": int(episode_number)}
    )
    likes = [str(u) for u in (doc.get("likes", []) if doc else [])]
    dislikes = [str(u) for u in (doc.get("dislikes", []) if doc else [])]
    result = {
        "like_count": len(likes),
        "dislike_count": len(dislikes),
        "user_liked": False,
        "user_disliked": False,
    }
    if user_id:
        result["user_liked"] = user_id in likes
        result["user_disliked"] = user_id in dislikes
    return result


def toggle_episode_reaction(anime_id: str, episode_number: int, user_id: str, reaction_type: str) -> dict:
    """Toggle like or dislike on an episode. Returns updated counts."""
    doc = episode_reactions_collection.find_one(
        {"anime_id": anime_id, "episode_number": int(episode_number)}
    )

    if doc:
        likes = [str(u) for u in doc.get("likes", [])]
        dislikes = [str(u) for u in doc.get("dislikes", [])]
    else:
        likes, dislikes = [], []

    if reaction_type == "like":
        if user_id in likes:
            likes.remove(user_id)
        else:
            likes.append(user_id)
            if user_id in dislikes:
                dislikes.remove(user_id)
    elif reaction_type == "dislike":
        if user_id in dislikes:
            dislikes.remove(user_id)
        else:
            dislikes.append(user_id)
            if user_id in likes:
                likes.remove(user_id)

    episode_reactions_collection.update_one(
        {"anime_id": anime_id, "episode_number": int(episode_number)},
        {"$set": {"likes": likes, "dislikes": dislikes}},
        upsert=True,
    )
    return {
        "like_count": len(likes),
        "dislike_count": len(dislikes),
        "user_liked": user_id in likes,
        "user_disliked": user_id in dislikes,
    }
