import asyncio
import re
from urllib.parse import quote

from nebula.core.logger import log_scraper_error
from nebula.scrapers.base import BaseScraper
from nebula.scrapers.models import ScrapeRequest
from nebula.services.torrent_manager import extract_trackers_from_magnet
from nebula.utils.formatting import size_to_bytes

BASE_URL = "https://1337x.to"

SEARCH_ROW_PATTERN = re.compile(
    r'<td[^>]*class="[^"]*\bname\b[^"]*"[^>]*>[^<]*<a[^>]*>.*?</a>\s*<a href="(/torrent/[^"]+)"[^>]*>([^<]+)</a>',
    re.DOTALL,
)
MAGNET_PATTERN = re.compile(r'href="(magnet:[^"]+)"')
INFO_HASH_PATTERN = re.compile(r"btih:([a-fA-F0-9]{40}|[a-zA-Z0-9]{32})", re.IGNORECASE)
SEEDERS_PATTERN = re.compile(r"<strong>Seeders</strong>\s*</dt>\s*<dd[^>]*>(\d+)")
SIZE_PATTERN = re.compile(r"<strong>Total size</strong>\s*</dt>\s*<dd[^>]*>([^<]+)")


async def _fetch_detail(session, semaphore: asyncio.Semaphore, href: str):
    async with semaphore:
        try:
            async with session.get(f"{BASE_URL}{href}") as response:
                if response.status != 200:
                    return None
                body = await response.text()
        except Exception:
            return None

    magnet_match = MAGNET_PATTERN.search(body)
    if not magnet_match:
        return None

    magnet = magnet_match.group(1)
    hash_match = INFO_HASH_PATTERN.search(magnet)
    if not hash_match:
        return None

    seeders_match = SEEDERS_PATTERN.search(body)
    seeders = int(seeders_match.group(1)) if seeders_match else None

    size_match = SIZE_PATTERN.search(body)
    size = None
    if size_match:
        size_str = size_match.group(1).strip().replace("iB", "B")
        try:
            size = size_to_bytes(size_str)
        except Exception:
            size = None

    return {
        "infoHash": hash_match.group(1).lower(),
        "magnet": magnet,
        "seeders": seeders,
        "size": size,
    }


class LeetxScraper(BaseScraper):
    impersonate = "chrome"

    def __init__(self, manager, session):
        super().__init__(manager, session)

    async def scrape(self, request: ScrapeRequest):
        torrents = []
        try:
            encoded = quote(request.title)
            if request.media_type == "series":
                url = f"{BASE_URL}/category-search/{encoded}/TV/1/"
            else:
                url = f"{BASE_URL}/search/{encoded}/1/"

            async with self.session.get(url) as response:
                if response.status != 200:
                    return torrents
                body = await response.text()

            if "1337x</title>" not in body:
                return torrents

            matches = SEARCH_ROW_PATTERN.findall(body)
            candidates = matches[:10]

            semaphore = asyncio.Semaphore(5)
            details = await asyncio.gather(
                *[_fetch_detail(self.session, semaphore, href) for href, _ in candidates]
            )

            for i, detail in enumerate(details):
                if detail is None:
                    continue
                _, name = candidates[i]
                torrents.append({
                    "title": name.strip(),
                    "infoHash": detail["infoHash"],
                    "fileIndex": None,
                    "seeders": detail["seeders"],
                    "size": detail["size"],
                    "tracker": "1337x",
                    "sources": extract_trackers_from_magnet(detail["magnet"]),
                })

        except Exception as e:
            log_scraper_error("Leetx", BASE_URL, request.media_id, e)

        return torrents
