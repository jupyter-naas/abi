"""Build the graph page payload: people, their acts of working and studying, and what those acts reach.

Generic over people: what a module that keeps internal records adds (an HR
roster's properties, an employee role) comes in through the roster rows'
``properties`` and ``roleClass`` / ``roleClassLabel`` / ``roleProperties``.

The canvas is explored breadth-first from the focused person, so which edges are
drawn decides what appears at each distance:

    distance 1  the acts of working and studying, and everything hanging directly
                off the person - the missions and profile document they carry,
                the occupation/student roles and skills they bear
    distance 2  what those acts reach - organization, site, temporal region,
                enrollment record
    distance 3  the temporal instants bounding each temporal region

``abi:hasWorkLocation`` / ``abi:hasStudyLocation`` (person → site)
are emitted with ``canvas=False``: they belong in the data, but drawing them would
pull Site up to distance 1 and collapse the layering above.
"""

from __future__ import annotations

import re

from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts.process_class_catalog import (
    build_process_class_catalog,
)

# Any naas.ai vocabulary namespace, compacted to its own prefix:
# http://ontology.naas.ai/people/Skill/x -> abi:Skill/x
_NAAS_NS = re.compile(r"^http://ontology\.naas\.ai/([a-zA-Z_]+)/(.+)$")


def _prop(uri: str, label: str, value: str | None) -> dict | None:
    if value is None or value == "":
        return None
    return {"uri": uri, "label": label, "value": str(value)}


def compact_graph_id(uri: str | None) -> str | None:
    """Compact a naas.ai individual URI to ``<prefix>:…`` (``people:…``, ``abi:…``)."""
    if not uri:
        return None
    text = str(uri).rstrip("/")
    match = _NAAS_NS.match(text)
    if match:
        return f"{match.group(1)}:{match.group(2)}"
    return text


def _entity_node(
    entity_id: str,
    *,
    label: str,
    class_uri: str,
    class_label: str,
    bfo_bucket: str,
    is_working_hub: bool = False,
    started_at: str | None = None,
    ended_at: str | None = None,
    properties: list[dict] | None = None,
) -> dict:
    """One canvas node.

    ``startedAt`` / ``endedAt`` are the ISO bounds of the node's temporal region,
    carried so the UI can order processes by recency and keep only the most
    recent ones per class.
    """
    return {
        "id": entity_id,
        "nodeKind": "entity",
        "label": label,
        "classUri": class_uri,
        "classLabel": class_label,
        "bfoBucket": bfo_bucket,
        "isWorkingHub": is_working_hub,
        "startedAt": started_at,
        "endedAt": ended_at,
        "properties": properties or [],
    }


