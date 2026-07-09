"""Canonical org/model workspace layout for ABI Desktop.

Each workspace root contains one folder per organization, and each
organization contains one folder per model context::

    {workspace_root}/{org}/{model}/AGENTS.md
    {workspace_root}/{org}/{model}/MEMORY.md
    {workspace_root}/{org}/{model}/ontology.ttl
    {workspace_root}/{org}/{model}/instances.ttl
"""

from __future__ import annotations

import re
from pathlib import Path

DEFAULT_ORG = "default"
DEFAULT_MODEL = "default"

ORG_MODEL_FILES: tuple[str, ...] = (
    "AGENTS.md",
    "MEMORY.md",
    "ontology.ttl",
    "instances.ttl",
)

# Workspace-root directories that are infrastructure, not org folders.
SKIP_ORG_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        "dist",
        "build",
        ".next",
        ".cache",
    }
)

_SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def sanitize_segment(name: str) -> str:
    """Return a safe single path segment for org or model names."""
    clean = name.strip()
    if not clean or clean in {".", ".."} or "/" in clean or "\\" in clean:
        raise ValueError(f"invalid org/model name: {name!r}")
    if not _SEGMENT_RE.match(clean):
        raise ValueError(f"invalid org/model name: {name!r}")
    return clean


def org_model_path(workspace: str | Path, org: str, model: str) -> Path:
    """Absolute path to the org/model context directory."""
    root = Path(workspace).expanduser().resolve()
    return root / sanitize_segment(org) / sanitize_segment(model)


def _agents_template(org: str, model: str) -> str:
    return f"""# Agent instructions — {org}/{model}

You are the ABI Desktop agent for organization **{org}** and model context **{model}**.

## Role

Describe the agent's responsibilities, tools, and constraints for this context.

## Conventions

- Follow project standards in the workspace root.
- Persist durable notes in `MEMORY.md`.
- Use `ontology.ttl` and `instances.ttl` for structured domain knowledge.
"""


def _memory_template(org: str, model: str) -> str:
    return f"""# Memory

Persistent notes for {org}/{model}.
"""


def _ontology_template(org: str, model: str) -> str:
    return f"""@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix ex: <http://ontology.naas.ai/abi/desktop/{org}/{model}#> .

ex:Context a owl:Ontology ;
    rdfs:label "ABI Desktop context for {org}/{model}" .
"""


def _instances_template(org: str, model: str) -> str:
    return f"""@prefix ex: <http://ontology.naas.ai/abi/desktop/{org}/{model}#> .

ex:ExampleInstance a ex:ExampleClass .
"""


def scaffold_org_model(workspace: str | Path, org: str, model: str) -> Path:
    """Create org/model directory and template files when missing."""
    path = org_model_path(workspace, org, model)
    path.mkdir(parents=True, exist_ok=True)

    templates: dict[str, str] = {
        "AGENTS.md": _agents_template(org, model),
        "MEMORY.md": _memory_template(org, model),
        "ontology.ttl": _ontology_template(org, model),
        "instances.ttl": _instances_template(org, model),
    }
    for filename, content in templates.items():
        target = path / filename
        if not target.exists():
            target.write_text(content, encoding="utf-8")
    return path


def _is_org_dir(path: Path) -> bool:
    if not path.is_dir() or path.name.startswith("."):
        return False
    if path.name in SKIP_ORG_DIRS:
        return False
    try:
        return any(child.is_dir() for child in path.iterdir())
    except OSError:
        return False


def list_orgs(workspace: str | Path) -> list[str]:
    """List organization folder names under the workspace root."""
    root = Path(workspace).expanduser().resolve()
    if not root.is_dir():
        return []
    orgs = [child.name for child in root.iterdir() if _is_org_dir(child)]
    return sorted(orgs, key=str.lower)


def list_models(workspace: str | Path, org: str) -> list[str]:
    """List model folder names under an organization."""
    org_path = org_model_path(workspace, org, DEFAULT_MODEL).parent
    if not org_path.is_dir():
        return []
    models: list[str] = []
    for child in org_path.iterdir():
        if not child.is_dir() or child.name.startswith("."):
            continue
        if child.name in SKIP_ORG_DIRS:
            continue
        models.append(child.name)
    return sorted(models, key=str.lower)


def read_context_file(
    workspace: str | Path, org: str, model: str, filename: str
) -> str:
    """Read a context file when present; return empty string otherwise."""
    path = org_model_path(workspace, org, model) / filename
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def build_agent_prompt_prefix(
    workspace: str | Path, org: str, model: str
) -> str:
    """Compose AGENTS.md + MEMORY.md for chat system context injection."""
    parts: list[str] = []
    agents = read_context_file(workspace, org, model, "AGENTS.md")
    memory = read_context_file(workspace, org, model, "MEMORY.md")
    if agents:
        parts.append(agents)
    if memory:
        parts.append(memory)
    if not parts:
        return ""
    return "\n\n".join(parts) + "\n\n"


def ensure_default_context(workspace: str | Path) -> Path:
    """Scaffold the default org/model context."""
    return scaffold_org_model(workspace, DEFAULT_ORG, DEFAULT_MODEL)
