# NebulaNet Docker Deployment

Complete Docker configurations for NebulaNet.

---

## Integrated Mode (Single Instance)

For simple deployments with a single Nebula instance.

### docker-compose.yml

```yaml
services:
  nebula:
    container_name: nebula
    image: g0ldyy/nebula
    restart: unless-stopped
    ports:
      - "8000:8000"
      - "8765:8765"  # NebulaNet P2P port
    environment:
      DATABASE_TYPE: postgresql
      DATABASE_URL: nebula:nebula@postgres:5432/nebula
      NEBULANET_ENABLED: "True"
      FASTAPI_WORKERS: "1"
    env_file:
      - .env
    volumes:
      - nebula_data:/app/data
    depends_on:
      postgres:
        condition: service_healthy

  postgres:
    container_name: nebula-postgres
    image: postgres:18-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: nebula
      POSTGRES_PASSWORD: nebula
      POSTGRES_DB: nebula
    volumes:
      - postgres_data:/var/lib/postgresql/
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U nebula -d nebula"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  nebula_data:
  postgres_data:
```

### .env

```env
# NebulaNet Configuration
NEBULANET_BOOTSTRAP_NODES=["wss://bootstrap.example.com:8765"]
NEBULANET_ADVERTISE_URL=wss://nebula.yourdomain.com:8765

# Optional: For home connections
NEBULANET_UPNP_ENABLED=True
```

---

## Relay Mode (Multi-Worker / Cluster)

For production deployments with multiple Nebula workers or replicas.

### docker-compose.yml

```yaml
services:
  nebula:
    container_name: nebula
    image: g0ldyy/nebula
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      DATABASE_TYPE: postgresql
      DATABASE_URL: nebula:nebula@postgres:5432/nebula
      NEBULANET_RELAY_URL: http://nebulanet:8766
      NEBULANET_API_KEY: ${NEBULANET_API_KEY} # Secure the relay connection
      FASTAPI_WORKERS: "4"  # Can use multiple workers
    env_file:
      - .env
    volumes:
      - nebula_data:/app/data
    depends_on:
      postgres:
        condition: service_healthy
      nebulanet:
        condition: service_started

  nebulanet:
    container_name: nebulanet
    image: g0ldyy/nebula
    restart: unless-stopped
    entrypoint: ["uv", "run", "python", "-m", "nebula.nebulanet.standalone"]
    ports:
      - "8765:8765"   # P2P WebSocket
      # - "8766:8766" # HTTP API (optional, only if needed externally)
    environment:
      DATABASE_TYPE: postgresql
      DATABASE_URL: nebula:nebula@postgres:5432/nebula
      NEBULANET_LISTEN_PORT: "8765"
      NEBULANET_HTTP_PORT: "8766"
      NEBULANET_API_KEY: ${NEBULANET_API_KEY}
    env_file:
      - .env-nebulanet
    volumes:
      - nebulanet_data:/app/data
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://127.0.0.1:8766/health"]
      interval: 10s
      timeout: 5s
      retries: 3

  postgres:
    container_name: nebula-postgres
    image: postgres:18-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: nebula
      POSTGRES_PASSWORD: nebula
      POSTGRES_DB: nebula
    volumes:
      - postgres_data:/var/lib/postgresql/
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U nebula -d nebula"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  nebula_data:
  nebulanet_data:
  postgres_data:
```

### .env-nebulanet

Create a separate environment file for the NebulaNet standalone service:

```env
# Network Discovery
NEBULANET_BOOTSTRAP_NODES=["wss://bootstrap.example.com:8765"]
NEBULANET_MANUAL_PEERS=[]

# Public URL (required for others to connect)
NEBULANET_ADVERTISE_URL=wss://nebula.yourdomain.com:8765

# Peer Limits
NEBULANET_MAX_PEERS=50
NEBULANET_MIN_PEERS=3

# Contribution Mode
NEBULANET_CONTRIBUTION_MODE=full

# Optional: Trust Pools
# NEBULANET_TRUSTED_POOLS=["my-community"]

# Mandatory: API Key for security (Auto-generated if not set)
NEBULANET_API_KEY=my-secret-key
```

---

## Scaling with Replicas

For high-availability deployments.

### docker-compose.yml

