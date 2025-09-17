# Docker Troubleshooting Guide

## When Docker Won't Start

**Problem:** `make` hangs forever, containers won't start, or you get port/connection errors.

**Solution:** Follow this simple 3-step process:

### Step 1: Is Docker Running?
```bash
docker info >/dev/null 2>&1 && echo "✅ Docker OK" || echo "❌ Start Docker Desktop"
```
- If you see "❌ Start Docker Desktop": Open Docker Desktop app and wait 30 seconds
- If you see "✅ Docker OK": Continue to Step 2

### Step 2: Quick Reset (Fixes 90% of issues)
```bash
make dev-down
docker compose --profile dev up -d
```
- Wait 30 seconds, then try `make` again
- If it works: You're done! 🎉
- If still broken: Continue to Step 3

### Step 3: Hard Reset (Nuclear option)
```bash
# Stop everything
docker compose --profile dev down --remove-orphans

# Clean up stuck containers
docker container prune -f
docker network prune -f

# Restart services
docker compose --profile dev up -d
```
- Wait 60 seconds, then try `make`
- If still broken: Restart your computer (seriously, this fixes weird Docker states)

## Specific Error Messages

### "Port already in use" (5432, 7878, 3000)
**One command fix:**
```bash
lsof -tiTCP:5432,7878,3000 -sTCP:LISTEN | xargs -r kill -9 && make dev-up
```

### "Cannot connect to Docker daemon"
**Fix:** Open Docker Desktop app, wait 30 seconds, try again.

### Containers stuck in "Exited" state
**One command fix:**
```bash
docker container prune -f && make dev-up
```

### "Out of space" or memory errors
**One command fix:**
```bash
docker system prune -f && make dev-up
```

## When All Else Fails

1. **Restart your computer** - Fixes 90% of "impossible" Docker states
2. **Reinstall Docker Desktop** - For corrupted installations
3. **Ask for help** - Run `make help` for project-specific commands

## Prevention (Optional Reading)

- Always run `make dev-down` when you're done working
- Weekly cleanup: `docker system prune -f`
- Before switching branches: `make dev-down` first