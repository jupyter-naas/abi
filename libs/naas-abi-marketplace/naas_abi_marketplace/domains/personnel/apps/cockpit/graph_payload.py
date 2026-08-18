"""Build Graph page payload (people + act-of-working instances) for the cockpit UI.

The canvas is explored breadth-first from the focused person, so which edges are
drawn decides what appears at each distance:

    distance 1  the acts of working, and everything hanging directly off the
                person — the missions and profile document they carry, the
                employee roles and skills they bear
    distance 2  what those acts reach — organization, site, temporal region,
                employment contract
    distance 3  the temporal instants bounding each temporal region

``personnel:hasWorkLocation`` (person → site) is emitted with ``canvas=False``:
it belongs in the data, but drawing it would pull Site up to distance 1 and
collapse the layering above.
"""

from __future__ import annotations

from naas_abi_marketplace.domains.personnel.individual_uri import compact_personnel

PERSONNEL_NS = "http://ontology.naas.ai/personnel/"
ABI_NS = "http://ontology.naas.ai/abi/"


def _prop(uri: str, label: str, value: str | None) -> dict | None:
    if value is None or value == "":
        return None
    return {"uri": uri, "label": label, "value": str(value)}


def compact_graph_id(uri: str | None) -> str | None:
    """Compact ontology individual URI to ``personnel:…`` / ``abi:…`` graph id."""
    if not uri:
        return None
    text = str(uri).rstrip("/")
    if text.startswith(PERSONNEL_NS):
        return f"personnel:{text[len(PERSONNEL_NS) :]}"
    if text.startswith(ABI_NS):
        return f"abi:{text[len(ABI_NS) :]}"
    uuid = compact_personnel(text)
    return uuid or text


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
) -> dict:
    """Return people, entities and relations for ``graph/index.json``."""
    people_map: dict[str, dict] = {}
    entities_map: dict[str, dict] = {}
    relations: list[dict] = []

    def ensure_person(
        label: str,
        *,
        kind: str = "person",
        job_title: str | None = None,
        job_family: str | None = None,
        status_value: str | None = None,
        employee_id: str | None = None,
        organization_label: str | None = None,
    ) -> None:
        if not label:
            return
        existing = people_map.get(label)
        props = [
            item
            for item in (
                _prop("personnel:job_title", "job title", job_title),
                _prop("personnel:job_family", "job family", job_family),
                _prop("personnel:employee_id", "employee id", employee_id),
                _prop("personnel:status_value", "status", status_value),
                _prop("abi:organizationLabel", "organization", organization_label),
            )
            if item
        ]

        if existing:
            if kind == "employee":
                existing["kind"] = "employee"
            for key, val in (
                ("job_title", job_title),
                ("job_family", job_family),
                ("status_value", status_value),
                ("employee_id", employee_id),
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
            "job_family": job_family,
            "status_value": status_value,
            "employee_id": employee_id,
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
            kind="employee",
            job_title=row.get("job_title"),
            job_family=row.get("job_family"),
            status_value=row.get("status_value"),
            employee_id=row.get("employee_id"),
            organization_label=row.get("organizationLabel") or "organization",
        )

    seen_workings: set[str] = set()

    for work in working_rows or []:
        subject = work.get("personLabel")
        if not subject:
            continue
        ensure_person(subject, kind="employee")

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
                class_uri="personnel:ActOfWorking",
                class_label="Act of Working",
                bfo_bucket="Process",
                is_working_hub=True,
                started_at=work.get("temporalStart"),
                ended_at=work.get("temporalEnd"),
                properties=[
                    p
                    for p in (
                        _prop("personnel:isActOfWorkingOf", "worker", subject),
                        _prop("personnel:forOrganization", "organization", org_label),
                        _prop("personnel:job_title", "job title", work.get("jobTitle")),
                        _prop("abi:hasFirstInstant", "start", work.get("temporalStart")),
                        _prop("abi:hasLastInstant", "end", work.get("temporalEnd")),
                        _prop(
                            "personnel:duration_label",
                            "duration",
                            work.get("durationLabel"),
                        ),
                    )
                    if p
                ],
            )
        )
        add_rel(subject, working_id, "personnel:hasActOfWorking", "has act of working")

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
            add_rel(working_id, org_id, "personnel:forOrganization", "for organization")

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
                "personnel:hasWorkLocation",
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
                                "personnel:duration_label",
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
                                    "personnel:instant_date",
                                    "instant date",
                                    work.get(date_key),
                                ),
                            )
                            if p
                        ],
                    )
                )
                add_rel(temporal_id, instant_id, predicate, predicate_label)

        # --- HOW WE KNOW: the contract ------------------------------------
        contract_id = compact_graph_id(work.get("contract"))
        if contract_id and work.get("contractLabel"):
            add_entity(
                _entity_node(
                    contract_id,
                    label=work.get("contractType") or work["contractLabel"],
                    class_uri="personnel:EmploymentContract",
                    class_label="Employment Contract",
                    bfo_bucket="GDC",
                    properties=[
                        p
                        for p in (
                            _prop(
                                "personnel:contract_type",
                                "contract type",
                                work.get("contractType"),
                            ),
                        )
                        if p
                    ],
                )
            )
            add_rel(working_id, contract_id, "personnel:hasContract", "has contract")

        # --- WHY: the role, and the mission it concretizes ----------------
        role_id = compact_graph_id(work.get("role"))
        mission_id = compact_graph_id(work.get("mission"))
        if role_id and work.get("roleLabel"):
            add_entity(
                _entity_node(
                    role_id,
                    label=work["roleLabel"],
                    class_uri="personnel:EmployeeRole",
                    class_label="Employee Role",
                    bfo_bucket="Realizable",
                    properties=[
                        p
                        for p in (
                            _prop("personnel:job_title", "job title", work.get("jobTitle")),
                            _prop("personnel:forOrganization", "organization", org_label),
                        )
                        if p
                    ],
                )
            )
            add_rel(working_id, role_id, "abi:realizes", "realizes")
            add_rel(subject, role_id, "personnel:hasEmployeeRole", "has employee role")

        if mission_id and work.get("missionLabel"):
            add_entity(
                _entity_node(
                    mission_id,
                    label=work["missionLabel"],
                    class_uri="personnel:Mission",
                    class_label="Mission",
                    bfo_bucket="GDC",
                    properties=[
                        p
                        for p in (
                            _prop(
                                "personnel:mission_content",
                                "mission content",
                                work.get("missionContent"),
                            ),
                            _prop("personnel:forOrganization", "organization", org_label),
                        )
                        if p
                    ],
                )
            )
            add_rel(
                subject,
                mission_id,
                "personnel:hasMissionCarried",
                "carries mission",
            )
            if role_id:
                add_rel(role_id, mission_id, "personnel:hasMission", "has mission")

            # --- HOW WE KNOW: where the mission was read from -------------
            profile_id = compact_graph_id(work.get("profile"))
            if profile_id and work.get("profileLabel"):
                add_entity(
                    _entity_node(
                        profile_id,
                        label=work["profileLabel"],
                        class_uri="personnel:ProfileDocument",
                        class_label="Profile Document",
                        bfo_bucket="GDC",
                        properties=[
                            p
                            for p in (
                                _prop(
                                    "personnel:source_url",
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
                    "personnel:hasProfileDocument",
                    "has profile document",
                )
                add_rel(
                    mission_id,
                    profile_id,
                    "personnel:isSourcedFrom",
                    "is sourced from",
                )

        # --- HOW IT IS: remuneration --------------------------------------
        rem_id = compact_graph_id(work.get("remuneration"))
        if rem_id and work.get("remunerationLabel"):
            add_entity(
                _entity_node(
                    rem_id,
                    label=work["remunerationLabel"],
                    class_uri="personnel:Remuneration",
                    class_label="Remuneration",
                    bfo_bucket="Quality",
                    properties=[
                        p
                        for p in (
                            _prop(
                                "personnel:remuneration_amount",
                                "amount",
                                work.get("remunerationAmount"),
                            ),
                            _prop(
                                "personnel:remuneration_currency",
                                "currency",
                                work.get("remunerationCurrency"),
                            ),
                        )
                        if p
                    ],
                )
            )
            add_rel(working_id, rem_id, "abi:hasParticipant", "has remuneration")

    # --- HOW IT IS: skills, one node per person and skill ------------------
    # A skill exercised in several jobs is a single node several acts point at,
    # which is what makes those jobs neighbours two hops apart on the canvas.
    for row in skill_rows or []:
        subject = row.get("personLabel")
        skill_id = compact_graph_id(row.get("skill"))
        skill_label = row.get("skillLabel")
        if not (subject and skill_id and skill_label):
            continue
        ensure_person(subject, kind="employee")
        add_entity(
            _entity_node(
                skill_id,
                label=skill_label,
                class_uri="personnel:Skill",
                class_label="Skill",
                bfo_bucket="Quality",
                properties=[p for p in (_prop("personnel:skill_name", "skill", skill_label),) if p],
            )
        )
        add_rel(subject, skill_id, "personnel:hasSkill", "has skill")
        working_id = compact_graph_id(row.get("working"))
        if working_id and working_id in seen_workings:
            add_rel(working_id, skill_id, "personnel:developsSkill", "develops skill")

    canvas_relations = [rel for rel in relations if rel.get("canvas", True)]

    return {
        "people": sorted(people_map.values(), key=lambda person: person["label"]),
        "processes": [],
        "entities": sorted(entities_map.values(), key=lambda entity: entity["label"]),
        "relations": canvas_relations,
        "allRelations": relations,
    }
