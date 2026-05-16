import asyncio
from datetime import datetime, timezone
import re

from flask import Blueprint, current_app, jsonify, render_template, request, session

from ...models import watch_together as wt
from ...providers.miruro.episodes import PROVIDER_CAPABILITIES, PROVIDER_PRIORITY
from ...utils.moderation import contains_banned_words
from .watch_routes import (
    EPS_CACHE,
    _fetch_video_only,
    _find_episode_id_for_provider,
    _parse_ep_number,
    _resolve_episode,
    _scavenge_intro_outro,
)


watch_together_bp = Blueprint("watch_together", __name__)


def _clean_anime_id(anime_id):
    return str(anime_id or "").split("?", 1)[0].strip()


def _json_error(message, status=400):
    return jsonify({"success": False, "message": message, "error": message}), status


def _identity(data):
    client_id = wt.clean_client_id((data or {}).get("client_id"))
    if session.get("username"):
        return {
            "client_id": client_id,
            "display_name": session.get("username"),
            "avatar": session.get("avatar"),
            "user_id": str(session.get("_id") or ""),
        }
    return {
        "client_id": client_id,
        "display_name": wt.clean_display_name((data or {}).get("display_name")),
        "avatar": None,
        "user_id": "",
    }





def _anime_slug_from_title(title):
    if not title:
        return None
    return re.sub(r"[^\w\s-]", "", title.lower()).replace(" ", "-").strip("-")


def _fetch_anime_info(anime_id):
    anime_info = None
    anime = {}
    anilist_id = None
    try:
        anime_info = asyncio.run(current_app.ha_scraper.get_anime_info(anime_id))
        if isinstance(anime_info, dict):
            anime = anime_info.get("info", anime_info)
            if not isinstance(anime, dict):
                anime = {}
            anilist_id = anime.get("anilistId") or anime.get("alID")
            if anilist_id:
                anilist_id = int(anilist_id)
    except Exception as exc:
        current_app.logger.warning("[WatchTogether] anime info failed: %s", exc)
    return anime_info, anime, anilist_id


def _fetch_episodes(anime_id, anime, anilist_id):
    fetch_id = anime_id if str(anime_id).isdigit() else (str(anilist_id) if anilist_id else anime_id)
    anime_slug = None
    if not str(anime_id).isdigit():
        anime_slug = anime_id
    else:
        anime_slug = _anime_slug_from_title(anime.get("title") or anime.get("name"))

    cached = EPS_CACHE.get(str(fetch_id))
    if cached:
        return cached

    episodes = asyncio.run(current_app.ha_scraper.episodes(fetch_id, anime_slug))
    if episodes and episodes.get("providers_map"):
        EPS_CACHE[str(fetch_id)] = episodes
    return episodes


def _hls_providers(providers_map):
    providers = []
    for provider in PROVIDER_PRIORITY:
        if provider not in (providers_map or {}):
            continue
        caps = PROVIDER_CAPABILITIES.get(provider, {"hls": True, "embed": False})
        if caps.get("hls"):
            providers.append(provider)
    for provider in (providers_map or {}):
        if provider in providers:
            continue
        caps = PROVIDER_CAPABILITIES.get(provider, {"hls": True, "embed": False})
        if caps.get("hls"):
            providers.append(provider)
    return providers


def _build_room_context(anime_id, episode_number, language, requested_provider=None):
    anime_id = _clean_anime_id(anime_id)
    try:
        ep_number = int(float(str(episode_number)))
    except (TypeError, ValueError):
        raise ValueError("Episode number is required")

    _, anime, anilist_id = _fetch_anime_info(anime_id)
    episodes = _fetch_episodes(anime_id, anime, anilist_id)
    providers_map = episodes.get("providers_map", {}) if episodes else {}
    providers = _hls_providers(providers_map)
    if not providers:
        raise ValueError("No HLS servers are available for this episode")

    default_provider = episodes.get("default_provider") if episodes else None
    provider = requested_provider if requested_provider in providers else None
    if not provider and default_provider in providers:
        provider = default_provider
    provider = provider or providers[0]

    resolved = _resolve_episode(episodes, ep_number, provider)
    if not resolved:
        raise ValueError("Episode not found")

    episode = resolved["episode_item"]
    poster = (
        anime.get("coverImage")
        or anime.get("poster")
        or anime.get("image")
        or ""
    )
    anime_title = anime.get("name") or anime.get("title") or anime_id.replace("-", " ").title()
    return {
        "anime_id": anime_id,
        "episode_number": ep_number,
        "language": language if language in ("sub", "dub") else "sub",
        "provider": provider,
        "hls_providers": providers,
        "anime": anime,
        "anilist_id": anilist_id,
        "episodes": episodes,
        "providers_map": providers_map,
        "metadata": {
            "anime_title": anime_title,
            "episode_title": episode.get("title") or "",
            "poster": poster,
            "episode_image": episode.get("image") or "",
            "anilist_id": anilist_id,
            "mal_id": anime.get("malId") or anime.get("malID"),
        },
    }


