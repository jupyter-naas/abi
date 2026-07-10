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
from typing import Any

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
        "templates",
    }
)

_SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

OLLAMA_MODELS_BEGIN = "# BEGIN abi-desktop:ollama-models"
OLLAMA_MODELS_END = "# END abi-desktop:ollama-models"
_OLLAMA_BLOCK_RE = re.compile(
    rf"\n?{re.escape(OLLAMA_MODELS_BEGIN)}.*?{re.escape(OLLAMA_MODELS_END)}\n?",
    re.DOTALL,
)


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
    return f"""@prefix abid: <http://ontology.naas.ai/abi/desktop#> .
@prefix ctx: <http://ontology.naas.ai/abi/desktop/{org}/{model}#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix abi: <http://ontology.naas.ai/abi/> .

ctx:Ontology a owl:Ontology ;
    rdfs:label "ABI Desktop context for {org}/{model}"@en ;
    rdfs:comment "Extends BFO7 bucket ontologies for routing agents and documents in this org/model workspace."@en ;
    owl:imports abi:BFO7Buckets .

ctx:ChatPlanningRoute a owl:Class ;
    rdfs:subClassOf abid:SectionRoute ;
    rdfs:label "Chat section route for {org}/{model}"@en .

ctx:CodeBuildingRoute a owl:Class ;
    rdfs:subClassOf abid:SectionRoute ;
    rdfs:label "Code section route for {org}/{model}"@en .
"""


def _instances_template(org: str, model: str) -> str:
    model_uri = f"http://ontology.naas.ai/abi/desktop/{org}/{model}"
    return f"""@prefix abid: <http://ontology.naas.ai/abi/desktop#> .
@prefix abi: <http://ontology.naas.ai/abi/> .
@prefix ctx: <http://ontology.naas.ai/abi/desktop/{org}/{model}#> .
@prefix bfo: <http://purl.obolibrary.org/obo/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

ctx:org a abid:Organization ;
    abid:orgName "{org}" ;
    abid:hasModelContext ctx:model .

ctx:model a abid:ModelContext ;
    abid:modelName "{model}" ;
    abid:modelUri "{model_uri}" ;
    abid:belongsToOrg ctx:org .

# Chat (plan): role bucket (WHY) — read-only planning agent
ctx:chatRoute a ctx:ChatPlanningRoute ;
    abid:forSection "chat" ;
    abid:harnessAgent "plan" ;
    abid:usesHarness "opencode" ;
    abid:mapsToBfoProcess bfo:BFO_0000023 .

# Code (build): process bucket (WHAT) — file-editing build agent
ctx:codeRoute a ctx:CodeBuildingRoute ;
    abid:forSection "code" ;
    abid:harnessAgent "build" ;
    abid:usesHarness "opencode" ;
    abid:mapsToBfoProcess bfo:BFO_0000015 .

ctx:agentsDoc a abid:ContextDocument ;
    abid:documentPath "AGENTS.md" .

ctx:memoryDoc a abid:ContextDocument ;
    abid:documentPath "MEMORY.md" .

# Language models for ABI model router (edit to match your installed models)

ctx:modelQwenLocal a abi:LanguageModel ;
    rdfs:label "Qwen 2.5 Coder 7B (local)"@en ;
    abi:hostedAt abi:SiteLocal ;
    abi:supportsTools true ;
    abi:canRealize bfo:BFO_0000015 ;
    abi:modelRef "ollama/qwen2.5-coder:7b" .

ctx:modelGptCloud a abi:LanguageModel ;
    rdfs:label "GPT (cloud)"@en ;
    abi:hostedAt abi:SiteCloud ;
    abi:supportsTools true ;
    abi:canRealize bfo:BFO_0000015 , bfo:BFO_0000023 ;
    abi:modelRef "openai/gpt-5" .
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


def _context_templates(org: str, model: str) -> dict[str, str]:
    return {
        "ontology.ttl": _ontology_template(org, model),
        "instances.ttl": _instances_template(org, model),
    }


def repair_invalid_context_ttl(
    workspace: str | Path, org: str, model: str
) -> list[str]:
    """Re-scaffold ontology/instances when Turtle parsing fails."""
    import pyoxigraph
    from pyoxigraph import RdfFormat

    path = org_model_path(workspace, org, model)
    repaired: list[str] = []
    for filename, content in _context_templates(org, model).items():
        target = path / filename
        if not target.is_file():
            continue
        try:
            store = pyoxigraph.Store()
            store.load(path=str(target), format=RdfFormat.TURTLE)
        except Exception:
            backup = target.with_name(f"{target.name}.bak")
            if backup.exists():
                backup.unlink()
            target.rename(backup)
            target.write_text(content, encoding="utf-8")
            repaired.append(filename)
    return repaired


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


def build_agent_prompt_prefix(workspace: str | Path, org: str, model: str) -> str:
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


def _ttl_local_name(prefix: str, model_name: str) -> str:
    """Build a ctx:-safe local name from an Ollama model tag."""
    slug = re.sub(r"[^a-zA-Z0-9]", "", model_name.replace(":", "_").replace(".", "_"))
    if not slug or not slug[0].isalpha():
        slug = f"m{slug}"
    return f"{prefix}{slug[:48]}"


def _render_ollama_models_block(models: list[dict[str, Any]]) -> str:
    """Render the auto-synced LanguageModel block for instances.ttl."""
    lines = [
        "",
        OLLAMA_MODELS_BEGIN,
        "# Auto-synced from Ollama integrations (edit outside markers only)",
        "",
    ]
    for model in models:
        if not model.get("supports_tools", True):
            continue
        name = str(model.get("name") or "").strip()
        if not name:
            continue
        local = _ttl_local_name("modelOllama", name)
        label = name.replace("\\", "\\\\").replace('"', '\\"')
        lines.extend(
            [
                f"ctx:{local} a abi:LanguageModel ;",
                f'    rdfs:label "{label} (local)"@en ;',
                "    abi:hostedAt abi:SiteLocal ;",
                "    abi:supportsTools true ;",
                "    abi:canRealize bfo:BFO_0000015 , bfo:BFO_0000023 ;",
                f'    abi:modelRef "ollama/{label}" .',
                "",
            ]
        )
    lines.append(OLLAMA_MODELS_END)
    lines.append("")
    return "\n".join(lines)


def sync_ollama_models_in_instances(
    instances_path: Path, models: list[dict[str, Any]]
) -> bool:
    """Merge tool-capable Ollama models into instances.ttl between markers."""
    if not instances_path.is_file():
        return False

    content = instances_path.read_text(encoding="utf-8")
    stripped = _OLLAMA_BLOCK_RE.sub("\n", content).rstrip()
    block = _render_ollama_models_block(models)
    updated = f"{stripped}{block}"
    if updated == content:
        return False
    instances_path.write_text(updated, encoding="utf-8")
    return True
