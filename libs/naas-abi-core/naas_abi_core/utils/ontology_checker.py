"""
ontology_checker.py
-------------------
Unified ontology inconsistency checker.

Accepts any .ttl / .owl / .nt / .rdf file and runs three independent
validation layers in sequence, producing a single consolidated JSON report.

LAYER 1 — Static analysis  (validate_bfo_ontology.validate)
    Structural checks: annotations, BFO bucket mapping, restriction
    inheritance, naming, inverses, disjointness, etc.
    Dependency: rdflib  (pip install rdflib)

LAYER 2 — OWL reasoning  (owlready2 + HermiT)
    Logical consistency: unsatisfiable classes, contradictory axioms,
    entailed subsumptions your axioms imply but didn't state.
    Dependency: owlready2 + Java >= 8  (pip install owlready2)

LAYER 3 — SHACL validation  (pyshacl)
    Instance/data conformance: cardinality, type constraints, pattern
    rules expressed as SHACL shapes.  You may supply your own shapes
    file or let the checker auto-generate minimal shapes from the
    ontology's own OWL restrictions.
    Dependency: pyshacl  (pip install pyshacl)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import textwrap
from typing import Any


# ---------------------------------------------------------------------------
# Optional dependency probes
# ---------------------------------------------------------------------------

def _probe_rdflib() -> tuple[bool, str]:
    try:
        import rdflib  # noqa: F401
        return True, ""
    except ImportError:
        return False, "rdflib not installed (pip install rdflib)"


def _probe_owlready2() -> tuple[bool, str]:
    try:
        import owlready2  # type: ignore[import-not-found]  # noqa: F401
        return True, ""
    except ImportError:
        return False, "owlready2 not installed (pip install owlready2)"


def _probe_pyshacl() -> tuple[bool, str]:
    try:
        import pyshacl  # type: ignore[import-not-found]  # noqa: F401
        return True, ""
    except ImportError:
        return False, "pyshacl not installed (pip install pyshacl)"


def _probe_validate_module() -> tuple[bool, str]:
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)
        import validate_bfo_ontology  # type: ignore[import-not-found]  # noqa: F401
        return True, ""
    except ImportError:
        return False, (
            "validate_bfo_ontology.py not found alongside this script. "
            "Place both files in the same directory."
        )


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

_EXT_TO_FORMAT: dict[str, str] = {
    ".ttl":    "turtle",
    ".turtle": "turtle",
    ".owl":    "xml",
    ".rdf":    "xml",
    ".xml":    "xml",
    ".nt":     "nt",
    ".n3":     "n3",
    ".trig":   "trig",
    ".jsonld": "json-ld",
    ".json":   "json-ld",
}


def detect_format(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return _EXT_TO_FORMAT.get(ext, "turtle")


# ---------------------------------------------------------------------------
# LAYER 1 — Static analysis
# ---------------------------------------------------------------------------

def run_static(source_path: str, raise_error: bool) -> dict[str, Any]:
    ok, reason = _probe_validate_module()
    if not ok:
        return {"layer": "static", "skipped": True, "reason": reason}

    ok2, reason2 = _probe_rdflib()
    if not ok2:
        return {"layer": "static", "skipped": True, "reason": reason2}

    import validate_bfo_ontology as v  # type: ignore[import-not-found]

    work_path = _ensure_turtle(source_path)
    try:
        report = v.validate(work_path, raise_error=raise_error)
    finally:
        if work_path != source_path:
            try:
                os.unlink(work_path)
            except OSError:
                pass

    report["layer"] = "static"
    return report


def _ensure_turtle(source_path: str) -> str:
    fmt = detect_format(source_path)
    if fmt == "turtle":
        return source_path

    from rdflib import Graph
    g = Graph()
    g.parse(source_path, format=fmt)
    tmp = tempfile.NamedTemporaryFile(
        suffix=".ttl", delete=False, mode="w", encoding="utf-8"
    )
    tmp.write(g.serialize(format="turtle"))
    tmp.close()
    return tmp.name


# ---------------------------------------------------------------------------
# LAYER 2 — OWL reasoning
# ---------------------------------------------------------------------------

def run_reasoning(source_path: str) -> dict[str, Any]:
    ok, reason = _probe_owlready2()
    if not ok:
        return {"layer": "reasoning", "skipped": True, "reason": reason}

    import owlready2  # type: ignore[import-not-found]
    from owlready2 import (  # type: ignore[import-not-found]
        get_ontology,
        sync_reasoner_hermit,
    )

    result: dict[str, Any] = {
        "layer":                 "reasoning",
        "skipped":               False,
        "consistent":            True,
        "inconsistency_reason":  "",
        "unsatisfiable_classes": [],
        "inferred_subclasses":   [],
        "errors":                [],
        "warnings":              [],
        "info":                  [],
    }

    abs_path = os.path.abspath(source_path)
    file_uri = f"file://{abs_path}"

    try:
        onto = get_ontology(file_uri).load()
    except Exception as exc:
        result["errors"].append({
            "severity": "ERROR",
            "category": "REASONING_LOAD",
            "subject":  source_path,
            "message":  f"owlready2 could not load the ontology: {exc}",
        })
        result["consistent"] = False
        return result

    stated_parents: dict[str, set[str]] = {}
    for cls in onto.classes():
        stated_parents[cls.iri] = {
            p.iri for p in cls.is_a
            if hasattr(p, "iri")
        }

    try:
        with onto:
            sync_reasoner_hermit(
                infer_property_values=False,
                infer_data_property_values=False,
                debug=0,
            )
    except owlready2.OwlReadyInconsistentOntologyError as exc:
        result["consistent"] = False
        result["inconsistency_reason"] = str(exc)
        result["errors"].append({
            "severity": "ERROR",
            "category": "INCONSISTENT_ONTOLOGY",
            "subject":  source_path,
            "message": (
                "The ontology is logically INCONSISTENT. "
                "No class can have any instance. "
                f"Reasoner detail: {exc}"
            ),
        })
        return result
    except Exception as exc:
        result["warnings"].append({
            "severity": "WARNING",
            "category": "REASONING_ERROR",
            "subject":  source_path,
            "message":  f"HermiT raised an unexpected error: {exc}",
        })
        return result

    unsat: list[dict] = []
    nothing = owlready2.Nothing
    for cls in onto.classes():
        if nothing in cls.equivalent_to or cls.iri == str(owlready2.Nothing.iri):
            continue
        parents_after = {p.iri for p in cls.is_a if hasattr(p, "iri")}
        if "http://www.w3.org/2002/07/owl#Nothing" in parents_after:
            label = (
                cls.label.first()
                if hasattr(cls, "label") and cls.label
                else cls.name
            )
            unsat.append({"iri": cls.iri, "label": str(label)})
            result["errors"].append({
                "severity": "ERROR",
                "category": "UNSATISFIABLE_CLASS",
                "subject":  cls.iri,
                "message": (
                    f"Class '{label}' ({cls.iri}) is unsatisfiable — "
                    f"the reasoner classified it as equivalent to owl:Nothing. "
                    f"It can never have any instance."
                ),
            })
    result["unsatisfiable_classes"] = unsat

    inferred: list[dict] = []
    for cls in onto.classes():
        after = {p.iri for p in cls.is_a if hasattr(p, "iri")}
        before = stated_parents.get(cls.iri, set())
        new_parents = after - before
        for parent_iri in new_parents:
            if parent_iri in (
                "http://www.w3.org/2002/07/owl#Thing",
                "http://www.w3.org/2002/07/owl#Nothing",
            ):
                continue
            inferred.append({"child": cls.iri, "parent": parent_iri})
            result["info"].append({
                "severity": "INFO",
                "category": "INFERRED_SUBCLASS",
                "subject":  cls.iri,
                "message": (
                    f"The reasoner inferred that '{cls.name}' is a subclass of "
                    f"'{parent_iri}' — this relationship was not stated explicitly "
                    f"but follows from your axioms."
                ),
            })
    result["inferred_subclasses"] = inferred

    if result["consistent"] and not unsat:
        result["info"].append({
            "severity": "INFO",
            "category": "REASONING_OK",
            "subject":  source_path,
            "message":  "Ontology is logically consistent. No unsatisfiable classes found.",
        })

    return result


# ---------------------------------------------------------------------------
# LAYER 3 — SHACL validation
# ---------------------------------------------------------------------------

_BUILTIN_SHACL = textwrap.dedent("""\
    @prefix sh:   <http://www.w3.org/ns/shacl#> .
    @prefix owl:  <http://www.w3.org/2002/07/owl#> .
    @prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
    @prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
    @prefix bfo:  <http://purl.obolibrary.org/obo/> .

    bfo:QualityShape a sh:NodeShape ;
        sh:targetClass bfo:BFO_0000019 ;
        sh:property [
            sh:path bfo:BFO_0000197 ;
            sh:minCount 1 ;
            sh:severity sh:Violation ;
            sh:message "A quality instance must have at least one 'inheres in' (bfo:BFO_0000197) value." ;
        ] .

    bfo:RoleShape a sh:NodeShape ;
        sh:targetClass bfo:BFO_0000023 ;
        sh:property [
            sh:path bfo:BFO_0000197 ;
            sh:minCount 1 ;
            sh:severity sh:Violation ;
            sh:message "A role instance must have at least one 'inheres in' (bfo:BFO_0000197) value." ;
        ] .

    bfo:DispositionShape a sh:NodeShape ;
        sh:targetClass bfo:BFO_0000016 ;
        sh:property [
            sh:path bfo:BFO_0000197 ;
            sh:minCount 1 ;
            sh:severity sh:Violation ;
            sh:message "A disposition instance must have at least one 'inheres in' (bfo:BFO_0000197) value." ;
        ] .

    bfo:ProcessShape a sh:NodeShape ;
        sh:targetClass bfo:BFO_0000015 ;
        sh:property [
            sh:path bfo:BFO_0000057 ;
            sh:minCount 1 ;
            sh:severity sh:Warning ;
            sh:message "A process instance should have at least one 'has participant' (bfo:BFO_0000057) value." ;
        ] .

    bfo:MaterialEntityShape a sh:NodeShape ;
        sh:targetClass bfo:BFO_0000040 ;
        sh:property [
            sh:path rdfs:label ;
            sh:minCount 1 ;
            sh:severity sh:Info ;
            sh:message "A material entity instance should carry an rdfs:label." ;
        ] .

    bfo:GDCShape a sh:NodeShape ;
        sh:targetClass bfo:BFO_0000031 ;
        sh:property [
            sh:path bfo:BFO_0000084 ;
            sh:minCount 1 ;
            sh:severity sh:Violation ;
            sh:message "A generically dependent continuant instance must have at least one 'generically depends on' (bfo:BFO_0000084) value." ;
        ] .
