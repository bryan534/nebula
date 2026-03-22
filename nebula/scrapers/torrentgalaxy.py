import re
from urllib.parse import quote

from nebula.core.logger import log_scraper_error
from nebula.scrapers.base import BaseScraper
from nebula.scrapers.models import ScrapeRequest
from nebula.services.torrent_manager import extract_trackers_from_magnet
from nebula.utils.formatting import size_to_bytes

BASE_URL = "https://torrentgalaxy.to"

# Split HTML on row boundaries — more reliable than matching nested closing divs
ROW_SPLIT_PATTERN = re.compile(r'<div class="tgxtablerow[^"]*">', re.IGNORECASE)
INFO_HASH_PATTERN = re.compile(r"btih:([a-fA-F0-9]{40}|[a-zA-Z0-9]{32})", re.IGNORECASE)
MAGNET_PATTERN = re.compile(r'href="(magnet:[^"]+)"')
NAME_PATTERN = re.compile(r'<a[^>]+href="/torrent/[^"]*"[^>]*>([^<]+)</a>')
SEEDERS_PATTERN = re.compile(r'<span[^>]*><b><font[^>]*>(\d+)</font></b></span>')
SIZE_PATTERN = re.compile(r'([\d.,]+\s*[KMGT]?B)')


class TorrentgalaxyScraper(BaseScraper):
    impersonate = "chrome"

    def __init__(self, manager, session):
        super().__init__(manager, session)

    async def scrape(self, request: ScrapeRequest):
        torrents = []
        try:
            encoded = quote(request.title)
            if request.media_type == "series":
                cat = "&c41=1&c42=1"
            else:
                cat = "&c3=1"

            url = f"{BASE_URL}/torrents.php?search={encoded}{cat}&lang=0&nox=2&sort=seeders&order=desc&page=0"

            async with self.session.get(url) as response:
                if response.status != 200:
                    return torrents
                body = await response.text()

            # Split on row starts; first segment is pre-table HTML, skip it
            row_segments = ROW_SPLIT_PATTERN.split(body)[1:]
            for row in row_segments:

                magnet_match = MAGNET_PATTERN.search(row)
                if not magnet_match:
                    continue
                magnet = magnet_match.group(1)

                hash_match = INFO_HASH_PATTERN.search(magnet)
                if not hash_match:
                    continue

                name_match = NAME_PATTERN.search(row)
                name = name_match.group(1).strip() if name_match else ""

                seeders_match = SEEDERS_PATTERN.search(row)
                seeders = int(seeders_match.group(1)) if seeders_match else None

                size = None
                size_match = SIZE_PATTERN.search(row)
                if size_match:
                    size_str = size_match.group(1).strip().replace("iB", "B")
                    try:
                        size = size_to_bytes(size_str)
                    except Exception:
                        size = None

                torrents.append({
                    "title": name,
                    "infoHash": hash_match.group(1).lower(),
                    "fileIndex": None,
                    "seeders": seeders,
                    "size": size,
                    "tracker": "TorrentGalaxy",
                    "sources": extract_trackers_from_magnet(magnet),
                })

        except Exception as e:
            log_scraper_error("Torrentgalaxy", BASE_URL, request.media_id, e)

        return torrents