def _fetch_room_episodes(room):
    anime_id = room.get("anime_id")
    _, anime, anilist_id = _fetch_anime_info(anime_id)
    if room.get("anilist_id"):
        anilist_id = room.get("anilist_id")
    episodes = _fetch_episodes(anime_id, anime, anilist_id)
    return anime, anilist_id, episodes, episodes.get("providers_map", {}) if episodes else {}


def _room_snapshot(room, client_id=None, since_chat_seq=0, messages=None):
    if messages is None:
        messages = wt.get_messages(room.get("room_id"), since_chat_seq)
    payload = wt.serialize_room(room, client_id, messages)
    payload["server_time"] = wt.utcnow().timestamp()
    return payload


@watch_together_bp.route("/watch-together/create", methods=["GET"])
def create_room_page():
    return render_template(
        "anime/watch_together_create.html",
        is_logged_in=bool(session.get("username")),
        username=session.get("username") or "",
        avatar=session.get("avatar") or "",
    )


@watch_together_bp.route("/watch-together/<room_id>", methods=["GET"])
def room_page(room_id):
    room = wt.get_room(room_id)
    if not room:
        return render_template("shared/404.html", error_message="Watch room not found"), 404
    return render_template(
        "anime/watch_together_room.html",
        room=wt.serialize_room(room),
        is_logged_in=bool(session.get("username")),
        username=session.get("username") or "",
        avatar=session.get("avatar") or "",
    )


@watch_together_bp.route("/api/watch-together/rooms", methods=["POST"])
def create_room_api():
    data = request.get_json(silent=True) or {}
    anime_id = _clean_anime_id(data.get("anime_id"))
    if not anime_id:
        return _json_error("Anime id is required")
    identity = _identity(data)

    try:
        context = _build_room_context(
            anime_id,
            data.get("episode_number"),
            data.get("language", "sub"),
            data.get("provider"),
        )
    except ValueError as exc:
        return _json_error(str(exc), 400)
    except Exception as exc:
        current_app.logger.exception("[WatchTogether] create context failed")
        return _json_error("Could not create room", 500)

    room = wt.create_room(
        anime_id=context["anime_id"],
        episode_number=context["episode_number"],
        language=context["language"],
        provider=context["provider"],
        hls_providers=context["hls_providers"],
        creator=identity,
        metadata=context["metadata"],
    )
    snapshot = _room_snapshot(room, identity["client_id"], 0)
    room_url = request.host_url.rstrip("/") + f"/watch-together/{room['room_id']}"
    return jsonify(
        {
            "success": True,
            "client_id": identity["client_id"],
            "room_id": room["room_id"],
            "room_url": room_url,
            "room": snapshot,
        }
    )


@watch_together_bp.route("/api/watch-together/rooms/<room_id>/join", methods=["POST"])
def join_room_api(room_id):
    data = request.get_json(silent=True) or {}
    identity = _identity(data)
    room = wt.touch_room(
        room_id,
        identity["client_id"],
        identity["display_name"],
        identity["avatar"],
        extend_messages=True,
    )
    if not room:
        return _json_error("Room not found", 404)
    return jsonify(
        {
            "success": True,
            "client_id": identity["client_id"],
            "room": _room_snapshot(room, identity["client_id"], 0),
        }
    )


@watch_together_bp.route("/api/watch-together/rooms/<room_id>/snapshot", methods=["GET"])
def room_snapshot_api(room_id):
    client_id = wt.clean_client_id(request.args.get("client_id"))
    display_name = request.args.get("display_name")
    if session.get("username"):
        display_name = session.get("username")
    since_chat_seq = request.args.get("since_chat_seq", 0)
    try:
        since_chat_seq = int(since_chat_seq or 0)
    except ValueError:
        since_chat_seq = 0
    room = wt.touch_room(
        room_id,
        client_id,
        display_name,
        session.get("avatar"),
        extend_messages=False,
    )
    if not room:
        return _json_error("Room not found", 404)
    return jsonify(
        {
            "success": True,
            "client_id": client_id,
            "room": _room_snapshot(room, client_id, since_chat_seq),
        }
    )


