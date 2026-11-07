# Antikythera Docker Setup Guide

> **Antikythera** is a perpetual, human-in-the-loop, asynchronous multi-agent automation platform.

This guide helps you run Antikythera using Docker with minimal setup.

---

## Quick Start

### Prerequisites

1. **Docker & Docker Compose** installed on your system
2. **Git** (to clone the repository, if building locally)

### Step 1: Create Configuration Directory

Antikythera stores credentials and configuration in `~/.antikythera/` on your host machine. This keeps secrets outside the container and Docker image.

```bash
mkdir -p ~/.antikythera
```

### Step 2: Create Configuration File

Create `~/.antikythera/.env` with your credentials:

```bash
vim ~/.antikythera/.env
```

**Required Configuration:**

```ini
# Server Configuration
# PORT and VITE_API_URL are the HOST-side values (D8). The container itself always listens on 8006
# and ignores PORT for its bind port; the local start script uses PORT.
PORT=18006
VITE_API_URL=http://localhost:18006

# Optional (see .env.example): ANTIKYTHERA_API_TOKEN, ANTIKYTHERA_CORS_ORIGINS, ANTIKYTHERA_ENABLE_DOCS

# Jira Integration (Optional: leave unset or remove to skip; the container only warns)
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_PAT=your_jira_personal_access_token

# AI Provider (At least one required for AI features)
# Choose one or more:
NVIDIA_API_KEY=your_nvidia_api_key
GOOGLE_API_KEY=your_google_api_key
OPENROUTER_API_KEY=your_openrouter_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
```

**Optional: AI Environment File**

For managing multiple AI model configurations, create `~/.antikythera/.ai_env`:

```ini
NVIDIA_API_KEY="nvapi-your-key-here"
GOOGLE_API_KEY="AIza-your-key-here"
OPENROUTER_API_KEY="your-key-here"
```

### Step 3: Create Data Directory

Antikythera stores all state (pipeline state, workflow runs, audit logs) in a data directory:

```bash
mkdir -p ~/antikythera-data
```

### Step 4: Start Antikythera

#### Option A: Pull Pre-built Images (Recommended)

```bash
# Create a directory for your compose file
mkdir -p ~/antikythera-run
cd ~/antikythera-run

# Download the docker-compose.yml
curl -O https://raw.githubusercontent.com/himanshusao/antikythera/main/docker/docker-compose.yml

# Start Antikythera
docker-compose pull
docker-compose up
```

#### Option B: Build from Source

```bash
# Clone the repository
git clone https://github.com/himanshusao/antikythera.git
cd antikythera/docker

# Build and start
docker-compose up --build
```

#### Option C: Test the Docker Setup

Before running, you can test the Docker setup autonomously:

```bash
cd antikythera/docker

# Run full test suite (builds, validates, tests API)
./test-docker.sh

# Quick smoke test only
./test-docker.sh quick

# Test build only
./test-docker.sh build

# Clean up test artifacts
./test-docker.sh cleanup
```

See [TESTING.md](TESTING.md) for detailed test documentation.

### Step 5: Access the Application

Nothing is published off-loopback. The compose files publish the API and the UI on the **Docker host's loopback only** (`127.0.0.1:18006` and `127.0.0.1:15173`). From a laptop, open the SSH tunnel below, then browse:

- **Frontend UI**: http://localhost:15173
- **Backend API**: http://localhost:18006
- **API Docs**: disabled by default; set `ANTIKYTHERA_ENABLE_DOCS=1` to serve http://localhost:18006/docs

If Docker runs on the same machine as your browser, the same URLs work without a tunnel.

---

## Ports and Remote Access (SSH Tunnel)

### Port table

| Service | Container port (internal, unchanged) | Published on the Docker host | URL on your laptop (via tunnel) |
|---------|--------------------------------------|------------------------------|---------------------------------|
| `backend` (API) | 8006 | `127.0.0.1:18006` | http://localhost:18006 |
| `frontend` (UI) | 5173 (dev image) or 80 (`docker-compose.prod.yml` nginx) | `127.0.0.1:15173` | http://localhost:15173 |
| `orchestrator` | none | none | none |

Containers keep 8006/5173 internally; only the host-side published ports changed. Nothing is published on any other interface, so the services are not reachable from the network, only from the Docker host itself.

### SSH tunnel

When the Docker daemon runs on a remote host (for example `DOCKER_HOST=ssh://...`), forward both ports to your laptop:

