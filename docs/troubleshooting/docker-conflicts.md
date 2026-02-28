# Docker Troubleshooting Guide

## When Docker Won't Start

**Problem:** `make local-up` hangs, containers won't start, or you get port/connection errors.

**Solution:** Follow this simple 3-step process:

### Step 1: Is Docker Running?
```bash
docker info >/dev/null 2>&1 && echo "✅ Docker OK" || echo "❌ Start Docker Desktop"
```
- If you see "❌ Start Docker Desktop": Open Docker Desktop and wait 30 seconds
- If you see "✅ Docker OK": Continue to Step 2

### Step 2: Quick Reset (Fixes 90% of issues)
```bash
make local-down
make local-up
```
- Wait 30 seconds, then try `make` again
- If it works: Done.
- If still broken: Continue to Step 3

### Step 3: Hard Reset (Nuclear option)
```bash
# Stop everything and remove orphan containers
make local-down
docker container prune -f
docker network prune -f

# Restart services
make local-up
```
- Wait 60 seconds, then try again
- If still broken: Restart your computer (this fixes persistent Docker daemon states)

## Specific Error Messages

### "Port already in use"

Common culprits and their ports:

| Service | Port |
|---|---|
| PostgreSQL | 5432 |
| Fuseki | 3030 |
| Qdrant | 6333 |
| MinIO | 9000/9001 |
| RabbitMQ | 5672/15672 |
| Redis | 6379 |
| Nexus API | 9879 |
| Dagster | 3001 |
| Oxigraph | 7878 |

Kill the conflicting process and retry:
```bash
# Find and kill process on a specific port (e.g. 5432)
lsof -tiTCP:5432 -sTCP:LISTEN | xargs -r kill -9
make local-up
```

### "Cannot connect to Docker daemon"
Open Docker Desktop, wait 30 seconds, try again.

### Containers stuck in "Exited" state
```bash
docker container prune -f && make local-up
```

### "Out of space" or memory errors
```bash
docker system prune -f && make local-up
```

## Checking Service Logs

```bash
make local-logs          # All services
make dagster-logs        # Dagster only
```

## When All Else Fails

1. **Restart your computer** — fixes 90% of "impossible" Docker states
2. **Reinstall Docker Desktop** — for corrupted installations
3. **Ask for help** — run `make help` for all available commands, or open an issue on GitHub

## Prevention

- Always run `make local-down` when done working
- Weekly cleanup: `docker system prune -f`
- Before switching branches: `make local-down` first
