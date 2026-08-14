"""Register people into the personnel graph via BirthProcess.

Every call emits one ``cco:ont00001237`` (Birth) process per person touched —
the subject and any newly named mother, father or registrant — so the graph
always carries a process log that later complementary registrations can chain
onto via ``personnel:updatesPriorRegistration``.

Uses the generated ontology classes under ``personnel/ontologies/`` plus
``abi:Person`` / ``abi:DocumentContentEntity`` for identity and provenance.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import Enum
from typing import Annotated, Any

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi.ontologies.modules.ABIOntology import (
    DocumentContentEntity,
    Person,
    Site,
    TemporalRegion,
)
from naas_abi_core import logger
from naas_abi_core.pipeline import (
    Pipeline,
    PipelineConfiguration,
    PipelineParameters,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.utils.Expose import APIRouter
from naas_abi_marketplace.domains.personnel import ABIModule
from naas_abi_marketplace.domains.personnel.individual_uri import (
    personnel_individual_uri,
)
from naas_abi_marketplace.domains.personnel.ontologies.modules.PersonnelOntology import (
    BiologicalSex,
    BirthFunction,
    BirthRecord,
    GestationalAge,
    Length,
    NewbornDisposition,
    Weight,
)
from naas_abi_marketplace.domains.personnel.ontologies.processes.BirthProcess import (
    Birth,
    BirthDeclarationAct,
    BirthProcess,
)
from pydantic import Field, model_validator
from rdflib import RDF, RDFS, Graph, Literal, Namespace, URIRef
from rdflib.namespace import XSD

PERSONNEL = Namespace("http://ontology.naas.ai/personnel/")
ABI = Namespace("http://ontology.naas.ai/abi/")
CCO = Namespace("https://www.commoncoreontologies.org/")
ABI_NS = "http://ontology.naas.ai/abi/"
PERSONNEL_NS = "http://ontology.naas.ai/personnel/"


@dataclass
class BirthRegistrationPipelineConfiguration(PipelineConfiguration):
    """Configuration for BirthRegistrationPipeline."""

    triple_store: TripleStoreService
    graph_name: URIRef = field(
        default_factory=lambda: URIRef(
            ABIModule.get_instance().configuration.graph_name
        )
    )
    ontology_namespace: str = field(
        default_factory=lambda: (
            ABIModule.get_instance().configuration.ontology_namespace
        )
    )


class BirthRegistrationPipelineParameters(PipelineParameters):
    """Inputs for registering (or enriching) a person via BirthProcess.

    At minimum ``first_name`` + ``last_name`` are required for the subject.
    The agent should try to collect every optional field. Exactly one source of
    trust must be provided: either a registrant person (name or URI) or a
    source document (label or URI).
    """

    first_name: Annotated[
        str,
        Field(
            description="Subject's first / given name (required).",
            examples=["Jeremy"],
        ),
    ]
    last_name: Annotated[
        str,
        Field(
            description="Subject's last / family name (required).",
            examples=["Ravenel"],
        ),
    ]
    birth_date: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "Subject's date of birth. Accepts YYYY-MM-DD or DD/MM/YYYY "
                "(e.g. '1989-12-05' or '05/12/1989')."
            ),
            examples=["05/12/1989", "1989-12-05"],
        ),
    ] = None
    birth_site: Annotated[
        str | None,
        Field(
            default=None,
            description="Place / site where the birth occurred (e.g. 'Vitré').",
            examples=["Vitré"],
        ),
    ] = None
    biological_sex: Annotated[
        str | None,
        Field(
            default=None,
            description="Biological sex assigned at birth (e.g. 'Male', 'Female').",
            examples=["Male"],
        ),
    ] = None
    weight: Annotated[
        str | None,
        Field(
            default=None,
            description="Birth weight as a human-readable string (e.g. '3.2 kg').",
            examples=["3.2 kg"],
        ),
    ] = None
    length: Annotated[
        str | None,
        Field(
            default=None,
            description="Birth length as a human-readable string (e.g. '50 cm').",
            examples=["50 cm"],
        ),
    ] = None
    gestational_age: Annotated[
        str | None,
        Field(
            default=None,
            description="Gestational age (e.g. '39 weeks and 2 days').",
            examples=["39 weeks"],
        ),
    ] = None
    mother_first_name: Annotated[
        str | None,
        Field(
            default=None,
            description="Mother's first name.",
            examples=["Christine"],
        ),
    ] = None
    mother_last_name: Annotated[
        str | None,
        Field(
            default=None,
            description="Mother's last name.",
            examples=["Ravenel"],
        ),
    ] = None
    father_first_name: Annotated[
        str | None,
        Field(
            default=None,
            description="Father's first name.",
            examples=["Pascal"],
        ),
    ] = None
    father_last_name: Annotated[
        str | None,
        Field(
            default=None,
            description="Father's last name.",
            examples=["Ravenel"],
        ),
    ] = None
    registrant_first_name: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "First name of the person registering this information "
                "(source of trust — material entity)."
            ),
            examples=["Florent"],
        ),
    ] = None
    registrant_last_name: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "Last name of the person registering this information "
                "(source of trust — material entity)."
            ),
            examples=["Ravenel"],
        ),
    ] = None
    registrant_uri: Annotated[
        str | None,
        Field(
            default=None,
            description="Existing URI of the registrant person, if already in the graph.",
        ),
    ] = None
    source_document_label: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "Label of a document used as source of trust "
                "(generically dependent continuant), e.g. a birth certificate."
            ),
            examples=["Birth certificate — Emma Petit"],
        ),
    ] = None
    source_document_uri: Annotated[
        str | None,
        Field(
            default=None,
            description="Existing URI of a source-of-trust document, if already in the graph.",
        ),
    ] = None
    persist: Annotated[
        bool,
        Field(
            default=True,
            description="Whether to insert the graph into the personnel named graph.",
        ),
    ] = True

    @model_validator(mode="after")
    def _require_source_of_trust(self) -> BirthRegistrationPipelineParameters:
        has_person_trust = bool(
            self.registrant_uri
            or (
                (self.registrant_first_name or "").strip()
                and (self.registrant_last_name or "").strip()
            )
        )
        has_document_trust = bool(
            self.source_document_uri or (self.source_document_label or "").strip()
        )
        if not has_person_trust and not has_document_trust:
            raise ValueError(
                "Provide a source of trust: registrant person "
                "(registrant_first_name + registrant_last_name, or registrant_uri) "
                "or a document (source_document_label or source_document_uri)."
            )
        return self


class BirthRegistrationPipeline(Pipeline):
    """Maps person + birth fields onto BirthProcess individuals."""

    __configuration: BirthRegistrationPipelineConfiguration

    def __init__(self, configuration: BirthRegistrationPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self._namespace = configuration.ontology_namespace
        self._exists_cache: dict[tuple[str, str], bool] = {}

    # ----- helpers --------------------------------------------------------------

    @staticmethod
    def _slug(*parts: str) -> str:
        joined = "-".join(p.strip().lower() for p in parts if p and p.strip())
        return re.sub(r"[^a-z0-9_\-]+", "-", joined).strip("-") or "unknown"

    @staticmethod
    def _full_name(first: str, last: str) -> str:
        return f"{first.strip()} {last.strip()}".strip()

    @staticmethod
    def _parse_birth_date(value: str | None) -> date | None:
        if not value:
            return None
        text = value.strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        raise ValueError(f"birth_date {value!r} must be YYYY-MM-DD or DD/MM/YYYY")

    def _uri(self, namespace: str, class_name: str, stable_id: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9_\-]", "_", stable_id)
        return f"{namespace}{class_name}/{safe}"

    def _process_uri(self, class_name: str, stable_id: str) -> str:
        """UUID IRI under the personnel namespace (no class segment, no rdfs:label)."""
        return personnel_individual_uri(f"{class_name}:{stable_id}")

    @staticmethod
    def _declared_content(
        person_label: str,
        *,
        birth_date: date | None,
        birth_site: str | None,
        mother: Person | None,
        father: Person | None,
    ) -> str:
        """Readable rendering of what was asserted, kept on the declaration act."""
        parts = [f"{person_label} was born"]
        if birth_date is not None:
            parts.append(f"on {birth_date.isoformat()}")
        if birth_site:
            parts.append(f"in {birth_site.strip()}")
        parents = [p.label for p in (mother, father) if p is not None and p.label]
        if parents:
            parts.append("to " + " and ".join(parents))
        return " ".join(parts) + "."

    def _content_hash(self, *chunks: Any) -> str:
        payload = "|".join("" if c is None else str(c).strip().lower() for c in chunks)
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]

    def _label_exists(self, label: str, class_uri: str) -> bool:
        key = (class_uri, label)
        cached = self._exists_cache.get(key)
        if cached is not None:
            return cached
        escaped = label.replace("\\", "\\\\").replace('"', '\\"')
        sparql = (
            f"ASK {{ GRAPH <{self.__configuration.graph_name}> {{ "
            f"?s a <{class_uri}> ; "
            f'<{RDFS.label}> "{escaped}" . }} }}'
        )
        try:
            exists = bool(self.__configuration.triple_store.query(sparql).askAnswer)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"BirthRegistrationPipeline: label-existence ASK failed ({exc}); "
                "assuming absent"
            )
            exists = False
        self._exists_cache[key] = exists
        return exists

    def _mark_existing(self, class_uri: str, label: str) -> None:
        self._exists_cache[(class_uri, label)] = True

    def _find_prior_registration_uri(self, person_uri: str) -> str | None:
        """Latest registration already logged against this person's birth.

        Looks for prior *registrations*, not prior births: a person has exactly
        one birth however many times it is registered, so chaining on the birth
        would never find anything to update.
        """
        sparql = f"""
        SELECT ?registration WHERE {{
          GRAPH <{self.__configuration.graph_name}> {{
            <{person_uri}> <{PERSONNEL.hasBirth}> ?birth .
            ?registration <{PERSONNEL.registersBirth}> ?birth .
          }}
        }}
        ORDER BY DESC(str(?registration))
        LIMIT 1
        """
        try:
            rows = list(self.__configuration.triple_store.query(sparql))
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"BirthRegistrationPipeline: prior-registration lookup failed ({exc})"
            )
            return None
        if not rows:
            return None
        row = rows[0]
        registration = getattr(row, "registration", None)
        if registration is None:
            try:
                registration = row[0]
            except Exception:  # noqa: BLE001
                return None
        return str(registration)

    # ----- entity builders ------------------------------------------------------

    def _ensure_person(
        self,
        graph: Graph,
        *,
        first_name: str,
        last_name: str,
        person_uri: str | None = None,
    ) -> tuple[Person, bool]:
        """Return (person, created). Reuses an existing label match when present."""
        full = self._full_name(first_name, last_name)
        uri = person_uri or self._uri(
            ABI_NS, "Person", self._slug(first_name, last_name)
        )
        person = Person(
            _uri=uri,
            label=full,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            full_name=full,
            created=datetime.now(UTC).replace(tzinfo=None),
            creator="BirthRegistrationPipeline",
        )
        created = not self._label_exists(full, Person._class_uri)
        if created:
            graph += person.rdf()
            graph.add((URIRef(uri), RDF.type, CCO.ont00000562))
            self._mark_existing(Person._class_uri, full)

            # Role-based names, held as strings on the person. abi:first_name /
            # abi:last_name above are the positional variants.
            graph.add(
                (
                    URIRef(uri),
                    PERSONNEL.given_name,
                    Literal(first_name.strip(), datatype=XSD.string),
                )
            )
            graph.add(
                (
                    URIRef(uri),
                    PERSONNEL.family_name,
                    Literal(last_name.strip(), datatype=XSD.string),
                )
            )
        return person, created

    def _ensure_document(
        self,
        graph: Graph,
        *,
        label: str,
        document_uri: str | None = None,
    ) -> DocumentContentEntity:
        uri = document_uri or self._uri(
            ABI_NS, "DocumentContentEntity", self._slug(label)
        )
        doc = DocumentContentEntity(
            _uri=uri,
            label=label.strip(),
            created=datetime.now(UTC).replace(tzinfo=None),
            creator="BirthRegistrationPipeline",
        )
        if not self._label_exists(label.strip(), DocumentContentEntity._class_uri):
            graph += doc.rdf()
            self._mark_existing(DocumentContentEntity._class_uri, label.strip())
        return doc

    def _build_birth_for_person(
        self,
        graph: Graph,
        *,
        person: Person,
        source_of_trust_uri: str,
        source_is_person: bool,
        birth_date: date | None = None,
        birth_site: str | None = None,
        biological_sex: str | None = None,
        weight: str | None = None,
        length: str | None = None,
        gestational_age: str | None = None,
        mother: Person | None = None,
        father: Person | None = None,
        rich: bool = False,
        content_key: str,
    ) -> Birth:
        """Emit the Birth plus one declaration act + registration for *person*.

        The Birth is keyed on the person alone — it is one mind-independent
        process however many people register it. The declaration act (the
        source) and the registration (the ledger entry) are keyed on the
        content hash, so a second declarant registering the same birth adds a
        second pair over the same Birth rather than duplicating it.
        """
        person_label = person.label or person.full_name or person._uri
        process_uri = self._process_uri("Birth", self._slug(person_label))
        declaration_uri = self._process_uri(
            "BirthDeclarationAct",
            f"{self._slug(person_label)}-{content_key}",
        )
        registration_uri = self._process_uri(
            "BirthProcess",
            f"{self._slug(person_label)}-{content_key}",
        )
        record_uri = self._process_uri(
            "BirthRecord",
            f"{self._slug(person_label)}-{content_key}",
        )

        participants: list[Any] = [person._uri]
        realizations: list[Any] = []
        qualities_for_person: list[Any] = []

        if rich:
            newborn = NewbornDisposition(
                _uri=self._uri(
                    self._namespace,
                    "NewbornDisposition",
                    f"{self._slug(person_label)}-{content_key}",
                ),
                label=f"Newborn disposition of {person_label}",
                inheres_in=[person._uri],
                created=datetime.now(UTC).replace(tzinfo=None),
                creator="BirthRegistrationPipeline",
            )
            graph += newborn.rdf()
            participants.append(newborn)
            realizations.append(newborn)
            qualities_for_person.append(newborn)

            if mother is not None:
                birth_fn = BirthFunction(
                    _uri=self._uri(
                        self._namespace,
                        "BirthFunction",
                        f"{self._slug(mother.label or mother._uri)}-{content_key}",
                    ),
                    label=f"Birth function of {mother.label}",
                    inheres_in=[mother._uri],
                    created=datetime.now(UTC).replace(tzinfo=None),
                    creator="BirthRegistrationPipeline",
                )
                graph += birth_fn.rdf()
                participants.extend([mother._uri, birth_fn])
                realizations.append(birth_fn)

            if father is not None:
                participants.append(father._uri)

            if biological_sex:
                sex = BiologicalSex(
                    _uri=self._uri(
                        self._namespace,
                        "BiologicalSex",
                        f"{self._slug(person_label)}-{self._slug(biological_sex)}",
                    ),
                    label=biological_sex.strip(),
                    inheres_in=[person._uri],
                    created=datetime.now(UTC).replace(tzinfo=None),
                    creator="BirthRegistrationPipeline",
                )
                graph += sex.rdf()
                participants.append(sex)
                qualities_for_person.append(sex)

            if weight:
                w = Weight(
                    _uri=self._uri(
                        self._namespace,
                        "Weight",
                        f"{self._slug(person_label)}-{content_key}",
                    ),
                    label=weight.strip(),
                    inheres_in=[person._uri],
                    created=datetime.now(UTC).replace(tzinfo=None),
                    creator="BirthRegistrationPipeline",
                )
                graph += w.rdf()
                participants.append(w)
                qualities_for_person.append(w)

            if length:
                ln = Length(
                    _uri=self._uri(
                        self._namespace,
                        "Length",
                        f"{self._slug(person_label)}-{content_key}",
                    ),
                    label=length.strip(),
                    inheres_in=[person._uri],
                    created=datetime.now(UTC).replace(tzinfo=None),
                    creator="BirthRegistrationPipeline",
                )
                graph += ln.rdf()
                participants.append(ln)
                qualities_for_person.append(ln)

            if gestational_age:
                ga = GestationalAge(
                    _uri=self._uri(
                        self._namespace,
                        "GestationalAge",
                        f"{self._slug(person_label)}-{content_key}",
                    ),
                    label=gestational_age.strip(),
                    inheres_in=[person._uri],
                    created=datetime.now(UTC).replace(tzinfo=None),
                    creator="BirthRegistrationPipeline",
                )
                graph += ga.rdf()
                participants.append(ga)
                qualities_for_person.append(ga)

        sites: list[Any] = []
        if birth_site:
            site_label = birth_site.strip()
            site = Site(
                _uri=self._uri(self._namespace, "Site", self._slug(site_label)),
                label=site_label,
                created=datetime.now(UTC).replace(tzinfo=None),
                creator="BirthRegistrationPipeline",
            )
            if not self._label_exists(site_label, Site._class_uri):
                graph += site.rdf()
                self._mark_existing(Site._class_uri, site_label)
            sites.append(site._uri)

        temporals: list[Any] = []
        if birth_date is not None:
            temporal_label = birth_date.isoformat()
            temporal = TemporalRegion(
                _uri=self._uri(self._namespace, "TemporalRegion", temporal_label),
                label=temporal_label,
                created=datetime.now(UTC).replace(tzinfo=None),
                creator="BirthRegistrationPipeline",
            )
            if not self._label_exists(temporal_label, TemporalRegion._class_uri):
                graph += temporal.rdf()
                self._mark_existing(TemporalRegion._class_uri, temporal_label)
            temporals.append(temporal._uri)

        # Chain onto whatever was already registered against this birth, before
        # this run's own registration is written.
        prior = self._find_prior_registration_uri(person._uri)

        participant_refs = [p if isinstance(p, str) else p._uri for p in participants]
        realization_refs = [r if isinstance(r, str) else r._uri for r in realizations]
        # 1. The birth itself — the natural process, one per person.
        birth = Birth(
            _uri=process_uri,
            label=f"Birth of {person_label}",
            hasParticipant=participant_refs,
            realizes=(realization_refs[0] if realization_refs else None),
            occursIn=sites or None,
            occupiesTemporalRegion=temporals or None,
            is_registered_by=[registration_uri],
            created=datetime.now(UTC).replace(tzinfo=None),
            creator="BirthRegistrationPipeline",
        )
        graph += birth.rdf()
        for extra_uri in realization_refs[1:]:
            graph.add((URIRef(process_uri), ABI.realizes, URIRef(extra_uri)))
        graph.add((URIRef(person._uri), PERSONNEL.hasBirth, URIRef(process_uri)))
        graph.add((URIRef(process_uri), PERSONNEL.isBirthOf, URIRef(person._uri)))

        # 2. The source — an act of representative communication. Who attested,
        #    when, and in what words; the registration keeps none of it.
        declared_on = datetime.now(UTC).replace(tzinfo=None)
        declared_label = declared_on.date().isoformat()
        declared_temporal = TemporalRegion(
            _uri=self._uri(self._namespace, "TemporalRegion", declared_label),
            label=declared_label,
            created=declared_on,
            creator="BirthRegistrationPipeline",
        )
        if not self._label_exists(declared_label, TemporalRegion._class_uri):
            graph += declared_temporal.rdf()
            self._mark_existing(TemporalRegion._class_uri, declared_label)

        declaration = BirthDeclarationAct(
            _uri=declaration_uri,
            declared_content=self._declared_content(
                person_label,
                birth_date=birth_date,
                birth_site=birth_site,
                mother=mother,
                father=father,
            ),
            occupiesTemporalRegion=[declared_temporal._uri],
            hasParticipant=[source_of_trust_uri] if source_is_person else None,
            created=declared_on,
            creator="BirthRegistrationPipeline",
        )
        graph += declaration.rdf()
        # A person source is the act's agent; a document source is what the act
        # produced (a birth certificate is the output of an earlier attestation).
        graph.add(
            (
                URIRef(declaration_uri),
                CCO.ont00001833 if source_is_person else CCO.ont00001829,
                URIRef(source_of_trust_uri),
            )
        )

        # 3. The record — about the birth, output by the registration.
        record = BirthRecord(
            _uri=record_uri,
            label=f"Birth record — {person_label} ({content_key})",
            genericallyDependsOn=[person._uri],
            isConcretizedBy=[registration_uri],
            created=datetime.now(UTC).replace(tzinfo=None),
            creator="BirthRegistrationPipeline",
        )
        graph += record.rdf()
        graph.add((URIRef(record_uri), CCO.ont00001808, URIRef(process_uri)))

        # 4. The ledger entry.
        registration = BirthProcess(
            _uri=registration_uri,
            has_information_source=[declaration_uri],
            registers_birth=[process_uri],
            ont00001829=record_uri,
            concretizes=record_uri,
            hasParticipant=[person._uri],
            occupiesTemporalRegion=[declared_temporal._uri],
            occursIn=sites or None,
            updates_prior_registration=(
                [prior] if prior and prior != registration_uri else None
            ),
            created=datetime.now(UTC).replace(tzinfo=None),
            creator="BirthRegistrationPipeline",
        )
        graph += registration.rdf()

        if mother is not None:
            graph.add((URIRef(person._uri), PERSONNEL.hasMother, URIRef(mother._uri)))
        if father is not None:
            graph.add((URIRef(person._uri), PERSONNEL.hasFather, URIRef(father._uri)))

        self._mark_existing(Birth._class_uri, birth.label or "")
        self._mark_existing(BirthRecord._class_uri, record.label or "")
        self._mark_existing(BirthProcess._class_uri, content_key)
        return birth

    # ----- run ------------------------------------------------------------------

    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, BirthRegistrationPipelineParameters):
            raise TypeError(
                "Parameters must be of type BirthRegistrationPipelineParameters"
            )

        self._exists_cache.clear()
        graph = Graph()
        birth_date = self._parse_birth_date(parameters.birth_date)

        # Source of trust (person material entity XOR document GDC).
        trust_uri: str
        registrant: Person | None = None
        registrant_created = False
        if parameters.registrant_uri or (
            parameters.registrant_first_name and parameters.registrant_last_name
        ):
            registrant, registrant_created = self._ensure_person(
                graph,
                first_name=parameters.registrant_first_name or "Unknown",
                last_name=parameters.registrant_last_name or "Registrant",
                person_uri=parameters.registrant_uri,
            )
            trust_uri = registrant._uri
        else:
            doc = self._ensure_document(
                graph,
                label=parameters.source_document_label or "Source document",
                document_uri=parameters.source_document_uri,
            )
            trust_uri = doc._uri

        subject, subject_created = self._ensure_person(
            graph,
            first_name=parameters.first_name,
            last_name=parameters.last_name,
        )

        mother: Person | None = None
        mother_created = False
        if parameters.mother_first_name and parameters.mother_last_name:
            mother, mother_created = self._ensure_person(
                graph,
                first_name=parameters.mother_first_name,
                last_name=parameters.mother_last_name,
            )

        father: Person | None = None
        father_created = False
        if parameters.father_first_name and parameters.father_last_name:
            father, father_created = self._ensure_person(
                graph,
                first_name=parameters.father_first_name,
                last_name=parameters.father_last_name,
            )

        content_key = self._content_hash(
            parameters.first_name,
            parameters.last_name,
            parameters.birth_date,
            parameters.birth_site,
            parameters.biological_sex,
            parameters.weight,
            parameters.length,
            parameters.gestational_age,
            parameters.mother_first_name,
            parameters.mother_last_name,
            parameters.father_first_name,
            parameters.father_last_name,
            trust_uri,
        )

        rich = any(
            [
                birth_date is not None,
                parameters.birth_site,
                parameters.biological_sex,
                parameters.weight,
                parameters.length,
                parameters.gestational_age,
                mother is not None,
                father is not None,
            ]
        )

        # Subject always gets a BirthProcess for this payload.
        self._build_birth_for_person(
            graph,
            person=subject,
            source_of_trust_uri=trust_uri,
            source_is_person=registrant is not None,
            birth_date=birth_date,
            birth_site=parameters.birth_site,
            biological_sex=parameters.biological_sex,
            weight=parameters.weight,
            length=parameters.length,
            gestational_age=parameters.gestational_age,
            mother=mother,
            father=father,
            rich=rich or subject_created,
            content_key=content_key,
        )

        # Newly introduced related people get their own stub registration process
        # so they can later be enriched (Florent / Pascal / Christine in the example).
        stub_people: list[tuple[Person, bool]] = []
        if mother is not None and mother_created:
            stub_people.append((mother, True))
        if father is not None and father_created:
            stub_people.append((father, True))
        if registrant is not None and registrant_created:
            # Avoid a duplicate process when registrant is also the subject.
            if registrant._uri != subject._uri:
                stub_people.append((registrant, True))

        for related, _created in stub_people:
            stub_key = self._content_hash(
                related.first_name,
                related.last_name,
                "stub",
                content_key,
            )
            self._build_birth_for_person(
                graph,
                person=related,
                source_of_trust_uri=trust_uri,
                source_is_person=registrant is not None,
                rich=False,
                content_key=stub_key,
            )

        logger.info(
            f"BirthRegistrationPipeline: produced {len(graph)} triples for "
            f"{subject.label} (rich={rich}, stubs={len(stub_people)})"
        )

        if parameters.persist:
            self.__configuration.triple_store.insert(
                graph, self.__configuration.graph_name
            )
            logger.info(
                f"BirthRegistrationPipeline: inserted into "
                f"<{self.__configuration.graph_name}>"
            )

        return graph

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="register_birth",
                description=(
                    "Register a person in the personnel knowledge graph via a "
                    "BirthProcess. Requires first_name and last_name "
                    "for the subject, plus a source of trust (registrant person "
                    "names/URI or a source document label/URI). Ask the user for "
                    "all optional fields when missing: birth_date, birth_site, "
                    "biological_sex, weight, length, gestational_age, mother and "
                    "father names. Each person touched (subject, new parents, "
                    "new registrant) gets its own Birth process so later "
                    "complementary facts create a retraceable process chain."
                ),
                func=lambda **kwargs: self.run(
                    BirthRegistrationPipelineParameters(**kwargs)
                ).serialize(format="turtle"),
                args_schema=BirthRegistrationPipelineParameters,
            )
        ]

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        if tags is None:
            tags = []