```bash
ssh -N -L 18006:127.0.0.1:18006 -L 15173:127.0.0.1:15173 <user>@<docker-host>
```

Leave it running, then open http://localhost:15173. The UI calls the API at `http://localhost:18006` (`VITE_API_URL`), which is the same tunnel.

Suggested block for `~/.ssh/config`, so `ssh antikythera -N` does the same thing:

```
Host antikythera
    HostName <docker-host>
    User <user>
    LocalForward 18006 127.0.0.1:18006
    LocalForward 15173 127.0.0.1:15173
    ExitOnForwardFailure yes
    ServerAliveInterval 30
```

### Rebuild after the port change

The published ports are in the compose files, and `VITE_API_URL` is read when the UI container starts. After pulling this change, recreate the containers (`docker-compose up -d --build --force-recreate`), and update `PORT=18006` and `VITE_API_URL=http://localhost:18006` in `~/.antikythera/.env` on the Docker host.

---

## Services Overview

| Service | Port | Description |
|---------|------|-------------|
| `backend` | 8006 in the container, published as `127.0.0.1:18006` | FastAPI REST API server |
| `frontend` | 5173 in the container, published as `127.0.0.1:15173` | React 19 + Vite development server |
| `orchestrator` | - | Background pipeline processor (runs every 30s) |

---

## Common Commands

```bash
# Start all services
docker-compose up

# Start in background (detached)
docker-compose up -d

# View logs
docker-compose logs

# Follow logs in real-time
docker-compose logs -f

# View specific service logs
docker-compose logs -f backend

# Stop all services
docker-compose down

# Restart a service
docker-compose restart backend

# Rebuild images
docker-compose build

# Pull latest images
docker-compose pull
```

---

## Configuration Validation

On startup, Antikythera validates your configuration:

### ✅ Validation Passed

```
[INFO] Validating Antikythera configuration...
[OK] Found AI environment file: /root/.antikythera/.ai_env
[OK] AI provider configured: NVIDIA_API_KEY
[OK] Configuration validation passed!
[INFO]   - Port: 18006
[INFO]   - Jira Base URL: https://your-domain.atlassian.net
[INFO]   - Data directory: /app/automation-ideas
[INFO]   - AI Provider: NVIDIA_API_KEY
```

### ⚠️ Warning: No AI Key

```
[WARN] No AI provider API key configured.
[WARN] Add one of these to your config:
[WARN]   - NVIDIA_API_KEY
[WARN]   - GOOGLE_API_KEY
[WARN]   - OPENROUTER_API_KEY
[WARN]   - ANTHROPIC_API_KEY
[WARN] AI features will not work until an API key is configured.
```

### ❌ Error: Missing Required Config

```
[ERROR] Configuration file not found: /root/.antikythera/.env
[ERROR] Please create this file with your credentials.
```

---

## Data Persistence

### Where is my data stored?

| Data Type | Location |
|-----------|----------|
| Pipeline State | `~/antikythera-data/pipeline-state.json` |
| Workflow Runs | `~/antikythera-data/workflow_runs.json` |
| Requirements | `~/antikythera-data/requirements/` |
| Audit Logs | `~/antikythera-data/audit/` |
| Brain Patterns | `~/antikythera-data/brain/` |

All data persists even if you delete containers. The `~/.antikythera/` directory on your host contains credentials, and `~/antikythera-data/` contains application state.

**The image contains no user data.** `automation-ideas/` is never copied into the image (it is excluded by the root `.dockerignore`); the container only gets an empty `/app/automation-ideas` mount point, and your data comes from the `~/antikythera-data` mount. The image does contain `config.yaml` (provider and model names and the names of the environment variables that hold keys, never key values), because the agents load it when the orchestrator starts.

### Backup Your Data

Use the backup script from a checkout of the repository. It writes a timestamped, `0600` `tar.gz` that includes dotfiles (such as `.vault.key`), skips `*.lock` files, and keeps the newest 14 archives:

```bash
# Back up the Docker data directory
scripts/backup_data.sh ~/antikythera-data

# Back up the local (non-Docker) data directory, <repo>/automation-ideas
scripts/backup_data.sh
```

| Setting | Default | Meaning |
|---------|---------|---------|
| `ANTIKYTHERA_BACKUP_DIR` | `~/antikythera-backups` | Where archives are written (created with mode `0700`) |
| `ANTIKYTHERA_BACKUP_KEEP` | `14` | Number of newest archives to keep; older ones are removed |

