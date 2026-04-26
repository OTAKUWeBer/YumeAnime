"""
Comix (comix.to) manga scraper.
"""
import html as html_module
import requests as std_requests
from bs4 import BeautifulSoup
from .base import logger, find_json_object

BASE_URL = "https://comix.to"
REFERER = BASE_URL
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": f"{BASE_URL}/",
}

def _fetch(path="/home", return_resp=False):
    try:
        from curl_cffi import requests as cffi_requests
        resp = cffi_requests.get(f"{BASE_URL}{path}", headers=HEADERS, impersonate="chrome124", timeout=30)
    except ImportError:
        resp = std_requests.get(f"{BASE_URL}{path}", headers=HEADERS, timeout=30)
    return resp if return_resp else resp.text

def _parse_item(el):
    data = {}
    poster_link = el.find("a", class_="poster") or el.find("a", href=lambda h: h and "/title/" in h)
    if poster_link:
        href = poster_link.get("href", "")
        data["url"] = BASE_URL + href if href.startswith("/") else href
        slug = href.split("/title/")[-1] if "/title/" in href else ""
        data["id"] = slug.split("-")[0] if slug else ""
        data["slug"] = slug
    img = el.find("img")
    if img:
        data["cover"] = img.get("src", "")
        data["title"] = html_module.unescape(img.get("alt", ""))
    title_link = el.find("a", class_="title")
    if title_link:
        data["title"] = html_module.unescape(title_link.get_text(strip=True))
    title_div = el.find("div", class_="title")
    if title_div and "title" not in data:
        data["title"] = html_module.unescape(title_div.get_text(strip=True))
    meta = el.find("div", class_="metadata")
    if meta:
        spans = meta.find_all("span")
        if len(spans) >= 1:
            data["latest_chapter"] = spans[0].get_text(strip=True)
    data["source"] = "comix"
    return data

def home():
    html_text = _fetch("/home")
    soup = BeautifulSoup(html_text, "html.parser")
    result = {}
    main_aside = soup.find("aside", class_="main")
    if main_aside:
        for sec in main_aside.find_all("section"):
            title_span = sec.find("span", class_="section-title")
            if title_span:
                name = title_span.get_text(strip=True)
                key = name.lower().replace(" ", "_")
                items = [_parse_item(d) for d in sec.find_all("div", class_="item") if _parse_item(d).get("title")]
                if items:
                    result[key] = {"title": name, "entries": items}
    sidebar = soup.find("aside", class_="sidebar")
    if sidebar:
        added_box = sidebar.find("section", class_="added-box")
        if added_box:
            items = [_parse_item(a) for a in added_box.find_all("a", class_="item") if _parse_item(a).get("title")]
            if items:
                result["recently_added"] = {"title": "Recently Added", "entries": items}
    return result

def details(id_or_slug):
    html_text = _fetch(f"/title/{id_or_slug}")
    data = find_json_object(html_text, "manga")
    if not data:
        return None
    result = {
        "title": data.get("title", ""), "slug": id_or_slug,
        "cover": data.get("poster", ""), "description": data.get("description", ""),
        "authors": ", ".join(data.get("authors", [])) if isinstance(data.get("authors"), list) else data.get("authors", "Unknown"),
        "status": data.get("status", "Unknown"), "genres": data.get("genres", []),
        "source": "comix", "chapters": [],
    }
    hash_id = data.get("hashId") or id_or_slug.split("-")[0]
    try:
        from curl_cffi import requests as cffi_requests
        resp = cffi_requests.get(f"{BASE_URL}/api/v2/manga/{hash_id}/chapters?limit=100&page=1&order[number]=desc",
                                  headers=HEADERS, impersonate="chrome124", timeout=30)
        if resp.status_code == 200:
            for c in resp.json().get("data", []):
                result["chapters"].append({
                    "id": f"{c.get('id', '')}-chapter-{c.get('number', '')}",
                    "title": f"Chapter {c.get('number', '')}", "number": c.get("number"),
                })
    except Exception:
        pass
    return result

def chapter_images(manga_slug, chapter_slug):
    html_text = _fetch(f"/title/{manga_slug}/{chapter_slug}")
    data = find_json_object(html_text, "images")
    if data and isinstance(data, list):
        return data, REFERER
    return [], REFERER

def search(keyword, limit=20):
    try:
        from curl_cffi import requests as cffi_requests
        params = {"order[relevance]": "desc", "keyword": keyword, "limit": limit, "page": 1}
        resp = cffi_requests.get(f"{BASE_URL}/api/v2/manga", params=params, headers=HEADERS, impersonate="chrome124", timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            results = []
            for item in data.get("data", []):
                results.append({
                    "id": item.get("hashId", ""), "title": item.get("title", ""),
                    "slug": f"{item.get('hashId', '')}-{item.get('slug', '')}",
                    "cover": item.get("poster", ""), "source": "comix",
                })
            return {"entries": results, "found": data.get("total", len(results))}
    except Exception as e:
        logger.error(f"Comix search error: {e}")
    return {"entries": [], "found": 0}
