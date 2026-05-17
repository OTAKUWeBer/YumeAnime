"""
Admin Panel routes — page routes and API endpoints.
All API routes are prefixed with /api/admin/
Page route is /admin
"""
from functools import wraps
from flask import (
    Blueprint, request, session, jsonify,
    render_template, redirect, flash, url_for,
)
from ...core.extensions import limiter
from ...models.admin import (
    get_user_role, set_user_role, can_moderate,
    ban_user, unban_user, mute_user, unmute_user, is_user_banned,
    get_dashboard_stats, search_users_admin, get_user_admin_detail,
    create_report, get_reports, get_report, resolve_report, ignore_report,
    get_report_counts, get_audit_logs, log_action,
    VALID_ROLES, REPORT_REASONS,
)
from ...models.comments import delete_comment
from ...core.db_connector import comments_collection
from bson import ObjectId
import logging

admin_bp = Blueprint("admin", __name__)
admin_api_bp = Blueprint("admin_api", __name__)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# RBAC decorators
# ─────────────────────────────────────────────────────────────────────────────

def require_auth(f):
    """Require logged-in user."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "username" not in session or "_id" not in session:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"success": False, "message": "Login required"}), 401
            flash("Please log in to continue.", "warning")
            return redirect("/")
        return f(*args, **kwargs)
    return decorated


def require_staff(f):
    """Require mod or admin role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "username" not in session or "_id" not in session:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"success": False, "message": "Login required"}), 401
            flash("Please log in to continue.", "warning")
            return redirect("/")

        user_id = session["_id"]
        role = get_user_role(user_id)
        if not can_moderate(role):
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"success": False, "message": "Insufficient permissions"}), 403
            flash("You don't have permission to access this page.", "error")
            return redirect("/")

        # Inject role into kwargs for the handler to use
        kwargs["_role"] = role
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    """Require admin role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "username" not in session or "_id" not in session:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"success": False, "message": "Login required"}), 401
            flash("Please log in to continue.", "warning")
            return redirect("/")

        user_id = session["_id"]
        role = get_user_role(user_id)
        if role != "admin":
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"success": False, "message": "Admin access required"}), 403
            flash("You don't have permission to access this page.", "error")
            return redirect("/")

        kwargs["_role"] = "admin"
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────────────────────────────────────
# Page route
# ─────────────────────────────────────────────────────────────────────────────

@admin_bp.route("/admin")
@require_staff
def admin_panel(**kwargs):
    """Render the admin panel."""
    role = kwargs.get("_role", "mod")
    user_id = session["_id"]
    username = session["username"]
    return render_template(
        "shared/admin.html",
        admin_role=role,
        admin_user_id=user_id,
        admin_username=username,
    )


# ─────────────────────────────────────────────────────────────────────────────
# API: Dashboard
# ─────────────────────────────────────────────────────────────────────────────

@admin_api_bp.route("/dashboard", methods=["GET"])
@require_staff
def api_dashboard(**kwargs):
    """Get dashboard stats."""
    try:
        stats = get_dashboard_stats()
        return jsonify({"success": True, **stats})
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        return jsonify({"success": False, "message": "Failed to load dashboard"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# API: Users
# ─────────────────────────────────────────────────────────────────────────────

@admin_api_bp.route("/users", methods=["GET"])
@require_staff
def api_search_users(**kwargs):
    """Search and list users."""
    q = request.args.get("q", "").strip()
    role_filter = request.args.get("role", "").strip() or None
    page = max(1, int(request.args.get("page", 1)))
    try:
        data = search_users_admin(query=q, role_filter=role_filter, page=page)
        return jsonify({"success": True, **data})
    except Exception as e:
        logger.error(f"User search error: {e}")
        return jsonify({"success": False, "message": "Search failed"}), 500


@admin_api_bp.route("/users/<user_id>", methods=["GET"])
@require_staff
def api_get_user(**kwargs):
    """Get user detail."""
    user_id = kwargs.get("user_id") or request.view_args.get("user_id")
    try:
        user = get_user_admin_detail(user_id)
        if not user:
            return jsonify({"success": False, "message": "User not found"}), 404
        return jsonify({"success": True, "user": user})
    except Exception as e:
        logger.error(f"User detail error: {e}")
        return jsonify({"success": False, "message": "Failed"}), 500


@admin_api_bp.route("/users/<user_id>/role", methods=["POST"])
@require_admin
@limiter.limit("10 per minute")
def api_set_role(**kwargs):
    """Set a user's role (admin only)."""
    target_user_id = kwargs.get("user_id") or request.view_args.get("user_id")
    data = request.get_json() or {}
    new_role = data.get("role", "").strip()

    if new_role not in VALID_ROLES:
        return jsonify({"success": False, "message": f"Invalid role: {new_role}"}), 400

    try:
        target_id = int(target_user_id)
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid user ID"}), 400

    # Don't allow changing own role
    if target_id == session["_id"]:
        return jsonify({"success": False, "message": "Cannot change your own role"}), 400

    old_role = get_user_role(target_id)
    if old_role is None:
        return jsonify({"success": False, "message": "User not found"}), 404

    if old_role == new_role:
        return jsonify({"success": False, "message": f"User already has role '{new_role}'"}), 400

    if set_user_role(target_id, new_role):
        log_action(
            session["_id"], session["username"],
            f"role_change:{old_role}->{new_role}",
            target_id,
            details=f"Changed role from {old_role} to {new_role}",
        )
        target = get_user_admin_detail(target_id)
        return jsonify({"success": True, "message": f"Role updated to {new_role}", "user": target})
    return jsonify({"success": False, "message": "Failed to update role"}), 500


