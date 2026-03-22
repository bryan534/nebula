# Spanish Scrapers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port 5 scrapers from the Spanish Scraper Stremio Node.js project into Nebula as first-class Python scrapers auto-discovered by the existing scraper manager.

**Architecture:** Each scraper is a Python class extending `BaseScraper` placed in `nebula/scrapers/`. Pelispanda and Hacktorrent share helper functions in `nebula/scrapers/helpers/wpreact_api.py`. All 5 scrapers are enabled/disabled via new `SCRAPE_*` settings in `nebula/core/models.py`. No changes to `manager.py` are needed — auto-discovery handles everything.

**Tech Stack:** Python 3.13, aiohttp (`AsyncClientWrapper`), regex for HTML parsing, existing Nebula utilities (`size_to_bytes`, `extract_trackers_from_magnet`, `log_scraper_error`)

**Spec:** `docs/superpowers/specs/2026-03-22-spanish-scrapers-to-nebula-design.md`

**No test framework exists in this project** — skip TDD, verify by code review and manual inspection.

---

## File Map

| Action | File | Purpose |
|--------|------|---------|
| Create | `nebula/scrapers/helpers/wpreact_api.py` | Shared WordPress REST API helpers for Pelispanda + Hacktorrent |
| Create | `nebula/scrapers/pelispanda.py` | `PelispandaScraper` — pelispanda.org |
| Create | `nebula/scrapers/hacktorrent.py` | `HacktorrentScraper` — hacktorrent.to |
| Create | `nebula/scrapers/leetx.py` | `LeetxScraper` — 1337x.to HTML scraping |
| Create | `nebula/scrapers/torrentgalaxy.py` | `TorrentgalaxyScraper` — torrentgalaxy.to HTML scraping |
| Create | `nebula/scrapers/eztv.py` | `EztvScraper` — eztv.re JSON API |
| Modify | `nebula/core/models.py` | Add 5 `SCRAPE_*` settings |

---

## Task 1: Add settings to `models.py`

This must come first — the manager checks for `SCRAPE_*` settings before instantiating scrapers. Without them, the scrapers are silently skipped.

**Files:**
- Modify: `nebula/core/models.py`

- [ ] **Step 1: Add the 5 settings**

Open `nebula/core/models.py`. Find the block of `SCRAPE_*` settings (around line 159 where `SCRAPE_PEERFLIX` is). Add the 5 new settings **after** `SCRAPE_PEERFLIX`:

```python
SCRAPE_PELISPANDA: Union[bool, str] = False
SCRAPE_HACKTORRENT: Union[bool, str] = False
SCRAPE_LEETX: Union[bool, str] = False
SCRAPE_TORRENTGALAXY: Union[bool, str] = False
SCRAPE_EZTV: Union[bool, str] = False
```

- [ ] **Step 2: Verify the pattern matches existing settings**

Check that these lines are consistent with the existing pattern — `Union[bool, str]`, default `False`, no trailing comma issues. Compare visually with `SCRAPE_TORRENTIO` and `SCRAPE_PEERFLIX` above.

- [ ] **Step 3: Commit**

```bash
git -C "/Users/bryan/ES SCRAPER/Nebula" add nebula/core/models.py
git -C "/Users/bryan/ES SCRAPER/Nebula" commit -m "feat: add SCRAPE_* settings for 5 new scrapers"
```

---

## Task 2: WordPress REST API helper (`wpreact_api.py`)

Shared functions used by both `PelispandaScraper` and `HacktorrentScraper`. These are plain async functions — no class needed.

**Files:**
- Create: `nebula/scrapers/helpers/wpreact_api.py`

- [ ] **Step 1: Create the file**

```python
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
```

- [ ] **Step 2: Verify no import cycles**

The helper imports only from `nebula.utils.network_manager`. It does NOT import from `nebula.scrapers.*` or `nebula.core.models`. This is safe.

- [ ] **Step 3: Commit**

```bash
git -C "/Users/bryan/ES SCRAPER/Nebula" add nebula/scrapers/helpers/wpreact_api.py
git -C "/Users/bryan/ES SCRAPER/Nebula" commit -m "feat: add wpreact_api helper for WordPress REST scraper shared logic"
```

---

## Task 3: Pelispanda scraper

**Files:**
- Create: `nebula/scrapers/pelispanda.py`

- [ ] **Step 1: Create the file**

