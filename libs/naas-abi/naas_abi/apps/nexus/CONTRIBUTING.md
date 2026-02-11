# Contributing to NEXUS

Thank you for your interest in contributing to NEXUS! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Code Style](#code-style)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Community](#community)

## Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md). We are committed to providing a welcoming and inclusive environment.

## Getting Started

### Prerequisites

- **Node.js** >= 18
- **Python** >= 3.11
- **PostgreSQL** >= 16
- **pnpm** >= 8.15
- **uv** (Python package manager)
- **Docker** (for database)

### Quick Start

```bash
# Clone the repository
git clone https://github.com/jravenel/nexus.git
cd nexus

# Install dependencies
make install

# Start PostgreSQL
make db-up

# Run migrations and seed demo data
make db-migrate
make db-seed

# Start dev servers
make up
```

Visit http://localhost:3000 and login with:
- Email: `alice@example.com`
- Password: `nexus2026`

## Development Setup

### Environment Configuration

```bash
# Copy example environment file
cp apps/api/.env.example apps/api/.env

# Add your API keys (optional for basic development)
nano apps/api/.env
```

Required for AI features:
- `OPENAI_API_KEY` - OpenAI models
- `ANTHROPIC_API_KEY` - Claude models
- `CLOUDFLARE_API_TOKEN` - Cloudflare Workers AI

### Database Management

```bash
make db-up        # Start PostgreSQL container
make db-migrate   # Run migrations
make db-seed      # Load demo data
make db-reset     # Reset database (WARNING: deletes all data)
```

### Development Workflow

```bash
make up           # Start API + Web servers
make test         # Run all tests
make lint         # Run linters
make format       # Format code
make check        # Run lint + typecheck + test
```

## Making Changes

### Branch Naming

- `feat/your-feature` - New features
- `fix/bug-description` - Bug fixes
- `docs/what-you-documented` - Documentation
- `refactor/what-you-refactored` - Code refactoring
- `test/what-you-tested` - Adding tests
- `chore/what-you-did` - Maintenance tasks

### Commit Message Format

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <description>

[optional body]

[optional footer]
```

**Types:**
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation only
- `style:` - Code style (formatting, no logic change)
- `refactor:` - Code restructure (no feature/bug change)
- `perf:` - Performance improvement
- `test:` - Adding tests
- `chore:` - Maintenance (deps, tooling)

**Examples:**
```
feat: add agent sync from ABI servers

fix: resolve CORS errors on inference server creation

docs: add deployment guide for Docker

refactor: extract chat streaming to separate module
```

## Code Style

### Frontend (TypeScript/React)

**Style Guide:**
- Use functional components with hooks
- Prefer `const` over `let`
- Use TypeScript types (avoid `any`)
- Use Tailwind CSS classes (avoid inline styles when possible)
- Follow Next.js 14 conventions (App Router)

**Tools:**
- ESLint for linting
- Prettier for formatting
- TypeScript for type checking

**Run checks:**
```bash
cd apps/web
pnpm lint        # ESLint
pnpm format      # Prettier
pnpm typecheck   # TypeScript
```

### Backend (Python/FastAPI)

**Style Guide:**
- Follow PEP 8
- Use type hints
- Async/await for all database operations
- Pydantic for request/response validation
- Keep routes thin (business logic in services)

**Tools:**
- Ruff for linting
- Black for formatting
- MyPy for type checking

**Run checks:**
```bash
cd apps/api
uv run ruff check .
uv run black --check .
uv run mypy .
```

### File Structure

```
apps/web/src/
├── app/              # Next.js pages (App Router)
├── components/       # React components
├── stores/           # Zustand state management
├── lib/              # Utilities
└── middleware.ts     # Next.js middleware

apps/api/app/
├── api/endpoints/    # FastAPI routes
├── services/         # Business logic
├── core/             # Config, database, logging
├── models.py         # SQLAlchemy models
└── main.py           # FastAPI app
```

## Testing

### Run Tests

```bash
# All tests
make test

# Frontend tests
cd apps/web
pnpm test

# Backend tests
cd apps/api
uv run pytest

# E2E tests
pnpm test:e2e
```

### Writing Tests

**Frontend:**
- Component tests: React Testing Library
- E2E tests: Playwright
- Store tests: Zustand testing utilities

**Backend:**
- Unit tests: pytest
- Integration tests: pytest with test database
- API tests: FastAPI TestClient

**Requirements:**
- New features require tests
- Bug fixes should include regression tests
- Aim for 80%+ coverage

## Pull Request Process

### Before Submitting

1. **Create a feature branch**
   ```bash
   git checkout -b feat/my-feature
   ```

2. **Make your changes**
   - Write code
   - Add tests
   - Update documentation

3. **Run checks**
   ```bash
   make check    # Lint, typecheck, test
   ```

4. **Commit changes**
   ```bash
   git add .
   git commit -m "feat: add my feature"
   ```

5. **Push to your fork**
   ```bash
   git push origin feat/my-feature
   ```

### Submitting PR

1. **Open Pull Request** on GitHub
2. **Fill out PR template** (description, testing, screenshots if UI change)
3. **Wait for review** - maintainers will review within 48 hours
4. **Address feedback** - make requested changes
5. **Merge** - maintainer will merge when approved

### PR Checklist

- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex logic
- [ ] Documentation updated
- [ ] Tests added/updated
- [ ] All tests passing
- [ ] No linter errors
- [ ] Commit messages follow conventions

## What to Contribute

### Good First Issues

Look for issues labeled `good-first-issue`:
- Documentation improvements
- UI polish
- Bug fixes
- Test coverage improvements

### Areas We Need Help

- **Testing** - Increase coverage, add E2E tests
- **Documentation** - Guides, tutorials, API docs
- **Integrations** - New AI providers, third-party services
- **Performance** - Optimization, caching, database queries
- **Accessibility** - A11y improvements, keyboard navigation

### Areas We DON'T Need Help (Yet)

- Major architectural changes (discuss first)
- New features without issue (create issue first)
- Breaking changes (requires RFC)

## Development Tips

### Makefile Commands

See [docs/reference/MAKEFILE.md](reference/MAKEFILE.md) for complete reference.

**Most used:**
```bash
make up          # Start dev servers
make down        # Stop servers
make test        # Run tests
make lint        # Run linters
make format      # Format code
make logs        # Show logs
make status      # Check server status
```

### Database Migrations

**Adding a migration:**

1. Create new SQL file: `apps/api/migrations/0022_your_change.sql`
2. Use sequential numbering
3. Make it idempotent (use `IF NOT EXISTS`)
4. Test with `make db-reset`

**Example:**
```sql
-- Migration: Add new field

ALTER TABLE users 
ADD COLUMN IF NOT EXISTS timezone VARCHAR(50) DEFAULT 'UTC';
```

Migrations run automatically on API startup.

### Hot Reload

Both frontend and backend have hot reload:
- **Frontend** - Next.js Fast Refresh (instant)
- **Backend** - Uvicorn auto-reload (2-3 seconds)

No need to restart servers during development.

### Debugging

**Frontend:**
- Browser DevTools
- React DevTools extension
- Console logs (automatically shown)

**Backend:**
- Logs in terminal (uvicorn output)
- Set `DEBUG=true` in `.env` for verbose logging
- Use `print()` or `logger.info()` for debugging

## Community

### Getting Help

- **GitHub Issues** - Bug reports, feature requests
- **Discussions** - Questions, ideas, show-and-tell
- **Discord** - Real-time chat (coming soon)

### Reporting Bugs

**Before reporting:**
1. Check existing issues
2. Try latest version (`git pull`)
3. Check `docs/TROUBLESHOOTING.md`

**When reporting:**
- Use bug report template
- Include steps to reproduce
- Include error messages/logs
- Include environment (OS, Node/Python versions)

### Suggesting Features

- Open GitHub Discussion first (for feedback)
- Create detailed issue if approved
- Explain use case and benefits
- Consider implementation complexity

## Recognition

Contributors are recognized in:
- GitHub contributors page
- Release notes
- README (for significant contributions)

## Questions?

- Check [docs/](docs/) for guides
- Review [README.md](README.md) for overview

