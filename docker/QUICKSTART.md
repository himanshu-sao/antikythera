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
| `Dockerfile.ui` | Frontend image: Vite dev server (default), or `--target prod` for nginx with the built UI |
| `docker-compose.yml` | Dev compose (bind mounts, hot reload) |
| `docker-compose.prod.yml` | Production (nginx serving the built UI, named volumes) |
| `docker-compose.user.yml` | Minimal compose for users |
| `entrypoint.sh` | Config validation + backend start |
| `ui-entrypoint.sh` | Frontend start |
| `build-docker.sh` | Build/push script |
| `nginx.conf` | Production nginx config (baked into the `prod` image) |
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

# Back up your data (rotating 0600 archives in ~/antikythera-backups)
scripts/backup_data.sh ~/antikythera-data
```

## Notes

- **No data in the image.** `automation-ideas/` is never copied into the image; your data lives in `~/antikythera-data`. `config.yaml` (provider and model names only) is copied in.
- **`~/.antikythera` is mounted read-write** for the backend and orchestrator: the AI Engine settings page saves `ai_config.json` and `.ai_env` there. Keep it private: `chmod 700 ~/.antikythera`.
- **Rebuild after updating**, then `docker-compose up -d --force-recreate`. Old images lack `config.yaml`, so the orchestrator cannot start.
- **Rotate secrets** if you pulled an image published before commit `eac8428`: those images contained a copy of the build machine's `automation-ideas/` data. Revoke and reissue the credentials that could have been in it, and remove the old tags.