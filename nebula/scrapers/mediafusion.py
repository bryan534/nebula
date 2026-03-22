from nebula.core.logger import log_scraper_error
from nebula.scrapers.base import BaseScraper
from nebula.scrapers.helpers.mediafusion import mediafusion_config
from nebula.scrapers.models import ScrapeRequest


class MediaFusionScraper(BaseScraper):
    def __init__(
        self,
        manager,
        session,
        url: str,
        password: str | None = None,
    ):
        super().__init__(manager, session, url)
        self.password = password

    async def scrape(self, request: ScrapeRequest):
        torrents = []
        try:
            headers = mediafusion_config.get_headers_for_password(self.password)

            async with self.session.get(
                f"{self.url}/stream/{request.media_type}/{request.media_id}.json",
                headers=headers,
            ) as response:
                results = await response.json()

            for torrent in results["streams"]:
                title_full = torrent["description"]
                lines = title_full.split("\n")

                title = lines[0].replace("📂 ", "").replace("/", "")

                seeders = None
                if "👤" in lines[1]:
                    seeders = int(lines[1].split("👤 ")[1].split("\n")[0])

                tracker = lines[-1].split("🔗 ")[1]

                torrents.append(
                    {
                        "title": title,
                        "infoHash": torrent["infoHash"].lower(),
                        "fileIndex": torrent.get("fileIdx", None),
                        "seeders": seeders,
                        "size": torrent["behaviorHints"][
                            "videoSize"
                        ],  # not the pack size but still useful for prowlarr users
                        "tracker": f"MediaFusion|{tracker}",
                        "sources": torrent.get("sources", []),
                    }
                )
        except Exception as e:
            log_scraper_error("MediaFusion", self.url, request.media_id, e)

        return torrents
