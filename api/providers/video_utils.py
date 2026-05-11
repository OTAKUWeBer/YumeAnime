"""
Video scraper utility functions
Handles URL encoding, episode ID extraction, subtitle sorting, and proxying.
"""

import base64
import json
import os
import re
from typing import Optional, List, Dict, Any, Union
from urllib.parse import quote

import dotenv
from bs4 import BeautifulSoup

dotenv.load_dotenv()

# ── Proxy endpoints ───────────────────────────────────────────────────────────
WORKER_BASE = os.getenv(
    "WORKER_URL",
    "",
).rstrip("/")

CDN_PROXY_URL = os.getenv(
    "PROXY_URL",
    "https://cdn-eu.1ani.me/proxy/m3u8",
).rstrip("/")

if WORKER_BASE.startswith("http://"):
    WORKER_BASE = WORKER_BASE.replace("http://", "https://", 1)

if CDN_PROXY_URL.startswith("http://"):
    CDN_PROXY_URL = CDN_PROXY_URL.replace("http://", "https://", 1)


# Providers that MUST use kiwi worker (/p/ Base64 route)
_WORKER_PROVIDERS = {
    "kiwi",
    "animex",
    "ax",
    "ax-uwu",
    "ax-mochi",
    "ax-wave",
    "ax-zaza",
    "ax-yuki",
    "ax-zen",
    "uwu",
    "mochi",
    "wave",
    "zaza",
    "yuki",
    "zen",
}


def _is_already_proxied(url: str) -> bool:
    """True if URL already routes through one of our proxies."""
    if not url:
        return False

    return (
        url.startswith(WORKER_BASE + "/p/")
        or url.startswith(CDN_PROXY_URL)
    )


# ── Kiwi worker proxy (/p/ Base64) ───────────────────────────────────────────
def encode_payload(url: str, referer: str = "") -> str:
    """
    Encode URL + referer into Base64 payload for kiwi worker.

    Used ONLY for:
      - kiwi
      - AnimeX providers
    """
    if not url or _is_already_proxied(url):
        return url

    try:
        raw = f"{url}\x00{referer or ''}".encode("utf-8")
        b64 = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

        return f"{WORKER_BASE}/p/{b64}"

    except Exception:
        return url


