# Antikythera Docker Quick Start

## For Users (3 Steps)

```bash
# Step 1: Create config
mkdir -p ~/.antikythera
cat > ~/.antikythera/.env << EOF
PORT=8006
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_PAT=your_token_here
NVIDIA_API_KEY=your_key_here
EOF

# Step 2: Create data directory
mkdir -p ~/antikythera-data

# Step 3: Run
docker-compose pull && docker-compose up
```

**Access:**
- UI: http://localhost:5173
- API: http://localhost:8006
- Docs: http://localhost:8006/docs

---

## For Developers (Build & Push)

```bash
cd docker

# Build locally
./build-docker.sh

# Build and push to Docker Hub
./build-docker.sh push
```

---

## Files Overview

| File | Purpose |
|------|---------|
| `Dockerfile` | Backend + orchestrator image |
| `Dockerfile.ui` | Frontend (Vite) image |
| `docker-compose.yml` | Dev compose (bind mounts, hot reload) |
| `docker-compose.prod.yml` | Production (nginx, named volumes) |
| `docker-compose.user.yml` | Minimal compose for users |
| `entrypoint.sh` | Config validation + backend start |
| `ui-entrypoint.sh` | Frontend start |
| `build-docker.sh` | Build/push script |
| `nginx.conf` | Production nginx config |
| `README.md` | Full documentation |

---

## Config Template (~/.antikythera/.env)

```ini
# Required
PORT=8006
VITE_API_URL=http://localhost:8006
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_PAT=your_jira_token

# AI Provider (at least one)
NVIDIA_API_KEY=your_nvidia_key
GOOGLE_API_KEY=your_google_key
OPENROUTER_API_KEY=your_openrouter_key
ANTHROPIC_API_KEY=your_anthropic_key

# Optional - Additional AI configs (in ~/.antikythera/.ai_env)
# See README.md for details
```

---

## Troubleshooting

```bash
# View logs
docker-compose logs -f

# Check config validation
docker-compose up 2>&1 | grep -E "\[ERROR\]|\[WARN\]"

# Restart services
docker-compose down && docker-compose up

# Rebuild images
docker-compose build --no-cache
```