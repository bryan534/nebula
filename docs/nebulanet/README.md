# NebulaNet Documentation

Welcome to the NebulaNet documentation. NebulaNet is a decentralized peer-to-peer network integrated into Nebula that automatically shares torrent metadata between instances.

For the full non-NebulaNet project documentation, see [`docs/README.md`](../README.md).

## Documentation

| Document | Description |
|----------|-------------|
| [Quick Start](quickstart.md) | Get NebulaNet running in 5 minutes |
| [Full Documentation](nebulanet.md) | Complete reference with all settings and features |
| [Docker Deployment](docker.md) | Docker-specific configurations and examples |

## Overview

NebulaNet enables Nebula instances to share discovered torrent **metadata** with each other automatically. When your instance finds a new torrent, its **metadata** (hash, title, size) is propagated to other nodes in the network - and you receive metadata discovered by others. No actual files are shared.

### Key Features

- **Peer-to-peer**: No central server, fully distributed
- **Cryptographically signed**: All contributions are verified
- **Trust Pools**: Create private communities of trusted contributors
- **Contribution modes**: Control what you share and receive
- **Reputation system**: Bad actors are automatically filtered

## Need Help?

- Check the [Troubleshooting](nebulanet.md#troubleshooting) section
- Join the [Nebula Discord](https://discord.com/invite/UJEqpT42nb)
