"""
Atsumaru (atsu.moe) manga scraper.
"""
import urllib.parse
import requests as std_requests
from .base import logger

BASE_URL = "https://atsu.moe"
REFERER = BASE_URL
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": f"{BASE_URL}/",
}


def _poster_url(path):
    """Convert an API poster path to a full static URL."""
    if not path:
        return ""
    # Already a full URL
    if path.startswith("http"):
        return path
    # Strip leading slash
    path = path.lstrip("/")
    # Ensure /static/ prefix
    if not path.startswith("static/"):
        path = f"static/{path}"
    return f"{BASE_URL}/{path}"

def _fetch_json(url):
    try:
        from curl_cffi import requests as cffi_requests
        return cffi_requests.get(url, headers=HEADERS, impersonate="chrome124", timeout=30).json()
    except ImportError:
        resp = std_requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        return resp.json()

def home():
    data = _fetch_json(f"{BASE_URL}/api/home/page")
    result = {}
    if "homePage" in data and "sections" in data["homePage"]:
        for section in data["homePage"]["sections"]:
            key = section.get("key", "unknown")
            title = section.get("title", key.replace("-", " ").title())
            items = []
            for item in section.get("items", []):
                items.append({
                    "id": item.get("id"), "title": item.get("title"),
                    "slug": item.get("id"),
                    "cover": _poster_url(item.get('image')),
                    "type": item.get("type"), "isAdult": item.get("isAdult", False),
                    "source": "atsumaru",
                })
            if items:
                result[key.replace("-", "_")] = {"title": title, "entries": items}
    return result

def details(manga_id):
    details_data = _fetch_json(f"{BASE_URL}/api/manga/page?id={manga_id}")
    info_data = _fetch_json(f"{BASE_URL}/api/manga/info?mangaId={manga_id}")
    manga_page = details_data.get("mangaPage", {})
    result = {
        "id": manga_id, "slug": manga_id, "title": info_data.get("title", ""),
        "type": info_data.get("type", ""), "views": manga_page.get("views", ""),
        "source": "atsumaru", "description": "", "authors": "Unknown",
        "status": "Unknown", "genres": [],
    }
    if manga_page.get("banner") and manga_page["banner"].get("url"):
        result["cover"] = _poster_url(manga_page['banner']['url'])
    chapters = []
    for chap in info_data.get("chapters", []):
        chapters.append({
            "id": chap.get("id"), "number": chap.get("number"),
            "title": chap.get("title", ""), "pageCount": chap.get("pageCount", 0),
        })
    result["chapters"] = chapters
    return result

def chapter_images(manga_id, chapter_id):
    data = _fetch_json(f"{BASE_URL}/api/read/chapter?mangaId={manga_id}&chapterId={chapter_id}")
    pages = []
    for page in data.get("readChapter", {}).get("pages", []):
        img = page.get("image")
        if img:
            pages.append(f"{BASE_URL}{img}" if img.startswith("/") else f"{BASE_URL}/{img}")
    return pages, REFERER

def search(query, limit=12):
    encoded = urllib.parse.quote_plus(query)
    url = (f"{BASE_URL}/collections/manga/documents/search?filter_by=&q={encoded}&limit={limit}"
           f"&query_by=title%2CenglishTitle%2CotherNames%2Cauthors&query_by_weights=4%2C3%2C2%2C1"
           f"&include_fields=id%2Ctitle%2CenglishTitle%2Cposter%2CposterSmall%2CposterMedium%2Ctype%2CisAdult%2Cstatus%2Cyear"
           f"&num_typos=4%2C3%2C2%2C1")
    data = _fetch_json(url)
    results = []
    for hit in data.get("hits", []):
        doc = hit.get("document", {})
        if doc:
            poster = doc.get("poster") or doc.get("posterMedium") or doc.get("posterSmall")
            results.append({
                "id": doc.get("id"), "title": doc.get("title") or doc.get("englishTitle"),
                "slug": doc.get("id"), "cover": _poster_url(poster),
                "type": doc.get("type"), "isAdult": doc.get("isAdult", False),
                "status": doc.get("status"), "source": "atsumaru",
            })
    return {"found": data.get("found", 0), "entries": results}
