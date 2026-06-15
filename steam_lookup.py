import re
import requests
from urllib.parse import quote

_TIMEOUT = 10
_cache = {}

_SUFFIX_RE = re.compile(
    r"\s+(?:игра\s+по\s+сети|играть|скачать|по\s+сети)\b.*$",
    re.IGNORECASE,
)


def _clean_title(raw_title):
    if not raw_title:
        return ""
    term = _SUFFIX_RE.sub("", raw_title)
    term = term.strip(" \t\r\n-—–/|:,.")
    term = re.sub(r"\s+", " ", term).strip()
    return term


def _storesearch(term):
    url = (
        "https://store.steampowered.com/api/storesearch/"
        f"?term={quote(term)}&cc=ru&l=russian"
    )
    resp = requests.get(url, timeout=_TIMEOUT)
    if resp.status_code != 200:
        return None
    items = (resp.json() or {}).get("items") or []
    if not items:
        return None
    return items[0].get("id")


def _resolve_appid(term):
    words = term.split()
    for n in range(len(words), 0, -1):
        appid = _storesearch(" ".join(words[:n]))
        if appid:
            return appid
    return None


def get_steam_context(raw_title):
    term = _clean_title(raw_title)
    if not term:
        return None
    if term in _cache:
        return _cache[term]
    result = _fetch(term)
    _cache[term] = result
    return result


def _fetch(term):
    try:
        appid = _resolve_appid(term)
        if not appid:
            print(f"steam: not found for {term}")
            return None
        url = (
            "https://store.steampowered.com/api/appdetails"
            f"?appids={appid}&cc=ru&l=russian"
        )
        resp = requests.get(url, timeout=_TIMEOUT)
        if resp.status_code != 200:
            print(f"steam: not found for {term}")
            return None
        details = (resp.json() or {}).get(str(appid)) or {}
        if not details.get("success"):
            print(f"steam: not found for {term}")
            return None
        data = details.get("data") or {}
        if data.get("type") != "game":
            print(f"steam: not found for {term}")
            return None
        return _build_context(data)
    except Exception:
        print(f"steam: not found for {term}")
        return None


def _build_context(data):
    name = data.get("name") or ""
    short_description = (data.get("short_description") or "").strip()
    genres = [g.get("description") for g in (data.get("genres") or []) if g.get("description")]
    categories = [
        c.get("description") for c in (data.get("categories") or []) if c.get("description")
    ]
    developers = data.get("developers") or []
    release_date = ((data.get("release_date") or {}).get("date") or "").strip()

    lines = []
    if name:
        lines.append(f"Steam: {name}")
    if short_description:
        lines.append(f"Описание: {short_description}")
    if genres:
        lines.append(f"Жанры: {', '.join(genres)}")
    if categories:
        lines.append(f"Категории: {', '.join(categories)}")
    if developers:
        lines.append(f"Разработчик: {', '.join(developers)}")
    if release_date:
        lines.append(f"Дата выхода: {release_date}")

    context = "\n".join(lines).strip()
    if not context:
        return None
    if len(context) > 1500:
        context = context[:1499].rstrip() + "…"
    return context
