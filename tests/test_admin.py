import unittest
import copy
from datetime import datetime, timezone
from unittest.mock import patch
from flask import Flask, session
from bson import ObjectId

from api.models import admin as adm
from api.routes.shared import admin_routes
from api.routes.shared.admin_routes import admin_bp, admin_api_bp


class MemoryCollection:
    def __init__(self):
        self.docs = []

    def create_index(self, *args, **kwargs):
        return kwargs.get("name", "idx")

    def insert_one(self, doc):
        if "_id" not in doc:
            doc["_id"] = ObjectId()
        self.docs.append(copy.deepcopy(doc))
        return type("InsertResult", (), {"inserted_id": doc["_id"]})()

    def find_one(self, query, projection=None):
        for doc in self.docs:
            if self._matches(doc, query):
                return copy.deepcopy(doc)
        return None

    def find(self, query=None, projection=None):
        query = query or {}
        matched = [copy.deepcopy(doc) for doc in self.docs if self._matches(doc, query)]
        
        class Cursor:
            def __init__(self, items):
                self.items = items

            def sort(self, *args, **kwargs):
                return self

            def skip(self, *args, **kwargs):
                return self

            def limit(self, count):
                self.items = self.items[:count]
                return self

            def __iter__(self):
                return iter(self.items)

        return Cursor(matched)

    def count_documents(self, query):
        return sum(1 for doc in self.docs if self._matches(doc, query))

    def update_one(self, query, update):
        for index, doc in enumerate(self.docs):
            if self._matches(doc, query):
                self._apply(doc, update)
                self.docs[index] = doc
                return type("UpdateResult", (), {"modified_count": 1})()
        return type("UpdateResult", (), {"modified_count": 0})()

    def update_many(self, query, update):
        count = 0
        for index, doc in enumerate(self.docs):
            if self._matches(doc, query):
                self._apply(doc, update)
                self.docs[index] = doc
                count += 1
        return type("UpdateResult", (), {"modified_count": count})()

    def find_one_and_update(self, query, update, return_document=None):
        for index, doc in enumerate(self.docs):
            if self._matches(doc, query):
                self._apply(doc, update)
                self.docs[index] = doc
                return copy.deepcopy(doc)
        return None

    def aggregate(self, pipeline):
        # basic fallback for group / signups
        return []

    def _matches(self, doc, query):
        for key, expected in query.items():
            if key == "$or":
                if not any(self._matches_clause(doc, c) for c in expected):
                    return False
            elif key == "$and":
                if not all(self._matches_clause(doc, c) for c in expected):
                    return False
            else:
                if not self._matches_clause(doc, {key: expected}):
                    return False
        return True

    def _matches_clause(self, doc, clause):
        for key, expected in clause.items():
            value = self._get(doc, key)
            if isinstance(expected, dict):
                if "$regex" in expected:
                    import re
                    pattern = expected["$regex"]
                    options = expected.get("$options", "")
                    flags = re.IGNORECASE if "i" in options else 0
                    if not (value is not None and re.search(pattern, str(value), flags)):
                        return False
                elif "$exists" in expected:
                    exists = expected["$exists"]
                    if (value is not None) != exists:
                        return False
                elif "$gte" in expected:
                    if not (value is not None and value >= expected["$gte"]):
                        return False
            elif value != expected:
                return False
        return True

    def _apply(self, doc, update):
        for key, value in update.get("$set", {}).items():
            self._set(doc, key, value)
        for key, value in update.get("$inc", {}).items():
            self._set(doc, key, (self._get(doc, key) or 0) + value)
        for key in update.get("$unset", {}):
            self._unset(doc, key)

    def _get(self, doc, dotted):
        cur = doc
        for part in dotted.split("."):
            if not isinstance(cur, dict):
                return None
            cur = cur.get(part)
        return cur

    def _set(self, doc, dotted, value):
        cur = doc
        parts = dotted.split(".")
        for part in parts[:-1]:
            cur = cur.setdefault(part, {})
        cur[parts[-1]] = value

    def _unset(self, doc, dotted):
        cur = doc
        parts = dotted.split(".")
        for part in parts[:-1]:
            cur = cur.get(part, {})
        if isinstance(cur, dict):
            cur.pop(parts[-1], None)


