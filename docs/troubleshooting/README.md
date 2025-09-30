# Troubleshooting Guide

Quick fixes for common ABI issues.

## Common Issues

### 🔧 [Docker Won't Start](docker-conflicts.md)
**Symptoms:** `make` hangs, containers won't start, port conflicts  
**Quick Fix:** `make dev-down && docker compose --profile dev up -d`

### 🎯 [Embedding Dimension Errors](embedding-dimensions.md)
**Symptoms:** `ValueError: could not broadcast input array from shape (768,) into shape (1536,)`  
**Quick Fix:** System now auto-detects dimensions and uses provider-specific caches

## Error Messages

| Error | Solution |
|-------|----------|
| `Port already in use` | `lsof -tiTCP:5432,7878,3000 -sTCP:LISTEN \| xargs -r kill -9 && make dev-up` |
| `Cannot connect to Docker daemon` | Open Docker Desktop, wait 30 seconds |
| `could not broadcast input array` | [See embedding dimensions guide](embedding-dimensions.md) |
| `Application crashed due to agent loading failure` | Usually embedding dimension mismatch - see above |

## Quick Diagnostics

```bash
# Check Docker status
docker info >/dev/null 2>&1 && echo "✅ Docker OK" || echo "❌ Start Docker Desktop"

# Check embedding dimensions
python -c "from lib.abi.services.agent.beta.Embeddings import embeddings; print('Dimension:', len(embeddings('test')))"

# Check cache structure
ls -la storage/cache/intent_mapping/
```

## When All Else Fails

1. **Restart your computer** - Fixes 90% of "impossible" states
2. **Clear all caches** - `rm -rf storage/cache/*`
3. **Hard Docker reset** - `docker system prune -f && make dev-up`
4. **Ask for help** - Run `make help` for project commands
