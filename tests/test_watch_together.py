import copy
import unittest
from unittest.mock import patch

from flask import Flask

from api.models import watch_together as wt
from api.routes.anime.watch_together_routes import watch_together_bp


class QueryResult:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, sort_spec):
        for key, direction in reversed(sort_spec):
            self.docs.sort(key=lambda item: item.get(key, 0), reverse=direction < 0)
        return self

    def limit(self, count):
        self.docs = self.docs[:count]
        return self

    def __iter__(self):
        return iter(copy.deepcopy(self.docs))


class MemoryCollection:
    def __init__(self):
        self.docs = []

    def create_index(self, *args, **kwargs):
        return kwargs.get("name", "idx")

    def insert_one(self, doc):
        self.docs.append(copy.deepcopy(doc))
        return type("InsertResult", (), {"inserted_id": len(self.docs)})()

    def find_one(self, query, projection=None):
        for doc in self.docs:
            if self._matches(doc, query):
                return copy.deepcopy(doc)
        return None

    def find(self, query):
        return QueryResult([copy.deepcopy(doc) for doc in self.docs if self._matches(doc, query)])

    def find_one_and_update(self, query, update, return_document=None):
        for index, doc in enumerate(self.docs):
            if self._matches(doc, query):
                self._apply(doc, update)
                self.docs[index] = doc
                return copy.deepcopy(doc)
        return None

    def update_many(self, query, update):
        count = 0
        for doc in self.docs:
            if self._matches(doc, query):
                self._apply(doc, update)
                count += 1
        return type("UpdateResult", (), {"modified_count": count})()

    def _matches(self, doc, query):
        for key, expected in query.items():
            value = self._get(doc, key)
            if isinstance(expected, dict):
                if "$gt" in expected and not (value is not None and value > expected["$gt"]):
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


def fake_room_context(anime_id, episode_number, language, requested_provider=None):
    provider = requested_provider if requested_provider in ("kiwi", "bee") else "kiwi"
    return {
        "anime_id": anime_id,
        "episode_number": int(episode_number),
        "language": language,
        "provider": provider,
        "hls_providers": ["kiwi", "bee"],
        "metadata": {
            "anime_title": "Test Show",
            "episode_title": "Pilot",
            "poster": "",
            "episode_image": "",
            "anilist_id": 123,
            "mal_id": 456,
        },
    }


class WatchTogetherApiTest(unittest.TestCase):
    def setUp(self):
        self.rooms = MemoryCollection()
        self.messages = MemoryCollection()
        wt.watch_together_rooms_collection = self.rooms
        wt.watch_together_messages_collection = self.messages
        wt._indexes_ready = False

        self.app = Flask(__name__, template_folder="../api/templates")
        self.app.secret_key = "test"
        self.app.register_blueprint(watch_together_bp)
        self.client = self.app.test_client()

        self.patches = [
            patch("api.routes.anime.watch_together_routes._build_room_context", fake_room_context),
            patch(
                "api.routes.anime.watch_together_routes._fetch_room_episodes",
                return_value=({}, 123, {"providers_map": {}}, {"kiwi": {}, "bee": {}}),
            ),
            patch(
                "api.routes.anime.watch_together_routes._find_episode_id_for_provider",
                return_value="watch/test/sub/episode-1",
            ),
            patch(
                "api.routes.anime.watch_together_routes._fetch_video_only",
                return_value=(
                    {
                        "hls_sources": [{"url": "https://cdn.example.test/master.m3u8"}],
                        "embed_sources": [{"url": "https://embed.example.test"}],
                    },
                    False,
                ),
            ),
            patch(
                "api.routes.anime.watch_together_routes._scavenge_intro_outro",
                side_effect=lambda data, *args: {**data, "intro": {"start": 1, "end": 9}},
            ),
        ]
        for patcher in self.patches:
            patcher.start()

    def tearDown(self):
        for patcher in reversed(self.patches):
            patcher.stop()

    def create_room(self):
        response = self.client.post(
            "/api/watch-together/rooms",
            json={
                "anime_id": "test-show",
                "episode_number": 1,
                "language": "sub",
                "display_name": "Host",
                "client_id": "host-1234",
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.get_json()["room_id"]

    def test_create_join_chat_and_incremental_snapshot(self):
        room_id = self.create_room()
        first_join = self.client.post(
            f"/api/watch-together/rooms/{room_id}/join",
            json={"client_id": "guest-1111", "display_name": "Mina"},
        )
        second_join = self.client.post(
            f"/api/watch-together/rooms/{room_id}/join",
            json={"client_id": "guest-2222", "display_name": "Rafi"},
        )
        self.assertEqual(first_join.status_code, 200)
        self.assertEqual(second_join.status_code, 200)

        chat = self.client.post(
            f"/api/watch-together/rooms/{room_id}/events",
            json={"type": "chat", "client_id": "guest-1111", "display_name": "Mina", "body": "Ready"},
        )
        self.assertEqual(chat.status_code, 200)

        snapshot = self.client.get(
            f"/api/watch-together/rooms/{room_id}/snapshot",
            query_string={"client_id": "guest-2222", "since_chat_seq": 0},
        ).get_json()["room"]
        self.assertEqual(len(snapshot["members"]), 3)
        self.assertEqual(snapshot["messages"][0]["body"], "Ready")

        incremental = self.client.get(
            f"/api/watch-together/rooms/{room_id}/snapshot",
            query_string={"client_id": "guest-2222", "since_chat_seq": snapshot["chat_seq"]},
        ).get_json()["room"]
        self.assertEqual(incremental["messages"], [])

    def test_playback_events_update_authoritative_state(self):
        room_id = self.create_room()
        play = self.client.post(
            f"/api/watch-together/rooms/{room_id}/events",
            json={
                "type": "play",
                "client_id": "host-1234",
                "display_name": "Host",
                "position": 12,
                "duration": 120,
                "rate": 1.25,
            },
        ).get_json()["room"]
        self.assertFalse(play["playback"]["paused"])
        self.assertEqual(play["playback"]["position"], 12)
        self.assertEqual(play["playback"]["rate"], 1.25)
        self.assertIn("server_time", play)

        pause = self.client.post(
            f"/api/watch-together/rooms/{room_id}/events",
            json={"type": "pause", "client_id": "host-1234", "display_name": "Host", "position": 18},
        ).get_json()["room"]
        self.assertTrue(pause["playback"]["paused"])
        self.assertGreater(pause["playback"]["seq"], play["playback"]["seq"])

    def test_server_change_and_hls_source_are_room_state_only(self):
        room_id = self.create_room()
        changed = self.client.post(
            f"/api/watch-together/rooms/{room_id}/events",
            json={"type": "server_change", "client_id": "host-1234", "display_name": "Host", "provider": "bee"},
        ).get_json()["room"]
        self.assertEqual(changed["provider"], "bee")

        source = self.client.get(
            f"/api/watch-together/rooms/{room_id}/source",
            query_string={"client_id": "guest-1111"},
        ).get_json()
        self.assertTrue(source["available"])
        self.assertEqual(source["provider"], "bee")
        self.assertIn("hls_sources", source)
        self.assertNotIn("embed_sources", source)

    def test_missing_room_returns_clean_404_json_and_page(self):
        response = self.client.get("/api/watch-together/rooms/NOPE/snapshot")
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.get_json()["success"])

        with patch("api.routes.anime.watch_together_routes.render_template", return_value="missing"):
            page = self.client.get("/watch-together/NOPE")
        self.assertEqual(page.status_code, 404)


if __name__ == "__main__":
    unittest.main()
