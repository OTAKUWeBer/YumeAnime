"""
MyAnimeList API v2 — OAuth2 (PKCE) helpers and anime list update utilities.
"""

import os
import hashlib
import base64
import secrets
import time
import logging
import requests

from ..core.config import Config

logger = logging.getLogger(__name__)

MAL_AUTH_URL = "https://myanimelist.net/v1/oauth2/authorize"
MAL_TOKEN_URL = "https://myanimelist.net/v1/oauth2/token"
MAL_API_BASE = "https://api.myanimelist.net/v2"


# ── PKCE helpers ────────────────────────────────────────────────

def _generate_code_verifier(length: int = 128) -> str:
    """Generate a high-entropy code_verifier (43–128 chars, URL-safe)."""
    return secrets.token_urlsafe(length)[:128]


def _generate_code_challenge(verifier: str) -> str:
    """MAL uses 'plain' code_challenge_method — verifier == challenge."""
    return verifier


# ── OAuth2 flow ─────────────────────────────────────────────────

def get_mal_auth_url(state: str, code_verifier: str) -> str:
    """Build the MAL authorization URL (with PKCE)."""
    params = {
        "response_type": "code",
        "client_id": Config.MAL_CLIENT_ID,
        "redirect_uri": Config.MAL_REDIRECT_URI,
        "state": state,
        "code_challenge": _generate_code_challenge(code_verifier),
        "code_challenge_method": "plain",
    }
    from urllib.parse import urlencode
    return f"{MAL_AUTH_URL}?{urlencode(params)}"


def exchange_mal_code(code: str, code_verifier: str) -> dict | None:
    """Exchange authorization code for access + refresh tokens."""
    try:
        resp = requests.post(MAL_TOKEN_URL, data={
            "client_id": Config.MAL_CLIENT_ID,
            "client_secret": Config.MAL_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": Config.MAL_REDIRECT_URI,
            "code_verifier": code_verifier,
        }, timeout=15)

        if resp.status_code != 200:
            logger.error(f"MAL token exchange failed ({resp.status_code}): {resp.text[:300]}")
            return None

        data = resp.json()
        return {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token"),
            "expires_in": data.get("expires_in", 3600),
        }
    except Exception as e:
        logger.error(f"MAL token exchange error: {e}")
        return None


def refresh_mal_token(refresh_token: str) -> dict | None:
    """Refresh an expired MAL access token."""
    try:
        resp = requests.post(MAL_TOKEN_URL, data={
            "client_id": Config.MAL_CLIENT_ID,
            "client_secret": Config.MAL_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }, timeout=15)

        if resp.status_code != 200:
            logger.error(f"MAL token refresh failed ({resp.status_code}): {resp.text[:300]}")
            return None

        data = resp.json()
        return {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token", refresh_token),
            "expires_in": data.get("expires_in", 3600),
        }
    except Exception as e:
        logger.error(f"MAL token refresh error: {e}")
        return None


# ── Authenticated API calls ─────────────────────────────────────

def _mal_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


def get_mal_user_info(access_token: str) -> dict | None:
    """GET /v2/users/@me — returns basic profile info."""
    try:
        resp = requests.get(
            f"{MAL_API_BASE}/users/@me",
            headers=_mal_headers(access_token),
            params={"fields": "anime_statistics"},
            timeout=10,
        )
        if resp.status_code != 200:
            logger.error(f"MAL user info failed ({resp.status_code}): {resp.text[:300]}")
            return None
        return resp.json()
    except Exception as e:
        logger.error(f"MAL user info error: {e}")
        return None


def update_mal_anime_status(
    access_token: str,
    mal_id: int,
    *,
    status: str | None = None,
    num_watched_episodes: int | None = None,
    score: int | None = None,
) -> bool:
    """
    PATCH /v2/anime/{mal_id}/my_list_status
    Updates the user's list entry on MAL.

    status: watching | completed | on_hold | dropped | plan_to_watch
    """
    url = f"{MAL_API_BASE}/anime/{mal_id}/my_list_status"
    data = {}
    if status:
        data["status"] = status
    if num_watched_episodes is not None:
        data["num_watched_episodes"] = num_watched_episodes
    if score is not None:
        data["score"] = score

    if not data:
        return True  # nothing to update

    try:
        resp = requests.patch(
            url,
            headers=_mal_headers(access_token),
            data=data,
            timeout=10,
        )
        if resp.status_code == 200:
            logger.info(f"MAL update OK: mal_id={mal_id} {data}")
            return True
        logger.error(f"MAL update failed ({resp.status_code}): {resp.text[:300]}")
        return False
    except Exception as e:
        logger.error(f"MAL update error for mal_id={mal_id}: {e}")
        return False


def get_mal_anime_status(access_token: str, mal_id: int) -> dict | None:
    """GET /v2/anime/{mal_id} with list_status field — check current progress."""
    try:
        resp = requests.get(
            f"{MAL_API_BASE}/anime/{mal_id}",
            headers=_mal_headers(access_token),
            params={"fields": "my_list_status,num_episodes"},
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        return resp.json()
    except Exception as e:
        logger.error(f"MAL get status error for mal_id={mal_id}: {e}")
        return None
