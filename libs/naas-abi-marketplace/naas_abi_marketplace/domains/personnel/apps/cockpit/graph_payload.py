"""Build Graph page payload (people + process instances) for the cockpit UI."""

from __future__ import annotations

from naas_abi_marketplace.domains.personnel.individual_uri import (
    compact_personnel,
    uuid_part,
)

PERSONNEL_NS = "http://ontology.naas.ai/personnel/"
ABI_NS = "http://ontology.naas.ai/abi/"


def _slug(label: str) -> str:
    return label.lower().replace(" ", "-").replace("'", "")


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


def _relation(
    from_id: str, to_id: str, predicate_uri: str, predicate_label: str
) -> dict:
    return {
        "from": from_id,
        "to": to_id,
        "predicateUri": predicate_uri,
        "predicateLabel": predicate_label,
        "canvas": True,
    }


def _entity_node(
    entity_id: str,
    *,
    label: str,
    class_uri: str,
    class_label: str,
    bfo_bucket: str,
    is_birth_hub: bool = False,
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
        "isBirthHub": is_birth_hub,
        "isWorkingHub": is_working_hub,
        "startedAt": started_at,
        "endedAt": ended_at,
        "properties": properties or [],
    }


def build_graph_page_payload(
    roster_rows: list[dict],
    births: list[dict],
    working_rows: list[dict] | None = None,
) -> dict:
    """Return people, processes, sources, entities, and relations for ``graph/index.json``."""
    people_map: dict[str, dict] = {}
    entities_map: dict[str, dict] = {}
    relations: list[dict] = []
    ledger_processes: list[dict] = []

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
        props: list[dict] = []
        for item in (
            _prop("personnel:job_title", "job title", job_title),
            _prop("personnel:job_family", "job family", job_family),
            _prop("personnel:employee_id", "employee id", employee_id),
            _prop("personnel:status_value", "status", status_value),
            _prop("abi:organizationLabel", "organization", organization_label),
        ):
            if item:
                props.append(item)

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
            **_relation(from_id, to_id, predicate_uri, predicate_label),
            "canvas": canvas,
        }
        if rel not in relations:
            relations.append(rel)

    seen_registrations: set[str] = set()
    seen_births: set[str] = set()
    seen_workings: set[str] = set()
    seen_orgs: set[str] = set()

    for birth in births:
        reg_uri = birth.get("registration") or ""
        if reg_uri and reg_uri in seen_registrations:
            continue
        if reg_uri:
            seen_registrations.add(reg_uri)

        subject = birth.get("personLabel")
        if not subject:
            continue
        ensure_person(subject)

        reg_id = (
            compact_graph_id(reg_uri)
            or compact_personnel(reg_uri)
            or (f"birth-{_slug(subject)}-{_slug(birth.get('declarantLabel') or '')}")
        )
        decl_uri = birth.get("declaration") or ""
        source_id = (
            compact_graph_id(decl_uri)
            or compact_personnel(decl_uri)
            or (f"source-{uuid_part(decl_uri) or _slug(subject)}")
        )
        declarant = birth.get("declarantLabel")

        birth_uri = birth.get("birth")
        birth_id = compact_graph_id(birth_uri)
        if not birth_id:
            continue

        if birth_id not in seen_births:
            seen_births.add(birth_id)
            birth_label = birth.get("birthLabel") or f"Birth of {subject}"
            add_entity(
                _entity_node(
                    birth_id,
                    label="Birth",
                    class_uri="cco:ont00001237",
                    class_label="Birth",
                    bfo_bucket="Process",
                    is_birth_hub=True,
                    started_at=birth.get("temporalStart"),
                    ended_at=birth.get("temporalEnd"),
                    properties=[
                        p
                        for p in (
                            _prop("rdfs:label", "label", birth_label),
                            _prop(
                                "personnel:registeredPerson",
                                "registered person",
                                subject,
                            ),
                            _prop(
                                "abi:hasFirstInstant",
                                "start",
                                birth.get("temporalStart"),
                            ),
                            _prop(
                                "abi:hasLastInstant", "end", birth.get("temporalEnd")
                            ),
                        )
                        if p
                    ],
                )
            )
            add_rel(subject, birth_id, "personnel:hasBirth", "has birth")

            site_uri = birth.get("site")
            site_label = birth.get("siteLabel")
            if site_uri and site_label:
                site_id = compact_graph_id(site_uri)
                if site_id:
                    add_entity(
                        _entity_node(
                            site_id,
                            label=site_label,
                            class_uri="bfo:BFO_0000029",
                            class_label="Site",
                            bfo_bucket="Site",
                        )
                    )
                    add_rel(birth_id, site_id, "abi:occursIn", "occurs in")

            temporal_uri = birth.get("temporal")
            temporal_label = birth.get("temporalLabel")
            if temporal_uri and temporal_label:
                temporal_id = compact_graph_id(temporal_uri)
                if temporal_id:
                    add_entity(
                        _entity_node(
                            temporal_id,
                            label=temporal_label,
                            class_uri="bfo:BFO_0000008",
                            class_label="Temporal Region",
                            bfo_bucket="Temporal Region",
                            started_at=birth.get("temporalStart"),
                            ended_at=birth.get("temporalEnd"),
                            properties=[
                                p
                                for p in (
                                    _prop(
                                        "abi:hasFirstInstant",
                                        "first instant",
                                        birth.get("temporalStart"),
                                    ),
                                    _prop(
                                        "abi:hasLastInstant",
                                        "last instant",
                                        birth.get("temporalEnd"),
                                    ),
                                )
                                if p
                            ],
                        )
                    )
                    add_rel(
                        birth_id,
                        temporal_id,
                        "abi:occupiesTemporalRegion",
                        "occupies temporal region",
                    )

            sex_uri = birth.get("sex")
            sex_label = birth.get("sexLabel")
            if sex_uri and sex_label:
                sex_id = compact_graph_id(sex_uri)
                if sex_id:
                    add_entity(
                        _entity_node(
                            sex_id,
                            label=sex_label,
                            class_uri="personnel:BiologicalSex",
                            class_label="Biological sex",
                            bfo_bucket="Quality",
                        )
                    )
                    add_rel(birth_id, sex_id, "abi:hasParticipant", "has sex")

            eye_uri = birth.get("eyeColor")
            eye_label = birth.get("eyeColorLabel")
            if eye_uri and eye_label:
                eye_id = compact_graph_id(eye_uri)
                if eye_id:
                    add_entity(
                        _entity_node(
                            eye_id,
                            label=eye_label,
                            class_uri="personnel:EyeColor",
                            class_label="Eye color",
                            bfo_bucket="Quality",
                        )
                    )
                    add_rel(birth_id, eye_id, "abi:hasParticipant", "has eye color")

        add_rel(birth_id, subject, "personnel:isBirthOf", "is birth of")

        for field, predicate_uri, predicate_label in (
            ("motherLabel", "personnel:hasMother", "has mother"),
            ("fatherLabel", "personnel:hasFather", "has father"),
        ):
            other = birth.get(field)
            if other:
                ensure_person(other, kind="family")
                add_rel(subject, other, predicate_uri, predicate_label)
                add_rel(birth_id, other, predicate_uri, predicate_label)

        if declarant:
            ensure_person(declarant, kind="family")
            add_rel(declarant, birth_id, "personnel:declared", "declared")

        record_uri = birth.get("record")
        record_label = birth.get("recordLabel")
        if record_uri and record_label:
            record_id = compact_graph_id(record_uri)
            if record_id:
                add_entity(
                    _entity_node(
                        record_id,
                        label=record_label,
                        class_uri="personnel:BirthRecord",
                        class_label="Birth Record",
                        bfo_bucket="GDC",
                    )
                )
                add_rel(record_id, birth_id, "cco:ont00001808", "is about")

        ledger_processes.append(
            {
                "id": reg_id,
                "registration": reg_uri,
                "birthId": birth_id,
                "sourceId": source_id,
                "nodeKind": "process",
                "processType": "birth-registration",
                "classUri": "personnel:BirthProcess",
                "classLabel": "Birth Registration Process",
                "canvasHidden": True,
                "startedAt": birth.get("registrationStart") or birth.get("declaredOn"),
                "endedAt": birth.get("registrationEnd") or birth.get("declaredOn"),
                "properties": [
                    p
                    for p in (
                        _prop("personnel:registersBirth", "registers birth", birth_id),
                        _prop(
                            "abi:occupiesTemporalRegion",
                            "ledger time",
                            birth.get("declaredOn"),
                        ),
                        _prop(
                            "abi:hasFirstInstant",
                            "start",
                            birth.get("registrationStart") or birth.get("declaredOn"),
                        ),
                        _prop(
                            "abi:hasLastInstant",
                            "end",
                            birth.get("registrationEnd") or birth.get("declaredOn"),
                        ),
                        _prop(
                            "personnel:declared_content",
                            "declared content",
                            birth.get("declaredContent"),
                        ),
                    )
                    if p
                ],
            }
        )
        add_rel(
            reg_id,
            birth_id,
            "personnel:registersBirth",
            "registers birth",
            canvas=False,
        )
        add_rel(
            reg_id,
            source_id,
            "personnel:hasInformationSource",
            "has information source",
            canvas=False,
        )
        if declarant:
            add_rel(source_id, declarant, "cco:ont00001833", "has agent", canvas=False)

    sources: list[dict] = []
    for ledger in ledger_processes:
        sources.append(
            {
                "id": ledger["sourceId"],
                "processId": ledger["id"],
                "nodeKind": "source",
                "classUri": "personnel:BirthDeclarationAct",
                "classLabel": "Birth Declaration Act",
                "canvasHidden": True,
                "bfoBucket": "Process",
                "startedAt": ledger.get("startedAt"),
                "endedAt": ledger.get("endedAt"),
                "properties": [
                    p
                    for p in (
                        _prop("abi:hasFirstInstant", "start", ledger.get("startedAt")),
                        _prop("abi:hasLastInstant", "end", ledger.get("endedAt")),
                    )
                    if p
                ],
            }
        )

    for row in roster_rows:
        label = row.get("personLabel")
        if not label:
            continue
        org = row.get("organizationLabel") or "organization"
        ensure_person(
            label,
            kind="employee",
            job_title=row.get("job_title"),
            job_family=row.get("job_family"),
            status_value=row.get("status_value"),
            employee_id=row.get("employee_id"),
            organization_label=org,
        )

    for work in working_rows or []:
        subject = work.get("personLabel")
        if not subject:
            continue
        ensure_person(subject, kind="employee", job_title=work.get("jobTitle"))

        working_uri = work.get("working") or ""
        working_id = compact_graph_id(working_uri)
        if not working_id or working_id in seen_workings:
            continue
        seen_workings.add(working_id)

        add_entity(
            _entity_node(
                working_id,
                label="Act of Working",
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
                        _prop("personnel:job_title", "job title", work.get("jobTitle")),
                        _prop(
                            "abi:hasFirstInstant", "start", work.get("temporalStart")
                        ),
                        _prop("abi:hasLastInstant", "end", work.get("temporalEnd")),
                    )
                    if p
                ],
            )
        )
        add_rel(subject, working_id, "personnel:hasActOfWorking", "has act of working")

        org_uri = work.get("org")
        org_label = work.get("orgLabel")
        if org_uri and org_label:
            org_id = compact_graph_id(org_uri)
            if org_id and org_id not in seen_orgs:
                seen_orgs.add(org_id)
                add_entity(
                    _entity_node(
                        org_id,
                        label=org_label,
                        class_uri="abi:Organization",
                        class_label="Organization",
                        bfo_bucket="Material Entity",
                    )
                )
            if org_id:
                add_rel(
                    working_id, org_id, "personnel:forOrganization", "for organization"
                )

        site_uri = work.get("site")
        site_label = work.get("siteLabel")
        if site_uri and site_label:
            site_id = compact_graph_id(site_uri)
            if site_id:
                add_entity(
                    _entity_node(
                        site_id,
                        label=site_label,
                        class_uri="bfo:BFO_0000029",
                        class_label="Site",
                        bfo_bucket="Site",
                    )
                )
                add_rel(working_id, site_id, "abi:occursIn", "occurs in")

        temporal_uri = work.get("temporal")
        temporal_label = work.get("temporalLabel")
        if temporal_uri and temporal_label:
            temporal_id = compact_graph_id(temporal_uri)
            if temporal_id:
                add_entity(
                    _entity_node(
                        temporal_id,
                        label=temporal_label,
                        class_uri="bfo:BFO_0000008",
                        class_label="Temporal Region",
                        bfo_bucket="Temporal Region",
                        started_at=work.get("temporalStart"),
                        ended_at=work.get("temporalEnd"),
                        properties=[
                            p
                            for p in (
                                _prop(
                                    "abi:hasFirstInstant",
                                    "first instant",
                                    work.get("temporalStart"),
                                ),
                                _prop(
                                    "abi:hasLastInstant",
                                    "last instant",
                                    work.get("temporalEnd"),
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

        contract_uri = work.get("contract")
        contract_label = work.get("contractLabel")
        if contract_uri and contract_label:
            contract_id = compact_graph_id(contract_uri)
            if contract_id:
                add_entity(
                    _entity_node(
                        contract_id,
                        label=contract_label,
                        class_uri="personnel:EmploymentContract",
                        class_label="Employment Contract",
                        bfo_bucket="GDC",
                    )
                )
                add_rel(
                    working_id, contract_id, "personnel:hasContract", "has contract"
                )

        position_uri = work.get("position")
        position_label = work.get("positionLabel")
        position_id = None
        if position_uri and position_label:
            position_id = compact_graph_id(position_uri)
            if position_id:
                add_entity(
                    _entity_node(
                        position_id,
                        label=position_label,
                        class_uri="personnel:JobPosition",
                        class_label="Job Position",
                        bfo_bucket="GDC",
                    )
                )
        role_uri = work.get("role")
        role_label = work.get("roleLabel")
        if role_uri and role_label:
            role_id = compact_graph_id(role_uri)
            if role_id:
                add_entity(
                    _entity_node(
                        role_id,
                        label=role_label,
                        class_uri="personnel:EmployeeRole",
                        class_label="Employee Role",
                        bfo_bucket="Role",
                    )
                )
                add_rel(working_id, role_id, "abi:realizes", "realizes")
                if position_id:
                    add_rel(
                        role_id,
                        position_id,
                        "personnel:hasJobPosition",
                        "has job position",
                    )

        rem_uri = work.get("remuneration")
        rem_label = work.get("remunerationLabel")
        if rem_uri and rem_label:
            rem_id = compact_graph_id(rem_uri)
            if rem_id:
                rem_props = [
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
                ]
                add_entity(
                    _entity_node(
                        rem_id,
                        label=rem_label,
                        class_uri="personnel:Remuneration",
                        class_label="Remuneration",
                        bfo_bucket="Quality",
                        properties=rem_props,
                    )
                )
                add_rel(working_id, rem_id, "abi:hasParticipant", "has remuneration")

    canvas_relations = [rel for rel in relations if rel.get("canvas", True)]

    return {
        "people": sorted(people_map.values(), key=lambda person: person["label"]),
        "processes": [],
        "ledgerProcesses": ledger_processes,
        "sources": sources,
        "entities": sorted(entities_map.values(), key=lambda entity: entity["label"]),
        "relations": canvas_relations,
        "allRelations": relations,
    }