The archives contain secrets, so keep them as private as the data directory. Example cron entry (daily at 02:30): `30 2 * * * /path/to/antikythera/scripts/backup_data.sh ~/antikythera-data`. To restore: `tar -C <empty dir> -xzf <archive>`.

`~/.antikythera` (credentials and AI Engine settings) is not part of this archive; copy it separately if you want it backed up:

```bash
tar -czf antikythera-config-$(date +%Y%m%d).tar.gz ~/.antikythera
chmod 600 antikythera-config-*.tar.gz
```

---

## Troubleshooting

### Container Won't Start

**Check configuration validation:**

```bash
docker-compose up 2>&1 | grep -E "\[ERROR\]|\[WARN\]"
```

**Verify config file exists:**

```bash
ls -la ~/.antikythera/
cat ~/.antikythera/.env
```

### Port Already in Use

If port 18006 or 15173 is already in use on the Docker host:

1. Edit `docker-compose.yml` and change the host side of the port mapping (keep the loopback address):
   ```yaml
   ports:
     - "127.0.0.1:18007:8006"  # Use host port 18007; the container still listens on 8006
   ```
   Then tunnel the new port too, and set `VITE_API_URL` to match.

2. Or stop the conflicting process:
   ```bash
   lsof -i :18006
   kill <PID>
   ```

### AI Features Not Working

Ensure at least one AI provider key is configured in `~/.antikythera/.env` or `~/.antikythera/.ai_env`:

```bash
# Check if API key is set
grep -E "NVIDIA_API_KEY|GOOGLE_API_KEY|OPENROUTER_API_KEY|ANTHROPIC" ~/.antikythera/.env
grep -E "NVIDIA_API_KEY|GOOGLE_API_KEY|OPENROUTER_API_KEY|ANTHROPIC" ~/.antikythera/.ai_env
```

### Permission Denied on Data Directory

```bash
# Fix permissions
chmod -R 755 ~/antikythera-data
```

---

## Advanced Configuration

### Using Different Image Tags

By default, `docker-compose.yml` uses `himanshusao/antikythera:latest`. To pin a specific version:

```yaml
services:
  backend:
    image: himanshusao/antikythera:v1.2.3
```

### Production Deployment

For production, use the production compose file which includes:
- Nginx serving the built UI (the `prod` stage of `Dockerfile.ui`, built locally with `--build`; `/api/` is proxied to the backend)
- Named volumes instead of bind mounts
- Restart policies

```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Custom Network Configuration

If you need Antikythera on a specific network:

```yaml
networks:
  antikythera-network:
    external: true
    name: your-existing-network
```

### Environment-Specific Overrides

Create `docker-compose.override.yml` for local development:

```yaml
version: '3.8'

services:
  backend:
    environment:
      - DEBUG=true
      - LOG_LEVEL=DEBUG
  
  frontend:
    environment:
      - VITE_DEBUG=true
```

---

## Security Notes

1. **Never commit credentials**: The `~/.antikythera/.env` file contains secrets. Never add it to version control.

2. **Config mount is read-write for backend and orchestrator**: the AI Engine settings page saves the default model to `~/.antikythera/ai_config.json` and API keys to `~/.antikythera/.ai_env`, so those two services mount `~/.antikythera` without `:ro`. With `:ro`, setting a default model failed with a 500 and setting a key silently did not persist. Keep the host directory private (`chmod 700 ~/.antikythera`). The frontend container does not need it. The containers set `ANTIKYTHERA_HOME=/root/.antikythera` so the service uses the mounted directory explicitly.

   The entrypoint reads `.env` and `.ai_env` as plain `KEY=VALUE` lines (it never runs them as shell), so a `$(...)` or backtick in a value is kept as text and is not executed.

3. **Network isolation**: All services communicate over an internal Docker network. Only the backend (`127.0.0.1:18006`) and the frontend (`127.0.0.1:15173`) are published, and only on the Docker host's loopback. Nothing is published off-loopback; reach them with the SSH tunnel described under "Ports and Remote Access".

4. **Health checks**: Backend has a health check endpoint. Consider adding one for orchestrator if you need liveness probes.

---

## Updating Antikythera

> **Rebuild and recreate after pulling these changes.** The image now includes `config.yaml` (the orchestrator could not start without it), and the compose files changed (read-write config mount). Run `docker-compose build --no-cache` (or `docker-compose pull`) and then `docker-compose up -d --force-recreate`. For production: `docker-compose -f docker-compose.prod.yml up -d --build`.
>
> **Rotate secrets if you used an image published before commit `eac8428`.** Those images were built with `automation-ideas/` copied in, so the pipeline state, integration records and vault files that were on the build machine are inside the image layers. Anyone who pulled the image can read them. Treat every credential that could have been in that data (Jira tokens, API keys, the vault key and anything the vault held) as exposed: revoke and reissue it, delete the old image tags from Docker Hub, and pull a freshly built image.

```bash
# Pull latest images
docker-compose pull

