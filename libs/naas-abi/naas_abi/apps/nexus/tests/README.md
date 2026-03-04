# NEXUS Testing Guide

## Overview

NEXUS uses **PostgreSQL** for ALL environments (development, production, **and testing**).

## Why PostgreSQL for Tests?

**Consistency with production:**
- Production uses PostgreSQL
- Test environment uses the same engine and dialect

**Result:** Identical behavior between tests and production.

## Requirements

**Docker must be running** (for PostgreSQL test database).

```bash
# Start PostgreSQL
make db-up

# Run tests
make test
```

## Test Database Lifecycle

Each test gets a **fresh, isolated database**:

1. **Before test:** Drop `nexus_test` → Create `nexus_test` → Apply all migrations
2. **Run test:** Isolated from other tests
3. **After test:** Drop `nexus_test` (cleanup)

## Test Configuration

**Test database:** `postgresql://nexus:nexus@localhost:5432/nexus_test`
**Configured in:** `apps/api/tests/conftest.py`

```python
TEST_DB_NAME = "nexus_test"
TEST_DATABASE_URL_SYNC = f"postgresql://nexus:nexus@localhost:5432/{TEST_DB_NAME}"
TEST_DATABASE_URL_ASYNC = f"postgresql+asyncpg://nexus:nexus@localhost:5432/{TEST_DB_NAME}"
```

## Running Tests

```bash
# All tests
make test

# Watch mode (reruns on file change)
make test-watch

# With coverage
make test-cov

# Specific test
cd apps/api && uv run pytest tests/test_auth.py -v
```

### Local PostgreSQL notes

- `make test` depends on `make db-up`, which starts a dockerized PostgreSQL 16 instance with the `nexus` superuser. No local superuser is required.
- Ensure Docker is running and port 5432 is available. If you already have Postgres bound on 5432, stop it or adjust the compose port mapping.
- The tests create and drop a database named `nexus_test`. If you choose to point tests at your own Postgres instead of Docker, set `DATABASE_URL` accordingly and ensure the user has `CREATEDB` privilege.

## Manual Test Scripts

Located in `tests/manual/`:
- `test_security_features.py`: Security feature validation
- `test_websocket.js`: WebSocket connection testing

## CI/CD

GitHub Actions should:
1. Start PostgreSQL service container
2. Wait for ready (`pg_isready`)
3. Run `make test`

**Example `.github/workflows/test.yml`:**
```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: nexus
          POSTGRES_PASSWORD: nexus
          POSTGRES_DB: nexus_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
    steps:
      - uses: actions/checkout@v3
      - name: Install dependencies
        run: make install
      - name: Run tests
        run: make test
```

## Troubleshooting

**Error: `connection refused`**
```bash
# Check if PostgreSQL is running
docker ps | grep nexus-postgres

# If not, start it
make db-up
```

**Error: `database "nexus_test" is being accessed by other users`**
```bash
# Terminate all connections
docker-compose exec postgres psql -U nexus -d postgres -c "
  SELECT pg_terminate_backend(pid)
  FROM pg_stat_activity
  WHERE datname = 'nexus_test' AND pid <> pg_backend_pid();
"
```

**Tests pass locally but fail in CI**
- Ensure CI has PostgreSQL service container
- Check `pg_isready` health check passes
- Verify port mapping (5432:5432)

## Performance

**PostgreSQL test database is fast:**
- Each test completes in ~50-200ms
- Fresh DB per test ensures isolation

## Migration Testing

All migrations in `apps/api/migrations/*.sql` are applied for tests to mirror production.

---

**Last updated:** 2026-02-08  
**Legacy note:** Earlier versions mentioned SQLite during transition; current setup is PostgreSQL-only.
