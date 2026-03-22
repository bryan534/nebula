import asyncio

from nebula.core.logger import log_scraper_error
from nebula.scrapers.base import BaseScraper
from nebula.scrapers.models import ScrapeRequest
from nebula.scrapers.helpers.wpreact_api import search, get_content_type, get_detail, extract_magnets
from nebula.services.torrent_manager import extract_trackers_from_magnet
from nebula.utils.formatting import size_to_bytes

BASE_URL = "https://hacktorrent.to/wp-json/wpreact/v1/"


class HacktorrentScraper(BaseScraper):
    impersonate = None

    def __init__(self, manager, session):
        super().__init__(manager, session)

    async def scrape(self, request: ScrapeRequest):
        torrents = []
        try:
            stubs = await search(self.session, BASE_URL, request.title)
            if not stubs:
                return torrents

            async def fetch_one(stub):
                content_type = get_content_type(stub.get("type", ""))
                slug = stub.get("slug", "")
                if not slug:
                    return []
                try:
                    detail = await get_detail(self.session, BASE_URL, content_type, slug)
                except Exception:
                    return []
                results = []
                for entry in extract_magnets(detail):
                    try:
                        size = size_to_bytes(entry["size_str"]) if entry["size_str"] else None
                    except Exception:
                        size = None
                    results.append({
                        "title": entry["title"],
                        "infoHash": entry["infoHash"],
                        "fileIndex": None,
                        "seeders": None,
                        "size": size,
                        "tracker": "Hacktorrent",
                        "sources": extract_trackers_from_magnet(entry["magnet"]),
                    })
                return results

            all_results = await asyncio.gather(*[fetch_one(s) for s in stubs])
            for batch in all_results:
                torrents.extend(batch)

        except Exception as e:
            log_scraper_error("Hacktorrent", BASE_URL, request.media_id, e)

        return torrents
