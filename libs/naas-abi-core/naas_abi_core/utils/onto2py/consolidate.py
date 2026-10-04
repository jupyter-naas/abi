"""
Consolidate a module's process slices into its module ontology.

A module keeps one TTL per process under ``ontologies/processes/``. The slices
share classes (OccupationRole, Skill, ProfileDocument...), so generating Python
from each slice on its own, or chaining them with ``owl:imports``, splits one
vocabulary across several Python modules. Consolidation copies every slice's
statements into ``ontologies/modules/<Module>Ontology.ttl`` so onto2py sees the
whole vocabulary in one file.

The module ontology stays hand-authored. The copied statements live between two
markers at the end of the file and are replaced on every run:

    # >>> onto2py:consolidated-processes >>>
    ...
    # <<< onto2py:consolidated-processes <<<

Outside the markers, the only edit is removing ``owl:imports`` of the slices
themselves: their content is now inline. Slice statements are copied verbatim,
comments included. Each slice's ``owl:Ontology`` header is dropped; the
``owl:imports`` it declared are carried over to the module ontology.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import rdflib
from rdflib.namespace import OWL, RDF

REGION_START = "# >>> onto2py:consolidated-processes >>>"
REGION_END = "# <<< onto2py:consolidated-processes <<<"

_REGION_RE = re.compile(
    r"\n*" + re.escape(REGION_START) + r".*?" + re.escape(REGION_END) + r"\n?",
    re.DOTALL,
)
_PREFIX_RE = re.compile(r"^\s*@prefix\s+([A-Za-z][\w.-]*)?:\s*<([^>]*)>\s*\.\s*$")
_SPARQL_PREFIX_RE = re.compile(
    r"^\s*PREFIX\s+([A-Za-z][\w.-]*)?:\s*<([^>]*)>\s*$", re.IGNORECASE
)


@dataclass
class _Chunk:
    kind: str  # "prefix" | "statement" | "trailing"
    text: str


@dataclass
class _ParsedTtl:
    path: Path
    prefixes: dict[str, str]
    chunks: list[_Chunk]
    ontology_iri: str | None = None
    header_index: int | None = None
    imports: list[str] = field(default_factory=list)


def split_statements(text: str) -> list[_Chunk]:
    """Split Turtle into top-level chunks, keeping every character.

    Comments and blank lines before a statement stay attached to it. ``.``
    ends a statement only outside IRIs, strings, ``[]`` and ``()``, and only
    when followed by whitespace, a comment or the end of input, so decimals
    (``1.5``) and dotted local names do not split a statement.
    """
    chunks: list[_Chunk] = []
    start = 0
    i = 0
    n = len(text)
    depth = 0
    seen_token = False

    def emit(end: int) -> None:
        nonlocal start, seen_token
        piece = text[start:end]
        first = _first_code_line(piece)
        if first is not None and (
            first.lstrip().startswith("@prefix") or first.lstrip().startswith("@base")
        ):
            kind = "prefix"
        else:
            kind = "statement"
        chunks.append(_Chunk(kind, piece))
        start = end
        seen_token = False

    while i < n:
        c = text[i]
        if c == "#":
            nl = text.find("\n", i)
            i = n if nl == -1 else nl + 1
            continue
        if c.isspace():
            i += 1
            continue
        # SPARQL-style PREFIX/BASE: a directive with no terminating dot.
        if not seen_token and depth == 0:
            m = re.match(r"(PREFIX|BASE)\s", text[i:], re.IGNORECASE)
            if m:
                nl = text.find("\n", i)
                end = n if nl == -1 else nl + 1
                chunks.append(_Chunk("prefix", text[start:end]))
                start = i = end
                continue
        seen_token = True
        if c == "<":
            close = text.find(">", i + 1)
            # `<` that is not an IRI cannot occur at top level in valid Turtle.
            i = n if close == -1 else close + 1
            continue
        if c in "\"'":
            triple = c * 3
            if text.startswith(triple, i):
                close = text.find(triple, i + 3)
                while close != -1 and _escaped(text, close):
                    close = text.find(triple, close + 1)
                i = n if close == -1 else close + 3
            else:
                j = i + 1
                while j < n and text[j] != c:
                    j += 2 if text[j] == "\\" else 1
                i = j + 1
            continue
        if c in "[(":
            depth += 1
        elif c in "])":
            depth -= 1
        elif c == "." and depth == 0:
            nxt = text[i + 1] if i + 1 < n else ""
            if nxt == "" or nxt.isspace() or nxt == "#":
                # Swallow the rest of the line (a trailing comment, the newline).
                nl = text.find("\n", i)
                emit(n if nl == -1 else nl + 1)
                i = start
                continue
        i += 1

    if start < n:
        rest = text[start:]
        if rest.strip():
            chunks.append(_Chunk("statement" if seen_token else "trailing", rest))
        else:
            chunks.append(_Chunk("trailing", rest))
    return chunks


def _escaped(text: str, pos: int) -> bool:
    backslashes = 0
    while pos - 1 - backslashes >= 0 and text[pos - 1 - backslashes] == "\\":
        backslashes += 1
    return backslashes % 2 == 1


def _first_code_line(piece: str) -> str | None:
    for line in piece.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return None


def _prefix_block(prefixes: dict[str, str]) -> str:
    return "".join(f"@prefix {p}: <{iri}> .\n" for p, iri in prefixes.items())


def parse_ttl(path: Path, text: str | None = None) -> _ParsedTtl:
    """Split a TTL file and locate its ``owl:Ontology`` header statement."""
    text = path.read_text(encoding="utf-8") if text is None else text
    chunks = split_statements(text)
    prefixes: dict[str, str] = {}
    for chunk in chunks:
        if chunk.kind != "prefix":
            continue
        for line in chunk.text.splitlines():
            m = _PREFIX_RE.match(line) or _SPARQL_PREFIX_RE.match(line)
            if m:
                prefixes[m.group(1) or ""] = m.group(2)

    parsed = _ParsedTtl(path=path, prefixes=prefixes, chunks=chunks)
    header = _prefix_block(prefixes)
    for idx, chunk in enumerate(chunks):
        if chunk.kind != "statement":
            continue
        g = rdflib.Graph()
        try:
            g.parse(data=header + chunk.text, format="turtle")
        except Exception as exc:
            raise ValueError(
                f"{path}: could not parse statement:\n{chunk.text.strip()[:400]}"
            ) from exc
        onto = next(g.subjects(RDF.type, OWL.Ontology), None)
        if onto is None:
            continue
        if parsed.header_index is not None:
            raise ValueError(f"{path}: declares more than one owl:Ontology")
        parsed.ontology_iri = str(onto)
        parsed.header_index = idx
        parsed.imports = sorted(str(o) for o in g.objects(onto, OWL.imports))
    return parsed


def module_ontology_name(module_root: Path) -> str:
    """``people`` -> ``PeopleOntology``; ``hr_core`` -> ``HrCoreOntology``."""
    parts = re.split(r"[^0-9A-Za-z]+", module_root.name)
    return "".join(p[:1].upper() + p[1:] for p in parts if p) + "Ontology"


def _python_package(module_root: Path) -> str:
    """Dotted package of ``module_root``, from the outermost ``__init__.py``."""
    parts = [module_root.name]
    parent = module_root.parent
    while (parent / "__init__.py").exists():
        parts.insert(0, parent.name)
        parent = parent.parent
    return ".".join(parts)


def _iri_forms(iri: str, prefixes: dict[str, str]) -> list[str]:
    forms = [re.escape(f"<{iri}>")]
    for prefix, ns in prefixes.items():
        if iri.startswith(ns) and re.fullmatch(r"[\w-]+", iri[len(ns) :]):
            forms.append(re.escape(f"{prefix}:{iri[len(ns) :]}") + r"(?![\w:-])")
    return forms


def _drop_imports(statement: str, iris: list[str], prefixes: dict[str, str]) -> str:
    """Remove ``owl:imports <iri>`` objects for ``iris`` from a header statement."""
    for iri in iris:
        for form in _iri_forms(iri, prefixes):
            # `owl:imports X ;` on a line of its own, the common layout.
            statement = re.sub(
                r"^[ \t]*owl:imports[ \t]+" + form + r"[ \t]*;[ \t]*(#[^\n]*)?\n",
                "",
                statement,
                flags=re.MULTILINE,
            )
            # Last predicate of the statement: `; owl:imports X .`
            statement = re.sub(
                r";\s*owl:imports\s+" + form + r"\s*\.",
                " .",
                statement,
            )
            # Inline, followed by another predicate.
            statement = re.sub(r"owl:imports\s+" + form + r"\s*;\s*", "", statement)
    return statement


def build_consolidated(
    module_root: Path, existing_text: str | None = None
) -> tuple[Path, str] | None:
    """Return ``(target_path, new_text)``, or ``None`` when there are no slices."""
    module_root = Path(module_root)
    processes_dir = module_root / "ontologies" / "processes"
    process_files = (
        sorted(processes_dir.glob("*.ttl")) if processes_dir.is_dir() else []
    )
    if not process_files:
        return None

    name = module_ontology_name(module_root)
    target = module_root / "ontologies" / "modules" / f"{name}.ttl"
    slices = [parse_ttl(p) for p in process_files]
    slice_iris = [s.ontology_iri for s in slices if s.ontology_iri]

    if existing_text is None and target.exists():
        existing_text = target.read_text(encoding="utf-8")

    if existing_text is not None:
        authored = _REGION_RE.sub("\n", existing_text).rstrip() + "\n"
        module = parse_ttl(target, authored)
        if module.ontology_iri is None or module.header_index is None:
            raise ValueError(f"{target}: no owl:Ontology header to consolidate into")
        header = module.chunks[module.header_index]
        header.text = _drop_imports(header.text, slice_iris, module.prefixes)
        authored = "".join(c.text for c in module.chunks)
        module_iri = module.ontology_iri
        prefixes = dict(module.prefixes)
        declared_imports = set(parse_ttl(target, authored).imports)
    else:
        prefixes = {}
        for s in slices:
            for p, iri in s.prefixes.items():
                prefixes.setdefault(p, iri)
        prefixes.setdefault("owl", str(OWL))
        prefixes.setdefault("abi", "http://ontology.naas.ai/abi/")
        prefixes.setdefault("dc", "http://purl.org/dc/terms/")
        prefixes.setdefault("rdfs", "http://www.w3.org/2000/01/rdf-schema#")
        first = next((s.ontology_iri for s in slices if s.ontology_iri), None)
        if first is None:
            raise ValueError(
                f"{processes_dir}: no slice declares an owl:Ontology, cannot derive "
                f"the namespace for {name}"
            )
        ns = first[: max(first.rfind("/"), first.rfind("#")) + 1]
        module_iri = f"{ns}{name}"
        title = re.sub(r"(?<!^)(?=[A-Z])", " ", name)
        authored = (
            _prefix_block(prefixes)
            + f"\n<{module_iri}> a owl:Ontology ;\n"
            + f'  abi:pythonPackage "{_python_package(module_root)}" ;\n'
            + f'  abi:ontologyResource "ontologies/modules/{name}.ttl" ;\n'
            + f'  abi:pythonResource "ontologies/modules/{name}.py" ;\n'
            + f'  dc:title "{title}"@en ;\n'
            + '  rdfs:comment "Generated from ontologies/processes/*.ttl by '
            + 'onto2py consolidation."@en .\n'
        )
        declared_imports = set()

    # Prefixes a slice uses that the module does not declare go into the region.
    extra_prefixes: dict[str, str] = {}
    for s in slices:
        for p, iri in s.prefixes.items():
            known = prefixes.get(p, extra_prefixes.get(p))
            if known is None:
                extra_prefixes[p] = iri
            elif known != iri:
                raise ValueError(
                    f"{s.path}: prefix '{p}:' is <{iri}> but {target.name} "
                    f"binds it to <{known}>"
                )

    skip = set(slice_iris) | {module_iri} | declared_imports
    extra_imports = sorted({i for s in slices for i in s.imports} - skip)

    out = [
        "",
        REGION_START,
        "# Generated by naas_abi_core.utils.onto2py.consolidate from",
        "# ontologies/processes/*.ttl. Do not edit between these markers: edit the",
        "# process files and re-run onto2py on the module.",
    ]
    if extra_prefixes:
        out.append(_prefix_block(extra_prefixes).rstrip("\n"))
    if extra_imports:
        lines = [f"  owl:imports <{i}>" for i in extra_imports]
        out.append("")
        out.append(f"<{module_iri}>\n" + " ;\n".join(lines) + " .")
    for s in slices:
        rel = s.path.relative_to(module_root).as_posix()
        body = "".join(
            c.text
            for idx, c in enumerate(s.chunks)
            if c.kind != "prefix" and idx != s.header_index
        ).strip("\n")
        out += [
            "",
            "#" * 65,
            f"#    Process slice: {s.ontology_iri or s.path.stem}",
            f"#    Source: {rel}",
            "#" * 65,
            "",
            body,
        ]
    out.append(REGION_END)
    text = authored.rstrip("\n") + "\n" + "\n".join(out) + "\n"

    # Fail here rather than hand onto2py a file it cannot parse.
    try:
        rdflib.Graph().parse(data=text, format="turtle")
    except Exception as exc:
        raise ValueError(f"Consolidated {target} is not valid Turtle: {exc}") from exc
    return target, text


def consolidate_processes(module_root: str | Path) -> Path | None:
    """Write the consolidated module ontology. Returns its path, or ``None``.

    Writes only when the content changes, so the file's hash stays stable
    across runs that change nothing.
    """
    result = build_consolidated(Path(module_root))
    if result is None:
        return None
    target, text = result
    if not target.exists() or target.read_text(encoding="utf-8") != text:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return target
