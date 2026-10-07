"""The profile's graph view: the 7-bucket person graph, fed live from this instance's graph.

The browser loads ``graph_page/GraphPage.js`` (mounted under the API prefix by
``api/mount.py``), and this module gives it its payload - built on request by
running the people competency queries against this instance's graph with
``?person`` bound to the profile's person. Bound, the queries return that
person's acts and what they reach, completely and in well under a second; run
over a directory of hundreds they take a minute and hit the row cap. A rebuilt
graph file is picked up on the next request.

``graph_page/graph-page.css`` holds the rules the page renders with, unscoped.
``graph_view_css`` serves them scoped under ``.profile-graph``, the element the
view is mounted in, so they cannot leak into the rest of the profile.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts import (
    datasets as ds,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts.graph_payload import (
    build_graph_page_payload,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts.profile_payload import (
    SLUG_PATTERN,
    ProfileNotFoundError,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts.sparql_queries import (
    fill_template,
    load_queries,
    strip_named_graph,
)
from naas_abi_marketplace.domains.intelligence.modules.people.utils.paths import (
    DEMO_GRAPH_FILE,
)
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDFS, XSD

GRAPH_PAGE_DIR = Path(__file__).resolve().parents[1] / "graph_page"
GRAPH_SCRIPTS = (
    GRAPH_PAGE_DIR / "GraphPage.js",
    GRAPH_PAGE_DIR / "graph-date-slicer.js",
)
GRAPH_CSS = GRAPH_PAGE_DIR / "graph-page.css"
GRAPH_SETTINGS = GRAPH_PAGE_DIR / "graph.yaml"
SCOPE = ".profile-graph"
PROFILE_SLUG = URIRef("http://ontology.naas.ai/abi/profile_slug")

# What the graph page draws around one person: their acts of working, the
# skills developed in them, and their acts of studying.
WORKING_QUERY = "find_working_experiences"
SKILLS_QUERY = "find_skills_developed"
STUDYING_QUERY = "find_educations"
ROW_LIMIT = 2000


def _graph_files(config: dict[str, Any]) -> list[Path]:
    graph = config["data"]["graph"]
    configured = graph.get("files") or ([graph["file"]] if graph.get("file") else [])
    return [Path(name) for name in configured] or [DEMO_GRAPH_FILE]


def _graph_key(config: dict[str, Any]) -> tuple[tuple[str, int], ...]:
    """Every graph file with its mtime, so a rebuilt file is read again."""
    return tuple((str(path), path.stat().st_mtime_ns) for path in _graph_files(config))


@lru_cache(maxsize=2)
def _graph(files: tuple[tuple[str, int], ...]) -> Graph:
    graph = Graph()
    for name, _mtime_ns in files:
        graph.parse(name, format="turtle")
    return graph


@lru_cache(maxsize=1)
def graph_settings() -> dict[str, Any]:
    return yaml.safe_load(GRAPH_SETTINGS.read_text(encoding="utf-8"))["graph"]


def _value(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, Literal):
        python = value.toPython()
        return python.isoformat() if hasattr(python, "isoformat") else python
    return str(value)


def person_rows(graph: Graph, query_name: str, person: URIRef) -> list[dict[str, Any]]:
    """One competency query's rows, with ``?person`` bound to one person."""
    sparql = fill_template(
        strip_named_graph(load_queries()[query_name]), limit=ROW_LIMIT
    )
    result = graph.query(sparql, initBindings={"person": person})
    keys = [str(var) for var in result.vars or []]
    return [{key: _value(row[key]) for key in keys} for row in result]


def person_graph_payload(
    graph: Graph, person: URIRef, *, org_label: str
) -> dict[str, Any]:
    """The graph page payload for one person and what their acts reach."""
    label = graph.value(person, RDFS.label)
    roster = (
        [{"personLabel": str(label), "organizationLabel": org_label or None}]
        if label
        else []
    )
    return build_graph_page_payload(
        roster,
        person_rows(graph, WORKING_QUERY, person),
        person_rows(graph, SKILLS_QUERY, person),
        person_rows(graph, STUDYING_QUERY, person),
    )


def person_by_slug(graph: Graph, slug: str) -> URIRef | None:
    """The person whose ``abi:profile_slug`` is ``slug``, typed or plain."""
    return next(
        (
            subject
            for literal in (Literal(slug, datatype=XSD.string), Literal(slug))
            for subject in graph.subjects(PROFILE_SLUG, literal)
            if isinstance(subject, URIRef)
        ),
        None,
    )


def graph_for(config: dict[str, Any]) -> Graph:
    """This instance's graph, read again when its file changes."""
    return _graph(_graph_key(config))


