# Makefile Reference

Run `make help` at any time to see all available commands with descriptions.

## Environment Setup

| Command | Description |
|---|---|
| `make` | Default: runs help menu |
| `uv sync --all-extras` | Install all dependencies (run after clone or pull) |
| `make install` | Install dependencies via uv |
| `make add dep=<pkg>` | Add a dependency to the root project |
| `make abi-add dep=<pkg>` | Add a dependency to the `lib/abi` package |
| `make lock` | Update uv.lock files after manual pyproject.toml changes |
| `make build` | Build Docker image (linux/amd64) |

## Starting Services

| Command | Description |
|---|---|
| `make local-up` | Start all local services (Oxigraph, PostgreSQL, Dagster, etc.) |
| `make local-down` | Stop and remove all local services |
| `make local-stop` | Stop services without removing containers |
| `make local-logs` | Tail logs for all running services |
| `make oxigraph-up` | Start only the Oxigraph triple store |
| `make oxigraph-down` | Stop only Oxigraph |
| `make oxigraph-status` | Check Oxigraph container status |

## Running Agents (CLI)

| Command | Description |
|---|---|
| `make chat-abi-agent` | Start the main ABI agent in terminal |
| `make chat-naas-agent` | Start the Naas platform agent |
| `make chat-support-agent` | Start the support agent |
| `make chat-ontology-agent` | Start the ontology engineer agent |
| `make chat-qwen-agent` | Local Qwen3 8B model (privacy-focused) |
| `make chat-deepseek-agent` | Local DeepSeek R1 8B |
| `make chat-gemma-agent` | Local Gemma3 4B |

## API and MCP

| Command | Description |
|---|---|
| `make api` | Start the REST API server on port 9879 |
| `make api-prod` | Run production API in Docker |
| `make api-local` | Run API with Docker volume mounting |
| `make mcp` | Start MCP server in STDIO mode (Claude Desktop) |
| `make mcp-http` | Start MCP server in HTTP mode on port 8000 |
| `make mcp-test` | Run MCP integration validation tests |

## Knowledge Graph

| Command | Description |
|---|---|
| `make sparql-terminal` | Interactive SPARQL query terminal |
| `make oxigraph-admin` | Oxigraph database admin interface |
| `make oxigraph-explorer` | Web-based knowledge graph explorer (http://localhost:7878) |
| `make triplestore-export-excel` | Export knowledge graph to Excel |
| `make triplestore-export-turtle` | Export knowledge graph to Turtle/RDF |
| `make triplestore-prod-pull` | Pull triple store from production |
| `make triplestore-prod-override` | Override production with local data |

## Orchestration (Dagster)

| Command | Description |
|---|---|
| `make dagster-dev` | Start Dagster development server |
| `make dagster-up` | Start Dagster in background |
| `make dagster-down` | Stop Dagster |
| `make dagster-ui` | Open Dagster web interface (http://localhost:3001) |
| `make dagster-status` | Check asset status |
| `make dagster-materialize` | Manually trigger all assets |
| `make dagster-logs` | View Dagster logs |

## Testing and Quality

| Command | Description |
|---|---|
| `make test` | Run all tests with pytest |
| `make test-abi` | Test the abi library specifically |
| `make test-api` | Test API functionality |
| `make ftest` | Interactive fuzzy test selector |
| `make check` | Run all code quality checks |
| `make check-core` | Check core modules |
| `make check-marketplace` | Check marketplace modules |
| `make fmt` | Format code with ruff |
| `make bandit` | Run security scan |

## Data Management

| Command | Description |
|---|---|
| `make datastore-pull` | Pull datastore from remote |
| `make datastore-push` | Push local datastore to remote |
| `make storage-pull` | Pull storage data |
| `make storage-push` | Push storage changes |

## Publishing

| Command | Description |
|---|---|
| `make publish-remote-agents` | Publish agents to NaasAI workspace |
| `make publish-remote-agents-dry-run` | Preview publishing without committing |
| `make pull-request-description` | Generate PR description with AI |
| `make docs-ontology` | Generate ontology documentation |

## Docker

| Command | Description |
|---|---|
| `make local-build` | Build all containers |
| `make docker-cleanup` | Clean up Docker conflicts |
| `make trivy-container-scan` | Security scan containers |
| `make clean` | Remove build artifacts, caches, and containers |

## Service URLs (when running)

| Service | URL |
|---|---|
| Nexus Web UI | http://localhost:3042 |
| Nexus API | http://localhost:9879 |
| YasGUI (SPARQL) | http://localhost:3000 |
| Service Portal | http://localhost:8080 |
| MCP Server (HTTP) | http://localhost:8000 |
| Oxigraph | http://localhost:7878 |
| Dagster | http://localhost:3001 |
| Fuseki | http://localhost:3030 |
| PostgreSQL | localhost:5432 |
| Qdrant | http://localhost:6333 |
| MinIO | http://localhost:9000 / 9001 |
| RabbitMQ | http://localhost:15672 |
| Redis | localhost:6379 |
| Matrix/Synapse | http://localhost:8008 |
| Element Web | http://localhost:8081 |
