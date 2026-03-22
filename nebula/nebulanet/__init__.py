"""
NebulaNet - Decentralized P2P Network for Nebula Instances

This package implements a gossip-based P2P network that allows Nebula instances
to share torrent metadata automatically across the network.
"""

from typing import Optional

from nebula.nebulanet.interface import NebulaNetBackend
from nebula.nebulanet.manager import NebulaNetService, get_nebulanet_service
from nebula.nebulanet.relay import NebulaNetRelay, get_relay

__all__ = ["NebulaNetService", "NebulaNetRelay", "NebulaNetBackend", "get_active_backend"]


def get_active_backend() -> Optional[NebulaNetBackend]:
    """
    Get the active NebulaNet backend (either local service or relay).
    Returns the backend instance if running, otherwise None.
    """
    # Try local service first
    service = get_nebulanet_service()
    if service and service.running:
        return service

    # Fall back to relay
    relay = get_relay()
    if relay and relay.running:
        return relay

    return None