```yaml
services:
  nebula:
    image: g0ldyy/nebula
    deploy:
      replicas: 3
    environment:
      DATABASE_TYPE: postgresql
      DATABASE_URL: nebula:nebula@postgres:5432/nebula
      NEBULANET_RELAY_URL: http://nebulanet:8766
      FASTAPI_WORKERS: "2"
    env_file:
      - .env
    volumes:
      - nebula_data:/app/data
    depends_on:
      - postgres
      - nebulanet

  nebulanet:
    image: g0ldyy/nebula
    entrypoint: ["uv", "run", "python", "-m", "nebula.nebulanet.standalone"]
    ports:
      - "8765:8765"
    environment:
      DATABASE_TYPE: postgresql
      DATABASE_URL: nebula:nebula@postgres:5432/nebula
    env_file:
      - .env-nebulanet
    volumes:
      - nebulanet_data:/app/data
    depends_on:
      - postgres
    deploy:
      replicas: 1  # Only one NebulaNet instance needed

  load-balancer:
    image: nginx:alpine
    ports:
      - "8000:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - nebula

  postgres:
    image: postgres:18-alpine
    environment:
      POSTGRES_USER: nebula
      POSTGRES_PASSWORD: nebula
      POSTGRES_DB: nebula
    volumes:
      - postgres_data:/var/lib/postgresql/

volumes:
  nebula_data:
  nebulanet_data:
  postgres_data:
```

---

## Private Network Deployment

For isolated NebulaNet networks.

### docker-compose.yml

```yaml
services:
  nebula:
    container_name: nebula
    image: g0ldyy/nebula
    restart: unless-stopped
    ports:
      - "8000:8000"
      - "8765:8765"
    environment:
      DATABASE_TYPE: postgresql
      DATABASE_URL: nebula:nebula@postgres:5432/nebula
      NEBULANET_ENABLED: "True"
      FASTAPI_WORKERS: "1"
      NEBULANET_PRIVATE_NETWORK: "True"
      NEBULANET_NETWORK_ID: my-private-network
      NEBULANET_NETWORK_PASSWORD: ${NEBULANET_NETWORK_PASSWORD}
    env_file:
      - .env
    volumes:
      - nebula_data:/app/data
    depends_on:
      postgres:
        condition: service_healthy

  postgres:
    container_name: nebula-postgres
    image: postgres:18-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: nebula
      POSTGRES_PASSWORD: nebula
      POSTGRES_DB: nebula
    volumes:
      - postgres_data:/var/lib/postgresql/
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U nebula -d nebula"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  nebula_data:
  postgres_data:
```

### .env

```env
# Private Network Secret (keep this secure!)
NEBULANET_NETWORK_PASSWORD=my-super-secret-password-change-me

# Add other private network members
NEBULANET_MANUAL_PEERS=["wss://friend1.example.com:8765", "wss://friend2.example.com:8765"]

NEBULANET_ADVERTISE_URL=wss://nebula.yourdomain.com:8765
```

---

## Nginx Configuration for WSS

### With SSL termination at Nginx

```nginx
server {
    listen 443 ssl http2;
    server_name nebula.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/nebula.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/nebula.yourdomain.com/privkey.pem;

    # Nebula HTTP API
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # NebulaNet WebSocket
    location /nebulanet/ws {
        proxy_pass http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

When using this configuration, set:
```env
NEBULANET_ADVERTISE_URL=wss://nebula.yourdomain.com/nebulanet/ws
```

---

## Health Checks

### Check Nebula
```bash
curl http://localhost:8000/health
```

### Check NebulaNet Standalone
```bash
curl http://localhost:8766/health
```

### Check NebulaNet Stats
```bash
curl http://localhost:8766/stats
```

### Check Connected Peers
```bash
curl http://localhost:8766/peers
```

---

## Best Practices

### State Persistence

NebulaNet periodically saves state (stats, peer reputation, pools) to disk every 5 minutes by default (configurable via `NEBULANET_STATE_SAVE_INTERVAL`).

This protects against data loss from:
- Abrupt container kills (OOM, SIGKILL)
- Docker stop timeouts
- System crashes

**Recommendation:** Ensure your `data` directory is mounted as a persistent volume:
```yaml
volumes:
  - ./data:/app/data  # or named volume: nebula_data:/app/data
```

### Graceful Shutdown

To ensure all state is saved on shutdown, allow sufficient time for graceful shutdown:

```yaml
services:
  nebula:
    stop_grace_period: 30s  # Allow 30s for graceful shutdown
```

Or when manually stopping:
```bash
docker stop -t 30 nebula
```

Without this, Docker may send SIGKILL after 10s, preventing final state save.

---

## Troubleshooting

### Container fails to start

Check logs:
```bash
docker compose logs nebulanet
```

### Port already in use

Change `NEBULANET_LISTEN_PORT` to an available port.

### Cannot connect to relay

Ensure the nebulanet service is healthy:
```bash
docker compose ps
```

### WebSocket connections failing

1. Verify firewall allows port 8765
2. Check Nginx WebSocket configuration
3. Verify `NEBULANET_ADVERTISE_URL` is accessible from outside
