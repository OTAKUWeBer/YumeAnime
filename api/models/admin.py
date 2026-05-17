"""
Admin & Moderation model layer.
Handles reports, audit logs, dashboard stats, and role management.
"""
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING

from ..core.db_connector import (
    users_collection,
    comments_collection,
    reports_collection,
    audit_log_collection,
)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

VALID_ROLES = ("user", "mod", "admin")
REPORT_REASONS = (
    "spam", "harassment", "nsfw", "hate_speech", "misinformation", "other"
)
REPORT_STATUSES = ("pending", "resolved", "ignored")
MAX_REPORTS_PAGE = 50
MAX_USERS_PAGE = 50
MAX_LOGS_PAGE = 50

_indexes_ready = False


def _ensure_indexes():
    global _indexes_ready
    if _indexes_ready:
        return
    try:
        reports_collection.create_index(
            [("status", ASCENDING), ("created_at", DESCENDING)],
            name="reports_status_date",
        )
        reports_collection.create_index(
            [("comment_id", ASCENDING)],
            name="reports_comment",
        )
        reports_collection.create_index(
            [("reported_user_id", ASCENDING)],
            name="reports_reported_user",
        )
        audit_log_collection.create_index(
            [("created_at", DESCENDING)],
            name="audit_log_date",
        )
        audit_log_collection.create_index(
            [("actor_id", ASCENDING)],
            name="audit_log_actor",
        )
    except Exception:
        pass
    _indexes_ready = True


def utcnow():
    return datetime.now(timezone.utc)


def iso(dt):
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# Role helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_user_role(user_id):
    """Return the role string for a user (defaults to 'user')."""
    user = users_collection.find_one({"_id": user_id}, {"role": 1})
    if not user:
        return None
    return user.get("role", "user")


def set_user_role(user_id, new_role):
    """Set a user's role. Returns True on success."""
    if new_role not in VALID_ROLES:
        return False
    result = users_collection.update_one(
        {"_id": user_id},
        {"$set": {"role": new_role, "updated_at": utcnow()}},
    )
    return result.modified_count > 0


def is_staff(user_id):
    """Check if a user is mod or admin."""
    role = get_user_role(user_id)
    return role in ("mod", "admin")


def is_admin(user_id):
    """Check if a user is admin."""
    return get_user_role(user_id) == "admin"


def can_moderate(role):
    """Check if a role has moderation permissions."""
    return role in ("mod", "admin")


# ─────────────────────────────────────────────────────────────────────────────
# Ban / Mute
# ─────────────────────────────────────────────────────────────────────────────

def ban_user(user_id):
    """Ban a user."""
    result = users_collection.update_one(
        {"_id": user_id},
        {"$set": {"is_banned": True, "updated_at": utcnow()}},
    )
    return result.modified_count > 0


def unban_user(user_id):
    """Unban a user."""
    result = users_collection.update_one(
        {"_id": user_id},
        {"$set": {"is_banned": False, "updated_at": utcnow()}},
    )
    return result.modified_count > 0


def mute_user(user_id, duration_hours=24):
    """Mute a user for a duration."""
    muted_until = utcnow() + timedelta(hours=duration_hours)
    result = users_collection.update_one(
        {"_id": user_id},
        {"$set": {"muted_until": muted_until, "updated_at": utcnow()}},
    )
    return result.modified_count > 0


def unmute_user(user_id):
    """Remove mute from a user."""
    result = users_collection.update_one(
        {"_id": user_id},
        {"$unset": {"muted_until": ""}, "$set": {"updated_at": utcnow()}},
    )
    return result.modified_count > 0


def is_user_banned(user_id):
    """Check if a user is banned."""
    user = users_collection.find_one({"_id": user_id}, {"is_banned": 1})
    return bool(user and user.get("is_banned"))