class AdminPanelTest(unittest.TestCase):
    def setUp(self):
        # Create memory collections
        self.users = MemoryCollection()
        self.comments = MemoryCollection()
        self.reports = MemoryCollection()
        self.logs = MemoryCollection()

        # Wire them up inside the model module
        adm.users_collection = self.users
        adm.comments_collection = self.comments
        adm.reports_collection = self.reports
        adm.audit_log_collection = self.logs
        adm._indexes_ready = False

        # Wire up inside routes module to prevent 404
        admin_routes.comments_collection = self.comments

        # Set up Flask App
        self.app = Flask(__name__)
        self.app.secret_key = "test-secret"
        self.app.register_blueprint(admin_bp)
        self.app.register_blueprint(admin_api_bp, url_prefix="/api/admin")
        self.client = self.app.test_client()

        # Seed initial data
        self.admin_user = {
            "_id": 1,
            "username": "weber",
            "email": "weber@yumezone.com",
            "role": "admin",
            "is_banned": False,
            "created_at": datetime.now(timezone.utc)
        }
        self.mod_user = {
            "_id": 2,
            "username": "mod_girl",
            "email": "mod@yumezone.com",
            "role": "mod",
            "is_banned": False,
            "created_at": datetime.now(timezone.utc)
        }
        self.regular_user = {
            "_id": 3,
            "username": "normal_dude",
            "email": "user@yumezone.com",
            "role": "user",
            "is_banned": False,
            "created_at": datetime.now(timezone.utc)
        }
        self.users.insert_one(self.admin_user)
        self.users.insert_one(self.mod_user)
        self.users.insert_one(self.regular_user)

        self.comment_doc = {
            "_id": ObjectId("60d5ec4b1f4142d1f0bb6c88"),
            "author_id": "4",
            "author": "other_dude",
            "body": "This is an offensive message!",
            "deleted": False,
            "report_count": 0,
            "created_at": datetime.now(timezone.utc)
        }
        self.comments.insert_one(self.comment_doc)

    def login_as(self, user):
        with self.client.session_transaction() as sess:
            sess["_id"] = user["_id"]
            sess["username"] = user["username"]

    def test_rbac_access_restrictions(self):
        # 1. Anonymous has no access to staff API
        r = self.client.get("/api/admin/dashboard")
        self.assertEqual(r.status_code, 401)

        # 2. Regular user has no access to staff API
        self.login_as(self.regular_user)
        r = self.client.get("/api/admin/dashboard")
        self.assertEqual(r.status_code, 403)

        # 3. Mod can access dashboard
        self.login_as(self.mod_user)
        r = self.client.get("/api/admin/dashboard")
        self.assertEqual(r.status_code, 200)

        # 4. Mod cannot update roles
        r = self.client.post("/api/admin/users/3/role", json={"role": "mod"})
        self.assertEqual(r.status_code, 403)

        # 5. Admin can update roles
        self.login_as(self.admin_user)
        r = self.client.post("/api/admin/users/3/role", json={"role": "mod"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.users.find_one({"_id": 3})["role"], "mod")

    def test_reporting_flow_and_resolving(self):
        # 1. User reports comment
        self.login_as(self.regular_user)
        r = self.client.post(
            "/api/admin/report-comment",
            json={
                "comment_id": "60d5ec4b1f4142d1f0bb6c88",
                "reason": "harassment",
                "details": "He is target bullying me."
            }
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.comments.find_one({"_id": ObjectId("60d5ec4b1f4142d1f0bb6c88")})["report_count"], 1)

        reports_list = self.reports.docs
        self.assertEqual(len(reports_list), 1)
        report_id = str(reports_list[0]["_id"])

        # 2. Mod resolves report with note
        self.login_as(self.mod_user)
        r = self.client.post(
            f"/api/admin/reports/{report_id}/resolve",
            json={"action": "warned", "note": "Gave user normal warning."}
        )
        self.assertEqual(r.status_code, 200)
        
        rep = self.reports.find_one({"_id": ObjectId(report_id)})
        self.assertEqual(rep["status"], "resolved")
        self.assertEqual(rep["moderator_note"], "Gave user normal warning.")
        self.assertEqual(rep["action_taken"], "warned")

        # 3. Log actions list shows moderation activity
        logs = self.logs.docs
        self.assertTrue(len(logs) > 0)
        self.assertIn("report_resolve", logs[0]["action"])

    def test_mute_user(self):
        self.login_as(self.mod_user)
        r = self.client.post(
            "/api/admin/users/3/mute",
            json={"action": "mute", "duration": 48, "note": "Spamming comments"}
        )
        self.assertEqual(r.status_code, 200)
        target = self.users.find_one({"_id": 3})
        self.assertIsNotNone(target.get("muted_until"))


if __name__ == "__main__":
    unittest.main()