def graph_view_config(config: dict[str, Any]) -> dict[str, Any]:
    """The settings the graph page is configured with."""
    return {
        "graph": graph_settings(),
        "theme": {"bfo_buckets": config["theme"].get("bfo_buckets")},
        "app": {"pages": []},
    }


@lru_cache(maxsize=64)
def _payload(
    files: tuple[tuple[str, int], ...], slug: str, org_label: str
) -> dict[str, Any] | None:
    graph = _graph(files)
    person = person_by_slug(graph, slug)
    if person is None:
        return None
    return person_graph_payload(graph, person, org_label=org_label)


def graph_view(
    service: ds.DatasetService, config: dict[str, Any], *, slug: str
) -> dict[str, Any]:
    """The graph payload, the node to open it on, and the view's settings."""
    if not SLUG_PATTERN.match(slug):
        raise ProfileNotFoundError(slug)
    data = config["data"]
    people = ds.fetch_people(
        service,
        namespace=data["namespace"],
        table=data["tables"]["people"],
        where=f"slug = {ds.sql_literal(slug)}",
        limit=1,
    )
    if not people:
        raise ProfileNotFoundError(slug)
    person = people[0]
    payload = _payload(
        _graph_key(config),
        slug,
        person.get("organization") or "",
    )
    if payload is None:
        # In the datasets but not in the graph: the two were built apart.
        raise ProfileNotFoundError(slug)
    return {
        # The graph page keys people by their label, which is the full name
        # the directory shows.
        "root": person.get("full_name"),
        "data": payload,
        "config": graph_view_config(config),
    }


# --- stylesheet --------------------------------------------------------------

_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def _rendered_classes() -> tuple[frozenset[str], tuple[str, ...]]:
    """Class names the graph page's scripts write or look up, and the stems of
    names they build (``graph-toolbar--${layout}`` gives ``graph-toolbar--``)."""
    js = "".join(path.read_text(encoding="utf-8") for path in GRAPH_SCRIPTS)
    names: set[str] = set()
    for match in re.finditer(r'class(?:Name)?="([^"]*)"', js):
        names.update(re.findall(r"[\w-]+", re.sub(r"\$\{[^}]*\}", " ", match.group(1))))
    for match in re.finditer(r'classList\.\w+\("([\w-]+)"', js):
        names.add(match.group(1))
    for match in re.finditer(r'querySelector(?:All)?\("([^"]+)"', js):
        names.update(re.findall(r"\.([\w-]+)", match.group(1)))
    stems = tuple(name for name in names if name.endswith("-"))
    return frozenset(names) - set(stems), stems


def _selector_matches(
    selector: str, classes: frozenset[str], stems: tuple[str, ...]
) -> bool:
    return any(
        name in classes or name.startswith(stems)
        for name in re.findall(r"\.([\w-]+)", selector)
    )


def _scope(selectors: str) -> str:
    return ",\n".join(
        f"{SCOPE} {part.strip()}" for part in selectors.split(",") if part.strip()
    )


def _blocks(css: str) -> list[tuple[str, str]]:
    """Top-level ``(prelude, body)`` pairs, with @media bodies left nested."""
    blocks: list[tuple[str, str]] = []
    depth, start, prelude = 0, 0, ""
    for index, char in enumerate(css):
        if char == "{":
            if depth == 0:
                prelude, start = css[start:index].strip(), index + 1
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                blocks.append((prelude, css[start:index]))
                start = index + 1
    return blocks


def _extract(css: str, classes: frozenset[str], stems: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    for prelude, body in _blocks(css):
        if prelude.startswith("@media"):
            inner = _extract(body, classes, stems)
            if inner:
                out.append(f"{prelude} {{\n" + "\n".join(inner) + "\n}")
        elif not prelude.startswith("@") and _selector_matches(prelude, classes, stems):
            out.append(f"{_scope(prelude)} {{{body}}}")
    return out


@lru_cache(maxsize=4)
def _css(mtime_ns: int) -> str:
    del mtime_ns
    css = _COMMENT.sub("", GRAPH_CSS.read_text(encoding="utf-8"))
    rules = _extract(css, *_rendered_classes())
    header = (
        "/* graph_page/graph-page.css: the rules the graph page renders with,\n"
        f"   scoped under {SCOPE}. Edit that stylesheet, not this. */\n"
        f"{SCOPE}, {SCOPE} * {{ box-sizing: border-box; }}\n"
    )
    return header + "\n".join(rules) + "\n"


def graph_view_css() -> str:
    return _css(GRAPH_CSS.stat().st_mtime_ns)
