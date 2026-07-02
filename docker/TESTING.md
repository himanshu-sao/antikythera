# Antikythera Docker Testing Guide

## Quick Local Test (Recommended)

Test the Docker setup without pushing to Docker Hub:

```bash
cd docker

# Build images locally
./build-docker.sh

# Start all services
docker-compose up

# Or start in background
docker-compose up -d

# View logs
docker-compose logs -f

# Check config validation
docker-compose up 2>&1 | grep -E "\[INFO\]|\[WARN\]|\[ERROR\]"
```

---

## Step-by-Step Testing

### 1. Test Configuration Validation

**Test with missing config:**

```bash
# Temporarily rename your config
mv ~/.antikythera/.env ~/.antikythera/.env.backup

# Try to start - should fail with clear error
docker-compose up

# Restore config
mv ~/.antikythera/.env.backup ~/.antikythera/.env
```

**Expected output:**
```
[ERROR] Configuration file not found: /root/.antikythera/.env
[ERROR] Please create this file with your credentials.
```

### 2. Test with Missing AI Key

```bash
# Temporarily remove AI keys
cp ~/.antikythera/.env ~/.antikythera/.env.backup
grep -v "API_KEY\|AUTH_TOKEN" ~/.antikythera/.env.backup > ~/.antikythera/.env

# Start - should warn but continue
docker-compose up 2>&1 | grep -A5 "WARN"

# Restore
mv ~/.antikythera/.env.backup ~/.antikythera/.env
```

**Expected output:**
```
[WARN] No AI provider API key configured.
[WARN] Add one of these to your config:
[WARN]   - NVIDIA_API_KEY
[WARN]   - GOOGLE_API_KEY
...
```

### 3. Test Individual Services

```bash
# Test backend only
docker-compose up backend

# Test frontend only
docker-compose up frontend

# Test orchestrator only
docker-compose up orchestrator
```

### 4. Test Health Checks

```bash
# Wait for services to start, then check health
docker-compose ps

# Should show all services as "healthy"
```

### 5. Test API Endpoints

```bash
# Test backend health
curl http://localhost:8006/

# Test API docs
curl http://localhost:8006/docs

# Expected:
# {"message":"Antikythera API is running"}
```

### 6. Test Data Persistence

```bash
# Create some data (via UI or API)
# Then stop containers
docker-compose down

# Verify data directory still has files
ls -la ~/antikythera-data/

# Restart - data should still be there
docker-compose up -d
```

### 7. Test Config Isolation

```bash
# Verify config is read-only inside container
docker exec antikythera-backend sh -c "echo test >> /root/.antikythera/.env"

# Expected: "Read-only file system" error
```

### 8. Full Integration Test

```bash
# Clean start
docker-compose down -v

# Create test config
cat > ~/.antikythera/.env.test << EOF
PORT=8006
VITE_API_URL=http://localhost:8006
JIRA_BASE_URL=https://test.atlassian.net
JIRA_PAT=test_token_123
NVIDIA_API_KEY=nvapi_test_key_456
EOF

# Use test config
cp ~/.antikythera/.env ~/.antikythera/.env.real
cp ~/.antikythera/.env.test ~/.antikythera/.env

# Start and verify
docker-compose up -d

# Check logs
docker-compose logs backend | grep "Configuration validation passed"

# Restore real config
cp ~/.antikythera/.env.real ~/.antikythera/.env
rm ~/.antikythera/.env.test ~/.antikythera/.env.real
```

---

## Build Verification Checklist

| Test | Command | Expected Result |
|------|---------|-----------------|
| **Build succeeds** | `./build-docker.sh` | Exit code 0, images listed |
| **Config validation (missing)** | Remove `.env`, run `docker-compose up` | `[ERROR] Configuration file not found` |
| **Config validation (empty)** | Empty `.env`, run `docker-compose up` | `[ERROR] Missing required variables` |
| **AI key warning** | No AI key in `.env` | `[WARN] No AI provider API key configured` |
| **Backend starts** | `docker-compose logs backend` | `Uvicorn running on http://0.0.0.0:8006` |
| **Frontend starts** | `docker-compose logs frontend` | `VITE ready in xxx ms` |
| **Health check passes** | `docker-compose ps` | All services show `(healthy)` |
| **API responds** | `curl http://localhost:8006/` | `{"message":"Antikythera API is running"}` |
| **UI loads** | Browser: http://localhost:5173 | Kanban board renders |
| **Data persists** | `docker-compose down` + `up`, check `~/antikythera-data/` | Files unchanged |
| **Config is read-only** | `docker exec ... echo test >> .env` | "Read-only file system" |

---

## Debugging Tips

### View Real-time Logs
```bash
docker-compose logs -f
docker-compose logs -f backend
docker-compose logs -f orchestrator
```

### Inspect Container Environment
```bash
# Check environment variables inside container
docker exec antikythera-backend env | grep -E "PORT|JIRA|API_KEY"

# Check mounted volumes
docker exec antikythera-backend mount | grep antikythera
```

### Test Network Connectivity
```bash
# Frontend can reach backend
docker exec antikythera-frontend wget -q -O- http://backend:8006/
```

### Clean Reset
```bash
# Stop all and remove containers
docker-compose down

# Also remove volumes (warning: deletes data!)
docker-compose down -v

# Rebuild without cache
docker-compose build --no-cache
```

---

## Production Image Test

After pushing to Docker Hub, test the pulled images:

```bash
# Remove local images
docker rmi himanshusao/antikythera:latest
docker rmi himanshusao/antikythera-ui:latest

# Pull from Docker Hub
docker-compose pull

# Start
docker-compose up
```

This verifies the Docker Hub images work correctly.