def is_user_muted(user_id):
    """Check if a user is currently muted."""
    user = users_collection.find_one({"_id": user_id}, {"muted_until": 1})
    if not user or not user.get("muted_until"):
        return False
    muted_until = user["muted_until"]
    if muted_until.tzinfo is None:
        muted_until = muted_until.replace(tzinfo=timezone.utc)
    return utcnow() < muted_until


# ─────────────────────────────────────────────────────────────────────────────
# Reports
# ─────────────────────────────────────────────────────────────────────────────

def create_report(
    comment_id,
    reported_user_id,
    reported_username,
    reporter_id,
    reporter_username,
    reason,
    comment_body="",
    anime_id="",
    episode_number=0,
    details="",
):
    """Create a new report on a comment."""
    _ensure_indexes()
    if reason not in REPORT_REASONS:
        reason = "other"

    doc = {
        "comment_id": str(comment_id),
        "reported_user_id": str(reported_user_id),
        "reported_username": reported_username or "Unknown",
        "reporter_id": str(reporter_id),
        "reporter_username": reporter_username or "Unknown",
        "reason": reason,
        "details": (details or "")[:500],
        "comment_body": (comment_body or "")[:1000],
        "anime_id": str(anime_id),
        "episode_number": int(episode_number) if episode_number else 0,
        "status": "pending",
        "moderator_id": None,
        "moderator_username": None,
        "moderator_note": None,
        "action_taken": None,
        "created_at": utcnow(),
        "resolved_at": None,
    }

    # Bump report_count on the comment
    try:
        comments_collection.update_one(
            {"_id": ObjectId(comment_id)},
            {"$inc": {"report_count": 1}},
        )
    except Exception:
        pass

    result = reports_collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize_report(doc)


def get_reports(status=None, reason=None, page=1, limit=MAX_REPORTS_PAGE):
    """Get paginated reports with optional filters."""
    _ensure_indexes()
    query = {}
    if status and status in REPORT_STATUSES:
        query["status"] = status
    if reason and reason in REPORT_REASONS:
        query["reason"] = reason

    skip = max(0, (page - 1) * limit)
    total = reports_collection.count_documents(query)
    docs = list(
        reports_collection.find(query)
        .sort("created_at", DESCENDING)
        .skip(skip)
        .limit(limit)
    )
    return {
        "reports": [serialize_report(d) for d in docs],
        "total": total,
        "page": page,
        "pages": max(1, (total + limit - 1) // limit),
    }


def get_report(report_id):
    """Get a single report by ID."""
    try:
        doc = reports_collection.find_one({"_id": ObjectId(report_id)})
        return serialize_report(doc) if doc else None
    except Exception:
        return None


def resolve_report(report_id, moderator_id, moderator_username, action, note=""):
    """Resolve a report with an action."""
    try:
        oid = ObjectId(report_id)
    except Exception:
        return None

    update = {
        "$set": {
            "status": "resolved",
            "moderator_id": str(moderator_id),
            "moderator_username": moderator_username,
            "moderator_note": (note or "")[:500],
            "action_taken": action,
            "resolved_at": utcnow(),
        }
    }
    doc = reports_collection.find_one_and_update(
        {"_id": oid},
        update,
        return_document=True,
    )
    return serialize_report(doc) if doc else None


def ignore_report(report_id, moderator_id, moderator_username, note=""):
    """Ignore a report."""
    try:
        oid = ObjectId(report_id)
    except Exception:
        return None

    update = {
        "$set": {
            "status": "ignored",
            "moderator_id": str(moderator_id),
            "moderator_username": moderator_username,
            "moderator_note": (note or "")[:500],
            "action_taken": "ignored",
            "resolved_at": utcnow(),
        }
    }
    doc = reports_collection.find_one_and_update(
        {"_id": oid},
        update,
        return_document=True,
    )
    return serialize_report(doc) if doc else None


def get_report_counts():
    """Get report status counts."""
    pipeline = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]
    results = list(reports_collection.aggregate(pipeline))
    counts = {"pending": 0, "resolved": 0, "ignored": 0, "total": 0}
    for r in results:
        status = r["_id"]
        if status in counts:
            counts[status] = r["count"]
        counts["total"] += r["count"]
    return counts


