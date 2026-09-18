"""Search: candidate rows from SQL, ranked and summarised here.

Two steps, on purpose. ``people.search_text`` answers *whether* someone matches
in SQL, over the whole directory, without sending it to the browser. Ranking and
the snippet then run over the candidates alone, where field-level weights and
the sentence that actually contains the match are available.
"""

from __future__ import annotations

from typing import Any

from naas_abi_core.services.dataset.DatasetService import DatasetService
from naas_abi_marketplace.domains.personnel.apps.people.scripts import datasets as ds
from naas_abi_marketplace.domains.personnel.apps.people.scripts.text import (
    query_tokens,
    truncate,
    words,
)

# How many people a query may rank. Beyond this the SQL filter has not narrowed
# anything and the result list is not a useful answer anyway.
CANDIDATE_LIMIT = 500
# An exact word beats a prefix: searching "audit" should put an auditor above an
# "audited" mention.
EXACT_MATCH_BONUS = 2.0


def _like_clause(tokens: list[str]) -> str:
    """Rows whose search_text contains a word starting with any token.

    search_text is single-space separated, so a word start is either the start
    of the column or a preceding space.
    """
    parts = []
    for token in tokens:
        escaped = ds.sql_literal(token + "%")
        prefixed = ds.sql_literal("% " + token + "%")
        parts.append(f"(search_text LIKE {escaped} OR search_text LIKE {prefixed})")
    return " OR ".join(parts)


def field_words(
    person: dict[str, Any], children: dict[str, list[dict[str, Any]]]
) -> dict[str, list[str]]:
    """The searchable words of one person, kept apart by field so they can be weighted."""
    return {
        "full_name": words(person.get("full_name")),
        "headline": words(person.get("headline")),
        "about": words(person.get("about")),
        "service_line": words(person.get("service_line")),
        "grade": words(person.get("grade")),
        "office": words(person.get("office")) + words(person.get("city")),
        "country": words(person.get("country")),
        "skills": [
            word
            for row in children.get("skills", [])
            for word in words(row.get("skill_name"))
        ],
        "experience": [
            word
            for row in children.get("experience", [])
            for value in (
                row.get("title"),
                row.get("organization"),
                row.get("description"),
            )
            for word in words(value)
        ],
        "education": [
            word
            for row in children.get("education", [])
            for value in (
                row.get("school"),
                row.get("degree"),
                row.get("field_of_study"),
            )
            for word in words(value)
        ],
        "certifications": [
            word
            for row in children.get("certifications", [])
            for value in (row.get("name"), row.get("issuer"))
            for word in words(value)
        ],
        "languages": [
            word
            for row in children.get("languages", [])
            for word in words(row.get("name"))
        ],
        "interests": [
            word
            for row in children.get("interests", [])
            for word in words(row.get("name"))
        ],
    }


def score(
    fields: dict[str, list[str]], tokens: list[str], weights: dict[str, float]
) -> tuple[float, int, list[str]]:
    """Rank one person against the query.

    Each token scores once, in whichever field it matches best, so repeating a
    skill across jobs does not outrank having the right name. Returns the score,
    how many tokens matched at all, and the fields that carried them.
    """
    total = 0.0
    matched = 0
    hit_fields: list[str] = []
    for token in tokens:
        best = 0.0
        best_field = None
        for field, field_word_list in fields.items():
            weight = weights.get(field, 0.0)
            if not weight:
                continue
            for word in field_word_list:
                if word == token:
                    candidate = weight * EXACT_MATCH_BONUS
                elif word.startswith(token):
                    candidate = weight
                else:
                    continue
                if candidate > best:
                    best = candidate
                    best_field = field
        if best:
            matched += 1
            total += best
            if best_field and best_field not in hit_fields:
                hit_fields.append(best_field)
    return total, matched, hit_fields


def _sentences(text: str) -> list[str]:
    out: list[str] = []
    current = ""
    for char in str(text or ""):
        current += char
        if char in ".!?":
            out.append(current.strip())
            current = ""
    if current.strip():
        out.append(current.strip())
    return out


def snippet(
    person: dict[str, Any],
    children: dict[str, list[dict[str, Any]]],
    tokens: list[str],
    *,
    length: int,
) -> dict[str, str]:
    """The line under a result: whichever part of the profile answers the query.

    Tokens already visible in the title line (name and headline) are discounted,
    so a search for "partner" does not produce a snippet repeating the job title
    the reader is looking at.
    """
    candidates: list[tuple[str, str]] = []
    for sentence in _sentences(person.get("about") or ""):
        candidates.append(("", sentence))
    if person.get("quote"):
        candidates.append(("", f"“{person['quote']}”"))
    skills = [
        row["skill_name"] for row in children.get("skills", []) if row.get("skill_name")
    ]
    if skills:
        candidates.append(("Skills", ", ".join(skills)))
    for row in children.get("experience", []):
        line = " · ".join(
            str(value) for value in (row.get("title"), row.get("organization")) if value
        )
        if line:
            candidates.append(("Experience", line))
    for row in children.get("education", []):
        line = ", ".join(
            str(value)
            for value in (
                row.get("school"),
                row.get("degree"),
                row.get("field_of_study"),
            )
            if value
        )
        if line:
            candidates.append(("Education", line))
    for row in children.get("certifications", []):
        line = ", ".join(
            str(value) for value in (row.get("name"), row.get("issuer")) if value
        )
        if line:
            candidates.append(("Certification", line))
    languages = [
        row["name"] for row in children.get("languages", []) if row.get("name")
    ]
    if languages:
        candidates.append(("Languages", ", ".join(languages)))
    for row in children.get("interests", []):
        if row.get("name"):
            candidates.append(("Interests", str(row["name"])))

    shown = set(words(person.get("full_name")) + words(person.get("headline")))
    residual = [
        token for token in tokens if not any(word.startswith(token) for word in shown)
    ]

    best: tuple[str, str] | None = None
    best_hits = 0
    if residual:
        for label, text in candidates:
            text_words = words(text)
            hits = sum(
                1
                for token in residual
                if any(word.startswith(token) for word in text_words)
            )
            if hits > best_hits:
                best = (label, text)
                best_hits = hits

    if best is None:
        lead = " ".join(_sentences(person.get("about") or "")[:2]).strip()
        return (
            {"label": "", "text": truncate(lead, length)}
            if lead
            else {"label": "", "text": ""}
        )
    return {"label": best[0], "text": truncate(best[1], length)}


