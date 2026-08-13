"""Build process-ledger entries for the Cockpit Logs page.

Each registration groups **triples** with eight fields: subject, subject type,
predicate, predicate type, object, object type, source, and source timestamp.
Process occurrents use ``{namespace}{uuid}`` IRIs; source is the declaration UUID.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from naas_abi_marketplace.domains.personnel.individual_uri import (
    compact_personnel,
    uuid_part,
)

PROP_DATA = "data_prop"
PROP_OBJECT = "object_prop"
PROP_ANNOTATION = "annotation"

OWL_DATATYPE = "owl:DatatypeProperty"
OWL_OBJECT = "owl:ObjectProperty"
OWL_ANNOTATION = "owl:AnnotationProperty"

PREDICATE_TYPE = {
    PROP_DATA: OWL_DATATYPE,
    PROP_OBJECT: OWL_OBJECT,
    PROP_ANNOTATION: OWL_ANNOTATION,
}


def _compact_uri(uri: str | None) -> str | None:
    if not uri:
        return None
    text = str(uri)
    compact = compact_personnel(text)
    if compact:
        return compact
    if text.startswith("http://ontology.naas.ai/abi/"):
        return "abi:" + text.rsplit("/abi/", 1)[-1]
    if text.startswith("http://purl.obolibrary.org/obo/"):
        return "bfo:" + text.rsplit("/", 1)[-1]
    if text.startswith("https://www.commoncoreontologies.org/"):
        return "cco:" + text.rsplit("/", 1)[-1]
    return text


def _label_to_person_uri(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    return f"personnel:Person/{slug or 'unknown'}"


def _split_name(label: str | None) -> tuple[str | None, str | None]:
    if not label:
        return None, None
    parts = label.strip().split()
    if len(parts) <= 1:
        return parts[0], None
    return " ".join(parts[:-1]), parts[-1]


def _source_at(declared_on: str | None) -> str:
    """Timestamp of the declaration act that sourced the registration."""
    if not declared_on:
        return datetime.now(ZoneInfo("Europe/Paris")).strftime("%Y-%m-%dT%H:%M:%S%z")
    try:
        day = datetime.strptime(str(declared_on)[:10], "%Y-%m-%d")
    except ValueError:
        return str(declared_on)
    dt = day.replace(hour=16, minute=0, second=19, tzinfo=ZoneInfo("Europe/Paris"))
    return dt.strftime("%Y-%m-%dT%H:%M:%S%z")


def _triple(
    *,
    subject_uri: str,
    subject_type_uri: str,
    predicate_kind: str,
    predicate_uri: str,
    object_value: str,
    object_type_uri: str,
    object_uri: str | None = None,
) -> dict[str, str]:
    return {
        "subject_uri": subject_uri,
        "subject_type_uri": subject_type_uri,
        "predicate_uri": predicate_uri,
        "predicate_type_uri": PREDICATE_TYPE[predicate_kind],
        "object": object_uri or object_value,
        "object_type_uri": object_type_uri,
    }


def _kinship_lookup(kinship: list[dict]) -> dict[tuple[str, str], dict]:
    out: dict[tuple[str, str], dict] = {}
    for item in kinship:
        person = item.get("personLabel") or ""
        declarant = item.get("declarantLabel") or ""
        out[(person, declarant)] = item
    return out


def build_ledger_log_entries(
    registrations: list[dict],
    kinship: list[dict] | None = None,
) -> list[dict[str, Any]]:
    """Group birth registrations into occurent headers + SPO triples."""
    kin = _kinship_lookup(kinship or [])
    entries: list[dict[str, Any]] = []

    for reg in registrations:
        declaration_uri = reg.get("declaration") or ""
        registration_uri = reg.get("registration") or ""
        source_uuid = uuid_part(declaration_uri) or "unknown"
        source_uri = compact_personnel(declaration_uri) or f"personnel:{source_uuid}"
        process_uri = compact_personnel(registration_uri) or "personnel:unknown"
        source_at = _source_at(reg.get("declaredOn"))
        person_label = reg.get("personLabel")
        given, family = _split_name(person_label)
        edge = kin.get((person_label or "", reg.get("declarantLabel") or ""), {})

        birth_uri = _compact_uri(reg.get("birth"))
        person_uri = _compact_uri(reg.get("person")) or (
            _label_to_person_uri(person_label) if person_label else None
        )
        if not person_uri and birth_uri:
            slug = birth_uri.rsplit("/", 1)[-1]
            person_uri = f"personnel:Person/{slug}"

        triples: list[dict[str, str]] = []

        if given and person_uri:
            triples.append(
                _triple(
                    subject_uri=person_uri,
                    subject_type_uri="abi:Person",
                    predicate_kind=PROP_DATA,
                    predicate_uri="personnel:given_name",
                    object_value=given,
                    object_type_uri="xsd:string",
                )
            )
        if family and person_uri:
            triples.append(
                _triple(
                    subject_uri=person_uri,
                    subject_type_uri="abi:Person",
                    predicate_kind=PROP_DATA,
                    predicate_uri="personnel:family_name",
                    object_value=family,
                    object_type_uri="xsd:string",
                )
            )

        temporal = reg.get("temporalLabel")
        if temporal and birth_uri:
            triples.append(
                _triple(
                    subject_uri=birth_uri,
                    subject_type_uri="cco:ont00001237",
                    predicate_kind=PROP_OBJECT,
                    predicate_uri="bfo:BFO_0000199",
                    object_value=str(temporal),
                    object_type_uri="xsd:date",
                )
            )

        site = reg.get("siteLabel")
        if site and birth_uri:
            triples.append(
                _triple(
                    subject_uri=birth_uri,
                    subject_type_uri="cco:ont00001237",
                    predicate_kind=PROP_OBJECT,
                    predicate_uri="bfo:BFO_0000066",
                    object_value=str(site),
                    object_type_uri="bfo:BFO_0000029",
                )
            )

        mother = edge.get("motherLabel") or reg.get("motherLabel")
        if mother and person_uri:
            triples.append(
                _triple(
                    subject_uri=person_uri,
                    subject_type_uri="abi:Person",
                    predicate_kind=PROP_OBJECT,
                    predicate_uri="personnel:hasMother",
                    object_value=str(mother),
                    object_type_uri="abi:Person",
                    object_uri=_label_to_person_uri(str(mother)),
                )
            )
        if mother and birth_uri:
            triples.append(
                _triple(
                    subject_uri=birth_uri,
                    subject_type_uri="cco:ont00001237",
                    predicate_kind=PROP_OBJECT,
                    predicate_uri="personnel:hasMother",
                    object_value=str(mother),
                    object_type_uri="abi:Person",
                    object_uri=_label_to_person_uri(str(mother)),
                )
            )

        father = edge.get("fatherLabel") or reg.get("fatherLabel")
        if father and person_uri:
            triples.append(
                _triple(
                    subject_uri=person_uri,
                    subject_type_uri="abi:Person",
                    predicate_kind=PROP_OBJECT,
                    predicate_uri="personnel:hasFather",
                    object_value=str(father),
                    object_type_uri="abi:Person",
                    object_uri=_label_to_person_uri(str(father)),
                )
            )
        if father and birth_uri:
            triples.append(
                _triple(
                    subject_uri=birth_uri,
                    subject_type_uri="cco:ont00001237",
                    predicate_kind=PROP_OBJECT,
                    predicate_uri="personnel:hasFather",
                    object_value=str(father),
                    object_type_uri="abi:Person",
                    object_uri=_label_to_person_uri(str(father)),
                )
            )

        for triple in triples:
            triple["source_uri"] = source_uri
            triple["source_at"] = source_at

        entries.append(
            {
                "process_uri": process_uri,
                "process_type_uri": "personnel:BirthRegistrationProcess",
                "source_at": source_at,
                "source_uuid": source_uuid,
                "source_uri": source_uri,
                "source_type_uri": "personnel:BirthDeclarationAct",
                "declarant_label": reg.get("declarantLabel"),
                "declared_on": reg.get("declaredOn"),
                "declared_content": reg.get("declaredContent"),
                "person_label": person_label,
                "birth_uri": birth_uri,
                "triples": triples,
            }
        )

    return entries


build_ledger_log_rows = build_ledger_log_entries
