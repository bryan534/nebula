# NebulaNet Quick Start Guide

Get NebulaNet running in 5 minutes.

---

## Choose Your Scenario

- [A: Single Instance (Home User)](#a-single-instance-home-user)
- [B: Single Instance (VPS/Server)](#b-single-instance-vpsserver)
- [C: Multiple Workers / Cluster](#c-multiple-workers--cluster)
- [D: Joining a Private Network](#d-joining-a-private-network)

---

## A: Single Instance (Home User)

You're running Nebula on your home network with a single instance.

### Step 1: Enable NebulaNet

Add to your `.env` file:

```env
NEBULANET_ENABLED=True
FASTAPI_WORKERS=1
```

### Step 2: Configure entry points

```env
# Option 1: Bootstrap nodes (if available)
NEBULANET_BOOTSTRAP_NODES='["wss://bootstrap.example.com:8765"]'

# Option 2: Direct peer connection
NEBULANET_MANUAL_PEERS='["ws://friend-nebula.example.com:8765"]'
```

### Step 3: Enable UPnP (for NAT traversal)

```env
NEBULANET_UPNP_ENABLED=True
```

This allows other nodes to connect to you through your router.

### Step 4: Start Nebula

```bash
uv run python -m nebula.main
```

Or with Docker:
```bash
docker compose up -d
```

**You're done!** Check the logs for "NebulaNet started".

---

## B: Single Instance (VPS/Server)

You're running Nebula on a VPS or dedicated server with a public IP.

### Step 1: Enable NebulaNet

```env
NEBULANET_ENABLED=True
FASTAPI_WORKERS=1
```

### Step 2: Configure entry points

```env
NEBULANET_BOOTSTRAP_NODES='["wss://bootstrap.example.com:8765"]'
NEBULANET_MANUAL_PEERS='["ws://friend-nebula.example.com:8765"]'
```

### Step 3: Set your public URL

If using a reverse proxy (recommended):

```env
NEBULANET_ADVERTISE_URL=wss://nebula.yourdomain.com/nebulanet/ws
```

If exposing the port directly:

```env
NEBULANET_ADVERTISE_URL=ws://YOUR_PUBLIC_IP:8765
```

### Step 4: Open the firewall

```bash
# Example for UFW
sudo ufw allow 8765/tcp
```

### Step 5: Nginx reverse proxy (optional but recommended)

Add to your Nginx config:

```nginx
location /nebulanet/ws {
    proxy_pass http://127.0.0.1:8765;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_read_timeout 300s;
}
```

### Step 6: Start Nebula

```bash
uv run python -m nebula.main
```

---

## C: Multiple Workers / Cluster

You're running multiple Nebula workers or replicas. Use Relay Mode.

### Step 1: Add standalone service to Docker Compose

```yaml
services:
  # ... your existing nebula service ...
  
  nebulanet:
    image: g0ldyy/nebula
    container_name: nebulanet
    restart: unless-stopped
    entrypoint: ["uv", "run", "python", "-m", "nebula.nebulanet.standalone"]
    ports:
      - "8765:8765"
    environment:
      DATABASE_TYPE: postgresql
      DATABASE_URL: nebula:nebula@postgres:5432/nebula
      NEBULANET_BOOTSTRAP_NODES: '["wss://bootstrap.example.com:8765"]'
      NEBULANET_ADVERTISE_URL: wss://nebula.yourdomain.com:8765
      NEBULANET_API_KEY: "your-secret-key"
    volumes:
      - nebulanet_data:/app/data
    env_file:
      - .env

volumes:
  nebulanet_data:
```

### Step 2: Configure Nebula instances

Add to your `.env`:

```env
NEBULANET_RELAY_URL=http://nebulanet:8766
NEBULANET_API_KEY="your-secret-key"
```

Remove any `NEBULANET_ENABLED` setting - it's ignored when using relay.

### Step 3: Deploy

```bash
docker compose up -d
```

---

## D: Joining a Private Network

Someone has invited you to their private NebulaNet network.

### Step 1: Get network details from the admin

You'll need:
- Network ID (e.g., `my-private-network`)
- Network password

### Step 2: Configure your instance

```env
NEBULANET_ENABLED=True
FASTAPI_WORKERS=1

NEBULANET_PRIVATE_NETWORK=True
NEBULANET_NETWORK_ID=my-private-network
NEBULANET_NETWORK_PASSWORD=the-shared-secret

# Add the admin's node as a peer
NEBULANET_MANUAL_PEERS='["wss://admin-node.example.com:8765"]'
```

### Step 3: Start Nebula

Your node will only communicate with other nodes in the same private network.

---

## Verify It's Working

### Check the logs

Look for:
```
NebulaNet started - Node ID: abc123...
Discovery service started with 2 known peers
Connected to peer def456...
```

### Check the Admin Dashboard

Navigate to **Admin Dashboard → NebulaNet** to see:
- Your Node ID
- Connected peers count
- Torrents propagated/repropagated/received

### Test propagation

1. Search for content to trigger scraping.
2. Watch the NebulaNet stats for "Torrents Propagated".
3. Your peers should see the same torrents appear.

---

## Common Issues

### "NebulaNet is disabled"

Make sure `NEBULANET_ENABLED=True` and `FASTAPI_WORKERS=1`.

### No peers connecting

1. Check if port 8765 is reachable (use a port checker tool)
2. Verify `NEBULANET_ADVERTISE_URL` is set correctly
3. Enable UPnP if behind NAT: `NEBULANET_UPNP_ENABLED=True`

### "Reachability check failed" on startup

NebulaNet verifies your advertise URL is accessible before joining the network. If this fails:

1. Check your firewall and port forwarding
2. If using a reverse proxy (e.g., Traefik), ensure WebSocket headers are forwarded
3. **Traefik or slow reverse proxy?** The port may take time to open. Increase retry settings:
   ```bash
   NEBULANET_REACHABILITY_RETRIES=10  # Default: 5
   NEBULANET_REACHABILITY_RETRY_DELAY=15  # Default: 10 seconds
   NEBULANET_REACHABILITY_TIMEOUT=15  # Default: 10 seconds
   ```
4. For local testing only: `NEBULANET_SKIP_REACHABILITY_CHECK=True`

### "System clock is not synchronized" on startup

NebulaNet requires an accurate clock for security. If this check fails:
1. Sync your clock: `sudo timedatectl set-ntp true`
2. Or increase tolerance: `NEBULANET_TIME_CHECK_TOLERANCE=120`
3. Or skip (local only): `NEBULANET_SKIP_TIME_CHECK=True`

### Using relay but getting errors

Make sure:
- The standalone service is running
- `NEBULANET_RELAY_URL` is reachable from your Nebula instances
- The standalone service has correct bootstrap/peer configuration

---

## Next Steps

- Read the [full documentation](nebulanet.md) for advanced configuration
- Set up [Trust Pools](nebulanet.md#trust-pools) for community-based sharing
- Configure [contribution modes](nebulanet.md#contribution-modes) based on your needs
