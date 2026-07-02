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
PORT=8006
VITE_API_URL=http://localhost:8006

# Jira Integration (Required)
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

Once all services are healthy:

- **Frontend UI**: http://localhost:5173
- **Backend API**: http://localhost:8006
- **API Docs**: http://localhost:8006/docs

---

## Services Overview

| Service | Port | Description |
|---------|------|-------------|
| `backend` | 8006 | FastAPI REST API server |
| `frontend` | 5173 | React 19 + Vite development server |
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
[INFO]   - Port: 8006
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

### Backup Your Data

```bash
# Backup all Antikythera data
tar -czf antikythera-backup-$(date +%Y%m%d).tar.gz \
    ~/.antikythera ~/antikythera-data
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

If port 8006 or 5173 is already in use:

1. Edit `docker-compose.yml` and change the port mapping:
   ```yaml
   ports:
     - "8007:8006"  # Use port 8007 externally
   ```

2. Or stop the conflicting process:
   ```bash
   lsof -i :8006
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
- Nginx for serving static frontend
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

2. **Read-only config mount**: Config is mounted as `:ro` (read-only) in containers to prevent accidental modification.

3. **Network isolation**: All services communicate over an internal Docker network. Only backend (8006) and frontend (5173) are exposed.

4. **Health checks**: Backend has a health check endpoint. Consider adding one for orchestrator if you need liveness probes.

---

## Updating Antikythera

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

**Q: Why is my config mounted as read-only?**  
A: Security! Containers should never modify your credentials. The `:ro` flag prevents any container from accidentally (or maliciously) changing your secrets.

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
[ERROR] Missing or unconfigured required variables: JIRA_PAT PORT
```

**A:** Add these to `~/.antikythera/.env`:
```ini
PORT=8006
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

**A:** The backend isn't responding on port 8006. Check:
1. Is the container running? `docker-compose ps`
2. Any startup errors? `docker-compose logs backend`
3. Is another process using port 8006? `lsof -i :8006`

**Q: Port already in use**

**A:** Change the external port in `docker-compose.yml`:
```yaml
ports:
  - "8007:8006"  # Use 8007 externally, 8006 internally
```

**Q: "Read-only file system" when trying to save config**

**A:** This is expected! Config is mounted read-only. Modify `~/.antikythera/.env` on your host, not inside the container.

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
- Nginx for serving static frontend
- Named volumes for data
- Resource limits
- Restart policies

```bash
docker-compose -f docker-compose.prod.yml up -d
```

**Q: How do I backup my data?**

```bash
tar -czf antikythera-backup-$(date +%Y%m%d).tar.gz \
    ~/.antikythera ~/antikythera-data
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
                    │      http://localhost:5173     │
                    │         (Frontend UI)          │
                    └────────────────┬───────────────┘
                                     │
                                     │ API requests
                                     ▼
                    ┌────────────────────────────────┐
                    │      http://localhost:8006     │
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
    │ (read-only) │  │ (read/write)│  │ (optional)  │
    └─────────────┘  └─────────────┘  └─────────────┘
```

### Network Topology

```
    Internet
       │
       ▼
┌──────────────────┐
│   Host Machine   │  Ports: 8006 (API), 5173 (UI)
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
- **API Docs**: http://localhost:8006/docs (when running)
- **First step**: Always check `docker-compose logs <service>` for error details