def _result(person: dict[str, Any], snippet_value: dict[str, str]) -> dict[str, Any]:
    place = [person.get("country"), person.get("office") or person.get("city")]
    return {
        "slug": person.get("slug"),
        "full_name": person.get("full_name"),
        "headline": person.get("headline"),
        "photo_url": person.get("photo_url"),
        "organization": person.get("organization"),
        "service_line": person.get("service_line"),
        "grade": person.get("grade"),
        "country_code": person.get("country_code"),
        "place": [value for value in place if value],
        "snippet": snippet_value,
    }


def search(
    service: DatasetService,
    config: dict[str, Any],
    *,
    query: str = "",
    facet: str = "",
    page: int = 1,
) -> dict[str, Any]:
    """Ranked results, facet counts and the tokens the browser should highlight."""
    data = config["data"]
    namespace = data["namespace"]
    tables = data["tables"]
    search_config = config["search"]
    weights = search_config["weights"]
    page_size = search_config["page_size"]
    facet_field = search_config["facet_field"]

    tokens = query_tokens(query)
    where = _like_clause(tokens) if tokens else ""
    people = ds.fetch_people(
        service,
        namespace=namespace,
        table=tables["people"],
        where=where,
        limit=CANDIDATE_LIMIT,
    )

    slugs = [person["slug"] for person in people]
    children_by_table = {
        logical: ds.fetch_children(
            service,
            namespace=namespace,
            table=tables[logical],
            slugs=slugs,
            order_by="skill_name" if logical == "skills" else "seq",
        )
        for logical in (
            "skills",
            "experience",
            "education",
            "certifications",
            "languages",
            "interests",
        )
    }

    def children_of(slug: str) -> dict[str, list[dict[str, Any]]]:
        return {
            logical: grouped.get(slug, [])
            for logical, grouped in children_by_table.items()
        }

    scored: list[dict[str, Any]] = []
    for person in people:
        children = children_of(person["slug"])
        if tokens:
            total, matched, _ = score(field_words(person, children), tokens, weights)
            if not matched:
                continue
        else:
            total, matched = 0.0, 0
        scored.append(
            {
                "person": person,
                "children": children,
                "score": total,
                "matched": matched,
            }
        )

    mode = "all"
    if tokens:
        complete = [hit for hit in scored if hit["matched"] == len(tokens)]
        if complete or len(tokens) == 1:
            hits = complete
        else:
            # Nobody matches every word. Showing the partial matches with a
            # notice beats an empty page that looks like nobody works here.
            hits = scored
            mode = "any"
    else:
        hits = scored

    hits.sort(
        key=lambda hit: (
            -hit["matched"],
            -hit["score"],
            str(hit["person"].get("full_name") or ""),
        )
    )

    facet_counts: dict[str, int] = {}
    for hit in hits:
        value = hit["person"].get(facet_field)
        if value:
            facet_counts[str(value)] = facet_counts.get(str(value), 0) + 1

    if facet:
        hits = [
            hit for hit in hits if str(hit["person"].get(facet_field) or "") == facet
        ]

    total_hits = len(hits)
    page = max(1, int(page))
    start = (page - 1) * page_size
    window = hits[start : start + page_size]

    return {
        "query": query,
        "tokens": tokens,
        "mode": mode,
        "facet": facet,
        "facet_field": facet_field,
        "facets": [
            {"value": value, "count": count}
            for value, count in sorted(
                facet_counts.items(), key=lambda item: (-item[1], item[0])
            )
        ],
        "total": total_hits,
        "page": page,
        "page_size": page_size,
        "results": [
            _result(
                hit["person"],
                snippet(
                    hit["person"],
                    hit["children"],
                    tokens,
                    length=search_config["snippet_length"],
                ),
            )
            for hit in window
        ],
    }


def suggest(
    service: DatasetService, config: dict[str, Any], *, query: str
) -> list[dict[str, Any]]:
    """Names for the autocomplete list: fewer fields, no snippet, no scoring depth."""
    search_config = config["search"]
    tokens = query_tokens(query)
    if not tokens:
        return []
    data = config["data"]
    people = ds.fetch_people(
        service,
        namespace=data["namespace"],
        table=data["tables"]["people"],
        where=_like_clause(tokens),
        limit=CANDIDATE_LIMIT,
    )
    weights = search_config["weights"]
    ranked = []
    for person in people:
        fields = {
            "full_name": words(person.get("full_name")),
            "headline": words(person.get("headline")),
            "service_line": words(person.get("service_line")),
        }
        total, matched, _ = score(fields, tokens, weights)
        if matched:
            ranked.append((matched, total, person))
    ranked.sort(
        key=lambda item: (-item[0], -item[1], str(item[2].get("full_name") or ""))
    )
    return [
        {
            "slug": person.get("slug"),
            "full_name": person.get("full_name"),
            "headline": person.get("headline"),
            "photo_url": person.get("photo_url"),
        }
        for _, _, person in ranked[: search_config["max_suggestions"]]
    ]
