import asyncio
import time
from contextlib import asynccontextmanager

import aiohttp
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from nebula.api.endpoints import (admin, base, chilllink, nebulanet, nebulanet_ui,
                                 config, debrid_sync, kodi, manifest, playback)
from nebula.api.endpoints import stream as streams_router
from nebula.background_scraper.worker import background_scraper
from nebula.nebulanet.manager import init_nebulanet_service
from nebula.nebulanet.relay import init_relay, stop_relay
from nebula.core.database import (cleanup_expired_kodi_setup_codes,
                                 cleanup_expired_locks, setup_database,
                                 teardown_database)
from nebula.core.execution import setup_executor, shutdown_executor
from nebula.core.logger import logger
from nebula.core.models import STREMIO_API_PREFIX, settings
from nebula.services.anime import anime_mapper
from nebula.services.bandwidth import bandwidth_monitor
from nebula.services.dmm_ingester import dmm_ingester
from nebula.services.indexer_manager import indexer_manager
from nebula.services.torrent_manager import (add_torrent_queue,
                                            check_torrents_exist,
                                            torrent_update_queue)
from nebula.services.trackers import download_best_trackers
from nebula.utils.http_client import http_client_manager
from nebula.utils.memory import periodic_memory_trim
from nebula.utils.network_manager import network_manager


class LoguruMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        try:
            response = await call_next(request)
        except Exception as e:
            logger.exception(f"Exception during request processing: {e}")
            raise
        finally:
            process_time = time.time() - start_time
            logger.log(
                "API",
                f"{request.method} {request.url.path} - {response.status_code if 'response' in locals() else '500'} - {process_time:.2f}s",
            )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    # loop = asyncio.get_running_loop()
    # loop.set_debug(True)

    await setup_database()
    setup_executor()
    await http_client_manager.init()

    if settings.DOWNLOAD_GENERIC_TRACKERS:
        await download_best_trackers()

    # Load anime ID mapping for enhanced metadata and anime detection
    async with aiohttp.ClientSession() as session:
        await anime_mapper.load_anime_mapping(session)

    # Initialize bandwidth monitoring system
    if settings.PROXY_DEBRID_STREAM:
        await bandwidth_monitor.initialize()

    # Start background cleanup tasks
    cleanup_locks_task = asyncio.create_task(cleanup_expired_locks())
    cleanup_kodi_task = asyncio.create_task(cleanup_expired_kodi_setup_codes())
    memory_trim_task = None
    memory_trim_interval = settings.MEMORY_TRIM_INTERVAL
    if memory_trim_interval > 0:
        memory_trim_task = asyncio.create_task(
            periodic_memory_trim(memory_trim_interval)
        )

    # Start background scraper if enabled
    if settings.BACKGROUND_SCRAPER_ENABLED:
        background_scraper.clear_finished_task()
        if not background_scraper.task:
            background_scraper.task = asyncio.create_task(background_scraper.start())

    # Start DMM Ingester if enabled
    dmm_ingester_task = None
    if settings.DMM_INGEST_ENABLED:
        dmm_ingester_task = asyncio.create_task(dmm_ingester.start())

    # Initialize NebulaNet
    nebulanet_service = None
    nebulanet_relay = None

    if settings.NEBULANET_RELAY_URL:
        nebulanet_relay = await init_relay(
            settings.NEBULANET_RELAY_URL, api_key=settings.NEBULANET_API_KEY
        )

    elif settings.NEBULANET_ENABLED:
        nebulanet_service = init_nebulanet_service(
            enabled=True,
            listen_port=settings.NEBULANET_LISTEN_PORT,
            bootstrap_nodes=settings.NEBULANET_BOOTSTRAP_NODES,
            manual_peers=settings.NEBULANET_MANUAL_PEERS,
            max_peers=settings.NEBULANET_MAX_PEERS,
            min_peers=settings.NEBULANET_MIN_PEERS,
        )

        # Set callback to save torrents received from the network
        nebulanet_service.set_save_torrent_callback(
            torrent_update_queue.add_network_torrent
        )
        nebulanet_service.set_check_torrents_exist_callback(check_torrents_exist)
        await nebulanet_service.start()

    # Start indexer manager
    indexer_manager_task = asyncio.create_task(indexer_manager.run())

    try:
        yield
    finally:
        indexer_manager_task.cancel()
        try:
            await indexer_manager_task
        except asyncio.CancelledError:
            pass
        await indexer_manager.close()

        if background_scraper.task:
            await background_scraper.stop()

        if dmm_ingester_task:
            await dmm_ingester.stop()
            dmm_ingester_task.cancel()
            try:
                await dmm_ingester_task
            except asyncio.CancelledError:
                pass

        cleanup_locks_task.cancel()
        cleanup_kodi_task.cancel()
        if memory_trim_task:
            memory_trim_task.cancel()
        try:
            await cleanup_locks_task
        except asyncio.CancelledError:
            pass
        try:
            await cleanup_kodi_task
        except asyncio.CancelledError:
            pass
        if memory_trim_task:
            try:
                await memory_trim_task
            except asyncio.CancelledError:
                pass

        if settings.PROXY_DEBRID_STREAM:
            await bandwidth_monitor.shutdown()

        if nebulanet_service:
            await nebulanet_service.stop()

        if nebulanet_relay:
            await stop_relay()

        await add_torrent_queue.stop()
        await torrent_update_queue.stop()

        await network_manager.close_all()
        await http_client_manager.close()

        await teardown_database()
        shutdown_executor()


tags_metadata = [
    {
        "name": "General",
        "description": "General application endpoints.",
    },
    {
        "name": "Configuration",
        "description": "Endpoints for configuring Nebula.",
    },
    {
        "name": "Stremio",
        "description": "Standard Stremio endpoints.",
    },
    {
        "name": "Kodi",
        "description": "Kodi specific endpoints.",
    },
    {
        "name": "ChillLink",
        "description": "Chillio specific endpoints.",
    },
    {
        "name": "Admin",
        "description": "Admin dashboard and API endpoints.",
    },
]

app = FastAPI(
    title="Nebula",
    summary="Stremio's fastest torrent/debrid search add-on.",
    lifespan=lifespan,
    docs_url=None if STREMIO_API_PREFIX else "/docs",
    openapi_url=None if STREMIO_API_PREFIX else "/openapi.json",
    redoc_url=None,
    openapi_tags=tags_metadata,
)


app.add_middleware(LoguruMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="nebula/templates"), name="static")

app.include_router(base.router)
app.include_router(config.router)
app.include_router(admin.router)
app.include_router(nebulanet.router)
app.include_router(nebulanet_ui.router)
app.include_router(kodi.router)

if STREMIO_API_PREFIX:
    app.include_router(config.router, prefix=STREMIO_API_PREFIX)

stremio_routers = (
    manifest.router,
    playback.router,
    debrid_sync.router,
    streams_router.streams,
    chilllink.router,
)

for stremio_router in stremio_routers:
    app.include_router(stremio_router, prefix=STREMIO_API_PREFIX)