""")


def _build_shacl_shapes_from_ontology(ont_path: str) -> str:
    try:
        from rdflib import Graph, RDF, RDFS, OWL, URIRef, BNode

        fmt = detect_format(ont_path)
        g = Graph()
        g.parse(ont_path, format=fmt)

        lines = [
            "@prefix sh:   <http://www.w3.org/ns/shacl#> .",
            "@prefix owl:  <http://www.w3.org/2002/07/owl#> .",
            "@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
            "@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .",
            "",
        ]

        for cls in g.subjects(RDF.type, OWL.Class):
            if not isinstance(cls, URIRef):
                continue
            props: list[str] = []
            for parent in g.objects(cls, RDFS.subClassOf):
                if not isinstance(parent, BNode):
                    continue
                if g.value(parent, RDF.type) != OWL.Restriction:
                    continue
                on_prop = g.value(parent, OWL.onProperty)
                if not isinstance(on_prop, URIRef):
                    continue

                svf = g.value(parent, OWL.someValuesFrom)
                avf = g.value(parent, OWL.allValuesFrom)

                if isinstance(svf, URIRef):
                    props.append(
                        f"    sh:property [\n"
                        f"        sh:path <{on_prop}> ;\n"
                        f"        sh:minCount 1 ;\n"
                        f"        sh:class <{svf}> ;\n"
                        f"        sh:severity sh:Violation ;\n"
                        f"        sh:message \"Instance of <{cls}> must have at least "
                        f"one <{on_prop}> value of type <{svf}>.\" ;\n"
                        f"    ]"
                    )
                elif isinstance(avf, URIRef):
                    props.append(
                        f"    sh:property [\n"
                        f"        sh:path <{on_prop}> ;\n"
                        f"        sh:class <{avf}> ;\n"
                        f"        sh:severity sh:Violation ;\n"
                        f"        sh:message \"All <{on_prop}> values of <{cls}> "
                        f"instances must be of type <{avf}>.\" ;\n"
                        f"    ]"
                    )

            if props:
                shape_iri = str(cls) + "Shape"
                lines.append(f"<{shape_iri}> a sh:NodeShape ;")
                lines.append(f"    sh:targetClass <{cls}> ;")
                lines.append(" ;\n".join(props) + " .")
                lines.append("")

        return "\n".join(lines)

    except Exception:
        return ""


def run_shacl(
    source_path: str,
    shapes_path: str | None = None,
) -> dict[str, Any]:
    ok, reason = _probe_pyshacl()
    if not ok:
        return {"layer": "shacl", "skipped": True, "reason": reason}

    from pyshacl import validate as shacl_validate  # type: ignore[import-not-found]

    result: dict[str, Any] = {
        "layer":      "shacl",
        "skipped":    False,
        "conforms":   True,
        "violations": [],
        "warnings":   [],
        "info":       [],
        "raw_report": "",
    }

    if shapes_path:
        with open(shapes_path, "r", encoding="utf-8") as fh:
            shapes_ttl = fh.read()
    else:
        auto_shapes = _build_shacl_shapes_from_ontology(source_path)
        shapes_ttl = _BUILTIN_SHACL + "\n" + auto_shapes

    fmt = detect_format(source_path)

    try:
        conforms, results_graph, results_text = shacl_validate(
            data_graph=source_path,
            data_graph_format=fmt,
            shacl_graph=shapes_ttl,
            shacl_graph_format="turtle",
            ont_graph=source_path,
            ont_graph_format=fmt,
            inference="rdfs",
            abort_on_first=False,
            serialize_report_to=None,
            meta_shacl=False,
            debug=False,
        )
    except Exception as exc:
        result["warnings"].append({
            "severity": "WARNING",
            "category": "SHACL_ERROR",
            "subject":  source_path,
            "message":  f"pyshacl raised an error: {exc}",
        })
        return result

    result["conforms"]   = conforms
    result["raw_report"] = results_text

    try:
        _parse_shacl_results(results_graph, result)
    except Exception:
        pass

    return result


def _parse_shacl_results(results_graph: Any, result: dict) -> None:
    from rdflib import Namespace, RDF
    SH = Namespace("http://www.w3.org/ns/shacl#")

    SEVERITY_MAP = {
        str(SH.Violation): ("ERROR",   "SHACL_VIOLATION"),
        str(SH.Warning):   ("WARNING", "SHACL_WARNING"),
        str(SH.Info):      ("INFO",    "SHACL_INFO"),
    }

    for result_node in results_graph.subjects(
        RDF.type, SH.ValidationResult
    ):
        severity_node = results_graph.value(result_node, SH.resultSeverity)
        severity_iri  = str(severity_node) if severity_node else str(SH.Violation)
        severity, category = SEVERITY_MAP.get(
            severity_iri, ("WARNING", "SHACL_WARNING")
        )

        focus   = results_graph.value(result_node, SH.focusNode)
        path    = results_graph.value(result_node, SH.resultPath)
        message = results_graph.value(result_node, SH.resultMessage)
        source  = results_graph.value(result_node, SH.sourceShape)

        issue = {
            "severity": severity,
            "category": category,
            "subject":  str(focus)   if focus   else "unknown",
            "path":     str(path)    if path    else "",
            "message":  str(message) if message else "",
            "source_shape": str(source) if source else "",
        }

        if severity == "ERROR":
            result["violations"].append(issue)
        elif severity == "WARNING":
            result["warnings"].append(issue)
        else:
            result["info"].append(issue)


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------

def _layer_summary(static: dict, reasoning: dict, shacl: dict) -> dict:
    def _count(layer: dict, key: str) -> int:
        if layer.get("skipped"):
            return 0
        items = layer.get(key, [])
        return len(items) if isinstance(items, list) else 0

    static_errors   = _count(static,   "errors")
    static_warnings = _count(static,   "warnings")
    static_info     = _count(static,   "info")

    reasoning_errors   = _count(reasoning, "errors")
    reasoning_warnings = _count(reasoning, "warnings")
    reasoning_info     = _count(reasoning, "info")

    shacl_violations = _count(shacl, "violations")
    shacl_warnings   = _count(shacl, "warnings")
    shacl_info       = _count(shacl, "info")

    total = (
        static_errors + static_warnings
        + reasoning_errors + reasoning_warnings
        + shacl_violations + shacl_warnings
    )

    return {
        "total_issues": total,
        "by_layer": {
            "static": {
                "skipped":  static.get("skipped", False),
                "errors":   static_errors,
                "warnings": static_warnings,
                "info":     static_info,
            },
            "reasoning": {
                "skipped":              reasoning.get("skipped", False),
                "consistent":           reasoning.get("consistent", None),
                "unsatisfiable_classes": len(reasoning.get("unsatisfiable_classes", [])),
                "inferred_subclasses":  len(reasoning.get("inferred_subclasses", [])),
                "errors":               reasoning_errors,
                "warnings":             reasoning_warnings,
                "info":                 reasoning_info,
            },
            "shacl": {
                "skipped":    shacl.get("skipped", False),
                "conforms":   shacl.get("conforms", None),
                "violations": shacl_violations,
                "warnings":   shacl_warnings,
                "info":       shacl_info,
            },
        },
    }


def build_full_report(
    source_path:    str,
    fmt:            str,
    layers_run:     list[str],
    layers_skipped: dict[str, str],
    static:         dict,
    reasoning:      dict,
    shacl:          dict,
    no_raw:         bool = False,
) -> dict[str, Any]:
    if no_raw:
        shacl.pop("raw_report", None)

    return {
        "source":          source_path,
        "format":          fmt,
        "layers_run":      layers_run,
        "layers_skipped":  layers_skipped,
        "summary":         _layer_summary(static, reasoning, shacl),
        "static":          static,
        "reasoning":       reasoning,
        "shacl":           shacl,
    }


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def check(
    source_path:    str,
    layers:         list[str]   | None = None,
    shapes_path:    str         | None = None,
    raise_error:    bool               = False,
    no_raw:         bool               = False,
) -> dict[str, Any]:
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Ontology file not found: {source_path}")

    requested = set(layers) if layers else {"static", "reasoning", "shacl"}
    fmt = detect_format(source_path)

    layers_run:     list[str]       = []
    layers_skipped: dict[str, str]  = {}

    static_result:    dict = {"layer": "static",    "skipped": True, "reason": "not requested"}
    reasoning_result: dict = {"layer": "reasoning", "skipped": True, "reason": "not requested"}
    shacl_result:     dict = {"layer": "shacl",     "skipped": True, "reason": "not requested"}

    if "static" in requested:
        static_result = run_static(source_path, raise_error=raise_error)
        if static_result.get("skipped"):
            layers_skipped["static"] = static_result.get("reason", "skipped")
        else:
            layers_run.append("static")

    if "reasoning" in requested:
        reasoning_result = run_reasoning(source_path)
        if reasoning_result.get("skipped"):
            layers_skipped["reasoning"] = reasoning_result.get("reason", "skipped")
        else:
            layers_run.append("reasoning")
            if raise_error:
                for issue in reasoning_result.get("errors", []):
                    raise ValueError(
                        f"[{issue['category']}] {issue['subject']}: {issue['message']}"
                    )

    if "shacl" in requested:
        shacl_result = run_shacl(source_path, shapes_path=shapes_path)
        if shacl_result.get("skipped"):
            layers_skipped["shacl"] = shacl_result.get("reason", "skipped")
        else:
            layers_run.append("shacl")
            if raise_error and not shacl_result.get("conforms", True):
                v = shacl_result.get("violations", [])
                if v:
                    msg = v[0]["message"] or "SHACL violation"
                    raise ValueError(f"[SHACL_VIOLATION] {v[0]['subject']}: {msg}")

    return build_full_report(
        source_path    = source_path,
        fmt            = fmt,
        layers_run     = layers_run,
        layers_skipped = layers_skipped,
        static         = static_result,
        reasoning      = reasoning_result,
        shacl          = shacl_result,
        no_raw         = no_raw,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Unified ontology inconsistency checker.\n"
            "Runs static analysis, OWL reasoning, and SHACL validation\n"
            "against a single ontology file and outputs a JSON report."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "source",
        help="Path to the ontology file (.ttl, .owl, .nt, .rdf, ...).",
    )
    parser.add_argument(
        "--layers",
        nargs="+",
        choices=["static", "reasoning", "shacl"],
        default=None,
        metavar="LAYER",
    )
    parser.add_argument("--shapes", default=None, metavar="SHAPES_FILE")
    parser.add_argument("--output", default=None, metavar="FILE")
    parser.add_argument("--raise-error", action="store_true", default=False)
    parser.add_argument("--no-raw", action="store_true", default=False)
    args = parser.parse_args()

    try:
        report = check(
            source_path = args.source,
            layers      = args.layers,
            shapes_path = args.shapes,
            raise_error = args.raise_error,
            no_raw      = args.no_raw,
        )
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        print(f"\nStopped on first error:\n  {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"UNEXPECTED ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    report_json = json.dumps(report, indent=2, ensure_ascii=False)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(report_json)
        print(f"Report written to: {args.output}", file=sys.stderr)
    else:
        print(report_json)

    summary = report.get("summary", {})
    if summary.get("total_issues", 0) > 0:
        sys.exit(1)
    reasoning = report.get("reasoning", {})
    if not reasoning.get("skipped") and not reasoning.get("consistent", True):
        sys.exit(1)
    shacl = report.get("shacl", {})
    if not shacl.get("skipped") and not shacl.get("conforms", True):
        sys.exit(1)


if __name__ == "__main__":
    main()
