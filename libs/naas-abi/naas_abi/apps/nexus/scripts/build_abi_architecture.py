"""Build a public code-architecture snapshot; never reads configuration or secrets.

Run from Nexus: python3 scripts/build_abi_architecture.py
Uses Graphify's local AST extractor (no LLM). Temporary corpus contains only
Python sources, excluding tests, migrations, virtualenvs and generated outputs.
"""

import argparse
import ast
import json
import shutil
import subprocess
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

LAYERS = [
    {
        "id": "applications",
        "label": "Agents & applications",
        "description": "ABI agents, workflows, pipelines and the Nexus application.",
        "color": "#B8A3F5",
    },
    {
        "id": "runtime",
        "label": "Execution & models",
        "description": "Engine, module lifecycle, agent execution and model abstractions.",
        "color": "#8EACF5",
    },
    {
        "id": "knowledge",
        "label": "Knowledge & data",
        "description": "Ontologies, structured datasets, vector search and the triple store.",
        "color": "#62C5C2",
    },
    {
        "id": "platform",
        "label": "Platform services",
        "description": "Service contracts for events, storage, secrets and integrations.",
        "color": "#D5B679",
    },
    {
        "id": "adapters",
        "label": "Infrastructure adapters",
        "description": "Concrete implementations of service ports; availability is not runtime health.",
        "color": "#92A4BC",
    },
]
EXCLUDED = {"node_modules", ".venv", "__pycache__", ".next", "migrations", ".git"}
RELATIONS = {
    "imports",
    "imports_from",
    "calls",
    "uses",
    "inherits",
    "references",
    "re_exports",
}


def is_test(path):
    return (
        "tests" in path.parts
        or path.name.startswith("test_")
        or path.stem.endswith("_test")
    )


def classify(path):
    p = path.parts
    if p[0] == "naas_abi":
        section = p[1] if len(p) > 2 else "module"
        name = (
            p[2].removesuffix(".py")
            if section in {"agents", "apps"} and len(p) > 2
            else section
        )
        if name == "__init__":
            section = name = "module"
        layer = "knowledge" if section == "ontologies" else "applications"
        return f"abi/{section}/{name}", name, layer
    if len(p) > 3 and p[1] == "services":
        service = p[2]
        if "adapters" in p:
            return f"adapters/{service}", service + " adapters", "adapters"
        layer = (
            "knowledge"
            if service in {"ontology", "triple_store", "vector_store", "dataset"}
            else "runtime"
            if service in {"agent", "coding_environment", "model_registry"}
            else "platform"
        )
        return f"services/{service}", service, layer
    section = p[1] if len(p) > 2 else "foundation"
    return f"core/{section}", section, "runtime"


def build(libs, graph):
    files = {}
    components = {}
    errors = []
    for package, folder in [
        ("naas-abi", "naas_abi"),
        ("naas-abi-core", "naas_abi_core"),
    ]:
        for f in sorted((libs / package / folder).rglob("*.py")):
            rel = f.relative_to(libs / package)
            if EXCLUDED.intersection(rel.parts):
                continue
            cid, name, layer = classify(rel)
            c = components.setdefault(
                cid,
                {
                    "id": cid,
                    "label": name.replace("_", " ").title() if name.islower() else name,
                    "layer": layer,
                    "files": 0,
                    "lines": 0,
                    "classes": 0,
                    "functions": 0,
                    "tests": 0,
                    "symbols": 0,
                    "sourcePaths": [],
                },
            )
            if is_test(rel):
                c["tests"] += 1
                continue
            source = f.read_text(encoding="utf-8")
            try:
                tree = ast.parse(source)
            except SyntaxError:
                errors.append(rel.as_posix())
                continue
            files[rel.as_posix()] = cid
            c["files"] += 1
            c["lines"] += len(source.splitlines())
            c["classes"] += sum(isinstance(n, ast.ClassDef) for n in ast.walk(tree))
            c["functions"] += sum(
                isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                for n in ast.walk(tree)
            )
            c["sourcePaths"].append(rel.as_posix())
    components = {k: v for k, v in components.items() if v["files"]}
    nodes = {n["id"]: files.get(n.get("source_file", "")) for n in graph["nodes"]}
    for cid in nodes.values():
        if cid in components:
            components[cid]["symbols"] += 1
    edges = Counter()
    kinds = {}
    for e in graph["edges"]:
        a, b = nodes.get(e["source"]), nodes.get(e["target"])
        if (
            a
            and b
            and a != b
            and e.get("confidence") == "EXTRACTED"
            and e.get("relation") in RELATIONS
        ):
            edges[a, b] += 1
            kinds.setdefault((a, b), Counter())[e["relation"]] += 1
    try:
        revision = subprocess.check_output(
            ["git", "-C", str(libs), "rev-parse", "--short", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except subprocess.CalledProcessError:
        revision = "unknown"
    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(UTC).isoformat(),
        "revision": revision,
        "extractor": "Graphify · local AST",
        "extractorVersion": "0.9.57",
        "scope": "Python source in naas_abi and naas_abi_core. Tests counted separately; migrations excluded. Shared code architecture, not workspace deployment or live telemetry.",
        "layers": LAYERS,
        "components": sorted(
            components.values(), key=lambda c: (c["layer"], c["label"])
        ),
        "edges": [
            {"source": a, "target": b, "count": n, "relations": dict(kinds[a, b])}
            for (a, b), n in sorted(edges.items())
        ],
        "extraction": {
            "nodes": len(graph["nodes"]),
            "edges": len(graph["edges"]),
            "skippedFiles": errors,
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--libs", type=Path, default=Path(__file__).resolve().parents[5]
    )
    parser.add_argument(
        "--graph",
        type=Path,
        help="Reuse Graphify JSON extracted from the same relative Python corpus",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "apps/web/src/app/workspace/[workspaceId]/settings/infrastructure/abi-architecture.json",
    )
    args = parser.parse_args()
    libs = args.libs.resolve()
    for package, folder in [
        ("naas-abi", "naas_abi"),
        ("naas-abi-core", "naas_abi_core"),
    ]:
        if not (libs / package / folder).is_dir():
            parser.error(f"Missing {libs / package / folder}")
    with tempfile.TemporaryDirectory(prefix="abi-architecture-") as tmp:
        tmp = Path(tmp)
        if args.graph:
            graph = json.loads(args.graph.read_text())
        else:
            corpus = tmp / "corpus"
            for package, folder in [
                ("naas-abi", "naas_abi"),
                ("naas-abi-core", "naas_abi_core"),
            ]:
                for f in (libs / package / folder).rglob("*.py"):
                    rel = f.relative_to(libs / package)
                    if EXCLUDED.intersection(rel.parts) or is_test(rel):
                        continue
                    dest = corpus / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(f, dest)
            subprocess.run(
                [
                    "uvx",
                    "--from",
                    "graphifyy==0.9.57",
                    "graphify",
                    "extract",
                    str(corpus),
                    "--code-only",
                    "--no-cluster",
                    "--max-workers",
                    "2",
                    "--out",
                    str(tmp / "result"),
                ],
                check=True,
            )
            graph = json.loads((tmp / "result/graphify-out/graph.json").read_text())
        result = build(libs, graph)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
        print(
            f"Wrote {len(result['components'])} components and {len(result['edges'])} dependencies to {args.output}"
        )


if __name__ == "__main__":
    main()
