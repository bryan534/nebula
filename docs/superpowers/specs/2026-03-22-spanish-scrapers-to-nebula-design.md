# Design: Port Spanish Scraper Stremio → Nebula

**Date:** 2026-03-22
**Status:** Approved

## Background

Two projects exist under `/Users/bryan/ES SCRAPER/`:
- **Nebula** — Python Stremio addon with 20+ scrapers, `BaseScraper` ABC, dynamic auto-discovery
- **Spanish Scraper Stremio** — Node.js addon with 6 scrapers focused on Spanish content + TorBox

Goal: port the 5 unique scrapers from the Node.js project into Nebula as first-class Python scrapers.

## Scrapers to Port

| Source | Node.js file | Nebula class | Nebula file |
|--------|-------------|-------------|-------------|
| pelispanda.org WordPress REST API | `lib/scraper.js` | `PelispandaScraper` | `nebula/scrapers/pelispanda.py` |
| hacktorrent.to WordPress REST API | `lib/scraper.js` | `HacktorrentScraper` | `nebula/scrapers/hacktorrent.py` |
| 1337x.to HTML scraping | `lib/1337x.js` | `LeetxScraper` | `nebula/scrapers/leetx.py` |
| torrentgalaxy.to HTML scraping | `lib/torrentgalaxy.js` | `TorrentgalaxyScraper` | `nebula/scrapers/torrentgalaxy.py` |
| eztv.re JSON API | `lib/eztv.js` | `EztvScraper` | `nebula/scrapers/eztv.py` |

Torrentio already exists in Nebula — not ported.

## Key Design Decisions

- **No language filtering** — the source Node.js code filters for Spanish keywords; do NOT port that filter. Return all results; Nebula's RTN ranking handles language preference.
- **No new dependencies** — HTML parsing with regex (same pattern as `nebula/scrapers/nyaa.py`)
- **No URL settings** — fixed public sites; scrapers use hardcoded `BASE_URL` constants
- **Shared helper** — `nebula/scrapers/helpers/wpreact_api.py` for WordPress REST API logic shared by Pelispanda and Hacktorrent. The `helpers/` subdirectory already has an `__init__.py` — do not create a new one. The manager's `pkgutil.iter_modules` will encounter `helpers` as a package name, import `nebula.scrapers.helpers` (runs its empty `__init__.py`), find no `BaseScraper` subclasses, and move on — this is harmless and consistent with how the existing helpers work.
- **Manager compatibility** — no changes to `manager.py` needed. The 5 `SCRAPE_*` settings added to `models.py` make scrapers discoverable. Since no `{NAME}_URL` setting exists, the manager instantiates each scraper via `scraper_class(self, client)` (url=None); scrapers fall back to their hardcoded `BASE_URL`.
- **Tracker field values**: `"Pelispanda"`, `"Hacktorrent"`, `"1337x"`, `"TorrentGalaxy"`, `"EZTV"` respectively.
- **Size parsing**: wrap all `size_to_bytes()` calls in try/except; return `None` on failure. The sites return sizes like `"1.4 GB"` or `"720 MB"` — `size_to_bytes()` handles these directly (it lowercases the unit and compares against `["b", "kb", "mb", "gb", "tb"]`). If a value like `"1.4 GiB"` appears, normalization (`str.replace("iB", "B")`) is required before calling, same as Nyaa.
- **Non-magnet download links**: skip any download entry where `download_link` does not start with `"magnet:"` or where the info hash regex finds no match.
- **Session type**: all helper functions that accept a `session` parameter receive `AsyncClientWrapper` (from `nebula.utils.network_manager`), used as `async with session.get(url) as response`.
- **URL encoding**: use `urllib.parse.quote(title)` or pass as an `aiohttp` query param (which encodes automatically) for all search queries.

## Architecture

### New Files

```
nebula/scrapers/pelispanda.py           # PelispandaScraper
nebula/scrapers/hacktorrent.py          # HacktorrentScraper
nebula/scrapers/leetx.py               # LeetxScraper (1337x)
nebula/scrapers/torrentgalaxy.py        # TorrentgalaxyScraper
nebula/scrapers/eztv.py                # EztvScraper
nebula/scrapers/helpers/wpreact_api.py  # Shared WordPress REST API helpers
```

