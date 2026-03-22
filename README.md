<h1 align="center" id="title">☄️ Nebula</h1>

<p align="center">
  <a href="https://discord.com/invite/UJEqpT42nb"><img src="https://img.shields.io/badge/Discord-Join%20Us-5865F2?style=flat-square&logo=discord&logoColor=white" /></a>
  <a href="https://stremio-addons.net/addons/nebula"><img src="https://img.shields.io/badge/Stremio-Addon-7B3FE4?style=flat-square&logo=stremio&logoColor=white" /></a>
  <a href="kodi/README.md"><img src="https://img.shields.io/badge/Kodi-Addon-17B2E7?style=flat-square&logo=kodi&logoColor=white" /></a>
</p>

<p align="center"><img src="https://socialify.git.ci/g0ldyy/nebula/image?description=1&font=Inter&forks=1&language=1&name=1&owner=1&pattern=Solid&stargazers=1&theme=Dark" /></p>

# Features
- **NebulaNet**: Decentralized P2P network for automatic torrent metadata sharing ([documentation](docs/nebulanet/README.md))
- **Kodi Support**: Dedicated official add-on with automatic updates ([documentation](kodi/README.md))
- Proxy Debrid Streams to allow simultaneous use on multiple IPs!
- IP-Based Max Connection Limit
- Administration Dashboard with Bandwidth Manager, Metrics and more...
- Supported Scrapers: Jackett, Prowlarr, Torrentio, Zilean, MediaFusion, Debridio, StremThru, AIOStreams, Nebula, Jackettio, TorBox, Nyaa, BitMagnet, TorrentsDB, Peerflix, DMM and SeaDex
- Caching system ft. SQLite / PostgreSQL
- Blazing Fast Background Scraper
- Debrid Account Scraper: Scrape torrents directly from your debrid account library
- [DMM](https://github.com/debridmediamanager/hashlists) Ingester: Automatically download and index Debrid Media Manager hashlists
- Smart Torrent Ranking powered by [TPR](https://github.com/g0ldyy/torrent-parse-rank)
- Proxy support to bypass debrid restrictions
- Real-Debrid, All-Debrid, Premiumize, TorBox, Debrid-Link, Debrider, EasyDebrid, OffCloud and PikPak supported
- Direct Torrent supported
- [Kitsu](https://kitsu.io/) support (anime)
- Adult Content Filter
- ChillLink Protocol support

# Installation
To customize your Nebula experience to suit your needs, please first take a look at all the [environment variables](https://github.com/g0ldyy/nebula/blob/main/.env-sample)!

## Self Hosted
### From source (developers)
- Clone the repository and enter the folder
    ```sh
    git clone https://github.com/g0ldyy/nebula
    cd nebula
    ```
- Install dependencies
    ```sh
    pip install uv
    uv sync
    ````
- Start Nebula
    ```sh
    uv run python -m nebula.main
    ````

### Docker / production-style setup

Use the dedicated documentation:

- Beginner step-by-step: [docs/beginner/01-get-started-docker.md](docs/beginner/01-get-started-docker.md)
- Full documentation index: [docs/README.md](docs/README.md)

# NebulaNet (P2P Network)
Nebula transforms your Nebula instance from an isolated scraper into a participant in a collaborative network. Instead of each instance independently discovering the same torrents, NebulaNet allows instances to share their discovered **metadata** (hashes, titles, etc.) with each other in a decentralized way. **No actual files are shared.**

Key benefits:
- **Improved Coverage**: Receive torrent metadata discovered by other nodes.
- **Reduced Load**: Less redundant scraping across the network.
- **Trust Pools**: Optional closed groups for trusted metadata sharing.

For more information on how to setup and configure NebulaNet, please refer to the [NebulaNet Documentation](docs/nebulanet/README.md).

## Support the Project
Nebula is a community-driven project, and your support helps it grow! 🚀

- ❤️ **Donate** via [GitHub Sponsors](https://github.com/sponsors/g0ldyy) or [Ko-fi](https://ko-fi.com/g0ldyy) to support development
- ⭐ **Star the repository** here on GitHub
- ⭐ **Star the add-on** on [stremio-addons.net](https://stremio-addons.net/addons/nebula)
- 🐛 **Contribute** by reporting issues, suggesting features, or submitting PRs

## Web UI Showcase
<img src="https://i.imgur.com/7xY5AEi.png" />
<img src="https://i.imgur.com/Dzs4wax.png" />
<img src="https://i.imgur.com/L3RkfO8.jpeg" />
