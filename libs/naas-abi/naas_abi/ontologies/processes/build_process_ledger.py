"""Regenerate the draft ABI process schemas from the bundled source ledger.

Run with the repository Python environment. This is an explicit build step, never
an API startup hook. Ontology files remain the runtime source of truth.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.collection import Collection
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SKOS, XSD

ABI = Namespace("http://ontology.naas.ai/abi/")
BFO = Namespace("http://purl.obolibrary.org/obo/")
CCO = Namespace("https://www.commoncoreontologies.org/")
STATUS = "Draft : simulated ledger hypothesis; not validated with ABI."
SOURCE = "libs/naas-abi/naas_abi/ontologies/processes/source_ledger.json"
BUCKETS = ("WHO", "WHERE", "WHEN", "HOWITIS", "WHY", "HOWWEKNOW")
# These source labels name information/software, not people or physical machines.
SOFTWARE = {
    "AIN", "AIN agents", "AIN finance agent", "AIN gap-detection agent",
    "AIN intelligence agent", "AIN predictive agent", "AIN procurement agent",
    "Fleet system", "HR system", "Identity system", "Learning system",
    "Messaging system", "Oracle ERP", "Planning system", "Scheduling system",
    "Screening system",
}
GROUPS = {"Cyber team", "Field team", "Function leads", "Line managers",
          "Maintenance team", "Resource owners", "Response team", "Security", "Staff"}
ORGANISATIONS = {"Vendor", "Supplier", "Partner organisation"}
# Stakeholder can be a person or an organisation: keep its material bearer generic.
GENERIC_ACTORS = {"Stakeholder", "Subject"}


def slug(value: str) -> str:
    return "".join(word[:1].upper() + word[1:] for word in re.findall(r"[A-Za-z0-9]+", value))


def read_ledger(path: Path) -> dict:
    data = json.loads(path.read_text())
    if data.get("status") != "Simulated, not validated":
        raise ValueError("Source status changed; review the model before rebuilding.")
    codes = []
    for subsystem in data["subsystems"]:
        for process in subsystem["processes"]:
            codes.append(process["code"])
            if not all(isinstance(process[key], list) for key in ("steps", *BUCKETS)):
                raise ValueError("Unexpected ledger shape: " + process["code"])
    if not codes or len(set(codes)) != len(codes):
        raise ValueError("Missing or duplicate process codes")
    return {**data, "source": SOURCE,
            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def graph() -> Graph:
    result = Graph()
    for prefix, ns in (("abi", ABI), ("bfo", BFO), ("cco", CCO), ("owl", OWL),
                       ("rdf", RDF), ("rdfs", RDFS), ("skos", SKOS),
                       ("dct", DCTERMS), ("xsd", XSD)):
        result.bind(prefix, ns)
    return result


def literal(g: Graph, subject, predicate, value: str):
    g.add((subject, predicate, Literal(value, lang="en")))


def define(g: Graph, iri, label: str, definition: str, parent=None, kind=OWL.Class):
    g.add((iri, RDF.type, kind))
    literal(g, iri, RDFS.label, label)
    literal(g, iri, SKOS.definition, definition)
    literal(g, iri, RDFS.comment, definition)
    if parent:
        g.add((iri, RDFS.subClassOf, parent))
    return iri


def restriction(g: Graph, subject, prop, target):
    node = BNode()
    g.add((subject, RDFS.subClassOf, node))
    g.add((node, RDF.type, OWL.Restriction))
    g.add((node, OWL.onProperty, prop))
    g.add((node, OWL.someValuesFrom, target))


def union(g: Graph, members):
    members = sorted(set(members), key=str)
    if len(members) == 1:
        return members[0]
    node, head = BNode(), BNode()
    g.add((node, RDF.type, OWL.Class))
    g.add((node, OWL.unionOf, head))
    Collection(g, head, members)
    return node


def header(g, iri, title, data, imports):
    g.add((iri, RDF.type, OWL.Ontology))
    literal(g, iri, DCTERMS.title, title)
    literal(g, iri, RDFS.label, title)
    literal(g, iri, RDFS.comment, STATUS)
    literal(g, iri, ABI.modelingStatus, STATUS)
    literal(g, iri, DCTERMS.source, SOURCE)
    literal(g, iri, ABI.sourceSHA256, data["source_sha256"])
    for imported in imports:
        g.add((iri, OWL.imports, imported))


def shared_model(data):
    g = graph()
    header(g, ABI.ABIProcessLedgerOntology, "ABI process ledger : shared vocabulary", data,
           [URIRef("http://purl.obolibrary.org/obo/bfo/2020/bfo-core.ttl"),
            URIRef("https://www.commoncoreontologies.org/AgentOntology")])
    for name, label, description in (
        ("modelingStatus", "modeling status", "Whether the schema has been validated with the process owner."),
        ("modelingNote", "modeling note", "An explicit modeling interpretation or unresolved issue."),
        ("ledgerCode", "ledger code", "Stable process or subsystem identifier in the ABI ledger."),
        ("sourceSHA256", "source checksum", "SHA-256 of the source ledger at generation time."),
        ("sourceBucket", "source bucket", "Original ledger bucket; provenance, not a BFO classification."),
        ("sourceValue", "source value", "Unmodified wording from the source ledger."),
        ("stepNumber", "step number", "Position in the ledger's suggested step list; not an observed temporal assertion."),
        ("qualityMappingStatus", "quality mapping status", "Whether qualities and their bearers have been explicitly mapped."),
    ):
        define(g, ABI[name], label, description, kind=OWL.AnnotationProperty)
    define(g, ABI.systemViewKind, "system view kind", "Marks a class as a system or subsystem in the process navigation view; not a BFO type.", kind=OWL.AnnotationProperty)
    define(g, ABI.systemViewParent, "system view parent", "Names the containing system for a subsystem navigation grouping; not an assertion about physical parthood.", kind=OWL.AnnotationProperty)
    literal(g, ABI.LedgerProcess, ABI.systemViewKind, "system")
    for bucket in BUCKETS:
        define(g, ABI["ledger" + bucket], "ledger " + bucket,
               "Original " + bucket + " values, retained without imposing a BFO type.", kind=OWL.AnnotationProperty)
    define(g, ABI.LedgerProcess, "ABI AI System", "A process type proposed in the simulated ABI ledger. Select a child process to inspect its participants, steps, places, timing, roles and evidence. " + STATUS, BFO.BFO_0000015)
    define(g, ABI.ProcessStep, "ABI process step", "A proposed temporal part of a ledger process; no execution occurrence is asserted.", BFO.BFO_0000015)
    define(g, ABI.MaterialParticipant, "ABI material participant", "A person, physical group or physical system participating in a proposed ABI process.", BFO.BFO_0000040)
    define(g, ABI.HumanParticipant, "ABI human participant", "A person participating in a proposed ABI process.", CCO.ont00001262)
    g.add((ABI.HumanParticipant, RDFS.subClassOf, ABI.MaterialParticipant))
    define(g, ABI.PhysicalTeam, "ABI physical team", "The aggregate of people performing a team activity, distinct from an organisation's legal identity.", BFO.BFO_0000027)
    g.add((ABI.PhysicalTeam, RDFS.subClassOf, ABI.MaterialParticipant))
    define(g, ABI.ComputingSystem, "ABI physical computing system", "Physical computing equipment carrying the software used in a ledger process. The ledger names software, not particular machines.", ABI.MaterialParticipant)
    define(g, ABI.ExecutionSite, "ABI execution site", "A physical site at which a proposed ledger process occurs.", BFO.BFO_0000029)
    define(g, ABI.ExecutionInterval, "ABI execution interval", "A one-dimensional temporal region occupied by an execution, distinct from its trigger or schedule description.", BFO.BFO_0000038)
    g.add((ABI.ExecutionInterval, RDFS.subClassOf, BFO.BFO_0000008))
    define(g, ABI.InformationArtifact, "ABI information artifact", "Recorded information associated with a ledger process, distinct from the physical medium carrying it.", BFO.BFO_0000031)
    for name, label, definition in (
        ("Software", "ABI software", "Software content, distinct from the material computer on which it executes."),
        ("EvidenceRecord", "ABI evidence record", "A kind of record listed in HOW WE KNOW; its existence, production direction and factual accuracy have not been validated."),
        ("IndicatorRecord", "ABI indicator record", "Recorded status, score or measure listed under HOW IT IS. This record is not itself a BFO quality."),
        ("ObjectiveSpecification", "ABI objective specification", "An intended outcome stated in WHY. An objective is information, distinct from the role realised in pursuing it."),
        ("ExecutionCondition", "ABI execution condition", "A trigger, cadence or timing target stated in WHEN; it is not an actual time interval or an achieved service level."),
        ("ProcessSpecification", "ABI process specification", "The simulated specification describing a proposed process and its steps."),
    ):
        define(g, ABI[name], label, definition, ABI.InformationArtifact)
    define(g, ABI.ExecutionRole, "ABI execution role", "A role borne by a material participant and realised in carrying out a ledger process.", BFO.BFO_0000023)
    restriction(g, ABI.ExecutionRole, BFO.BFO_0000197, ABI.MaterialParticipant)
    # Ranges constrain semantics; omitting broad domains avoids implying that every
    # process in the workspace uses every ledger-specific property.
    for name, label, target, definition in (
        ("documentedBy", "documented by", ABI.EvidenceRecord, "Relates a process to a record documenting it; does not assert whether that record is an input or output."),
        ("usesInformation", "uses information", ABI.InformationArtifact, "Relates a process to information used during it, including software or source material."),
        ("hasIndicatorRecord", "has indicator record", ABI.IndicatorRecord, "Relates a process to recorded measures or statuses associated with it; no quality bearer is implied."),
        ("pursuesObjective", "pursues objective", ABI.ObjectiveSpecification, "Relates a process to its intended outcome specification, without asserting that the outcome is achieved."),
        ("hasExecutionCondition", "has execution condition", ABI.ExecutionCondition, "Relates a process to its described trigger, schedule or timing target."),
        ("hasAssessedQuality", "has assessed quality", BFO.BFO_0000019, "Relates a process to a quality being assessed. The quality inheres in a material bearer, not in the process."),
    ):
        define(g, ABI[name], label, definition, kind=OWL.ObjectProperty)
        g.add((ABI[name], RDFS.range, target))
    literal(g, ABI.LedgerProcess, ABI.modelingStatus, STATUS)
    return g


def actor(g, name):
    """Return (material actor, optional information) without typing software as WHO."""
    if name == "OSINT sources":
        info = define(g, ABI.OSINTSourceInformation, name, "Open-source intelligence information listed as WHO in the ledger; treated as information used, not a material actor.", ABI.InformationArtifact)
        return None, info
    if name in SOFTWARE:
        info = define(g, ABI[slug(name) + "Software"], name + " software", "Software referred to as '" + name + "' in the ledger. Its material deployment is unspecified.", ABI.Software)
        host = define(g, ABI[slug(name) + "Host"], name + " physical host", "Physical computing equipment carrying '" + name + "'. Proposed bearer mapping; no particular machine or deployment is asserted.", ABI.ComputingSystem)
        restriction(g, host, BFO.BFO_0000101, info)
        literal(g, host, ABI.modelingNote, "Physical host inferred from software use; confirm deployment with ABI.")
        return host, info
    if name == "Infrastructure":
        return define(g, ABI.Infrastructure, "Physical IT infrastructure", "Material IT infrastructure participating in provisioning and cyber activities.", ABI.MaterialParticipant), None
    parent = (ABI.PhysicalTeam if name in GROUPS | ORGANISATIONS else
              ABI.MaterialParticipant if name in GENERIC_ACTORS else ABI.HumanParticipant)
    label = name + (" personnel" if name in ORGANISATIONS else " participant")
    participant = define(g, ABI[slug(name) + "Participant"], label, "The material participant referred to as '" + name + "' in the ledger. " + ("For organisations this denotes the people acting on its behalf, not its legal identity." if name in ORGANISATIONS else "Its actual identity is not specified."), parent)
    role = define(g, ABI[slug(name) + "Role"], name + " role", "The role borne by the material participant described as '" + name + "'.", BFO.BFO_0000023)
    restriction(g, participant, BFO.BFO_0000196, role)
    restriction(g, role, BFO.BFO_0000197, participant)
    return participant, None


def generate(data, output, quality_mappings=None):
    quality_mappings = quality_mappings or {}
    output.mkdir(parents=True, exist_ok=True)
    common = shared_model(data)
    actors = {name: actor(common, name) for name in sorted({a for s in data["subsystems"] for p in s["processes"] for a in p["WHO"]})}
    all_codes = {p["code"] for s in data["subsystems"] for p in s["processes"]}
    if set(quality_mappings) - all_codes:
        raise ValueError("Quality mappings refer to unknown processes")
    files, rows = [], []
    for subsystem in data["subsystems"]:
        category = define(common, ABI[subsystem["code"] + "Process"], subsystem["code"] + " · " + subsystem["name"] + " processes", "A proposed process in the " + subsystem["name"] + " subsystem.", BFO.BFO_0000015)
        literal(common, category, ABI.ledgerCode, subsystem["code"])
        literal(common, category, ABI.systemViewKind, "subsystem")
        common.add((category, ABI.systemViewParent, ABI.LedgerProcess))
        for p in subsystem["processes"]:
            code = p["code"].replace("-", "")
            iri = ABI[code]
            g = graph()
            filename = "ABI" + code + slug(p["name"]) + ".ttl"
            header(g, ABI[code + "Ontology"], p["code"] + " · " + p["name"], data, [ABI.ABIProcessLedgerOntology])
            define(g, iri, p["name"], "A proposed ABI " + p["name"].lower() + " process. Suggested steps: " + " → ".join(p["steps"]) + ". " + STATUS + (" HOW IT IS quality mappings are proposed for review." if quality_mappings.get(p["code"]) else " HOW IT IS values are retained as indicator records; quality bearers remain unresolved."), BFO.BFO_0000015)
            g.add((iri, RDFS.subClassOf, ABI.LedgerProcess))
            g.add((iri, RDFS.subClassOf, category))
            literal(g, iri, SKOS.altLabel, p["code"])
            literal(g, iri, ABI.ledgerCode, p["code"])
            literal(g, iri, ABI.modelingStatus, STATUS)
            literal(g, iri, DCTERMS.source, SOURCE)
            for bucket in BUCKETS:
                for value in p[bucket]:
                    literal(g, iri, ABI["ledger" + bucket], value)
            specification = define(g, ABI[code + "Specification"], p["name"] + " specification", "The simulated ledger specification for " + p["code"] + ". It describes a possible process, not an executed run.", ABI.ProcessSpecification)
            restriction(g, iri, BFO.BFO_0000059, specification)
            participants = []
            for name in p["WHO"]:
                material, info = actors[name]
                if material:
                    participants.append(material)
                    restriction(g, iri, BFO.BFO_0000057, material)
                if info:
                    restriction(g, iri, ABI.usesInformation, info)
            for place in p["WHERE"]:
                if place == "Secure network perimeter":
                    site = ABI.ExecutionSite
                    literal(g, iri, ABI.modelingNote, "WHERE 'Secure network perimeter' describes a deployment boundary, not an identified physical site. The occurrence site remains generic pending clarification.")
                else:
                    site = ABI[slug(place) + "Site"]
                    define(common, site, place, "A physical site described as '" + place + "' in the ledger; no concrete location is identified.", ABI.ExecutionSite)
                restriction(g, iri, BFO.BFO_0000066, site)
            interval = define(g, ABI[code + "Interval"], p["name"] + " execution interval", "The temporal region occupied by an execution of " + p["name"] + "; actual dates are unspecified.", ABI.ExecutionInterval)
            restriction(g, iri, BFO.BFO_0000199, interval)
            for idx, condition in enumerate(p["WHEN"], 1):
                target = define(g, ABI[code + "Condition" + str(idx)], p["name"] + " timing condition", "Ledger trigger/cadence/target: " + condition + ". No occurrence or achieved timing is asserted.", ABI.ExecutionCondition)
                literal(g, target, ABI.sourceValue, condition)
                restriction(g, iri, ABI.hasExecutionCondition, target)
            role = define(g, ABI[code + "ExecutionRole"], p["name"] + " execution role", "A proposed role realised in " + p["name"] + " and borne by a listed material participant. The accountable bearer must be confirmed with ABI.", ABI.ExecutionRole)
            restriction(g, role, BFO.BFO_0000197, union(g, participants))
            restriction(g, iri, BFO.BFO_0000055, role)
            for idx, objective in enumerate(p["WHY"], 1):
                target = define(g, ABI[code + "Objective" + str(idx)], p["name"] + " objective", "Intended outcome: " + objective + ". This is an objective specification, not a role or a guaranteed result.", ABI.ObjectiveSpecification)
                literal(g, target, ABI.sourceValue, objective)
                restriction(g, iri, ABI.pursuesObjective, target)
            for bucket, suffix, parent, prop in (
                ("HOWWEKNOW", "Record", ABI.EvidenceRecord, ABI.documentedBy),
                ("HOWITIS", "Indicator", ABI.IndicatorRecord, ABI.hasIndicatorRecord),
            ):
                for value in p[bucket]:
                    target = ABI[slug(value) + suffix]
                    define(common, target, value + (" record" if bucket == "HOWITIS" else ""), "Information described as '" + value + "' under " + bucket + " in the simulated ledger.", parent)
                    literal(common, target, ABI.sourceBucket, bucket)
                    literal(common, target, ABI.sourceValue, value)
                    restriction(g, iri, prop, target)
            for idx, step in enumerate(p["steps"], 1):
                step_iri = define(g, ABI[code + "Step" + str(idx)], p["name"] + " · " + step, "Suggested step " + str(idx) + " of " + p["name"] + ": " + step + ". Its ordering is a specification, not observed timing.", BFO.BFO_0000015)
                g.add((step_iri, RDFS.subClassOf, ABI.ProcessStep))
                g.add((step_iri, ABI.stepNumber, Literal(idx, datatype=XSD.integer)))
                restriction(g, iri, BFO.BFO_0000117, step_iri)
                restriction(g, step_iri, BFO.BFO_0000132, iri)
            mappings = quality_mappings.get(p["code"], [])
            for idx, mapping in enumerate(mappings, 1):
                if mapping["bearer"] not in p["WHO"] or not actors[mapping["bearer"]][0]:
                    raise ValueError("Quality bearer must be a material participant in " + p["code"])
                if mapping["indicator"] not in p["HOWITIS"]:
                    raise ValueError("Quality indicator not in " + p["code"])
                quality = define(g, ABI[code + "Quality" + str(idx)], mapping["label"], mapping["definition"], BFO.BFO_0000019)
                literal(g, quality, ABI.modelingStatus, "Proposed quality mapping; requires ABI validation.")
                literal(g, quality, ABI.modelingNote, mapping["rationale"])
                literal(g, quality, ABI.sourceValue, mapping["indicator"])
                restriction(g, quality, BFO.BFO_0000197, actors[mapping["bearer"]][0])
                restriction(g, iri, ABI.hasAssessedQuality, quality)
            quality_status = "Proposed : bearer and quality require review" if mappings else "Unresolved : source indicators retained as information; no quality bearer supplied"
            literal(g, iri, ABI.qualityMappingStatus, quality_status)
            literal(g, iri, RDFS.comment, quality_status)
            for subject in set(g.subjects(RDF.type, OWL.Class)):
                if isinstance(subject, URIRef):
                    literal(g, subject, ABI.modelingStatus, STATUS)
            g.serialize(output / filename, format="turtle")
            files.append(filename)
            rows.append({"code": p["code"], "name": p["name"], "iri": str(iri), "file": filename,
                         "subsystem": subsystem["name"], "qualities": len(mappings), "quality_status": quality_status})
    # Shared terms also carry explicit draft status and source provenance.
    for subject in set(common.subjects(RDF.type, OWL.Class)):
        if isinstance(subject, URIRef) and str(subject).startswith(str(ABI)):
            literal(common, subject, ABI.modelingStatus, STATUS)
            literal(common, subject, DCTERMS.source, SOURCE)
    common.serialize(output / "ABIProcessLedgerOntology.ttl", format="turtle")
    manifest = {"source": SOURCE, "source_sha256": data["source_sha256"], "status": STATUS,
                "process_count": len(rows), "step_count": sum(len(p["steps"]) for s in data["subsystems"] for p in s["processes"]),
                "subsystem_count": len(data["subsystems"]), "files": ["ABIProcessLedgerOntology.ttl", *files], "processes": rows}
    (output / "process_ledger_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).parent / "source_ledger.json")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent)
    parser.add_argument("--quality-mappings", type=Path, help="Explicitly reviewed draft quality/bearer proposals keyed by process code.")
    args = parser.parse_args()
    mappings = json.loads(args.quality_mappings.read_text()) if args.quality_mappings else None
    result = generate(read_ledger(args.source), args.output, mappings)
    print(f"Generated {result['process_count']} process ontologies, {result['step_count']} steps and one shared vocabulary.")


if __name__ == "__main__":
    main()
