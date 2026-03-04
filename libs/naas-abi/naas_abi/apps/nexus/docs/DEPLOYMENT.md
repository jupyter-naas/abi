# NEXUS Deployment Guide

Complete guide for deploying NEXUS in development, staging, and production environments.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Prerequisites](#prerequisites)
- [Development Deployment](#development-deployment)
- [Production Deployment](#production-deployment)
- [Environment Variables](#environment-variables)
- [Database Setup](#database-setup)
- [Troubleshooting](#troubleshooting)

## Architecture Overview

NEXUS consists of three main components:

```
┌─────────────┐     ┌─────────────┐     ┌──────────────┐
│             │────▶│             │────▶│              │
│  Next.js    │     │  FastAPI    │     │ PostgreSQL   │
│  Frontend   │◀────│  Backend    │◀────│  Database    │
│  (port 3000)│     │  (port 8000)│     │  (port 5432) │
└─────────────┘     └─────────────┘     └──────────────┘
```

**Additional services (optional):**
- Redis (caching, sessions)
- MinIO (S3-compatible file storage)

## Prerequisites

### Development
- Node.js >= 18
- Python >= 3.11
- pnpm >= 8.15
- uv (Python package manager)
- Docker (for PostgreSQL)
- Git

### Production
- Same as development, plus:
- Reverse proxy (Nginx/Caddy/Traefik)
- SSL certificate (Let's Encrypt)
- Domain name
- Server with >= 4GB RAM

## Development Deployment

### Quick Start (Recommended)

```bash
# 1. Clone repository
git clone https://github.com/jravenel/nexus.git
cd nexus

# 2. Install dependencies
make install

# 3. Start PostgreSQL
make db-up

# 4. Run migrations and seed demo data
make db-migrate
make db-seed

# 5. Start dev servers
make up

# Access at http://localhost:3000
# API docs at http://localhost:8000/docs
```

### Manual Setup

```bash
# Frontend
cd apps/web
pnpm install
pnpm dev  # Runs on http://localhost:3000

# Backend
cd apps/api
cp .env.example .env  # Configure environment
uv sync               # Install dependencies
uv run uvicorn app.main:app --reload --port 8000

# Database
docker-compose up -d postgres
```

## Production Deployment

### Option 1: Docker Compose (Recommended)

**Full `docker-compose.yml` example:**

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: nexus
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: nexus
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped

  api:
    build:
      context: .
      dockerfile: apps/api/Dockerfile
    environment:
      DATABASE_URL: postgresql+asyncpg://nexus:${DB_PASSWORD}@postgres:5432/nexus
      SECRET_KEY: ${SECRET_KEY}
      REDIS_URL: redis://redis:6379/0
      DEBUG: "false"
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  web:
    build:
      context: .
      dockerfile: apps/web/Dockerfile
    environment:
      NEXT_PUBLIC_API_URL: https://api.yourdomain.com
    depends_on:
      - api
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./certs:/etc/nginx/certs
    depends_on:
      - web
      - api
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

**Deploy:**
```bash
# Set environment variables
export DB_PASSWORD="your-strong-password"
export SECRET_KEY="your-secret-key"

# Start services
docker-compose up -d

# Run migrations
docker-compose exec api python -c "import asyncio; from app.core.database import init_db; asyncio.run(init_db())"

# Check status
docker-compose ps
docker-compose logs -f
```

### Option 2: Manual Production Deployment

#### 1. Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install prerequisites
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs postgresql-16 python3.11 nginx

# Install pnpm and uv
npm install -g pnpm
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### 2. Application Setup

```bash
# Clone repository
git clone https://github.com/jravenel/nexus.git
cd nexus

# Install dependencies
pnpm install
cd apps/api && uv sync && cd ../..
```

#### 3. Configure Environment

```bash
# Backend environment
cat > apps/api/.env << EOF
NEXUS_ENV=production
DEBUG=false
DATABASE_URL=postgresql+asyncpg://nexus:STRONG_PASSWORD@localhost:5432/nexus
SECRET_KEY=$(openssl rand -hex 32)
CORS_ORIGINS_STR=https://nexus.yourdomain.com
REDIS_URL=redis://localhost:6379/0
EOF

# Frontend environment
cat > apps/web/.env.production << EOF
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
EOF
```

#### 4. Database Setup

```bash
# Create database and user
sudo -u postgres psql << EOF
CREATE DATABASE nexus;
CREATE USER nexus WITH PASSWORD 'STRONG_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE nexus TO nexus;
EOF

# Run migrations
cd apps/api
uv run python -c "import asyncio; from app.core.database import init_db; asyncio.run(init_db())"
```

#### 5. Build Frontend

```bash
cd apps/web
pnpm build
```

#### 6. Process Management (systemd)

**API service:**
```ini
# /etc/systemd/system/nexus-api.service
[Unit]
Description=NEXUS API
After=network.target postgresql.service

[Service]
Type=simple
User=nexus
WorkingDirectory=/opt/nexus/apps/api
Environment="PATH=/opt/nexus/apps/api/.venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/opt/nexus/apps/api/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

**Frontend service:**
```ini
# /etc/systemd/system/nexus-web.service
[Unit]
Description=NEXUS Web
After=network.target

[Service]
Type=simple
User=nexus
WorkingDirectory=/opt/nexus/apps/web
Environment="PATH=/usr/bin:/bin"
ExecStart=/usr/bin/pnpm start
Restart=always

[Install]
WantedBy=multi-user.target
```

**Enable services:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable nexus-api nexus-web
sudo systemctl start nexus-api nexus-web
sudo systemctl status nexus-api nexus-web
```

#### 7. Nginx Configuration

```nginx
# /etc/nginx/sites-available/nexus
upstream api {
    server localhost:8000;
}

upstream web {
    server localhost:3000;
}

# API subdomain
server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts for streaming
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
}

# Frontend
server {
    listen 443 ssl http2;
    server_name nexus.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/nexus.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/nexus.yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://web;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name api.yourdomain.com nexus.yourdomain.com;
    return 301 https://$host$request_uri;
}
```

**Enable site:**
```bash
sudo ln -s /etc/nginx/sites-available/nexus /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

#### 8. SSL Certificate (Let's Encrypt)

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Get certificates
sudo certbot --nginx -d nexus.yourdomain.com -d api.yourdomain.com

# Auto-renewal (already configured)
sudo certbot renew --dry-run
```

## Environment Variables

### Required

```bash
# Backend (apps/api/.env)
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/nexus
SECRET_KEY=your-secret-key-min-32-chars
CORS_ORIGINS_STR=https://nexus.yourdomain.com

# Frontend (apps/web/.env.production)
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
```

### Optional (AI Providers)

```bash
# OpenAI
OPENAI_API_KEY=sk-...

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Cloudflare Workers AI
CLOUDFLARE_API_TOKEN=...
CLOUDFLARE_ACCOUNT_ID=...

# File Storage (S3/R2)
S3_ENDPOINT=https://...
S3_ACCESS_KEY=...
S3_SECRET_KEY=...
S3_BUCKET=nexus-files
```

### Full Reference

See [apps/api/.env.example](apps/api/.env.example) for complete list with descriptions.

## Database Setup

### PostgreSQL Configuration

**For production, tune PostgreSQL:**

```bash
# Edit postgresql.conf
sudo nano /etc/postgresql/16/main/postgresql.conf
```

**Recommended settings:**
```ini
# Memory
shared_buffers = 256MB           # 25% of RAM
effective_cache_size = 1GB       # 50-75% of RAM
work_mem = 16MB                  # Per operation
maintenance_work_mem = 128MB     # For VACUUM, CREATE INDEX

# Connections
max_connections = 100

# Write Ahead Log (WAL)
wal_buffers = 16MB
checkpoint_completion_target = 0.9

# Query Planner
random_page_cost = 1.1           # For SSD
effective_io_concurrency = 200   # For SSD
```

### Backups

**Automated daily backups:**

```bash
# Create backup script
cat > /opt/nexus/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR=/opt/nexus/backups
DATE=$(date +%Y%m%d_%H%M%S)
pg_dump -U nexus nexus | gzip > $BACKUP_DIR/nexus_$DATE.sql.gz
# Keep only last 30 days
find $BACKUP_DIR -name "nexus_*.sql.gz" -mtime +30 -delete
EOF

chmod +x /opt/nexus/backup.sh

# Add to crontab
crontab -e
# Add: 0 2 * * * /opt/nexus/backup.sh
```

### Restore from Backup

```bash
# Stop services
sudo systemctl stop nexus-api nexus-web

# Restore database
gunzip -c /opt/nexus/backups/nexus_YYYYMMDD_HHMMSS.sql.gz | psql -U nexus -d nexus

# Start services
sudo systemctl start nexus-api nexus-web
```

## Monitoring

### Health Checks

```bash
# API health
curl https://api.yourdomain.com/health

# Frontend health
curl https://nexus.yourdomain.com/

# Database health
docker exec nexus-postgres pg_isready -U nexus
```

### Logs

```bash
# Application logs
sudo journalctl -u nexus-api -f
sudo journalctl -u nexus-web -f

# Database logs
sudo tail -f /var/log/postgresql/postgresql-16-main.log

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Metrics (Optional)

Consider adding:
- **Prometheus** - Metrics collection
- **Grafana** - Visualization
- **Sentry** - Error tracking
- **DataDog** - APM

## Scaling

### Horizontal Scaling

**Frontend (stateless):**
```bash
# Run multiple Next.js instances behind load balancer
pm2 start pnpm --name nexus-web-1 -- start
pm2 start pnpm --name nexus-web-2 -- start
```

**Backend (stateless):**
```bash
# Run multiple FastAPI instances
gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

**Database (read replicas):**
```bash
# Configure PostgreSQL read replicas
# Update connection strings to route reads to replicas
```

### Vertical Scaling

**Increase resources:**
- 2 CPU cores → 4-8 cores
- 4GB RAM → 8-16GB RAM
- Standard SSD → NVMe SSD

## Troubleshooting

### API won't start

```bash
# Check logs
docker-compose logs api

# Common issues:
# 1. Database not ready - wait for PostgreSQL to start
# 2. Missing .env file - copy from .env.example
# 3. Port 8000 in use - kill process: lsof -ti:8000 | xargs kill
```

### Frontend won't build

```bash
# Clear Next.js cache
rm -rf apps/web/.next
pnpm dev

# Check Node.js version
node --version  # Should be >= 18
```

### Database connection error

```bash
# Check PostgreSQL is running
docker ps | grep postgres

# Test connection
psql postgresql://nexus:nexus@localhost:5432/nexus

# Check DATABASE_URL in .env
cat apps/api/.env | grep DATABASE_URL
```

### Migrations fail

```bash
# Check migration files
ls apps/api/migrations/

# Manually run migrations
cd apps/api
uv run python -c "import asyncio; from app.core.database import init_db; asyncio.run(init_db())"

# Check for duplicate migration numbers
ls apps/api/migrations/ | grep "^0016"  # Should have only one
```

### CORS errors

```bash
# Update CORS_ORIGINS in .env
CORS_ORIGINS_STR=http://localhost:3000,https://nexus.yourdomain.com

# Restart API
make restart
```

For more troubleshooting, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## Performance Optimization

### Frontend
- Enable Next.js image optimization
- Use CDN for static assets
- Enable HTTP/2 on Nginx
- Implement service worker caching

### Backend
- Enable Redis caching for API responses
- Use connection pooling (already configured)
- Optimize database queries (add indexes)
- Use async operations everywhere (already done)

### Database
- Create indexes on frequently queried columns
- Run `VACUUM ANALYZE` weekly
- Monitor slow queries
- Consider read replicas for high traffic

## Security Hardening

See [SECURITY.md](SECURITY.md) for complete security guide.

**Production checklist:**
- [ ] HTTPS enabled (SSL certificate)
- [ ] Strong passwords (database, SECRET_KEY)
- [ ] CORS restricted to production domains
- [ ] DEBUG=false in production
- [ ] Security headers enabled (CSP, HSTS)
- [ ] Database backups configured
- [ ] Firewall rules configured
- [ ] Rate limiting enabled (already built-in)
- [ ] Audit logging enabled (already built-in)

## Updates & Maintenance

### Updating NEXUS

```bash
# Pull latest code
git pull origin main

# Install dependencies
make install

# Run migrations
make db-migrate

# Restart services
make restart
```

### Dependency Updates

```bash
# Frontend
cd apps/web
pnpm update

# Backend
cd apps/api
uv lock --upgrade
```

### Database Maintenance

```bash
# Vacuum (reclaim space)
docker exec nexus-postgres psql -U nexus -d nexus -c "VACUUM ANALYZE;"

# Check database size
docker exec nexus-postgres psql -U nexus -d nexus -c "SELECT pg_size_pretty(pg_database_size('nexus'));"

# Check table sizes
docker exec nexus-postgres psql -U nexus -d nexus -c "SELECT tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) FROM pg_tables WHERE schemaname='public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"
```

## Cost Estimation

### Small Team (5-10 users)
- **Server**: $20-40/month (DigitalOcean/Linode - 4GB RAM)
- **Database**: Included (same server)
- **Storage**: $5/month (50GB)
- **Total**: ~$25-45/month

### Medium Team (50-100 users)
- **Server**: $80-120/month (8GB RAM, 4 cores)
- **Database**: $40/month (managed PostgreSQL)
- **Storage**: $20/month (200GB)
- **CDN**: $10/month
- **Total**: ~$150-190/month

### Enterprise (500+ users)
- **App Servers**: $300/month (load balanced)
- **Database**: $200/month (replicas, backups)
- **Storage**: $100/month (1TB+)
- **CDN**: $50/month
- **Monitoring**: $50/month
- **Total**: ~$700+/month

## Support

- **Documentation**: [docs/](docs/)
- **Issues**: [GitHub Issues](https://github.com/jravenel/nexus/issues)
- **Community**: [GitHub Discussions](https://github.com/jravenel/nexus/discussions)
- **Email**: support@naas.ai

---

**Happy deploying!** 🚀
