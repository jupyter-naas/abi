"""SPARQL provenance for each profile section."""

from __future__ import annotations

from naas_abi_marketplace.domains.personnel.apps.people import sparql_queries as sq

# Logical section id -> competency query label(s) in PersonnelSparqlQueries.ttl.
SECTION_QUERY_NAMES: dict[str, tuple[str, ...]] = {
    "about": ("find_profile_header",),
    "experience": ("find_working_processes",),
    "education": ("find_acts_of_studying",),
    "skills": ("find_person_skills",),
    "certifications": ("find_certifications",),
    "languages": ("find_languages",),
    "recommendations": ("find_recommendations",),
    "interests": ("find_interests",),
    # Built at export from profile URL + mission source URLs on acts of working.
    "sources": ("find_profile_header", "find_working_processes"),
}


def competency_queries_for_profile(slug: str) -> list[dict[str, str]]:
    """One entry per distinct competency query used on this profile."""
    seen: set[str] = set()
    queries: list[dict[str, str]] = []
    for names in SECTION_QUERY_NAMES.values():
        for name in names:
            if name in seen:
                continue
            seen.add(name)
            queries.append(
                {
                    "name": name,
                    "label": sq.format_query_label(name),
                    "text": sq.render_query(name, slug=slug),
                }
            )
    return queries


def section_sparql(section_id: str, slug: str) -> dict[str, str]:
    """Query label and filled SPARQL text for one profile section."""
    names = SECTION_QUERY_NAMES.get(section_id)
    if not names:
        return {"label": "", "text": ""}

    if len(names) == 1:
        name = names[0]
        return {
            "label": sq.format_query_label(name),
            "text": sq.render_query(name, slug=slug),
        }

    parts: list[str] = []
    for index, name in enumerate(names):
        header = f"# {name}\n"
        parts.append(header + sq.render_query(name, slug=slug))
    return {
        "label": " · ".join(sq.format_query_label(name) for name in names),
        "text": "\n\n".join(parts),
    }