```python
import asyncio

from nebula.core.logger import log_scraper_error
from nebula.scrapers.base import BaseScraper
from nebula.scrapers.models import ScrapeRequest
from nebula.scrapers.helpers.wpreact_api import search, get_content_type, get_detail, extract_magnets
from nebula.services.torrent_manager import extract_trackers_from_magnet
from nebula.utils.formatting import size_to_bytes

BASE_URL = "https://pelispanda.org/wp-json/wpreact/v1/"


class PelispandaScraper(BaseScraper):
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
                        "tracker": "Pelispanda",
                        "sources": extract_trackers_from_magnet(entry["magnet"]),
                    })
                return results

            all_results = await asyncio.gather(*[fetch_one(s) for s in stubs])
            for batch in all_results:
                torrents.extend(batch)

        except Exception as e:
            log_scraper_error("Pelispanda", BASE_URL, request.media_id, e)

        return torrents
```

- [ ] **Step 2: Cross-check against pattern**

Compare this file against `nebula/scrapers/torrentsdb.py` and `nebula/scrapers/nyaa.py`:
- `__init__` matches (manager, session, no url)
- `scrape` returns a list
- top-level try/except uses `log_scraper_error`
- `ScrapeResult` keys: `title`, `infoHash`, `fileIndex`, `seeders`, `size`, `tracker`, `sources`

- [ ] **Step 3: Commit**

```bash
git -C "/Users/bryan/ES SCRAPER/Nebula" add nebula/scrapers/pelispanda.py
git -C "/Users/bryan/ES SCRAPER/Nebula" commit -m "feat: add PelispandaScraper"
```

---

## Task 4: Hacktorrent scraper

Identical to Pelispanda except `BASE_URL` and tracker name. Do not duplicate logic — both import from `wpreact_api.py`.

**Files:**
- Create: `nebula/scrapers/hacktorrent.py`

- [ ] **Step 1: Create the file**

```python
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
```

- [ ] **Step 2: Commit**

```bash
git -C "/Users/bryan/ES SCRAPER/Nebula" add nebula/scrapers/hacktorrent.py
git -C "/Users/bryan/ES SCRAPER/Nebula" commit -m "feat: add HacktorrentScraper"
```

---

## Task 5: 1337x scraper (`LeetxScraper`)

HTML scraping — two-stage: search page → up to 10 detail pages in parallel.

**Files:**
- Create: `nebula/scrapers/leetx.py`

Reference: `nebula/scrapers/nyaa.py` for the HTML regex + asyncio.gather pattern.

- [ ] **Step 1: Create the file**

```python
import asyncio
import re
from urllib.parse import quote

from nebula.core.logger import log_scraper_error
from nebula.scrapers.base import BaseScraper
from nebula.scrapers.models import ScrapeRequest
from nebula.services.torrent_manager import extract_trackers_from_magnet
from nebula.utils.formatting import size_to_bytes

BASE_URL = "https://1337x.to"

# Matches the second <a> href in each table row's td.name cell
# e.g. href="/torrent/5123456/Movie-Name-1080p/"
SEARCH_ROW_PATTERN = re.compile(
    r'<td class="name">[^<]*<a[^>]*>.*?</a>\s*<a href="(/torrent/[^"]+)"[^>]*>([^<]+)</a>',
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
        size_str = size_match.group(1).strip()
        # Normalize "GiB"/"MiB" → "GB"/"MB" for size_to_bytes compatibility
        size_str = size_str.replace("iB", "B")
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

            # Sanity check — block pages return garbage HTML
            if "1337x</title>" not in body:
                return torrents

            matches = SEARCH_ROW_PATTERN.findall(body)
            candidates = matches[:10]  # first 10, no language pre-filter

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
```

- [ ] **Step 2: Verify regex against source HTML structure**

The source JS (`1337x.js` line 75-80) describes: `td.name` contains two `<a>` tags — the first is a category link, the second is the torrent link. The regex above captures the second `<a>` href and text. Cross-check this matches actual 1337x HTML by reading the JS source again at `/Users/bryan/ES SCRAPER/Spanish Scraper Stremio/lib/1337x.js` lines 69-85.

- [ ] **Step 3: Commit**

```bash
git -C "/Users/bryan/ES SCRAPER/Nebula" add nebula/scrapers/leetx.py
git -C "/Users/bryan/ES SCRAPER/Nebula" commit -m "feat: add LeetxScraper (1337x)"
```

---

## Task 6: TorrentGalaxy scraper

HTML scraping — single page, magnet links embedded directly in search results.

**Files:**
- Create: `nebula/scrapers/torrentgalaxy.py`

- [ ] **Step 1: Create the file**