def build_graph_page_payload(
    roster_rows: list[dict],
    working_rows: list[dict] | None = None,
    skill_rows: list[dict] | None = None,
    studying_rows: list[dict] | None = None,
    *,
    process_class_catalog: dict | None = None,
) -> dict:
    """Return people, entities and relations for ``graph/index.json``.

    ``roster_rows`` name the people to draw even when no act reaches them:
    ``personLabel`` and ``organizationLabel``, optionally ``kind``,
    ``job_title``, ``properties`` (extra ``{uri, label, value}`` items) and a
    ``role`` with its ``roleClass``, ``roleClassLabel`` and ``roleProperties``.
    """
    people_map: dict[str, dict] = {}
    entities_map: dict[str, dict] = {}
    relations: list[dict] = []

    def ensure_person(
        label: str,
        *,
        kind: str = "person",
        job_title: str | None = None,
        organization_label: str | None = None,
        extra_properties: list[dict] | None = None,
    ) -> None:
        if not label:
            return
        existing = people_map.get(label)
        props = [
            item
            for item in (
                _prop("abi:job_title", "job title", job_title),
                _prop("abi:organizationLabel", "organization", organization_label),
            )
            if item
        ] + list(extra_properties or [])

        if existing:
            # A kind other than the default is a promotion (an "employee" in an
            # HR roster): never demote it back to a plain person.
            if kind != "person":
                existing["kind"] = kind
            for key, val in (
                ("job_title", job_title),
                ("organizationLabel", organization_label),
            ):
                if val:
                    existing[key] = val
            if props:
                existing["properties"] = props
            return

        people_map[label] = {
            "id": label,
            "label": label,
            "kind": kind,
            "nodeKind": "person",
            "classUri": "abi:Person",
            "classLabel": "Person",
            "bfoBucket": "Material Entity",
            "job_title": job_title,
            "organizationLabel": organization_label,
            "properties": props,
        }

    def add_entity(entity: dict) -> str:
        if entity["id"] not in entities_map:
            entities_map[entity["id"]] = entity
        return entity["id"]

    def add_rel(
        from_id: str,
        to_id: str,
        predicate_uri: str,
        predicate_label: str,
        *,
        canvas: bool = True,
    ) -> None:
        rel = {
            "from": from_id,
            "to": to_id,
            "predicateUri": predicate_uri,
            "predicateLabel": predicate_label,
            "canvas": canvas,
        }
        if rel not in relations:
            relations.append(rel)

    for row in roster_rows:
        label = row.get("personLabel")
        if not label:
            continue
        ensure_person(
            label,
            kind=row.get("kind") or "person",
            job_title=row.get("job_title"),
            organization_label=row.get("organizationLabel"),
            extra_properties=row.get("properties"),
        )
        # Someone with no act of working still bears the role their record
        # documents; without this edge they would sit on the canvas alone.
        role_id = compact_graph_id(row.get("role"))
        if role_id and row.get("job_title"):
            add_entity(
                _entity_node(
                    role_id,
                    label=row["job_title"],
                    class_uri=row.get("roleClass") or "abi:OccupationRole",
                    class_label=row.get("roleClassLabel") or "Occupation Role",
                    bfo_bucket="Realizable",
                    properties=[
                        p
                        for p in (
                            _prop(
                                "abi:job_title", "job title", row.get("job_title")
                            ),
                        )
                        if p
                    ]
                    + list(row.get("roleProperties") or []),
                )
            )
            add_rel(
                label,
                role_id,
                row.get("rolePredicate") or "abi:hasOccupationRole",
                row.get("rolePredicateLabel") or "has occupation role",
            )

    seen_workings: set[str] = set()

    for work in working_rows or []:
        subject = work.get("personLabel")
        if not subject:
            continue
        ensure_person(subject, kind="person")

        working_id = compact_graph_id(work.get("working"))
        if not working_id or working_id in seen_workings:
            continue
        seen_workings.add(working_id)

        org_label = work.get("orgLabel")
        title = work.get("roleLabel") or work.get("jobTitle") or "Act of Working"

        # --- WHAT: the act itself -----------------------------------------
        add_entity(
            _entity_node(
                working_id,
                label=work.get("workingLabel") or f"{title} @ {org_label}",
                class_uri="abi:ActOfWorking",
                class_label="Act of Working",
                bfo_bucket="Process",
                is_working_hub=True,
                started_at=work.get("temporalStart"),
                ended_at=work.get("temporalEnd"),
                properties=[
                    p
                    for p in (
                        _prop("abi:isActOfWorkingOf", "worker", subject),
                        _prop("abi:forOrganization", "organization", org_label),
                        _prop("abi:forClient", "client", work.get("clientLabel")),
                        _prop("abi:job_title", "job title", work.get("jobTitle")),
                        _prop(
                            "abi:employment_type",
                            "employment type",
                            work.get("employmentType"),
                        ),
                        _prop(
                            "abi:hasFirstInstant", "start", work.get("temporalStart")
                        ),
                        _prop("abi:hasLastInstant", "end", work.get("temporalEnd")),
                        _prop(
                            "abi:duration_label",
                            "duration",
                            work.get("durationLabel"),
                        ),
                    )
                    if p
                ],
            )
        )
        add_rel(subject, working_id, "abi:hasActOfWorking", "has act of working")

        # --- WHO: the employer --------------------------------------------
        org_id = compact_graph_id(work.get("org"))
        if org_id and org_label:
            add_entity(
                _entity_node(
                    org_id,
                    label=org_label,
                    class_uri="abi:Organization",
                    class_label="Organization",
                    bfo_bucket="Material Entity",
                )
            )
            add_rel(working_id, org_id, "abi:forOrganization", "for organization")

        # --- WHO: the client a consulting engagement was performed for -----
        client_id = compact_graph_id(work.get("client"))
        if client_id and work.get("clientLabel"):
            add_entity(
                _entity_node(
                    client_id,
                    label=work["clientLabel"],
                    class_uri="abi:Organization",
                    class_label="Organization",
                    bfo_bucket="Material Entity",
                )
            )
            add_rel(working_id, client_id, "abi:forClient", "for client")

        # --- WHERE: the site of execution ---------------------------------
        site_id = compact_graph_id(work.get("site"))
        site_label = work.get("siteLabel")
        if site_id and site_label:
            add_entity(
                _entity_node(
                    site_id,
                    label=site_label,
                    class_uri="abi:Site",
                    class_label="Site",
                    bfo_bucket="Site",
                )
            )
            add_rel(working_id, site_id, "abi:occursIn", "occurs in")
            # Data-only: drawing this would lift Site to distance 1.
            add_rel(
                subject,
                site_id,
                "abi:hasWorkLocation",
                "has work location",
                canvas=False,
            )

        # --- WHEN: temporal region, then its bounding instants ------------
        temporal_id = compact_graph_id(work.get("temporal"))
        if temporal_id and work.get("temporalLabel"):
            add_entity(
                _entity_node(
                    temporal_id,
                    label=work["temporalLabel"],
                    class_uri="abi:TemporalRegion",
                    class_label="Temporal Region",
                    bfo_bucket="Temporal Region",
                    started_at=work.get("temporalStart"),
                    ended_at=work.get("temporalEnd"),
                    properties=[
                        p
                        for p in (
                            _prop(
                                "abi:duration_label",
                                "duration",
                                work.get("durationLabel"),
                            ),
                        )
                        if p
                    ],
                )
            )
            add_rel(
                working_id,
                temporal_id,
                "abi:occupiesTemporalRegion",
                "occupies temporal region",
            )

            for uri_key, label_key, date_key, predicate, predicate_label in (
                (
                    "firstInstant",
                    "firstInstantLabel",
                    "temporalStart",
                    "abi:hasFirstInstant",
                    "has first instant",
                ),
                (
                    "lastInstant",
                    "lastInstantLabel",
                    "temporalEnd",
                    "abi:hasLastInstant",
                    "has last instant",
                ),
            ):
                instant_id = compact_graph_id(work.get(uri_key))
                if not instant_id:
                    continue
                add_entity(
                    _entity_node(
                        instant_id,
                        label=work.get(label_key) or work.get(date_key) or "instant",
                        class_uri="abi:TemporalInstant",
                        class_label="Temporal Instant",
                        bfo_bucket="Temporal Region",
                        started_at=work.get(date_key),
                        ended_at=work.get(date_key),
                        properties=[
                            p
                            for p in (
                                _prop(
                                    "abi:instant_date",
                                    "instant date",
                                    work.get(date_key),
                                ),
                            )
                            if p
                        ],
                    )
                )
                add_rel(temporal_id, instant_id, predicate, predicate_label)

        # --- WHY: the role, and the mission it concretizes ----------------
        role_id = compact_graph_id(work.get("role"))
        mission_id = compact_graph_id(work.get("mission"))
        if role_id and work.get("roleLabel"):
            add_entity(
                _entity_node(
                    role_id,
                    label=work["roleLabel"],
                    class_uri="abi:OccupationRole",
                    class_label="Occupation Role",
                    bfo_bucket="Realizable",
                    properties=[
                        p
                        for p in (
                            _prop(
                                "abi:job_title", "job title", work.get("jobTitle")
                            ),
                            _prop("abi:forOrganization", "organization", org_label),
                        )
                        if p
                    ],
                )
            )
            add_rel(working_id, role_id, "abi:realizes", "realizes")
            add_rel(subject, role_id, "abi:hasOccupationRole", "has occupation role")

        if mission_id and work.get("missionLabel"):
            add_entity(
                _entity_node(
                    mission_id,
                    label=work["missionLabel"],
                    class_uri="abi:Mission",
                    class_label="Mission",
                    bfo_bucket="GDC",
                    properties=[
                        p
                        for p in (
                            _prop(
                                "abi:mission_content",
                                "mission content",
                                work.get("missionContent"),
                            ),
                            _prop("abi:forOrganization", "organization", org_label),
                        )
                        if p
                    ],
                )
            )
            add_rel(
                subject,
                mission_id,
                "abi:hasMissionCarried",
                "carries mission",
            )
            if role_id:
                add_rel(role_id, mission_id, "abi:hasMission", "has mission")

            # --- HOW WE KNOW: where the mission was read from -------------
            profile_id = compact_graph_id(work.get("profile"))
            if profile_id and work.get("profileLabel"):
                add_entity(
                    _entity_node(
                        profile_id,
                        label=work["profileLabel"],
                        class_uri="abi:ProfileDocument",
                        class_label="Profile Document",
                        bfo_bucket="GDC",
                        properties=[
                            p
                            for p in (
                                _prop(
                                    "abi:source_url",
                                    "source url",
                                    work.get("sourceUrl"),
                                ),
                            )
                            if p
                        ],
                    )
                )
                add_rel(
                    subject,
                    profile_id,
                    "abi:hasProfileDocument",
                    "has profile document",
                )
                add_rel(
                    mission_id,
                    profile_id,
                    "abi:isSourcedFrom",
                    "is sourced from",
                )

    seen_studyings: set[str] = set()

    for study in studying_rows or []:
        subject = study.get("personLabel")
        if not subject:
            continue
        ensure_person(subject, kind="person")

        studying_id = compact_graph_id(study.get("studying"))
        if not studying_id or studying_id in seen_studyings:
            continue
        seen_studyings.add(studying_id)

        org_label = study.get("orgLabel")
        program = (
            study.get("programName") or study.get("roleLabel") or "Act of Studying"
        )

        add_entity(
            _entity_node(
                studying_id,
                label=study.get("studyingLabel") or f"{program} @ {org_label}",
                class_uri="abi:ActOfStudying",
                class_label="Act of Studying",
                bfo_bucket="Process",
                started_at=study.get("temporalStart"),
                ended_at=study.get("temporalEnd"),
                properties=[
                    p
                    for p in (
                        _prop("abi:isActOfStudyingOf", "student", subject),
                        _prop(
                            "abi:forEducationalOrganization",
                            "organization",
                            org_label,
                        ),
                        _prop(
                            "abi:program_name", "program", study.get("programName")
                        ),
                        _prop(
                            "abi:hasFirstInstant", "start", study.get("temporalStart")
                        ),
                        _prop("abi:hasLastInstant", "end", study.get("temporalEnd")),
                        _prop(
                            "abi:duration_label",
                            "duration",
                            study.get("durationLabel"),
                        ),
                    )
                    if p
                ],
            )
        )
        add_rel(subject, studying_id, "abi:hasActOfStudying", "has act of studying")

        org_id = compact_graph_id(study.get("org"))
        if org_id and org_label:
            add_entity(
                _entity_node(
                    org_id,
                    label=org_label,
                    class_uri="abi:Organization",
                    class_label="Organization",
                    bfo_bucket="Material Entity",
                )
            )
            add_rel(
                studying_id,
                org_id,
                "abi:forEducationalOrganization",
                "for educational organization",
            )

        site_id = compact_graph_id(study.get("site"))
        site_label = study.get("siteLabel")
        if site_id and site_label:
            add_entity(
                _entity_node(
                    site_id,
                    label=site_label,
                    class_uri="abi:Site",
                    class_label="Site",
                    bfo_bucket="Site",
                )
            )
            add_rel(studying_id, site_id, "abi:occursIn", "occurs in")
            add_rel(
                subject,
                site_id,
                "abi:hasStudyLocation",
                "has study location",
                canvas=False,
            )

        temporal_id = compact_graph_id(study.get("temporal"))
        if temporal_id and study.get("temporalLabel"):
            add_entity(
                _entity_node(
                    temporal_id,
                    label=study["temporalLabel"],
                    class_uri="abi:TemporalRegion",
                    class_label="Temporal Region",
                    bfo_bucket="Temporal Region",
                    started_at=study.get("temporalStart"),
                    ended_at=study.get("temporalEnd"),
                    properties=[
                        p
                        for p in (
                            _prop(
                                "abi:duration_label",
                                "duration",
                                study.get("durationLabel"),
                            ),
                        )
                        if p
                    ],
                )
            )
            add_rel(
                studying_id,
                temporal_id,
                "abi:occupiesTemporalRegion",
                "occupies temporal region",
            )

            for uri_key, label_key, date_key, predicate, predicate_label in (
                (
                    "firstInstant",
                    "firstInstantLabel",
                    "temporalStart",
                    "abi:hasFirstInstant",
                    "has first instant",
                ),
                (
                    "lastInstant",
                    "lastInstantLabel",
                    "temporalEnd",
                    "abi:hasLastInstant",
                    "has last instant",
                ),
            ):
                instant_id = compact_graph_id(study.get(uri_key))
                if not instant_id:
                    continue
                add_entity(
                    _entity_node(
                        instant_id,
                        label=study.get(label_key) or study.get(date_key) or "instant",
                        class_uri="abi:TemporalInstant",
                        class_label="Temporal Instant",
                        bfo_bucket="Temporal Region",
                        started_at=study.get(date_key),
                        ended_at=study.get(date_key),
                        properties=[
                            p
                            for p in (
                                _prop(
                                    "abi:instant_date",
                                    "instant date",
                                    study.get(date_key),
                                ),
                            )
                            if p
                        ],
                    )
                )
                add_rel(temporal_id, instant_id, predicate, predicate_label)

        enrollment_id = compact_graph_id(study.get("enrollment"))
        if enrollment_id and study.get("enrollmentLabel"):
            add_entity(
                _entity_node(
                    enrollment_id,
                    label=study.get("programName") or study["enrollmentLabel"],
                    class_uri="abi:EnrollmentRecord",
                    class_label="Enrollment Record",
                    bfo_bucket="GDC",
                    properties=[
                        p
                        for p in (
                            _prop(
                                "abi:program_name",
                                "program",
                                study.get("programName"),
                            ),
                        )
                        if p
                    ],
                )
            )
            add_rel(
                studying_id, enrollment_id, "abi:hasEnrollment", "has enrollment"
            )

        role_id = compact_graph_id(study.get("role"))
        if role_id and study.get("roleLabel"):
            add_entity(
                _entity_node(
                    role_id,
                    label=study["roleLabel"],
                    class_uri="abi:StudentRole",
                    class_label="Student Role",
                    bfo_bucket="Realizable",
                    properties=[
                        p
                        for p in (
                            _prop(
                                "abi:program_name",
                                "program",
                                study.get("programName"),
                            ),
                            _prop(
                                "abi:forEducationalOrganization",
                                "organization",
                                org_label,
                            ),
                        )
                        if p
                    ],
                )
            )
            add_rel(studying_id, role_id, "abi:realizes", "realizes")
            add_rel(subject, role_id, "abi:hasStudentRole", "has student role")

        degree_id = compact_graph_id(study.get("degree"))
        if degree_id and study.get("degreeLabel"):
            add_entity(
                _entity_node(
                    degree_id,
                    label=study["degreeLabel"],
                    class_uri="abi:AcademicDegree",
                    class_label="Academic Degree",
                    bfo_bucket="GDC",
                )
            )
            add_rel(studying_id, degree_id, "abi:hasDegree", "has degree")

    # --- HOW IT IS: skills, one node per person and skill ------------------
    # A skill exercised in several jobs is a single node several acts point at,
    # which is what makes those jobs neighbours two hops apart on the canvas.
    for row in skill_rows or []:
        subject = row.get("personLabel")
        skill_id = compact_graph_id(row.get("skill"))
        skill_label = row.get("skillLabel")
        if not (subject and skill_id and skill_label):
            continue
        ensure_person(subject, kind="person")
        add_entity(
            _entity_node(
                skill_id,
                label=skill_label,
                class_uri="abi:Skill",
                class_label="Skill",
                bfo_bucket="Quality",
                properties=[
                    p for p in (_prop("abi:skill_name", "skill", skill_label),) if p
                ],
            )
        )
        add_rel(subject, skill_id, "abi:hasSkill", "has skill")
        working_id = compact_graph_id(row.get("working"))
        if working_id and working_id in seen_workings:
            add_rel(working_id, skill_id, "abi:developsSkill", "develops skill")

    canvas_relations = [rel for rel in relations if rel.get("canvas", True)]

    return {
        "people": sorted(people_map.values(), key=lambda person: person["label"]),
        "processes": [],
        "entities": sorted(entities_map.values(), key=lambda entity: entity["label"]),
        "relations": canvas_relations,
        "allRelations": relations,
        "processClassCatalog": process_class_catalog
        if process_class_catalog is not None
        else build_process_class_catalog(),
    }