# Recreate containers
docker-compose up -d --force-recreate

# Clean up old images
docker image prune -f
```

---

## Frequently Asked Questions (FAQ)

### General

**Q: Do I need to clone the repository to run Antikythera?**  
A: No! If you pull pre-built images from Docker Hub, you only need the `docker-compose.user.yml` file. Copy it to your machine and run `docker-compose up`.

**Q: Where is my data stored?**  
A: All data is stored on your host machine in `~/antikythera-data/`. Containers can be deleted and recreated without losing data.

**Q: Can I run multiple instances of Antikythera?**  
A: Yes, but you'll need different ports for each instance. Either:
- Use different host directories (`~/antikythera-data-1`, `~/antikythera-data-2`)
- Change the port mappings in `docker-compose.yml`

---

### Configuration

**Q: What happens if I lose my `~/.antikythera/.env` file?**  
A: The containers won't start. The entrypoint script validates that required variables are present. Simply recreate the file with your credentials.

**Q: Is my config mounted read-only?**  
A: Not for the backend and orchestrator. The AI Engine settings page needs to write `ai_config.json` and `.ai_env` into `~/.antikythera`, so that mount is read-write (the frontend container has no need for it). Keep the directory private with `chmod 700 ~/.antikythera`.

**Q: I added a new API key but it's not being picked up. Why?**  
A: Restart the container: `docker-compose restart backend`. Environment variables are loaded at container start.

---

### Troubleshooting

**Q: "Configuration file not found" error**

```
[ERROR] Configuration file not found: /root/.antikythera/.env
```

**A:** The container can't find your config file. Check:
1. `~/.antikythera/.env` exists on your host
2. The volume mount in `docker-compose.yml` is correct
3. File permissions allow the container to read it

**Q: "Missing or unconfigured required variables"**

```
[ERROR] Missing or unconfigured required variables: PORT
```

**A:** Add this to `~/.antikythera/.env` (values starting with `your_` or `dummy` count as unconfigured):
```ini
PORT=18006
```

(The container listens on 8006 regardless; `PORT` is the host-side value.)

Jira is optional. If `JIRA_BASE_URL` or `JIRA_PAT` is missing or still a placeholder, the container logs a warning and starts without Jira. To enable it:
```ini
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_PAT=your_actual_token_here
```

**Q: "No AI provider API key configured" warning**

```
[WARN] No AI provider API key configured.
```

**A:** This is a warning, not an error. Antikythera will run but AI features won't work. Add at least one:
```ini
NVIDIA_API_KEY=...
GOOGLE_API_KEY=...
OPENROUTER_API_KEY=...
ANTHROPIC_API_KEY=...
```

**Q: Container exits immediately**

**A:** Check the logs:
```bash
docker-compose logs backend
```
Common causes:
- Missing config file
- Invalid config values
- Port already in use

**Q: Health check keeps failing**

**A:** The backend isn't responding on its internal port 8006. Check:
1. Is the container running? `docker-compose ps`
2. Any startup errors? `docker-compose logs backend`
3. Is another process using the published host port 18006? `lsof -i :18006`

**Q: Port already in use**

**A:** Change the host port in `docker-compose.yml`, keeping the loopback address:
```yaml
ports:
  - "127.0.0.1:18007:8006"  # Use 18007 on the host, 8006 inside the container
```

**Q: "Read-only file system" or a 500 when saving AI Engine settings**

**A:** Your compose file still mounts `~/.antikythera` with `:ro`. Update to the current compose files (the backend and orchestrator mount it read-write) and recreate the containers: `docker-compose up -d --force-recreate`. `.env` itself is still best edited on the host.

**Q: Data directory permission denied**

```
PermissionError: [Errno 13] Permission denied: '/app/automation-ideas'
```

**A:** Fix permissions on your host:
```bash
chmod -R 755 ~/antikythera-data
chown -R $(whoami) ~/antikythera-data
```

---

### Images & Updates

**Q: How do I update to the latest version?**

```bash
# Pull new images
docker-compose pull

# Recreate containers
docker-compose up -d --force-recreate

