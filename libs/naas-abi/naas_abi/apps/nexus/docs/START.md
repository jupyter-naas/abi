# NEXUS Quick Start

## Install & Run (2 minutes)

```bash
git clone https://github.com/jravenel/nexus.git && cd nexus
make install    # Install dependencies
make db-up      # Start database
make db-migrate # Setup tables
make db-seed    # Load demo data
make up         # Start servers
```

Visit http://localhost:3000

**Login:** alice@example.com / nexus2026

## What Is This?

NEXUS = Multi-workspace AI chat platform

- **Chat** with multiple AI providers (OpenAI, Claude, Ollama, custom)
- **Organize** in workspaces with teams
- **Stream** responses in real-time
- **Track** conversations and context
- **Deploy** anywhere (Docker, cloud, local)

## Stack

- **Frontend:** Next.js 14 + React + Tailwind
- **Backend:** FastAPI + Python 3.11
- **Database:** PostgreSQL 16
- **State:** Zustand
- **Auth:** JWT tokens

## Core Concepts

**Organization** → **Workspace** → **Agent** → **Conversation**

1. **Organization** = Company (TechCorp, Acme Inc)
2. **Workspace** = Project/Team (Platform, Sales, Research)
3. **Agent** = AI model config (GPT-4, Claude, custom system prompt)
4. **Conversation** = Chat thread with history

## Common Commands

```bash
make up          # Start dev servers
make down        # Stop servers
make logs        # View logs
make db-reset    # Reset database (deletes data!)
make test        # Run tests
```

## Project Structure

```
apps/
  api/           # FastAPI backend
    app/
      api/       # Endpoints
      models.py  # Database models
      main.py    # App entry
  web/           # Next.js frontend
    src/
      app/       # Pages
      components/
      stores/    # Zustand state
demo/            # Demo data (JSON)
docs/            # You are here
ontology/        # BFO ontology (provider specs)
```

## Key Files

- `.env` → Config (API keys, database URL)
- `Makefile` → Dev commands
- `docker-compose.yml` → Database setup
- `turbo.json` → Monorepo build config

## Need More?

- **Deploy:** See [DEPLOYMENT.md](DEPLOYMENT.md)
- **API:** See [API.md](API.md) or visit /docs endpoint
- **Issues:** See [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **Contribute:** See [CONTRIBUTING.md](../CONTRIBUTING.md)
- **Ontology:** See [docs/research/NEXUS_PROVIDERS_README.md](docs/research/NEXUS_PROVIDERS_README.md)

## Support

- GitHub Issues: https://github.com/jravenel/nexus/issues
- Email: support@naas.ai

---

**That's it.** Run `make up` and start building.