```python
import re
from urllib.parse import quote

from nebula.core.logger import log_scraper_error
from nebula.scrapers.base import BaseScraper
from nebula.scrapers.models import ScrapeRequest
from nebula.services.torrent_manager import extract_trackers_from_magnet
from nebula.utils.formatting import size_to_bytes

BASE_URL = "https://torrentgalaxy.to"

INFO_HASH_PATTERN = re.compile(r"btih:([a-fA-F0-9]{40}|[a-zA-Z0-9]{32})", re.IGNORECASE)

# Each row: div.tgxtablerow — capture magnet, name, seeders, size
# TGx structure per row (simplified):
#   cell[1]: language flag img title
#   cell[3]: name link
#   cell[7]: size text
#   cell[10]: span > b > font > seeders
ROW_PATTERN = re.compile(
    r'<div class="tgxtablerow[^"]*">(.*?)</div>\s*</div>',
    re.DOTALL,
)
MAGNET_PATTERN = re.compile(r'href="(magnet:[^"]+)"')
NAME_PATTERN = re.compile(r'<div class="tgxtablecell[^"]*">[^<]*(?:<[^>]+>[^<]*){3}<a[^>]*>([^<]+)</a>')
SEEDERS_PATTERN = re.compile(r'<span[^>]*><b><font[^>]*>(\d+)</font></b></span>')
SIZE_PATTERN = re.compile(r'<div class="tgxtablecell[^"]*"[^>]*>\s*([\d.,]+\s*[KMGT]?B)\s*</div>')


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

            for row_match in ROW_PATTERN.finditer(body):
                row = row_match.group(1)

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
```

- [ ] **Step 2: Note on HTML regex fragility**

TorrentGalaxy's HTML structure may change. The regex patterns above are best-effort based on the JS source. If results are empty at runtime, the HTML structure may have shifted — inspect the raw response to update the patterns. This is a known trade-off of HTML scraping without a library.

- [ ] **Step 3: Commit**

```bash
git -C "/Users/bryan/ES SCRAPER/Nebula" add nebula/scrapers/torrentgalaxy.py
git -C "/Users/bryan/ES SCRAPER/Nebula" commit -m "feat: add TorrentgalaxyScraper"
```

---

## Task 7: EZTV scraper

JSON API — cleanest of the five. Series-only.

**Files:**
- Create: `nebula/scrapers/eztv.py`

- [ ] **Step 1: Create the file**

```python
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
            numeric_id = request.media_only_id.lstrip("t")  # "tt1234567" → "1234567"

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

                # Cast season/episode to int — API may return strings or ints
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
```

- [ ] **Step 2: Verify `media_only_id` stripping**

`request.media_only_id` is e.g. `"tt1234567"`. `lstrip("t")` removes all leading `"t"` characters, giving `"1234567"`. Confirm this is correct — `"tt1234567".lstrip("t")` → `"1234567"`. ✓

- [ ] **Step 3: Commit**

```bash
git -C "/Users/bryan/ES SCRAPER/Nebula" add nebula/scrapers/eztv.py
git -C "/Users/bryan/ES SCRAPER/Nebula" commit -m "feat: add EztvScraper"
```

---

## Task 8: Smoke-check manager auto-discovery

Verify all 5 scrapers are discovered without errors.

**Files:** None (read-only verification)

- [ ] **Step 1: Confirm class names derive to correct settings**

For each scraper, trace the manager's naming logic:
`scraper_name.replace("Scraper", "").upper()` → `setting_key = f"SCRAPE_{result}"`

| Class | Clean name | Setting key | Exists in models.py? |
|-------|-----------|-------------|----------------------|
| `PelispandaScraper` | `Pelispanda` | `SCRAPE_PELISPANDA` | ✓ (added in Task 1) |
| `HacktorrentScraper` | `Hacktorrent` | `SCRAPE_HACKTORRENT` | ✓ |
| `LeetxScraper` | `Leetx` | `SCRAPE_LEETX` | ✓ |
| `TorrentgalaxyScraper` | `Torrentgalaxy` | `SCRAPE_TORRENTGALAXY` | ✓ |
| `EztvScraper` | `Eztv` | `SCRAPE_EZTV` | ✓ |

- [ ] **Step 2: Confirm no URL settings — manager uses no-URL branch**

For each scraper, `getattr(settings, "PELISPANDA_URL", None)` returns `None` (setting doesn't exist). Manager falls through to `scraper_class(self, client)` — no `url` argument — which calls `BaseScraper.__init__(manager, session, url=None)`. Each scraper's `__init__` passes through to `super().__init__(manager, session)` without a `url`. Confirmed safe.

- [ ] **Step 3: Verify helpers directory is not mistakenly loaded as a scraper module**

`pkgutil.iter_modules` on `nebula/scrapers/` will enumerate `helpers` as a subpackage. The manager does `importlib.import_module("nebula.scrapers.helpers")` which runs the existing `__init__.py` (empty). The class scan loop finds no `BaseScraper` subclasses in it. This is harmless — confirmed by comparing against how existing helpers (aiostreams, mediafusion, debridio) are already present and the project works.

- [ ] **Step 4: Final commit message**

```bash
git -C "/Users/bryan/ES SCRAPER/Nebula" log --oneline -8
```

Confirm the 7 commits from Tasks 1-7 are present and clean.