def serialize_report(doc):
    """Serialize a report document."""
    if not doc:
        return None
    return {
        "_id": str(doc["_id"]),
        "comment_id": doc.get("comment_id"),
        "reported_user_id": doc.get("reported_user_id"),
        "reported_username": doc.get("reported_username", "Unknown"),
        "reporter_id": doc.get("reporter_id"),
        "reporter_username": doc.get("reporter_username", "Unknown"),
        "reason": doc.get("reason", "other"),
        "details": doc.get("details", ""),
        "comment_body": doc.get("comment_body", ""),
        "anime_id": doc.get("anime_id", ""),
        "episode_number": doc.get("episode_number", 0),
        "status": doc.get("status", "pending"),
        "moderator_id": doc.get("moderator_id"),
        "moderator_username": doc.get("moderator_username"),
        "moderator_note": doc.get("moderator_note"),
        "action_taken": doc.get("action_taken"),
        "created_at": iso(doc.get("created_at")),
        "resolved_at": iso(doc.get("resolved_at")),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Audit Log
# ─────────────────────────────────────────────────────────────────────────────

def log_action(actor_id, actor_username, action, target_id=None, target_username=None, details=""):
    """Log a moderation action."""
    _ensure_indexes()
    doc = {
        "actor_id": str(actor_id),
        "actor_username": actor_username or "Unknown",
        "action": action,
        "target_id": str(target_id) if target_id else None,
        "target_username": target_username,
        "details": (details or "")[:500],
        "created_at": utcnow(),
    }
    audit_log_collection.insert_one(doc)
    return doc


def get_audit_logs(page=1, limit=MAX_LOGS_PAGE, actor_id=None):
    """Get paginated audit logs."""
    _ensure_indexes()
    query = {}
    if actor_id:
        query["actor_id"] = str(actor_id)

    skip = max(0, (page - 1) * limit)
    total = audit_log_collection.count_documents(query)
    docs = list(
        audit_log_collection.find(query)
        .sort("created_at", DESCENDING)
        .skip(skip)
        .limit(limit)
    )
    return {
        "logs": [serialize_log(d) for d in docs],
        "total": total,
        "page": page,
        "pages": max(1, (total + limit - 1) // limit),
    }


def serialize_log(doc):
    if not doc:
        return None
    return {
        "_id": str(doc["_id"]),
        "actor_id": doc.get("actor_id"),
        "actor_username": doc.get("actor_username"),
        "action": doc.get("action"),
        "target_id": doc.get("target_id"),
        "target_username": doc.get("target_username"),
        "details": doc.get("details", ""),
        "created_at": iso(doc.get("created_at")),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard stats
# ─────────────────────────────────────────────────────────────────────────────

def get_dashboard_stats():
    """Get dashboard statistics for the admin panel."""
    now = utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)

    total_users = users_collection.count_documents({})
    new_users_today = users_collection.count_documents({"created_at": {"$gte": today_start}})
    new_users_week = users_collection.count_documents({"created_at": {"$gte": week_ago}})
    banned_users = users_collection.count_documents({"is_banned": True})
    total_comments = comments_collection.count_documents({"deleted": False})
    report_counts = get_report_counts()

    # Role distribution
    role_pipeline = [
        {"$group": {"_id": {"$ifNull": ["$role", "user"]}, "count": {"$sum": 1}}},
    ]
    role_results = list(users_collection.aggregate(role_pipeline))
    roles = {"user": 0, "mod": 0, "admin": 0}
    for r in role_results:
        role = r["_id"]
        if role in roles:
            roles[role] = r["count"]

    # Recent users
    recent_users = list(
        users_collection.find({}, {"password": 0, "anilist_access_token": 0, "mal_access_token": 0, "mal_refresh_token": 0})
        .sort("created_at", DESCENDING)
        .limit(10)
    )

    # Recent mod actions
    recent_logs = list(
        audit_log_collection.find()
        .sort("created_at", DESCENDING)
        .limit(10)
    )

    # Signups per day (last 7 days)
    signup_pipeline = [
        {"$match": {"created_at": {"$gte": week_ago}}},
        {
            "$group": {
                "_id": {
                    "$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}
                },
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"_id": 1}},
    ]
    signup_chart = list(users_collection.aggregate(signup_pipeline))

    return {
        "total_users": total_users,
        "new_users_today": new_users_today,
        "new_users_week": new_users_week,
        "banned_users": banned_users,
        "total_comments": total_comments,
        "reports": report_counts,
        "roles": roles,
        "recent_users": [_serialize_user_brief(u) for u in recent_users],
        "recent_logs": [serialize_log(l) for l in recent_logs],
        "signup_chart": signup_chart,
    }


def _serialize_user_brief(user):
    """Serialize a user document for admin display."""
    if not user:
        return None
    return {
        "_id": str(user["_id"]),
        "username": user.get("username", "Unknown"),
        "email": user.get("email", ""),
        "avatar": user.get("avatar"),
        "role": user.get("role", "user"),
        "is_banned": bool(user.get("is_banned")),
        "muted_until": iso(user.get("muted_until")),
        "auth_method": user.get("auth_method", "local"),
        "created_at": iso(user.get("created_at")),
    }


# ─────────────────────────────────────────────────────────────────────────────
# User search / management for admin
# ─────────────────────────────────────────────────────────────────────────────

def search_users_admin(query="", role_filter=None, page=1, limit=MAX_USERS_PAGE):
    """Search users with filters for admin panel."""
    mongo_query = {}

    if query:
        # Try numeric ID search
        try:
            numeric_id = int(query)
            mongo_query["_id"] = numeric_id
        except (ValueError, TypeError):
            mongo_query["$or"] = [
                {"username": {"$regex": query, "$options": "i"}},
                {"email": {"$regex": query, "$options": "i"}},
            ]

    if role_filter and role_filter in VALID_ROLES:
        if role_filter == "user":
            # Users without role field or with role="user"
            mongo_query["$and"] = mongo_query.get("$and", []) + [
                {"$or": [{"role": "user"}, {"role": {"$exists": False}}]}
            ]
        else:
            mongo_query["role"] = role_filter

    skip = max(0, (page - 1) * limit)
    total = users_collection.count_documents(mongo_query)
    docs = list(
        users_collection.find(
            mongo_query,
            {"password": 0, "anilist_access_token": 0, "mal_access_token": 0, "mal_refresh_token": 0},
        )
        .sort("created_at", DESCENDING)
        .skip(skip)
        .limit(limit)
    )
    return {
        "users": [_serialize_user_brief(u) for u in docs],
        "total": total,
        "page": page,
        "pages": max(1, (total + limit - 1) // limit),
    }


def get_user_admin_detail(user_id):
    """Get full user detail for admin panel."""
    try:
        uid = int(user_id)
    except (ValueError, TypeError):
        return None

    user = users_collection.find_one(
        {"_id": uid},
        {"password": 0, "anilist_access_token": 0, "mal_access_token": 0, "mal_refresh_token": 0},
    )
    if not user:
        return None

    # Count user's comments
    comment_count = comments_collection.count_documents(
        {"author_id": str(uid), "deleted": False}
    )

    # Count reports against this user
    reports_against = reports_collection.count_documents(
        {"reported_user_id": str(uid)}
    )

    detail = _serialize_user_brief(user)
    detail["comment_count"] = comment_count
    detail["reports_against"] = reports_against
    detail["anilist_id"] = user.get("anilist_id")
    detail["mal_id"] = user.get("mal_id")
    detail["mal_username"] = user.get("mal_username")
    return detail



