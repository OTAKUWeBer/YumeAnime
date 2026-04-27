"""
Shared constants and helpers for manga scrapers.
"""
import json
import re
import logging

logger = logging.getLogger(__name__)

# Common fallback placeholder for missing cover images
NO_COVER_B64 = (
    "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjMwMCIgeG1sbnM9"
    "Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMjAwIiBoZWlnaHQ9"
    "IjMwMCIgZmlsbD0iIzFhMWEyZSIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBkb21pbmFudC1i"
    "YXNlbGluZT0ibWlkZGxlIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmaWxsPSIjNjY2IiBmb250"
    "LXNpemU9IjE0Ij5ObyBDb3ZlcjwvdGV4dD48L3N2Zz4="
)


def find_json_object(html: str, key: str):
    """
    Extract a JSON object/array from inline JS by searching for a given key.
    Used by Comix to pull data embedded in SSR HTML.
    """
    for pattern in [
        rf'\\\"{key}\\\":\s*([{{\[].*)',
        rf'"{key}":\s*([{{\[].*)',
    ]:
        match = re.search(pattern, html)
        if match:
            raw_chunk = match.group(1)
            is_obj = raw_chunk.startswith("{") or raw_chunk.startswith("\\{")
            start_char = "{" if is_obj else "["
            end_char = "}" if is_obj else "]"

            count = 0
            json_str = ""
            for char in raw_chunk:
                if char == start_char:
                    count += 1
                elif char == end_char:
                    count -= 1
                json_str += char
                if count == 0:
                    break

            if json_str:
                try:
                    if '\\"' in json_str or "\\\\" in json_str:
                        json_str = json_str.replace('\\"', '"').replace("\\\\", "\\")
                    return json.loads(json_str)
                except Exception:
                    continue
    return None