@admin_api_bp.route("/users/<user_id>/ban", methods=["POST"])
@require_admin
@limiter.limit("10 per minute")
def api_ban_user(**kwargs):
    """Ban or unban a user (admin only)."""
    target_user_id = kwargs.get("user_id") or request.view_args.get("user_id")
    data = request.get_json() or {}
    action = data.get("action", "ban")

    try:
        target_id = int(target_user_id)
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid user ID"}), 400

    if target_id == session["_id"]:
        return jsonify({"success": False, "message": "Cannot ban yourself"}), 400

    # Don't allow banning admins
    target_role = get_user_role(target_id)
    if target_role == "admin":
        return jsonify({"success": False, "message": "Cannot ban an admin"}), 403

    if action == "ban":
        success = ban_user(target_id)
        action_label = "ban"
    else:
        success = unban_user(target_id)
        action_label = "unban"

    if success:
        log_action(
            session["_id"], session["username"],
            action_label, target_id,
            details=f"User {action_label}ned",
        )
        target = get_user_admin_detail(target_id)
        return jsonify({"success": True, "message": f"User {action_label}ned", "user": target})
    return jsonify({"success": False, "message": f"Failed to {action_label}"}), 500


@admin_api_bp.route("/users/<user_id>/mute", methods=["POST"])
@require_staff
@limiter.limit("10 per minute")
def api_mute_user(**kwargs):
    """Mute or unmute a user."""
    target_user_id = kwargs.get("user_id") or request.view_args.get("user_id")
    data = request.get_json() or {}
    action = data.get("action", "mute")
    duration = int(data.get("duration", 24))

    try:
        target_id = int(target_user_id)
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid user ID"}), 400

    if target_id == session["_id"]:
        return jsonify({"success": False, "message": "Cannot mute yourself"}), 400

    target_role = get_user_role(target_id)
    if target_role in ("mod", "admin"):
        return jsonify({"success": False, "message": "Cannot mute staff members"}), 403

    if action == "mute":
        success = mute_user(target_id, duration)
        action_label = "muted"
    else:
        success = unmute_user(target_id)
        action_label = "unmuted"

    if success:
        log_action(
            session["_id"], session["username"],
            action, target_id,
            details=f"User {action_label} for {duration}h" if action == "mute" else f"User {action_label}",
        )
        target = get_user_admin_detail(target_id)
        return jsonify({"success": True, "message": f"User {action_label}", "user": target})
    return jsonify({"success": False, "message": f"Failed to {action}"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# API: Reports
# ─────────────────────────────────────────────────────────────────────────────

@admin_api_bp.route("/reports", methods=["GET"])
@require_staff
def api_list_reports(**kwargs):
    """List reports with filters."""
    status = request.args.get("status", "").strip() or None
    reason = request.args.get("reason", "").strip() or None
    page = max(1, int(request.args.get("page", 1)))
    try:
        data = get_reports(status=status, reason=reason, page=page)
        return jsonify({"success": True, **data})
    except Exception as e:
        logger.error(f"Reports list error: {e}")
        return jsonify({"success": False, "message": "Failed to load reports"}), 500


@admin_api_bp.route("/reports/<report_id>", methods=["GET"])
@require_staff
def api_get_report(**kwargs):
    """Get a single report detail."""
    report_id = kwargs.get("report_id") or request.view_args.get("report_id")
    report = get_report(report_id)
    if not report:
        return jsonify({"success": False, "message": "Report not found"}), 404
    return jsonify({"success": True, "report": report})


@admin_api_bp.route("/reports/<report_id>/resolve", methods=["POST"])
@require_staff
@limiter.limit("20 per minute")
def api_resolve_report(**kwargs):
    """Resolve a report with an action."""
    report_id = kwargs.get("report_id") or request.view_args.get("report_id")
    data = request.get_json() or {}
    action = data.get("action", "resolved")
    note = data.get("note", "")

    report = resolve_report(
        report_id, session["_id"], session["username"], action, note
    )
    if report:
        log_action(
            session["_id"], session["username"],
            f"report_resolve:{action}",
            details=f"Report {report_id} resolved with action: {action}",
        )
        return jsonify({"success": True, "report": report})
    return jsonify({"success": False, "message": "Failed to resolve report"}), 500


@admin_api_bp.route("/reports/<report_id>/ignore", methods=["POST"])
@require_staff
@limiter.limit("20 per minute")
def api_ignore_report(**kwargs):
    """Ignore a report."""
    report_id = kwargs.get("report_id") or request.view_args.get("report_id")
    data = request.get_json() or {}
    note = data.get("note", "")

    report = ignore_report(
        report_id, session["_id"], session["username"], note
    )
    if report:
        log_action(
            session["_id"], session["username"],
            "report_ignore",
            details=f"Report {report_id} ignored",
        )
        return jsonify({"success": True, "report": report})
    return jsonify({"success": False, "message": "Failed to ignore report"}), 500


@admin_api_bp.route("/reports/<report_id>/delete-comment", methods=["POST"])
@require_staff
@limiter.limit("20 per minute")
def api_delete_reported_comment(**kwargs):
    """Delete the comment from a report and resolve the report."""
    report_id = kwargs.get("report_id") or request.view_args.get("report_id")
    data = request.get_json() or {}
    note = data.get("note", "")

    # Get the report to find the comment
    report = get_report(report_id)
    if not report:
        return jsonify({"success": False, "message": "Report not found"}), 404

    comment_id = report.get("comment_id")
    if comment_id:
        delete_comment(comment_id)

    # Resolve the report
    resolved = resolve_report(
        report_id, session["_id"], session["username"],
        "comment_deleted", note,
    )

    log_action(
        session["_id"], session["username"],
        "comment_delete_from_report",
        target_id=report.get("reported_user_id"),
        target_username=report.get("reported_username"),
        details=f"Deleted comment {comment_id} from report {report_id}",
    )

    return jsonify({"success": True, "report": resolved, "message": "Comment deleted and report resolved"})


# ─────────────────────────────────────────────────────────────────────────────
# API: Comments (mod actions)
# ─────────────────────────────────────────────────────────────────────────────

@admin_api_bp.route("/comments/<comment_id>/delete", methods=["POST"])
@require_staff
@limiter.limit("30 per minute")
def api_mod_delete_comment(**kwargs):
    """Delete any comment (mod/admin power)."""
    comment_id = kwargs.get("comment_id") or request.view_args.get("comment_id")
    data = request.get_json() or {}
    reason = data.get("reason", "moderation")

    try:
        oid = ObjectId(comment_id)
    except Exception:
        return jsonify({"success": False, "message": "Invalid comment ID"}), 400

    doc = comments_collection.find_one({"_id": oid})
    if not doc:
        return jsonify({"success": False, "message": "Comment not found"}), 404

    delete_comment(comment_id)

    log_action(
        session["_id"], session["username"],
        "comment_delete",
        target_id=doc.get("author_id"),
        target_username=doc.get("author"),
        details=f"Deleted comment {comment_id}: {reason}",
    )

    return jsonify({"success": True, "message": "Comment deleted"})


# ─────────────────────────────────────────────────────────────────────────────
# API: Audit Logs
# ─────────────────────────────────────────────────────────────────────────────

@admin_api_bp.route("/logs", methods=["GET"])
@require_staff
def api_audit_logs(**kwargs):
    """Get paginated audit logs."""
    page = max(1, int(request.args.get("page", 1)))
    try:
        data = get_audit_logs(page=page)
        return jsonify({"success": True, **data})
    except Exception as e:
        logger.error(f"Audit log error: {e}")
        return jsonify({"success": False, "message": "Failed to load logs"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# API: Report counts (for badges)
# ─────────────────────────────────────────────────────────────────────────────

@admin_api_bp.route("/report-counts", methods=["GET"])
@require_staff
def api_report_counts(**kwargs):
    """Get report status counts."""
    counts = get_report_counts()
    return jsonify({"success": True, **counts})


# ─────────────────────────────────────────────────────────────────────────────
# API: Comment reporting (for regular users too)
# ─────────────────────────────────────────────────────────────────────────────

@admin_api_bp.route("/report-comment", methods=["POST"])
@require_auth
@limiter.limit("5 per minute")
def api_report_comment():
    """Report a comment (any logged-in user can do this)."""
    data = request.get_json() or {}
    comment_id = data.get("comment_id", "").strip()
    reason = data.get("reason", "other").strip()
    details = data.get("details", "").strip()

    if not comment_id:
        return jsonify({"success": False, "message": "Missing comment ID"}), 400

    if reason not in REPORT_REASONS:
        reason = "other"

    # Find the comment
    try:
        doc = comments_collection.find_one({"_id": ObjectId(comment_id)})
    except Exception:
        return jsonify({"success": False, "message": "Invalid comment ID"}), 400

    if not doc:
        return jsonify({"success": False, "message": "Comment not found"}), 404

    # Don't allow reporting own comments
    reporter_id = str(session["_id"])
    comment_author_id = doc.get("author_id")
    if comment_author_id and str(comment_author_id) == reporter_id:
        return jsonify({"success": False, "message": "Cannot report your own comment"}), 400

    report = create_report(
        comment_id=comment_id,
        reported_user_id=doc.get("author_id", ""),
        reported_username=doc.get("author", "Unknown"),
        reporter_id=reporter_id,
        reporter_username=session["username"],
        reason=reason,
        comment_body=doc.get("body", ""),
        anime_id=doc.get("anime_id", ""),
        episode_number=doc.get("episode_number", 0),
        details=details,
    )

    if report:
        return jsonify({"success": True, "message": "Report submitted successfully"})
    return jsonify({"success": False, "message": "Failed to submit report"}), 500



