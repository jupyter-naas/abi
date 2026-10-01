"""The profile's graph view: the cockpit graph page, fed live from this instance's graph.

The view is not a copy. The browser loads the cockpit's own ``GraphPage.js``
(mounted under the API prefix by ``api/mount.py``), and this module gives it
the payload the cockpit's exporter writes to ``graph/index.json`` - built on
request by running the same competency queries against this instance's graph,
with ``?person`` bound to the profile's person. Bound, the queries return that
person's acts and what they reach, completely and in well under a second; run
over a directory of hundreds they take a minute and hit the row cap. A rebuilt
graph file is picked up on the next request.

The cockpit's stylesheet styles its whole shell, so it cannot be loaded as is.
``graph_view_css`` keeps the rules that name a class the graph page renders and
scopes each one under ``.profile-graph``, the element the view is mounted in.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from naas_abi_marketplace.domains.personnel.apps import cockpit
from naas_abi_marketplace.domains.personnel.apps.cockpit.config_loader import (
    public_config as cockpit_public_config,
)
from naas_abi_marketplace.domains.personnel.apps.cockpit.graph_query import (
    graph_page_payload,
)
from naas_abi_marketplace.domains.personnel.apps.people.scripts import datasets as ds
from naas_abi_marketplace.domains.personnel.apps.people.scripts.profile_payload import (
    SLUG_PATTERN,
    ProfileNotFoundError,
)
from naas_abi_marketplace.domains.personnel.paths import DEMO_GRAPH_FILE
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import XSD

COCKPIT_WEB = Path(cockpit.__file__).resolve().parent / "web"
COCKPIT_PAGES = COCKPIT_WEB / "components" / "pages"
COCKPIT_CSS = COCKPIT_WEB / "css" / "app.css"
GRAPH_SCRIPTS = (
    COCKPIT_PAGES / "graph" / "GraphPage.js",
    COCKPIT_PAGES / "graph" / "graph-date-slicer.js",
)
SCOPE = ".profile-graph"
PROFILE_SLUG = URIRef("http://ontology.naas.ai/personnel/profile_slug")


def _graph_file(config: dict[str, Any]) -> Path:
    configured = config["data"]["graph"].get("file")
    return Path(configured) if configured else DEMO_GRAPH_FILE


@lru_cache(maxsize=2)
def _graph(graph_file: str, mtime_ns: int) -> Graph:
    # mtime is part of the key, so a rebuilt graph file is read again.
    del mtime_ns
    return Graph().parse(graph_file, format="turtle")


@lru_cache(maxsize=64)
def _payload(
    graph_file: str, mtime_ns: int, slug: str, org_label: str
) -> dict[str, Any] | None:
    graph = _graph(graph_file, mtime_ns)
    person = next(
        (
            subject
            for literal in (Literal(slug, datatype=XSD.string), Literal(slug))
            for subject in graph.subjects(PROFILE_SLUG, literal)
        ),
        None,
    )
    if person is None:
        return None
    return graph_page_payload(graph, org_label=org_label, person=person)


def graph_view(
    service: ds.DatasetService, config: dict[str, Any], *, slug: str
) -> dict[str, Any]:
    """The cockpit graph payload, the node to open it on, and the view's settings."""
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
    graph_file = _graph_file(config)
    payload = _payload(
        str(graph_file),
        graph_file.stat().st_mtime_ns,
        slug,
        person.get("organization") or "",
    )
    if payload is None:
        # In the datasets but not in the graph: the two were built apart.
        raise ProfileNotFoundError(slug)
    cockpit_config = cockpit_public_config()
    return {
        # The cockpit keys people by their label, which is the full name the
        # directory shows.
        "root": person.get("full_name"),
        "data": payload,
        "config": {
            "graph": cockpit_config["graph"],
            "theme": {"bfo_buckets": cockpit_config["theme"].get("bfo_buckets")},
            "app": {"pages": []},
        },
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
    css = _COMMENT.sub("", COCKPIT_CSS.read_text(encoding="utf-8"))
    rules = _extract(css, *_rendered_classes())
    header = (
        "/* Generated from the cockpit's app.css: the rules its graph page uses,\n"
        f"   scoped under {SCOPE}. Edit the cockpit stylesheet, not this. */\n"
        f"{SCOPE}, {SCOPE} * {{ box-sizing: border-box; }}\n"
    )
    return header + "\n".join(rules) + "\n"


def graph_view_css() -> str:
    return _css(COCKPIT_CSS.stat().st_mtime_ns)