@watch_together_bp.route("/api/watch-together/rooms/<room_id>/events", methods=["POST"])
def room_event_api(room_id):
    data = request.get_json(silent=True) or {}
    identity = _identity(data)
    event_type = str(data.get("type") or "").strip()
    room = wt.touch_room(
        room_id,
        identity["client_id"],
        identity["display_name"],
        identity["avatar"],
        extend_messages=True,
    )
    if not room:
        return _json_error("Room not found", 404)

    if event_type in ("play", "pause", "seek", "ratechange"):
        room = wt.update_playback(
            room,
            identity["client_id"],
            identity["display_name"],
            data,
            event_type,
        )
    elif event_type == "server_change":
        room = wt.update_provider(
            room,
            str(data.get("provider") or ""),
            identity["client_id"],
            identity["display_name"],
            data,
        )
        if not room:
            return _json_error("HLS server is not available", 400)
    elif event_type == "chat":
        body = str(data.get("body") or "").strip()
        if not body:
            return _json_error("Message is empty")
        if contains_banned_words(body):
            return _json_error("Message contains inappropriate language", 400)
        room, message = wt.add_chat_message(
            room,
            identity["client_id"],
            identity["display_name"],
            identity["avatar"],
            body,
        )
        return jsonify(
            {
                "success": True,
                "client_id": identity["client_id"],
                "message": message,
                "room": _room_snapshot(room, identity["client_id"], data.get("since_chat_seq", 0)),
            }
        )
    elif event_type == "heartbeat":
        pass
    else:
        return _json_error("Unsupported room event", 400)

    return jsonify(
        {
            "success": True,
            "client_id": identity["client_id"],
            "room": _room_snapshot(room, identity["client_id"], data.get("since_chat_seq", 0)),
        }
    )


@watch_together_bp.route("/api/watch-together/rooms/<room_id>/source", methods=["GET"])
def room_source_api(room_id):
    client_id = wt.clean_client_id(request.args.get("client_id"))
    room = wt.touch_room(room_id, client_id, request.args.get("display_name"), session.get("avatar"))
    if not room:
        return _json_error("Room not found", 404)

    try:
        _, anilist_id, episodes, providers_map = _fetch_room_episodes(room)
        provider = room.get("provider")
        lang = room.get("language") or "sub"
        episode_id = _find_episode_id_for_provider(
            providers_map,
            provider,
            room.get("episode_number"),
            lang,
        )
        if not episode_id and episodes:
            resolved = _resolve_episode(episodes, room.get("episode_number"), provider)
            episode_id = resolved["episode_id"] if resolved else None
        if not episode_id:
            return _json_error("Episode source not found", 404)

        if str(episode_id).startswith("watch/"):
            parts = str(episode_id).split("/")
            if len(parts) >= 5:
                parts[3] = lang
            full_slug = "/".join(parts)
        else:
            full_slug = str(episode_id)

        video_data, _ = _fetch_video_only(full_slug, lang, provider, anilist_id, providers_map)
        video_data = _scavenge_intro_outro(
            video_data,
            providers_map,
            room.get("episode_number"),
            lang,
            provider,
            anilist_id,
        )
        hls_sources = video_data.get("hls_sources") or []
        if not hls_sources:
            return jsonify(
                {
                    "success": False,
                    "available": False,
                    "provider": provider,
                    "hls_providers": room.get("hls_providers") or [],
                    "message": "Selected HLS server has no playable source.",
                }
            ), 200
        return jsonify(
            {
                "success": True,
                "available": True,
                "provider": provider,
                "hls_providers": room.get("hls_providers") or [],
                "hls_sources": hls_sources,
                "intro": video_data.get("intro"),
                "outro": video_data.get("outro"),
                "subtitles": video_data.get("subtitle_tracks") or [],
            }
        )
    except Exception as exc:
        current_app.logger.exception("[WatchTogether] source failed")
        return _json_error("Could not load HLS source", 500)


@watch_together_bp.route("/api/watch-together/rooms/<room_id>/leave", methods=["POST"])
def leave_room_api(room_id):
    data = request.get_json(silent=True) or {}
    room = wt.leave_room(room_id, data.get("client_id"))
    return jsonify({"success": True, "room": wt.serialize_room(room) if room else None})
