from datetime import datetime, timedelta, timezone
import secrets
import re

from pymongo import ASCENDING, DESCENDING, ReturnDocument

from ..core.db_connector import (
    watch_together_rooms_collection,
    watch_together_messages_collection,
)


ROOM_TTL_SECONDS = 6 * 60 * 60
MEMBER_TTL_SECONDS = 90
MAX_CHAT_MESSAGES = 200
MAX_ROOM_MEMBERS = 20
ROOM_ID_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_indexes_ready = False


def utcnow():
    return datetime.now(timezone.utc)


def iso(dt):
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def epoch(dt):
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def clean_room_id(room_id):
    return re.sub(r"[^A-Z0-9]", "", str(room_id or "").upper())[:12]


def clean_client_id(client_id):
    raw = str(client_id or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{8,64}", raw):
        return raw
    return secrets.token_urlsafe(16)


def clean_display_name(name, fallback="Guest"):
    cleaned = re.sub(r"\s+", " ", str(name or "")).strip()
    cleaned = re.sub(r"[^\w\s\-\.\(\)\[\]]", "", cleaned) # Basic anti-XSS/malformed
    return (cleaned or fallback)[:32]


def room_expiry(now=None):
    now = now or utcnow()
    return now + timedelta(seconds=ROOM_TTL_SECONDS)


def _ensure_indexes():
    global _indexes_ready
    if _indexes_ready:
        return
    try:
        watch_together_rooms_collection.create_index(
            [("expires_at", ASCENDING)],
            expireAfterSeconds=0,
            name="watch_together_room_ttl",
        )
        watch_together_rooms_collection.create_index(
            [("room_id", ASCENDING)],
            unique=True,
            name="watch_together_room_id",
        )
        watch_together_messages_collection.create_index(
            [("expires_at", ASCENDING)],
            expireAfterSeconds=0,
            name="watch_together_message_ttl",
        )
        watch_together_messages_collection.create_index(
            [("room_id", ASCENDING), ("seq", DESCENDING)],
            name="watch_together_room_messages",
        )
    except Exception:
        pass
    _indexes_ready = True


def new_room_id():
    _ensure_indexes()
    while True:
        room_id = "".join(secrets.choice(ROOM_ID_ALPHABET) for _ in range(8))
        if not watch_together_rooms_collection.find_one({"room_id": room_id}, {"_id": 1}):
            return room_id


def _member_doc(client_id, display_name, avatar=None, now=None):
    now = now or utcnow()
    return {
        "id": client_id,
        "name": clean_display_name(display_name),
        "avatar": avatar,
        "joined_at": now,
        "last_seen": now,
    }


def _serialize_member(member, host_id=None, client_id=None):
    member_id = member.get("id")
    return {
        "id": member_id,
        "name": member.get("name") or "Guest",
        "avatar": member.get("avatar"),
        "is_host": member_id == host_id,
        "is_self": member_id == client_id,
        "last_seen": iso(member.get("last_seen")),
    }


def _serialize_playback(playback):
    playback = playback or {}
    return {
        "paused": bool(playback.get("paused", True)),
        "position": float(playback.get("position", 0) or 0),
        "rate": float(playback.get("rate", 1) or 1),
        "duration": float(playback.get("duration", 0) or 0),
        "seq": int(playback.get("seq", 0) or 0),
        "event": playback.get("event") or "sync",
        "updated_by": playback.get("updated_by"),
        "updated_by_name": playback.get("updated_by_name"),
        "updated_at": epoch(playback.get("updated_at")),
    }


def serialize_message(message):
    return {
        "seq": int(message.get("seq", 0) or 0),
        "author": message.get("author") or "Guest",
        "author_id": message.get("author_id"),
        "avatar": message.get("avatar"),
        "body": message.get("body") or "",
        "created_at": iso(message.get("created_at")),
    }


def serialize_room(room, client_id=None, messages=None):
    if not room:
        return None
    host_id = room.get("host_id")
    members = [
        _serialize_member(member, host_id, client_id)
        for member in (room.get("members") or {}).values()
        if member.get("id")
    ]
    members.sort(key=lambda item: (not item["is_host"], item["name"].lower()))
    return {
        "room_id": room.get("room_id"),
        "anime_id": room.get("anime_id"),
        "episode_number": room.get("episode_number"),
        "language": room.get("language") or "sub",
        "provider": room.get("provider"),
        "hls_providers": room.get("hls_providers") or [],
        "anime_title": room.get("anime_title") or "",
        "episode_title": room.get("episode_title") or "",
        "poster": room.get("poster") or "",
        "episode_image": room.get("episode_image") or "",
        "created_at": iso(room.get("created_at")),
        "updated_at": iso(room.get("updated_at")),
        "expires_at": iso(room.get("expires_at")),
        "host_id": host_id,
        "state_seq": int(room.get("state_seq", 0) or 0),
        "chat_seq": int(room.get("chat_seq", 0) or 0),
        "playback": _serialize_playback(room.get("playback")),
        "members": members,
        "messages": messages or [],
    }


def create_room(
    anime_id,
    episode_number,
    language,
    provider,
    hls_providers,
    creator,
    metadata=None,
):
    _ensure_indexes()
    now = utcnow()
    expires_at = room_expiry(now)
    room_id = new_room_id()
    client_id = clean_client_id(creator.get("client_id"))
    member = _member_doc(
        client_id,
        creator.get("display_name"),
        creator.get("avatar"),
        now,
    )
    metadata = metadata or {}
    doc = {
        "room_id": room_id,
        "anime_id": str(anime_id),
        "episode_number": int(episode_number),
        "language": language if language in ("sub", "dub") else "sub",
        "provider": provider,
        "hls_providers": hls_providers,
        "anime_title": metadata.get("anime_title") or "",
        "episode_title": metadata.get("episode_title") or "",
        "poster": metadata.get("poster") or "",
        "episode_image": metadata.get("episode_image") or "",
        "anilist_id": metadata.get("anilist_id"),
        "mal_id": metadata.get("mal_id"),
        "host_id": client_id,
        "members": {client_id: member},
        "playback": {
            "paused": True,
            "position": 0.0,
            "rate": 1.0,
            "duration": 0.0,
            "seq": 1,
            "event": "created",
            "updated_by": client_id,
            "updated_by_name": member["name"],
            "updated_at": now,
        },
        "state_seq": 1,
        "chat_seq": 0,
        "created_at": now,
        "updated_at": now,
        "expires_at": expires_at,
    }
    watch_together_rooms_collection.insert_one(doc)
    return doc


def get_room(room_id):
    _ensure_indexes()
    clean_id = clean_room_id(room_id)
    return watch_together_rooms_collection.find_one(
        {"room_id": clean_id, "expires_at": {"$gt": utcnow()}}
    )


def touch_room(room_id, client_id=None, display_name=None, avatar=None, extend_messages=False):
    room = get_room(room_id)
    if not room:
        return None
    now = utcnow()
    expires_at = room_expiry(now)
    update = {
        "updated_at": now,
        "expires_at": expires_at,
    }
    if client_id:
        client_id = clean_client_id(client_id)
        existing = (room.get("members") or {}).get(client_id, {})
        
        # Check member limit for NEW members
        if not existing and len(room.get("members") or {}) >= MAX_ROOM_MEMBERS:
            return room

        update[f"members.{client_id}"] = {
            "id": client_id,
            "name": clean_display_name(display_name or existing.get("name")),
            "avatar": avatar if avatar is not None else existing.get("avatar"),
            "joined_at": existing.get("joined_at", now),
            "last_seen": now,
        }
    room = watch_together_rooms_collection.find_one_and_update(
        {"room_id": room["room_id"]},
        {"$set": update},
        return_document=ReturnDocument.AFTER,
    )
    if extend_messages:
        watch_together_messages_collection.update_many(
            {"room_id": room["room_id"]},
            {"$set": {"expires_at": expires_at}},
        )
    return prune_members(room)


def prune_members(room):
    if not room:
        return None
    now = utcnow()
    stale = []
    for member_id, member in (room.get("members") or {}).items():
        last_seen = member.get("last_seen") or room.get("created_at") or now
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        if (now - last_seen).total_seconds() > MEMBER_TTL_SECONDS:
            stale.append(member_id)
    if stale:
        unset = {f"members.{member_id}": "" for member_id in stale}
        room = watch_together_rooms_collection.find_one_and_update(
            {"room_id": room["room_id"]},
            {"$unset": unset},
            return_document=ReturnDocument.AFTER,
        )
    members = room.get("members") or {}
    if room.get("host_id") not in members and members:
        next_host = sorted(
            members.values(),
            key=lambda item: item.get("joined_at") or now,
        )[0]["id"]
        room = watch_together_rooms_collection.find_one_and_update(
            {"room_id": room["room_id"]},
            {"$set": {"host_id": next_host}},
            return_document=ReturnDocument.AFTER,
        )
    return room


def leave_room(room_id, client_id):
    room = get_room(room_id)
    if not room:
        return None
    client_id = clean_client_id(client_id)
    room = watch_together_rooms_collection.find_one_and_update(
        {"room_id": room["room_id"]},
        {
            "$unset": {f"members.{client_id}": ""},
            "$set": {"updated_at": utcnow(), "expires_at": room_expiry()},
        },
        return_document=ReturnDocument.AFTER,
    )
    return prune_members(room)


def get_messages(room_id, since_seq=0, limit=MAX_CHAT_MESSAGES):
    _ensure_indexes()
    query = {"room_id": clean_room_id(room_id)}
    try:
        since_seq = int(since_seq or 0)
    except (TypeError, ValueError):
        since_seq = 0
    if since_seq:
        query["seq"] = {"$gt": since_seq}
        sort = [("seq", ASCENDING)]
    else:
        sort = [("seq", DESCENDING)]
    messages = list(
        watch_together_messages_collection.find(query).sort(sort).limit(limit)
    )
    if not since_seq:
        messages.reverse()
    return [serialize_message(message) for message in messages]


def add_chat_message(room, client_id, display_name, avatar, body):
    body = re.sub(r"\s+", " ", str(body or "")).strip()
    if not body:
        return room, None
    if len(body) > 500:
        body = body[:500]
    # Basic HTML escaping for safety
    body = body.replace("<", "&lt;").replace(">", "&gt;")
    now = utcnow()
    expires_at = room_expiry(now)
    room = watch_together_rooms_collection.find_one_and_update(
        {"room_id": room["room_id"]},
        {
            "$inc": {"chat_seq": 1, "state_seq": 1},
            "$set": {"updated_at": now, "expires_at": expires_at},
        },
        return_document=ReturnDocument.AFTER,
    )
    seq = int(room.get("chat_seq", 0) or 0)
    message = {
        "room_id": room["room_id"],
        "seq": seq,
        "author_id": clean_client_id(client_id),
        "author": clean_display_name(display_name),
        "avatar": avatar,
        "body": body,
        "created_at": now,
        "expires_at": expires_at,
    }
    watch_together_messages_collection.insert_one(message)
    return room, serialize_message(message)


def update_playback(room, client_id, display_name, payload, event_type):
    now = utcnow()
    try:
        position = max(0.0, float(payload.get("position", 0) or 0))
    except (TypeError, ValueError):
        position = 0.0
    try:
        duration = max(0.0, float(payload.get("duration", 0) or 0))
    except (TypeError, ValueError):
        duration = 0.0
    try:
        rate = float(payload.get("rate", 1) or 1)
    except (TypeError, ValueError):
        rate = 1.0
    if rate <= 0 or rate > 4:
        rate = 1.0
    paused = bool(payload.get("paused", event_type != "play"))
    if event_type == "play":
        paused = False
    elif event_type == "pause":
        paused = True
    update = {
        "playback": {
            "paused": paused,
            "position": position,
            "rate": rate,
            "duration": duration,
            "seq": int(room.get("playback", {}).get("seq", 0) or 0) + 1,
            "event": event_type,
            "updated_by": clean_client_id(client_id),
            "updated_by_name": clean_display_name(display_name),
            "updated_at": now,
        },
        "updated_at": now,
        "expires_at": room_expiry(now),
    }
    return watch_together_rooms_collection.find_one_and_update(
        {"room_id": room["room_id"]},
        {"$inc": {"state_seq": 1}, "$set": update},
        return_document=ReturnDocument.AFTER,
    )


def update_provider(room, provider, client_id, display_name, payload=None):
    if provider not in (room.get("hls_providers") or []):
        return None
    payload = payload or {}
    now = utcnow()
    playback = dict(room.get("playback") or {})
    if "position" in payload:
        try:
            playback["position"] = max(0.0, float(payload.get("position") or 0))
        except (TypeError, ValueError):
            pass
    if "duration" in payload:
        try:
            playback["duration"] = max(0.0, float(payload.get("duration") or 0))
        except (TypeError, ValueError):
            pass
    playback["seq"] = int(playback.get("seq", 0) or 0) + 1
    playback["event"] = "server_change"
    playback["updated_by"] = clean_client_id(client_id)
    playback["updated_by_name"] = clean_display_name(display_name)
    playback["updated_at"] = now
    return watch_together_rooms_collection.find_one_and_update(
        {"room_id": room["room_id"]},
        {
            "$inc": {"state_seq": 1},
            "$set": {
                "provider": provider,
                "playback": playback,
                "updated_at": now,
                "expires_at": room_expiry(now),
            },
        },
        return_document=ReturnDocument.AFTER,
    )
