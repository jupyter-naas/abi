# NEXUS Troubleshooting Guide

Common issues and their solutions. If you don't find your issue here, check [GitHub Issues](https://github.com/jravenel/nexus/issues) or open a new one.

## Table of Contents

- [Installation Issues](#installation-issues)
- [Database Issues](#database-issues)
- [API Issues](#api-issues)
- [Frontend Issues](#frontend-issues)
- [Authentication Issues](#authentication-issues)
- [AI Provider Issues](#ai-provider-issues)
- [Performance Issues](#performance-issues)
- [Docker Issues](#docker-issues)

## Installation Issues

### `make install` fails

**Symptom:** Dependencies fail to install

**Solutions:**

```bash
# 1. Check Node.js version (must be >= 18)
node --version

# 2. Check Python version (must be >= 3.11)
python3 --version

# 3. Check pnpm is installed
pnpm --version
# If not: npm install -g pnpm

# 4. Check uv is installed
uv --version
# If not: curl -LsSf https://astral.sh/uv/install.sh | sh

# 5. Clear caches and retry
pnpm store prune
cd apps/api && uv cache clean && cd ../..
make install
```

### `make: command not found`

**Symptom:** `make` command not recognized

**Solutions:**

```bash
# macOS
xcode-select --install

# Ubuntu/Debian
sudo apt install build-essential

# Windows
# Use WSL2 or run commands manually from Makefile
```

### Permission denied errors

**Symptom:** `EACCES: permission denied`

**Solutions:**

```bash
# Fix npm/pnpm permissions (macOS/Linux)
sudo chown -R $USER:$GROUP ~/.npm
sudo chown -R $USER:$GROUP ~/.pnpm-store

# Don't use sudo for npm/pnpm install
```

## Database Issues

### PostgreSQL won't start

**Symptom:** `make db-up` fails or database unreachable

**Solutions:**

```bash
# 1. Check Docker is running
docker ps

# 2. Check port 5432 is not in use
lsof -i :5432
# If in use, stop the process or change port

# 3. Remove old containers
docker-compose down -v
docker-compose up -d postgres

# 4. Check logs
docker-compose logs postgres
```

### Database connection refused

**Symptom:** `FATAL: password authentication failed` or `connection refused`

**Solutions:**

```bash
# 1. Check DATABASE_URL in .env
cat apps/api/.env | grep DATABASE_URL
# Should be: postgresql+asyncpg://nexus:nexus@localhost:5432/nexus

# 2. Wait for PostgreSQL to be ready
docker-compose logs postgres | grep "ready to accept connections"
# Should appear twice (takes ~5-10 seconds)

# 3. Test connection manually
docker exec nexus-postgres psql -U nexus -d nexus -c "SELECT 1;"

# 4. Recreate database
make db-reset
```

### Migrations fail

**Symptom:** `sqlalchemy.exc.ProgrammingError` or migration errors

**Solutions:**

```bash
# 1. Check migration files
ls -la apps/api/migrations/
# Ensure sequential numbering (0001, 0002, 0003...)

# 2. Check for duplicates
ls apps/api/migrations/ | cut -d_ -f1 | sort | uniq -d
# Should return nothing

# 3. Manually run migrations
cd apps/api
uv run python -c "import asyncio; from app.core.database import init_db; asyncio.run(init_db())"

# 4. Reset database if needed
make db-reset
```

### Seeding fails

**Symptom:** `ForeignKeyViolationError` or `IntegrityError`

**Solutions:**

```bash
# 1. Run migrations first
make db-migrate

# 2. Check demo data files
ls -la demo/*.json
# Ensure all JSON files are valid

# 3. Reset and reseed
make db-reset

# 4. Check for foreign key mismatches
# Example: agents.json references workspace-nexus but it doesn't exist
grep -r "workspace-nexus" demo/
```

### Database is too large

**Symptom:** Running out of disk space

**Solutions:**

```bash
# 1. Check database size
docker exec nexus-postgres psql -U nexus -d nexus -c "SELECT pg_size_pretty(pg_database_size('nexus'));"

# 2. Check table sizes
docker exec nexus-postgres psql -U nexus -d nexus -c "
SELECT tablename, pg_size_pretty(pg_total_relation_size(tablename::regclass)) 
FROM pg_tables 
WHERE schemaname='public' 
ORDER BY pg_total_relation_size(tablename::regclass) DESC;"

# 3. Clean old conversations (example)
docker exec nexus-postgres psql -U nexus -d nexus -c "
DELETE FROM conversations WHERE created_at < NOW() - INTERVAL '90 days';"

# 4. Vacuum database
docker exec nexus-postgres psql -U nexus -d nexus -c "VACUUM FULL ANALYZE;"
```

## API Issues

### API won't start

**Symptom:** `make up` shows errors for API

**Solutions:**

```bash
# 1. Check logs
make logs
# Or: cd apps/api && uv run uvicorn app.main:app --reload

# 2. Check port 8000 is not in use
lsof -i :8000
# Kill process: kill -9 <PID>

# 3. Check environment file exists
ls -la apps/api/.env
# Create from example: cp apps/api/.env.example apps/api/.env

# 4. Check Python dependencies
cd apps/api
uv sync
uv run python -c "import fastapi; print('OK')"

# 5. Check database connection
uv run python -c "
import asyncio
from app.core.database import async_engine
async def test():
    async with async_engine.begin() as conn:
        await conn.execute('SELECT 1')
    print('Database OK')
asyncio.run(test())
"
```

### API returns 500 errors

**Symptom:** Internal server errors

**Solutions:**

```bash
# 1. Check API logs
make logs
# Look for stack traces

# 2. Enable debug mode
echo "DEBUG=true" >> apps/api/.env
make restart

# 3. Test API health
curl http://localhost:8000/health

# 4. Check database connection
curl http://localhost:8000/docs
# If FastAPI docs load, API is running

# 5. Check specific endpoint
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","password":"nexus2026"}'
```

### CORS errors

**Symptom:** `Access-Control-Allow-Origin` errors in browser console

**Solutions:**

```bash
# 1. Check CORS_ORIGINS in .env
cat apps/api/.env | grep CORS_ORIGINS_STR
# Should include your frontend URL

# 2. Update CORS_ORIGINS for development
echo 'CORS_ORIGINS_STR=http://localhost:3000' >> apps/api/.env

# 3. For production, use actual domain
echo 'CORS_ORIGINS_STR=https://nexus.yourdomain.com' >> apps/api/.env

# 4. Restart API
make restart
```

### Slow API responses

**Symptom:** Requests take > 1 second

**Solutions:**

```bash
# 1. Check database query performance
docker exec nexus-postgres psql -U nexus -d nexus -c "
SELECT query, calls, total_time, mean_time 
FROM pg_stat_statements 
ORDER BY mean_time DESC LIMIT 10;"

# 2. Enable query logging
echo "LOG_QUERIES=true" >> apps/api/.env
make restart

# 3. Add database indexes (example)
docker exec nexus-postgres psql -U nexus -d nexus -c "
CREATE INDEX IF NOT EXISTS idx_conversations_workspace ON conversations(workspace_id);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);"

# 4. Check for N+1 queries
# Look in logs for repeated similar queries
```

## Frontend Issues

### Frontend won't start

**Symptom:** `make up` shows errors for web

**Solutions:**

```bash
# 1. Check logs
cd apps/web
pnpm dev

# 2. Check port 3000 is not in use
lsof -i :3000
# Kill process: kill -9 <PID>

# 3. Clear Next.js cache
rm -rf apps/web/.next
rm -rf apps/web/node_modules/.cache

# 4. Reinstall dependencies
cd apps/web
rm -rf node_modules pnpm-lock.yaml
pnpm install

# 5. Check Node.js version
node --version
# Must be >= 18
```

### Build fails

**Symptom:** `pnpm build` errors

**Solutions:**

```bash
# 1. Check for TypeScript errors
cd apps/web
pnpm typecheck

# 2. Check for linting errors
pnpm lint

# 3. Clear cache and rebuild
rm -rf .next node_modules/.cache
pnpm build

# 4. Check environment variables
cat .env.local
# Ensure NEXT_PUBLIC_API_URL is set

# 5. Increase Node memory (if out of memory)
export NODE_OPTIONS="--max-old-space-size=4096"
pnpm build
```

### White screen on load

**Symptom:** Frontend loads but shows blank page

**Solutions:**

```bash
# 1. Check browser console for errors
# Open DevTools (F12) and look for red errors

# 2. Check API is running
curl http://localhost:8000/health

# 3. Check API URL in frontend
# Inspect Network tab in DevTools
# Requests should go to http://localhost:8000

# 4. Check for hydration errors
# Look for "Hydration failed" in console
# Usually means server/client HTML mismatch

# 5. Clear browser cache
# Hard reload: Ctrl+Shift+R (Windows) or Cmd+Shift+R (Mac)
```

### Images not loading

**Symptom:** Uploaded logos/avatars show as broken images

**Solutions:**

```bash
# 1. Check uploads directory exists
ls -la apps/api/uploads/
# Should have logos/ and avatars/ subdirectories

# 2. Check file permissions
chmod -R 755 apps/api/uploads/

# 3. Check API serves static files
curl http://localhost:8000/uploads/logos/test.png
# Should return image or 404 (not 500)

# 4. Check full URL in browser console
# Should be: http://localhost:8000/uploads/logos/filename.png

# 5. Verify CORS headers for static files
curl -I http://localhost:8000/uploads/logos/test.png
# Should include Access-Control-Allow-Origin header
```

## Authentication Issues

### Can't login

**Symptom:** Login button does nothing or shows error

**Solutions:**

```bash
# 1. Check demo users exist
docker exec nexus-postgres psql -U nexus -d nexus -c "SELECT email FROM users;"

# 2. Try demo credentials
# Email: alice@example.com
# Password: nexus2026

# 3. Check API login endpoint
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","password":"nexus2026"}'
# Should return {"access_token": "...", "refresh_token": "..."}

# 4. Check browser console for errors
# Look for network errors or CORS issues

# 5. Reset demo data
make db-reset
```

### Session expired immediately

**Symptom:** Login works but immediately redirected back

**Solutions:**

```bash
# 1. Check SECRET_KEY is set
cat apps/api/.env | grep SECRET_KEY
# Should be at least 32 characters

# 2. Check token expiration
# Default is 1 day - inspect JWT token at jwt.io

# 3. Check system time
date
# If time is wrong, JWT validation will fail

# 4. Clear browser cookies
# DevTools → Application → Cookies → Clear All

# 5. Check for multiple API instances
ps aux | grep uvicorn
# Kill duplicates: kill -9 <PID>
```

### "Unauthorized" on every request

**Symptom:** 401 errors after login

**Solutions:**

```bash
# 1. Check auth header is sent
# Browser DevTools → Network → Request Headers
# Should include: Authorization: Bearer <token>

# 2. Check token is valid
# Copy token from localStorage
# Decode at jwt.io - check expiration

# 3. Check CORS credentials
# Frontend should use credentials: 'include' for fetch

# 4. Logout and login again
# Tokens might be corrupted

# 5. Check API authentication middleware
make logs | grep "401"
```

## AI Provider Issues

### OpenAI: Rate limit errors

**Symptom:** `RateLimitError` in logs

**Solutions:**

```bash
# 1. Check API key is valid
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# 2. Check your OpenAI usage/limits
# Visit: https://platform.openai.com/usage

# 3. Wait and retry (rate limits reset)
# Free tier: 3 requests/minute
# Tier 1: 60 requests/minute

# 4. Use different model
# gpt-4 has stricter limits than gpt-3.5-turbo

# 5. Add retry logic (already implemented)
```

### Anthropic: API key invalid

**Symptom:** `AuthenticationError` for Claude models

**Solutions:**

```bash
# 1. Check API key format
cat apps/api/.env | grep ANTHROPIC_API_KEY
# Should start with: sk-ant-

# 2. Test API key
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{"model":"claude-3-sonnet-20240229","max_tokens":10,"messages":[{"role":"user","content":"Hi"}]}'

# 3. Generate new API key
# Visit: https://console.anthropic.com/settings/keys

# 4. Update .env and restart
echo "ANTHROPIC_API_KEY=sk-ant-..." >> apps/api/.env
make restart
```

### Ollama: Connection refused

**Symptom:** Can't connect to local Ollama

**Solutions:**

```bash
# 1. Check Ollama is running
curl http://localhost:11434/api/tags

# 2. Start Ollama
ollama serve

# 3. Pull a model
ollama pull llama2

# 4. Configure NEXUS to use Ollama
# In UI: Settings → Servers → Add Server
# Name: Ollama
# Type: Ollama
# Endpoint: http://localhost:11434

# 5. Check CORS (if Ollama in Docker)
# Set OLLAMA_ORIGINS=* in Ollama environment
```

### ABI server: Models not syncing

**Symptom:** "Sync Agents" does nothing

**Solutions:**

```bash
# 1. Check ABI server is reachable
curl https://your-abi-server.com/health

# 2. Check health path in server config
# UI: Settings → Servers → Edit Server
# Health Path: /health (or custom path)

# 3. Check API logs during sync
make logs | grep "abi_sync"

# 4. Manually test ABI endpoint
curl https://your-abi-server.com/models

# 5. Check agent table after sync
docker exec nexus-postgres psql -U nexus -d nexus -c "SELECT name, source FROM agent_configs;"
```

### Streaming stops mid-response

**Symptom:** Chat response cuts off early

**Solutions:**

```bash
# 1. Check browser console for errors
# Look for EventSource or fetch errors

# 2. Check API timeout settings
# In nginx: proxy_read_timeout should be high (300s)

# 3. Test streaming endpoint directly
curl -N http://localhost:8000/api/chat/stream \
  -H "Authorization: Bearer <token>" \
  -d '{"message":"Hello","agent_id":"..."}'

# 4. Check provider API limits
# Some providers have response length limits

# 5. Check for network interruptions
# Streaming requires stable connection
```

## Performance Issues

### Slow page loads

**Symptom:** Pages take > 3 seconds to load

**Solutions:**

```bash
# 1. Check database query time
# Add indexes for frequently queried columns

# 2. Enable Redis caching (optional)
docker-compose up -d redis
echo "REDIS_URL=redis://localhost:6379/0" >> apps/api/.env

# 3. Optimize frontend bundle
cd apps/web
pnpm build --analyze

# 4. Check network waterfall
# Browser DevTools → Network → Waterfall
# Look for slow requests

# 5. Enable HTTP/2 in production
# Nginx config: listen 443 ssl http2;
```

### High memory usage

**Symptom:** System running out of RAM

**Solutions:**

```bash
# 1. Check Docker memory
docker stats

# 2. Limit PostgreSQL memory
# Edit postgresql.conf:
# shared_buffers = 256MB
# work_mem = 16MB

# 3. Limit Node.js memory
export NODE_OPTIONS="--max-old-space-size=2048"

# 4. Check for memory leaks
# Monitor API: docker stats nexus-api
# If memory keeps growing, restart API

# 5. Use connection pooling (already enabled)
# Check pool size in database.py
```

### Database queries slow

**Symptom:** Queries take > 500ms

**Solutions:**

```bash
# 1. Enable slow query logging
docker exec nexus-postgres psql -U nexus -d nexus -c "
ALTER SYSTEM SET log_min_duration_statement = 500;
SELECT pg_reload_conf();"

# 2. Check logs for slow queries
docker logs nexus-postgres | grep "duration:"

# 3. Analyze query plan
docker exec nexus-postgres psql -U nexus -d nexus -c "
EXPLAIN ANALYZE SELECT * FROM conversations WHERE workspace_id = '...';"

# 4. Add indexes
docker exec nexus-postgres psql -U nexus -d nexus -c "
CREATE INDEX idx_conversations_workspace ON conversations(workspace_id);
CREATE INDEX idx_messages_conversation ON messages(conversation_id);
CREATE INDEX idx_agent_configs_workspace ON agent_configs(workspace_id);"

# 5. Run VACUUM
docker exec nexus-postgres psql -U nexus -d nexus -c "VACUUM ANALYZE;"
```

## Docker Issues

### Docker Compose fails

**Symptom:** `make db-up` or `docker-compose up` errors

**Solutions:**

```bash
# 1. Check Docker is installed and running
docker --version
docker ps

# 2. Check Docker Compose is installed
docker-compose --version
# Or: docker compose version (newer syntax)

# 3. Check docker-compose.yml syntax
docker-compose config

# 4. Remove old containers
docker-compose down -v
docker-compose up -d

# 5. Check logs
docker-compose logs
```

### Port conflicts

**Symptom:** `port is already allocated`

**Solutions:**

```bash
# 1. Find process using port
lsof -i :5432  # PostgreSQL
lsof -i :8000  # API
lsof -i :3000  # Frontend

# 2. Kill process
kill -9 <PID>

# 3. Or change port in docker-compose.yml
# ports:
#   - "5433:5432"  # Use 5433 instead

# 4. Update DATABASE_URL to use new port
echo "DATABASE_URL=postgresql+asyncpg://nexus:nexus@localhost:5433/nexus" > apps/api/.env
```

### Volume permission errors

**Symptom:** Can't write to mounted volumes

**Solutions:**

```bash
# 1. Fix ownership
sudo chown -R $USER:$USER .

# 2. Check Docker volume permissions
docker volume inspect nexus_postgres_data

# 3. Recreate volume
docker-compose down -v
docker-compose up -d

# 4. On Linux, check SELinux
# Add :z flag to volume: ./uploads:/app/uploads:z
```

## Still Having Issues?

### Collect Debug Info

```bash
# System info
uname -a
node --version
python3 --version
docker --version

# Application status
make status
docker ps
docker-compose logs

# Environment
cat apps/api/.env | grep -v "KEY\|SECRET\|TOKEN"
env | grep -E "NODE_|PYTHON_|DOCKER_"

# Database status
docker exec nexus-postgres psql -U nexus -d nexus -c "\dt"
docker exec nexus-postgres psql -U nexus -d nexus -c "SELECT version();"
```

### Get Help

1. **Search existing issues**: [GitHub Issues](https://github.com/jravenel/nexus/issues)
2. **Ask the community**: [GitHub Discussions](https://github.com/jravenel/nexus/discussions)
3. **Report a bug**: [New Issue](https://github.com/jravenel/nexus/issues/new)
4. **Email support**: support@naas.ai

When reporting issues, include:
- NEXUS version (`git rev-parse HEAD`)
- Operating system
- Node.js and Python versions
- Error messages and logs
- Steps to reproduce

---

**Need more help?** Check out the [full documentation](../README.md) or join our community.
