# NebulaNet Documentation

NebulaNet is a decentralized peer-to-peer network built into Nebula that enables automatic sharing of torrent metadata between instances. When you discover a torrent on your instance, it can be propagated to other nodes in the network and vice versa - dramatically improving content coverage for all participants.

This documentation covers everything you need to set up and configure NebulaNet for your deployment.

---

## Table of Contents

1. [Overview](#overview)
2. [How It Works](#how-it-works)
3. [Deployment Modes](#deployment-modes)
   - [Integrated Mode](#integrated-mode)
   - [Relay Mode](#relay-mode)
4. [Quick Start](quickstart.md)
5. [Configuration Reference](#configuration-reference)
   - [Core Settings](#core-settings)
   - [Network Discovery](#network-discovery)
   - [Peer Management](#peer-management)
   - [Identity & Security](#identity--security)
   - [Contribution Modes](#contribution-modes)
   - [Trust Pools](#trust-pools)
   - [Private Networks](#private-networks)
   - [Advanced Tuning](#advanced-tuning)
6. [Trust Pools](#trust-pools-1)
   - [Creating a Pool](#creating-a-pool)
   - [Joining a Pool](#joining-a-pool)
   - [Managing Members](#managing-members)
7. [Network Architecture](#network-architecture)
8. [Security Considerations](#security-considerations)
9. [Troubleshooting](#troubleshooting)

---

## Overview

NebulaNet transforms your Nebula instance from an isolated scraper into a participant in a collaborative network. Instead of each instance independently discovering the same torrents, NebulaNet allows instances to share their discoveries with each other.

**Key Benefits:**

- **Improved Coverage**: Receive torrents discovered by other nodes, even from sources you don't scrape directly.
- **Reduced Load**: Less redundant scraping across the network since discoveries are shared.
- **Faster Updates**: New releases propagate quickly through the network.
- **Community Trust**: Trust Pools allow you to create closed groups with trusted contributors.

**Important Notes:**

- NebulaNet is an **experimental feature** and may have bugs or breaking changes.
- **Metadata Only**: NebulaNet shares **only metadata** (titles, infohashes, file sizes). It **never** transmits actual video files, copyrighted content, or `.torrent` files. Running a node does not involve hosting or distributing copyrighted material.
- All propagated data is cryptographically signed to ensure authenticity.

---

## How It Works

NebulaNet uses a gossip-based protocol to propagate torrent metadata across the network:

1. **Discovery**: When your Nebula instance discovers a new torrent (from any scraper), it is signed with your node's private key.

2. **Gossip**: The signed torrent is sent to a random subset of your connected peers (fanout).

3. **Propagation**: Each peer validates the signature, stores the torrent, and forwards it to their own peers.

4. **Deduplication**: Messages are deduplicated to prevent flooding - each torrent announcement is only processed once.

5. **Reputation**: Nodes build reputation based on the quality of their contributions. Bad actors are automatically deprioritized.

The network uses WebSocket connections for peer-to-peer communication, with optional encryption via `wss://` (TLS).

---

## Deployment Modes

NebulaNet offers two deployment modes to fit different infrastructure setups.

### Integrated Mode

**Best for**: Simple setups with a single Nebula instance.

In Integrated Mode, NebulaNet runs directly within your Nebula process. This is the simplest setup but has a limitation: it only works with a single worker (`FASTAPI_WORKERS=1`) because multiple workers cannot share the same P2P port.

**Configuration:**
```env
NEBULANET_ENABLED=True
FASTAPI_WORKERS=1
```

### Relay Mode

**Best for**: Production deployments with multiple workers or replicas.

In Relay Mode, you run a standalone NebulaNet service (a separate process) alongside your Nebula instances. This service handles all P2P networking and writes discovered torrents directly to your shared database.

**Bidirectional Flow:**
1. **Sending:** Nebula workers send their discoveries to the standalone service via HTTP.
2. **Receiving:** The standalone service receives torrents from the P2P network and writes them to the database, making them immediately available to all workers.

**Configuration on Nebula instances:**
```env
NEBULANET_RELAY_URL=http://nebulanet:8766
```

When `NEBULANET_RELAY_URL` is set, the `NEBULANET_ENABLED` setting is ignored - Nebula will use the relay instead.

**Running the standalone service:**
The standalone service requires access to your database environment variables (`DATABASE_URL`, etc.) to save received torrents.
```bash
uv run python -m nebula.nebulanet.standalone
```

The standalone service exposes:
- **WebSocket port** (default `8765`) for P2P connections
- **HTTP port** (default `8766`) for the relay API

---

## Configuration Reference

### Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `NEBULANET_ENABLED` | `False` | Enable Integrated Mode. Set to `True` for single-instance deployments. |
| `NEBULANET_LISTEN_PORT` | `8765` | WebSocket port for incoming P2P connections. |
| `NEBULANET_HTTP_PORT` | `8766` | HTTP API port (standalone service only). |
| `NEBULANET_RELAY_URL` | *(empty)* | URL of standalone NebulaNet service. When set, Integrated Mode is disabled. |
| `NEBULANET_API_KEY` | *(auto)* | Mandatory API key for standalone service authentication. If not provided, a random key is generated. |

### Network Discovery

NebulaNet uses two methods to find peers:

| Variable | Default | Description |
|----------|---------|-------------|
| `NEBULANET_BOOTSTRAP_NODES` | `[]` | JSON array of public entry points. Format: `'["wss://node1:8765", "wss://node2:8765"]'` |
| `NEBULANET_MANUAL_PEERS` | `[]` | JSON array of trusted peers to always connect to. Format: `'["ws://friend:8765"]'` |

**Bootstrap Nodes** are public servers that help new nodes discover peers. They're optional but recommended if you don't have manual peers configured.

**Manual Peers** are nodes you explicitly trust and want to stay connected to. They're prioritized over discovered peers.

### Peer Management

| Variable | Default | Description |
|----------|---------|-------------|
| `NEBULANET_MAX_PEERS` | `50` | Maximum simultaneous connections. More peers = more bandwidth. |
| `NEBULANET_MIN_PEERS` | `3` | Minimum desired peers. NebulaNet actively discovers if below this. |

### Identity & Security

| Variable | Default | Description |
|----------|---------|-------------|
| `NEBULANET_KEYS_DIR` | `data/nebulanet` | Directory to store your node's identity keys. |
| `NEBULANET_ADVERTISE_URL` | *(empty)* | **Required if behind a reverse proxy.** Your public WebSocket URL (e.g., `wss://nebula.example.com/nebulanet/ws`). |
| `NEBULANET_NODE_ALIAS` | *(empty)* | Optional friendly name for your node. Shared with peers for identification. |
| `NEBULANET_KEY_PASSWORD` | *(empty)* | Optional password to encrypt your private key on disk. |

**Identity Persistence:**

NebulaNet generates a unique Ed25519 keypair when first started. This keypair:
- Identifies your node on the network (your node ID is derived from your public key)
- Signs all your contributions (other nodes verify your signatures)
- Is stored in `NEBULANET_KEYS_DIR`

If you lose your keys, you'll appear as a new node and lose any built-up reputation.

### Contribution Modes

Control what your node shares and receives:

| Mode | Shares Own Torrents | Receives | Repropagates | Use Case |
|------|---------------------|----------|--------------|----------|
| `full` | Yes | Yes | Yes | Default. Full network participation. |
| `consumer` | No | Yes | Yes | Receive and help propagate, but don't share your discoveries. |
| `source` | Yes | No | No | Dedicated scraper that only contributes. |
| `leech` | No | Yes | No | Selfish mode. Receives but doesn't help the network. |

**Configuration:**
```env
NEBULANET_CONTRIBUTION_MODE=full
```

> **Note**: Contribution modes apply globally to **all** network traffic, including Trust Pools. For example, if you are in `consumer` mode, you will not share your own discoveries even to pools you are a member of. If you are in `source` mode, you will not save torrents even from your trusted pools.

### Trust Pools

Trust Pools allow you to create private groups where only members can contribute torrents.

> **Note**: **Trust Pools are optional.** By default, NebulaNet runs in "Open Mode", allowing you to receive metadata from the entire public network. You do not need to create or subscribe to a pool to use NebulaNet.

Subscribing to a pool acts as a filter: instead of receiving metadata from everyone, you will **only** receive updates from other verified members of that pool. This is useful for communities that want to maintain a high-quality, curated index free from spam, but it effectively isolates you from the wider public discovery network.

| Variable | Default | Description |
|----------|---------|-------------|
| `NEBULANET_TRUSTED_POOLS` | `[]` | JSON array of pool IDs to accept torrents from. Empty = accept from everyone (open mode). |
| `NEBULANET_POOLS_DIR` | `data/nebulanet/pools` | Storage directory for pool data. |

**Example:**
```env
NEBULANET_TRUSTED_POOLS='["my-community", "french-scene"]'
```

When `NEBULANET_TRUSTED_POOLS` is set, your node will only accept torrents from members of the specified pools.

### Private Networks

Create completely isolated NebulaNet networks:

| Variable | Default | Description |
|----------|---------|-------------|
| `NEBULANET_PRIVATE_NETWORK` | `False` | Enable private network mode. |
| `NEBULANET_NETWORK_ID` | *(empty)* | Unique identifier for your private network. Required if private mode is enabled. |
| `NEBULANET_NETWORK_PASSWORD` | *(empty)* | Shared secret to join the network. Required if private mode is enabled. |
| `NEBULANET_INGEST_POOLS` | `[]` | Pool IDs to ingest from public network even in private mode. |

Private networks are completely separate from the public NebulaNet network. All nodes in a private network must share the same `NETWORK_ID` and `NETWORK_PASSWORD`.

### Advanced Tuning

#### Gossip Protocol

| Variable | Default | Description |
|----------|---------|-------------|
| `NEBULANET_GOSSIP_FANOUT` | `3` | Number of peers to forward each message to. Higher = faster propagation, more bandwidth. |
| `NEBULANET_GOSSIP_INTERVAL` | `1.0` | Seconds between gossip rounds. |
| `NEBULANET_GOSSIP_MESSAGE_TTL` | `5` | Maximum hops a message can travel. |
| `NEBULANET_GOSSIP_MAX_TORRENTS_PER_MESSAGE` | `1000` | Maximum torrents per gossip message. |

#### Validation

| Variable | Default | Description |
|----------|---------|-------------|
| `NEBULANET_GOSSIP_VALIDATION_FUTURE_TOLERANCE` | `60` | Seconds tolerance for future timestamps (clock drift). |
| `NEBULANET_GOSSIP_VALIDATION_PAST_TOLERANCE` | `300` | Seconds tolerance for past timestamps. |
| `NEBULANET_GOSSIP_TORRENT_MAX_AGE` | `604800` | Maximum age (7 days) for accepting torrent updates. |
| `NEBULANET_SKIP_TIME_CHECK` | `False` | Skip the system clock synchronization check on startup. |
| `NEBULANET_TIME_CHECK_TOLERANCE` | `60` | Maximum allowed clock drift in seconds. |
| `NEBULANET_TIME_CHECK_TIMEOUT` | `5` | Timeout for the time check request. |

#### Peer Discovery

| Variable | Default | Description |
|----------|---------|-------------|
| `NEBULANET_PEX_BATCH_SIZE` | `20` | Number of peers shared in Peer Exchange responses. |
| `NEBULANET_PEER_CONNECT_BACKOFF_MAX` | `300` | Maximum seconds before reconnecting to a failed peer. |
| `NEBULANET_PEER_MAX_FAILURES` | `5` | Failures before temporarily banning a peer. |
| `NEBULANET_PEER_CLEANUP_AGE` | `604800` | Seconds (7 days) to keep inactive peers. |
| `NEBULANET_ALLOW_PRIVATE_PEX` | `False` | Allow private/internal IPs via Peer Exchange. Enable for LAN setups. |
| `NEBULANET_SKIP_REACHABILITY_CHECK` | `False` | Skip the external reachability check on startup. Only use for local testing. |
| `NEBULANET_STATE_SAVE_INTERVAL` | `300` | Periodic state save interval in seconds. Protects stats and peer reputation from being lost in abrupt container shutdowns. |
| `NEBULANET_REACHABILITY_RETRIES` | `5` | Number of retry attempts for the reachability check. Useful when using Traefik or other reverse proxies that take time to start. |
| `NEBULANET_REACHABILITY_RETRY_DELAY` | `10` | Delay in seconds between retry attempts for the reachability check. |
| `NEBULANET_REACHABILITY_TIMEOUT` | `10` | Timeout in seconds for each reachability check attempt. |

#### Transport

| Variable | Default | Description |
|----------|---------|-------------|
| `NEBULANET_TRANSPORT_MAX_MESSAGE_SIZE` | `10485760` | Maximum WebSocket message size (10MB). |
| `NEBULANET_TRANSPORT_MAX_CONNECTIONS_PER_IP` | `3` | Maximum connections from a single IP (anti-Sybil). |
| `NEBULANET_TRANSPORT_PING_INTERVAL` | `30.0` | Seconds between keepalive pings. |
| `NEBULANET_TRANSPORT_CONNECTION_TIMEOUT` | `120.0` | Seconds before dropping a silent connection. |
| `NEBULANET_TRANSPORT_MAX_LATENCY_MS` | `10000.0` | Maximum acceptable peer latency (ms). Peers exceeding this are disconnected. |
| `NEBULANET_TRANSPORT_RATE_LIMIT_ENABLED` | `True` | Enable rate limiting for incoming messages. |
| `NEBULANET_TRANSPORT_RATE_LIMIT_COUNT` | `20` | Max messages per window. |
| `NEBULANET_TRANSPORT_RATE_LIMIT_WINDOW` | `1.0` | Window size (seconds). |

#### NAT Traversal

| Variable | Default | Description |
|----------|---------|-------------|
| `NEBULANET_UPNP_ENABLED` | `False` | Enable UPnP to automatically open ports on your router. |
| `NEBULANET_UPNP_LEASE_DURATION` | `3600` | UPnP port mapping lease duration (seconds). |

#### Reputation System

The reputation system tracks peer quality and filters bad actors:

| Variable | Default | Description |
|----------|---------|-------------|
| `NEBULANET_REPUTATION_INITIAL` | `100.0` | Starting reputation for new peers. |
| `NEBULANET_REPUTATION_MIN` | `0.0` | Minimum reputation score. |
| `NEBULANET_REPUTATION_MAX` | `10000.0` | Maximum reputation score. |
| `NEBULANET_REPUTATION_THRESHOLD_TRUSTED` | `1000.0` | Score needed to be considered "trusted". |
| `NEBULANET_REPUTATION_THRESHOLD_UNTRUSTED` | `50.0` | Score below which a peer is ignored. |
| `NEBULANET_REPUTATION_BONUS_VALID_CONTRIBUTION` | `0.001` | Bonus per valid torrent contributed. |
| `NEBULANET_REPUTATION_BONUS_PER_DAY_ANCIENNETY` | `10.0` | Daily bonus for long-running peers. |
| `NEBULANET_REPUTATION_PENALTY_INVALID_CONTRIBUTION` | `50.0` | Penalty for sending bad data. |
| `NEBULANET_REPUTATION_PENALTY_INVALID_SIGNATURE` | `500.0` | Penalty for invalid signatures. |

---

## Trust Pools

Trust Pools allow you to create communities of trusted contributors. Only pool members can contribute torrents that other members will accept.

### Creating a Pool

1. Navigate to the Admin Dashboard → NebulaNet tab.
2. Click "Create Pool".
3. Enter:
   - **Pool ID**: Unique identifier (lowercase, dashes allowed)
   - **Display Name**: Human-readable name
   - **Description**: What this pool is for
4. Click "Create".

You become the pool creator and administrator.

### Joining a Pool

**Via Invite Link:**

1. Get an invite link from a pool administrator.
2. In the Admin Dashboard → NebulaNet tab, click "Join Pool".
3. Paste the invite link.
4. Click "Join".

The invite link format is:
```
nebulanet://join?pool=pool-id&code=invite-code&node=wss://admin-node:8765
```

### Managing Members

Pool creators and admins can:

- **View Members**: See all pool members and their roles.
- **Create Invites**: Generate invite links with optional expiration or usage limits.
- **Promote to Admin**: Give members administrative privileges.
- **Demote Admins**: Remove admin privileges.
- **Kick Members**: Remove members from the pool.
- **Delete Pool**: Permanently remove the pool (creator only).

**Member Roles:**

| Role | Can Invite | Can Kick | Can Promote/Demote | Can Delete Pool |
|------|------------|----------|-------------------|-----------------|
| Creator | Yes | Yes | Yes | Yes |
| Admin | Yes | Yes | Yes (except creator) | No |
| Member | No | No | No | No |

---

## Network Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        NebulaNet Network                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐     WebSocket      ┌──────────────┐          │
│  │   Node A     │◄──────────────────►│   Node B     │          │
│  │  (Scraper)   │                    │  (Scraper)   │          │
│  └──────┬───────┘                    └──────┬───────┘          │
│         │                                   │                   │
│         │ Gossip                            │ Gossip            │
│         ▼                                   ▼                   │
│  ┌──────────────┐                    ┌──────────────┐          │
│  │   Node C     │                    │   Node D     │          │
│  │  (Consumer)  │◄──────────────────►│  (Consumer)  │          │
│  └──────────────┘                    └──────────────┘          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Components:**

1. **Identity (Crypto)**: Ed25519 keypair for signing and node identification.
2. **Transport**: WebSocket connections with keepalive and automatic reconnection.
3. **Discovery**: Finds peers via bootstrap nodes, manual peers, and Peer Exchange (PEX).
4. **Gossip Engine**: Propagates torrents with signature verification and deduplication.
5. **Reputation Store**: Tracks peer quality and filters bad actors.
6. **Pool Store**: Manages Trust Pools and memberships.

---

## Security Considerations

### Cryptographic Signing

- Every torrent contribution is signed with the contributor's Ed25519 private key.
- Signatures are verified before accepting any data.
- Invalid signatures result in reputation penalties and potential disconnection.

### Anti-Abuse Measures

- **Timestamp Validation**: Old or future-dated messages are rejected.
- **Sybil Resistance**: Connections per IP are limited.
- **Deduplication**: Prevents message flooding.

### Recommendations

1. **Use TLS**: Configure `wss://` instead of `ws://` for encrypted connections.
2. **Encrypt Keys**: Set `NEBULANET_KEY_PASSWORD` to encrypt your private key on disk.
3. **Trust Pools**: In production, use Trust Pools to limit who can contribute.
4. **Firewall**: Only expose NebulaNet ports to trusted networks or the internet if necessary.
5. **API Key for Standalone**: When running the standalone service, the `NEBULANET_API_KEY` is mandatory. If you do not provide one, a random key will be generated and printed in the logs at startup. Use this key to authenticate your Nebula instances.

### What NebulaNet Does NOT Protect Against

- A malicious majority in a pool (if >50% of trusted contributors are malicious)
- Denial of service (flooding with valid but useless torrents)
- Metadata quality (NebulaNet doesn't validate torrent content, only signatures)

---

## Troubleshooting

### Reachability Check Failed

On startup, NebulaNet verifies that your `NEBULANET_ADVERTISE_URL` is actually reachable from the outside. If this check fails:

1. **Check your URL**: Ensure `NEBULANET_ADVERTISE_URL` points to your public address.
2. **Firewall/NAT**: Make sure port 8765 is open and forwarded.
3. **Reverse proxy**: If using nginx/caddy/Traefik, ensure WebSocket headers are forwarded (`Upgrade` and `Connection`).
4. **SSL certificate**: If using `wss://`, verify your SSL certificate is valid.
5. **Using Traefik or slow reverse proxy?** The reverse proxy may take time to open. Increase retry settings:
   - `NEBULANET_REACHABILITY_RETRIES=10` (default: 5)
   - `NEBULANET_REACHABILITY_RETRY_DELAY=15` (default: 10 seconds)
   - `NEBULANET_REACHABILITY_TIMEOUT=15` (default: 10 seconds)
6. **Testing locally?** Set `NEBULANET_SKIP_REACHABILITY_CHECK=True` to bypass this check.

The check makes multiple attempts to connect to your WebSocket URL with configurable retries and delays to accommodate slow-starting reverse proxies like Traefik.

### System Clock Not Synchronized

NebulaNet requires an accurate system clock for cryptographic signature validation and SSL/TLS connections. If the startup check fails:

1. **Check Drift**: The error message will show the current drift. If it's more than 60s, your clock is too far off.
2. **Synchronize**:
   - Linux: `sudo ntpdate pool.ntp.org` or `sudo timedatectl set-ntp true`
   - Docker: Ensure your host machine's clock is synchronized.
3. **Increase Tolerance**: If you cannot perfectly sync the clock, increase `NEBULANET_TIME_CHECK_TOLERANCE` (e.g., to 120).
4. **Bypass**: Set `NEBULANET_SKIP_TIME_CHECK=True` (not recommended for production).

### No Peers Connecting

1. **Check firewall**: Ensure `NEBULANET_LISTEN_PORT` (default 8765) is accessible.
2. **Behind NAT?** Enable `NEBULANET_UPNP_ENABLED=True` or manually forward the port.
3. **Verify bootstrap nodes**: Ensure they're online and using correct addresses.
4. **Check logs**: Look for "NebulaNet started" and connection attempts.

### Not Receiving Torrents

1. **Contribution mode**: Ensure you're not in `source` mode (which doesn't receive).
2. **Trust Pools**: If `NEBULANET_TRUSTED_POOLS` is set, ensure you're subscribed to active pools.
3. **Peer count**: Check the Admin Dashboard for connected peers.

### Not Sharing Torrents

1. **Contribution mode**: Ensure you're in `full` or `source` mode.
2. **Scrapers enabled**: NebulaNet shares what your scrapers find - if nothing is scraped, nothing is shared.

### Pool Sync Issues

1. **Version mismatch**: Pool manifests sync automatically. Wait a few minutes.
2. **Creator offline**: The pool creator's node must be reachable for new join requests.

### High Memory/CPU

1. Reduce `NEBULANET_MAX_PEERS` (fewer connections = less overhead).
3. Increase `NEBULANET_GOSSIP_INTERVAL` (less frequent gossiping).

### Logs and Debugging

NebulaNet logs under the `NEBULANET` tag. Key events to watch for:

```
NebulaNet started - Node ID: abc123...
Discovery service started with 2 known peers
Connected to peer def456...
Received 10 torrents from peer abc123...
```

---

## Support

For issues specific to NebulaNet, please include:

1. Your deployment mode (Integrated or Relay)
2. Relevant settings (contribution mode, pools, etc.)
3. NebulaNet-specific log entries

Join the Nebula Discord for community support and discussion.