### Modified Files

```
nebula/core/models.py    # 5 new SCRAPE_* settings
```

### Settings Added to `models.py`

```python
SCRAPE_PELISPANDA: Union[bool, str] = False
SCRAPE_HACKTORRENT: Union[bool, str] = False
SCRAPE_LEETX: Union[bool, str] = False
SCRAPE_TORRENTGALAXY: Union[bool, str] = False
SCRAPE_EZTV: Union[bool, str] = False
```

## Data Flow Per Scraper

### Pelispanda & Hacktorrent

Both use the identical WordPress REST API (`/wp-json/wpreact/v1/`) at different base URLs:
- Pelispanda: `https://pelispanda.org/wp-json/wpreact/v1/`
- Hacktorrent: `https://hacktorrent.to/wp-json/wpreact/v1/`

**Flow:**
1. `GET {base_url}search?query={request.title}` → JSON array of result stubs
2. Each stub has a `type` field. Map to the **singular** API endpoint string (used directly in the URL path):
   - `type` contains `"serie"` → `"serie"`
   - `type` contains `"anime"` → `"anime"`
   - otherwise → `"movie"`
3. For each stub, parallel `asyncio.gather`: `GET {base_url}{endpoint}/{slug}` → detail dict with `downloads[]`
4. For each entry in `downloads[]`:
   - Skip if `download_link` does not start with `"magnet:"`
   - Extract info hash via regex `btih:([a-fA-F0-9]{40}|[a-zA-Z0-9]{32})` — skip if no match
   - Parse `size` field (e.g. `"1.4 GB"`) via `size_to_bytes()`; wrap in try/except, use `None` on failure
   - Build `ScrapeResult` with `tracker="Pelispanda"` or `"Hacktorrent"` as appropriate
