import re
import asyncio

from nebula.utils.network_manager import AsyncClientWrapper

INFO_HASH_PATTERN = re.compile(r"btih:([a-fA-F0-9]{40}|[a-zA-Z0-9]{32})", re.IGNORECASE)

_CONTENT_TYPE_MAP = {
    "serie": "serie",
    "anime": "anime",
}


def get_content_type(item_type: str) -> str:
    """Map a search result's raw 'type' field to the singular API endpoint string."""
    item_type = (item_type or "").lower()
    for key, endpoint in _CONTENT_TYPE_MAP.items():
        if key in item_type:
            return endpoint
    return "movie"


async def search(session: AsyncClientWrapper, base_url: str, query: str) -> list:
    """Search the WP REST API. Returns raw list of result stubs."""
    try:
        async with session.get(
            f"{base_url}search", params={"query": query}
        ) as response:
            if response.status != 200:
                return []
            data = await response.json()
            if isinstance(data, list):
                return data
            return data.get("results", [])
    except Exception:
        return []


async def get_detail(
    session: AsyncClientWrapper, base_url: str, content_type: str, slug: str
) -> dict:
    """Fetch full detail for a single item (includes downloads with magnet links)."""
    async with session.get(f"{base_url}{content_type}/{slug}") as response:
        response.raise_for_status()
        return await response.json()


def extract_magnets(detail: dict) -> list[dict]:
    """
    Extract all magnet-based downloads from a detail dict.
    Skips entries without a magnet URI or valid info hash.
    Title is combined top-level title + per-download quality string.
    """
    results = []
    top_title = detail.get("title", "")

    for dl in detail.get("downloads", []):
        link = dl.get("download_link", "")
        if not link.startswith("magnet:"):
            continue

        match = INFO_HASH_PATTERN.search(link)
        if not match:
            continue

        quality = dl.get("quality", "")
        title = f"{top_title} {quality}".strip() if quality else top_title
        size_str = dl.get("size", "")

        results.append({
            "infoHash": match.group(1).lower(),
            "title": title,
            "size_str": size_str,  # raw string; caller passes to size_to_bytes()
            "magnet": link,
        })

    return results
