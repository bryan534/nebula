from nebula.core.logger import log_scraper_error
from nebula.scrapers.base import BaseScraper
from nebula.scrapers.models import ScrapeRequest
from nebula.services.torrent_manager import extract_trackers_from_magnet

BASE_URL = "https://eztv.re/api"


class EztvScraper(BaseScraper):
    impersonate = None

    def __init__(self, manager, session):
        super().__init__(manager, session)

    async def scrape(self, request: ScrapeRequest):
        if request.media_type == "movie":
            return []

        torrents = []
        try:
            numeric_id = request.media_only_id.removeprefix("tt")  # "tt1234567" → "1234567"

            async with self.session.get(
                f"{BASE_URL}/get-torrents",
                params={"imdb_id": numeric_id, "limit": 100, "page": 1},
            ) as response:
                if response.status != 200:
                    return torrents
                data = await response.json()

            for t in data.get("torrents", []):
                if not t.get("hash") or not t.get("magnet_url"):
                    continue

                try:
                    t_season = int(t["season"]) if t.get("season") else None
                except (ValueError, TypeError):
                    t_season = None
                try:
                    t_episode = int(t["episode"]) if t.get("episode") else None
                except (ValueError, TypeError):
                    t_episode = None

                if request.season is not None and t_season != request.season:
                    continue
                if request.episode is not None and t_episode != request.episode:
                    continue

                size_bytes = t.get("size_bytes")
                size = int(size_bytes) if size_bytes else None

                torrents.append({
                    "title": t.get("title") or t.get("filename") or "",
                    "infoHash": t["hash"].lower(),
                    "fileIndex": None,
                    "seeders": t.get("seeds") or None,
                    "size": size,
                    "tracker": "EZTV",
                    "sources": extract_trackers_from_magnet(t["magnet_url"]),
                })

        except Exception as e:
            log_scraper_error("Eztv", BASE_URL, request.media_id, e)

        return torrents