5. Return all results (do not port the source's `isSpanish()` filter)

**`helpers/wpreact_api.py` interface:**
- `async def search(session: AsyncClientWrapper, base_url: str, query: str) -> list` — returns raw stub list
- `def get_content_type(item_type: str) -> str` — returns singular endpoint string (`"movie"`, `"serie"`, or `"anime"`)
- `async def get_detail(session: AsyncClientWrapper, base_url: str, content_type: str, slug: str) -> dict` — returns raw detail dict
- `def extract_magnets(detail: dict) -> list[dict]` — returns list of `{infoHash, title, size, magnet}` dicts with non-magnet entries already filtered out. `title` is `f"{detail['title']} {dl.get('quality', '')}".strip()` — combines the top-level title with the per-download quality string (e.g. `"Movie Title WEB-DL 1080p"`). `size` is the raw `dl["size"]` string passed to `size_to_bytes()` by the caller.

### 1337x (`LeetxScraper`)

Base URL: `https://1337x.to`

**Flow:**
1. Build search URL (URL-encode `request.title`):
   - Movies: `GET /search/{encoded_title}/1/`
   - Series: `GET /category-search/{encoded_title}/TV/1/`
2. Validate response body contains `"1337x</title>"` — raise/return `[]` if not (proxy/block detection, same as source)
3. Parse HTML with regex to extract rows from `.table-list > tbody > tr`:
   - Capture the second `<a>` href in `td.name` → this is the full path like `/torrent/12345/movie-name/`
   - Capture link text → torrent name
   - Capture `td.seeds` text → seeders (int)
4. Take the **first 10 rows** (no pre-filtering — do not port `SPANISH_KEYWORDS` name filter)
5. For those 10, parallel `asyncio.gather`: `GET {BASE_URL}{href}` (use the full href path from step 3 directly)
6. Parse detail page HTML:
   - Magnet link: find `<a>` containing `"Magnet Download"` → extract `href`
   - Skip result if no magnet link found
   - Info hash: regex `btih:([a-fA-F0-9]{40}|[a-zA-Z0-9]{32})` on magnet
   - Seeders: text after `<strong>` containing `"Seeders"`
   - Size: text after `<strong>` containing `"Total size"` — parse via `size_to_bytes()` with try/except
7. `tracker = "1337x"`; `sources = extract_trackers_from_magnet(magnet)`
8. `impersonate = "chrome"`

### TorrentGalaxy

Base URL: `https://torrentgalaxy.to`

**Flow:**
1. Build search URL (URL-encode `request.title`):
   - Movies: `GET /torrents.php?search={title}&c3=1&lang=0&nox=2&sort=seeders&order=desc&page=0`
   - Series: `GET /torrents.php?search={title}&c41=1&c42=1&lang=0&nox=2&sort=seeders&order=desc&page=0`
   - (`lang=0` = all languages, `nox=2` = exclude XXX, `page=0` = first page)
2. Parse HTML with regex to extract rows from `div.tgxtablerow`:
   - Magnet link: find `href` starting with `"magnet:"` → extract directly (TGx embeds magnets in search results, no detail page needed)
   - Skip row if no magnet found
   - Info hash: regex `btih:([a-fA-F0-9]{40}|[a-zA-Z0-9]{32})` on magnet — skip if no match
   - Name: text of first `<a>` in the 4th `div.tgxtablecell` (0-indexed: cell index 3)
   - Seeders: text of the innermost `<font>` element inside `<b>` inside `<span>` in cell index 10 (structure: `span > b > font > NUMBER`)
   - Size: text of cell index 7 — parse via `size_to_bytes()` with try/except
3. Return all results (do not port `SPANISH_KEYWORDS` filter)
4. `tracker = "TorrentGalaxy"`; `sources = extract_trackers_from_magnet(magnet)`
5. `impersonate = "chrome"`

### EZTV

Base URL: `https://eztv.re/api`

**Flow:**
1. If `request.media_type == "movie"` → return `[]` immediately (TV-only tracker)
2. Strip `"tt"` prefix from `request.media_only_id` → numeric IMDB ID string
3. `GET {BASE_URL}/get-torrents?imdb_id={numeric_id}&limit=100&page=1` → JSON
4. Iterate `data["torrents"]` (empty list if key missing):
   - Skip entries where `hash` or `magnet_url` is missing/falsy
   - Cast `t["season"]` and `t["episode"]` to `int` before comparing (API returns them as strings or ints depending on version — always cast)
   - Filter: if `request.season is not None`, keep only entries where `int(t.get("season", 0)) == request.season`
   - Filter: if `request.episode is not None`, additionally keep only entries where `int(t.get("episode", 0)) == request.episode`
   - If both are `None`, return all entries
5. For each kept entry:
   - `infoHash = t["hash"].lower()`
   - `size = int(t["size_bytes"])` if present and truthy, else `None` — no `size_to_bytes()` needed
   - `sources = extract_trackers_from_magnet(t["magnet_url"])`
   - `title = t.get("title") or t.get("filename") or ""`
6. `tracker = "EZTV"`; `impersonate = None` (JSON API, no browser fingerprinting needed)

## Nebula Pattern Compliance

All scrapers follow Nebula conventions exactly:
- Extend `BaseScraper`, implement `async def scrape(self, request: ScrapeRequest) -> list`
- `__init__(self, manager, session)` — no `url` parameter (no URL setting; uses hardcoded `BASE_URL`)
- Use `async with self.session.get(url) as response` for HTTP calls
- Top-level try/except in `scrape()` with `log_scraper_error(name, BASE_URL, request.media_id, e)`
- Size via `nebula.utils.formatting.size_to_bytes()` wrapped in try/except → `None` on failure
- Tracker sources via `nebula.services.torrent_manager.extract_trackers_from_magnet()`
- `impersonate = "chrome"` on HTML scrapers (Leetx, TorrentGalaxy); `None` on JSON/REST scrapers (Pelispanda, Hacktorrent, EZTV)
- Settings follow `SCRAPE_{NAME}: Union[bool, str] = False` pattern