# ── CDN-EU proxy (normal ?url= format) ───────────────────────────────────────
def encode_proxy(
    url: Optional[str],
    headers: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """
    Route through cdn-eu proxy.

    Used for:
      - arc
      - jet
      - zoro
      - all Miruro providers
      - subtitles

    Example:
    https://cdn-eu.1ani.me/proxy/m3u8?url=...&headers={"referer":"https://megaup.nl/"}
    """
    if not url or _is_already_proxied(url):
        return url

    try:
        encoded_url = quote(url, safe="")

        query = f"?url={encoded_url}"

        if headers:
            # Keep normal JSON structure
            encoded_headers = quote(json.dumps(headers), safe="")
            query += f"&headers={encoded_headers}"

        result = f"{CDN_PROXY_URL}{query}"

        if result.startswith("http://"):
            result = result.replace("http://", "https://", 1)

        return result

    except Exception:
        return url


# ── Backward compatibility wrappers ──────────────────────────────────────────
def encode_kiwi_proxy(
    url: Optional[str],
    referer: str = "https://kwik.cx/",
) -> Optional[str]:
    return encode_payload(url or "", referer)


def _normalize_provider(provider: Optional[str]) -> str:
    return (provider or "").strip().lower()


# ── Route selector ───────────────────────────────────────────────────────────
def _route_proxy(
    url: str,
    provider: Optional[str],
    headers: Optional[Dict[str, str]],
) -> str:
    """
    Decide which proxy to use.

    kiwi + AnimeX:
        → kiwi worker (/p/ Base64)

    arc / jet / zoro / Miruro:
        → cdn-eu normal proxy
    """
    if not url or _is_already_proxied(url):
        return url

    provider_norm = _normalize_provider(provider)

    is_worker_provider = (
        provider_norm in _WORKER_PROVIDERS
        or provider_norm.startswith("ax-")
        or provider_norm.startswith("animex")
    )

    # Kiwi + AnimeX → worker
    if is_worker_provider:
        referer = (
            (headers or {}).get("referer")
            or (headers or {}).get("Referer")
            or ""
        )

        if not referer and provider_norm == "kiwi":
            referer = "https://kwik.cx/"

        return encode_payload(url, referer)

    # arc / jet / zoro / everything else → cdn-eu
    return encode_proxy(url, headers) or url


# ── Episode ID extraction ────────────────────────────────────────────────────
def extract_episode_id(
    data: Union[str, Dict[str, Any], BeautifulSoup]
) -> Optional[str]:
    """
    Try multiple methods to extract numeric episode ID.
    """

    def find_in_text(text: Optional[str]) -> Optional[str]:
        if not text:
            return None

        m = re.search(r"[?&]ep=(\d+)", text)
        if m:
            return m.group(1)

        m = re.search(r"/(?:ep|episode)/(\d+)", text)
        if m:
            return m.group(1)

        m = re.search(r"(\d{5,})", text)
        if m:
            return m.group(1)

        return None

    # Dict input
    if isinstance(data, dict):

        for key in ("episodeId", "episode_id", "ep_id", "id"):
            if key in data and data[key]:

                val = str(data[key])

                ep = find_in_text(val)

                if ep:
                    data["episode_id"] = ep
                    return ep

                if re.fullmatch(r"\d+", val):
                    data["episode_id"] = val
                    return val

        candidates: List[str] = []

        sources = data.get("sources")

        if isinstance(sources, dict):
            candidates.extend([
                str(sources.get(k))
                for k in ("url", "file")
                if sources.get(k)
            ])

        elif isinstance(sources, list):
            for s in sources:
                if isinstance(s, dict):
                    candidates.extend([
                        str(s.get(k))
                        for k in ("url", "file")
                        if s.get(k)
                    ])
                elif isinstance(s, str):
                    candidates.append(s)

        tracks = data.get("tracks", [])

        if isinstance(tracks, list):
            for t in tracks:
                if isinstance(t, dict):
                    candidates.extend([
                        str(t.get(k))
                        for k in ("url", "file")
                        if t.get(k)
                    ])
                elif isinstance(t, str):
                    candidates.append(t)

        for c in candidates:
            ep = find_in_text(c)

            if ep:
                data["episode_id"] = ep
                return ep

        for key in ("anilistID", "anilistId", "malID", "malId"):
            if key in data and data[key]:
                val = str(data[key])
                data["episode_id"] = val
                return val

        return None

    # HTML input
    html_text = ""

    if isinstance(data, BeautifulSoup):
        html_text = str(data)

    elif isinstance(data, str):
        html_text = data

    patterns = [
        r"[?&]ep=(\d+)",
        r"getSources\?id=(\d+)",
        r'["\']ep["\']\s*[:=]\s*["\']?(\d+)["\']?',
        r'["\']id["\']\s*[:=]\s*["\']?(\d{3,})["\']?',
        r"/(?:ep|episode)/(\d+)",
    ]

    for patt in patterns:
        m = re.search(patt, html_text)

        if m:
            return m.group(1)

    m = re.search(r"(\d{5,})", html_text)

    if m:
        return m.group(1)

    return None


# ── Subtitle sorting ─────────────────────────────────────────────────────────
def sort_subtitle_priority(track: Dict[str, Any]) -> int:
    """
    Prioritize English subtitles and deprioritize thumbnails.
    Lower return value = higher priority.
    """
    if not isinstance(track, dict):
        return 50

    lang_label = (
        track.get("lang")
        or track.get("label")
        or ""
    ).lower()

    # thumbnails last
    if "thumbnail" in lang_label or "thumbnails" in lang_label:
        return 100

    # English first
    if any(k in lang_label for k in ("english", "eng", "en")):
        return 0

    # explicit default
    if track.get("default") is True:
        return 1

    return 10


# ── Main proxy dispatcher ────────────────────────────────────────────────────
def proxy_video_sources(
    data: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
    provider: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Route video links and subtitles through appropriate proxies.
    Modifies the input dictionary in-place.
    """
    if not isinstance(data, dict):
        return data

    if headers is None:
        headers = {"referer": "https://kwik.cx/"}

    def _pick(url: str, for_subtitles: bool = False) -> str:
        if not url or _is_already_proxied(url):
            return url
        if for_subtitles:
            return encode_proxy(url, headers) or url
        return _route_proxy(url, provider, headers)

    # ── video_link ──────────────────────────────────────────────────────────
    if data.get("video_link"):
        data["video_link"] = _pick(data["video_link"])

    # ── sources / video_sources ──────────────────────────────────────────────
    sources = data.get("sources") or data.get("video_sources")
    if isinstance(sources, dict):
        for k in ("file", "url"):
            if sources.get(k):
                sources[k] = _pick(sources[k])
    elif isinstance(sources, list):
        for s in sources:
            if isinstance(s, dict):
                for k in ("file", "url"):
                    if s.get(k):
                        s[k] = _pick(s[k])

    # ── hls_sources ──────────────────────────────────────────────────────────
    hls = data.get("hls_sources")
    if isinstance(hls, list):
        for s in hls:
            if isinstance(s, dict):
                for k in ("file", "url"):
                    if s.get(k):
                        s[k] = _pick(s[k])
        # Rebuild video_link if missing
        if hls and not data.get("video_link"):
            data["video_link"] = hls[0].get("url") or hls[0].get("file")

    # ── tracks / subtitle_tracks ───────────────────────────────────────────
    tracks = data.get("tracks") or data.get("subtitle_tracks")
    if isinstance(tracks, list):
        for track in tracks:
            if not isinstance(track, dict):
                continue
            if track.get("lang") and not track.get("label"):
                track["label"] = track["lang"]
            if not track.get("kind"):
                ll = (track.get("lang") or track.get("label") or "").lower()
                track["kind"] = "metadata" if "thumbnail" in ll else "subtitles"
            for k in ("file", "url"):
                if track.get(k):
                    track[k] = _pick(track[k], for_subtitles=True)
        try:
            tracks.sort(key=sort_subtitle_priority)
        except Exception:
            pass

    return data