# Clean up old images
docker image prune -f
```

**Q: Can I pin a specific version?**  
A: Yes, change the image tag in `docker-compose.yml`:
```yaml
image: himanshusao/antikythera:v1.0.0
```

**Q: How do I rebuild images from source?**

```bash
docker-compose build --no-cache
```

---

### Production

**Q: Can I use this in production?**  
A: Yes! Use `docker-compose.prod.yml` which includes:
- Nginx serving the built UI (`Dockerfile.ui`, `target: prod`)
- Named volumes for data
- Resource limits
- Restart policies

```bash
docker-compose -f docker-compose.prod.yml up -d
```

**Q: How do I backup my data?**

```bash
scripts/backup_data.sh ~/antikythera-data     # rotating, 0600 archives (see "Backup Your Data")
```

---

### Development

**Q: How do I enable debug logging?**

Add to `docker-compose.yml`:
```yaml
services:
  backend:
    environment:
      - DEBUG=true
      - LOG_LEVEL=DEBUG
```

**Q: How do I run a single service?**

```bash
# Backend only
docker-compose up backend

# Frontend only
docker-compose up frontend

# Orchestrator only
docker-compose up orchestrator
```

---

## Architecture Diagram

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Docker Compose                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  frontend   │  │   backend   │  │   orchestrator      │  │
│  │  (5173)     │──▶│   (8006)    │  │   (background)      │  │
│  │ 127.0.0.1:  │   │ 127.0.0.1:  │  │                     │  │
│  │   15173     │   │   18006     │  │                     │  │
│  └─────────────┘  └──────┬──────┘  └──────────┬──────────┘  │
│                          │                      │            │
│         ┌────────────────┴──────────────────────┘            │
│         │                                                    │
│  ┌──────▼───────────────────────────┐                        │
│  │     ~/antikythera-data           │                        │
│  │  (pipeline-state, workflows,     │                        │
│  │   requirements, brain, audit)    │                        │
│  └──────────────────────────────────┘                        │
│                                                              │
│  ┌───────────────────────────────────┐                       │
│  │     ~/.antikythera/.env           │                       │
│  │  (JIRA_PAT, API keys, config)     │                       │
│  └───────────────────────────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
                                    USER
                                     │
                                     ▼
                    ┌────────────────────────────────┐
                    │     http://localhost:15173     │
                    │         (Frontend UI)          │
                    └────────────────┬───────────────┘
                                     │
                                     │ API requests
                                     ▼
                    ┌────────────────────────────────┐
                    │     http://localhost:18006     │
                    │        (Backend API)           │
                    │                                │
                    │  ┌──────────────────────────┐  │
                    │  │  entrypoint.sh           │  │
                    │  │  - Validate config       │  │
                    │  │  - Check required vars   │  │
                    │  │  - Warn on missing AI    │  │
                    │  └──────────────────────────┘  │
                    └────────┬───────────────────────┘
                             │
           ┌─────────────────┼─────────────────┐
           │                 │                 │
           ▼                 ▼                 ▼
    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
    │   Config    │  │    Data     │  │   Logs      │
    │ ~/.ant...   │  │ ~/ant...    │  │ ./logs/     │
    │ (read/write)│  │ (read/write)│  │ (optional)  │
    └─────────────┘  └─────────────┘  └─────────────┘
```

### Network Topology

```
    Internet
       │
       ▼
┌──────────────────┐
│   Docker host    │  127.0.0.1:18006 (API), 127.0.0.1:15173 (UI)
└────────┬─────────┘
         │
         │ Docker Bridge Network
         ▼
┌─────────────────────────────────────────────────┐
│           antikythera-network                   │
│                                                 │
│  ┌─────────────┐    ┌─────────────┐            │
│  │  frontend   │    │   backend   │◀───────────┼── Health checks
│  │  :5173      │    │   :8006     │            │
│  └─────────────┘    └──────┬──────┘            │
│                            │                   │
│                     ┌──────▼──────┐            │
│                     │orchestrator │            │
│                     │  (no ports) │            │
│                     └─────────────┘            │
└─────────────────────────────────────────────────┘
```

---

## Getting Help

If your issue isn't covered in the FAQ above:

- **Documentation**: See `docs/` directory in the repository or the `docker/` folder
- **Issues**: https://github.com/himanshusao/antikythera/issues
- **API Docs**: http://localhost:18006/docs (when running with `ANTIKYTHERA_ENABLE_DOCS=1`, through the tunnel)
- **First step**: Always check `docker-compose logs <service>` for error details