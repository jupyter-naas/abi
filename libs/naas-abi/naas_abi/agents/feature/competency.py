"""Competency questions for the Nexus feature office agents, and their grading.

Each feature agent must answer the four kinds of question the product asks of
it: what can I do here, how was it built, how do I operate it, and anything
else about the feature. Abi, the orchestrator that hands off to every feature
agent (and the Home and Chat agent when a workspace sets no default), must
answer the same questions by handing off. Questions are self-contained (they name the
feature) so the same text works on the feature pane and through Abi.

Grading is deliberately mechanical so a live run is comparable across models:
the run must not fail, a grounded question must use at least one of its
expected tools (feature tools, or the source tools for "how was it built"),
and the answer must contain at least one expected term.
``competency_eval`` runs them against a live engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Kind = Literal["capabilities", "implementation", "operate", "other"]

SOURCE_TOOLS = ("read_nexus_source", "search_nexus_source", "list_nexus_source")

# Phrases that mean the run failed or the agent gave up.
FAILURE_MARKERS = (
    "do not have the capabilit",
    "don't have the capabilit",
    "operation failed. check server logs",
    "step limit",
    "recursion limit",
    "an error occurred",
    "no authenticated user on this agent session",
)


@dataclass(frozen=True)
class CompetencyQuestion:
    question: str
    kind: Kind
    expect_tools: tuple[str, ...] = ()
    expect_terms: tuple[str, ...] = ()


@dataclass
class Grade:
    passed: bool
    reasons: list[str] = field(default_factory=list)


def _q(
    question: str,
    kind: Kind,
    tools: tuple[str, ...] = (),
    terms: tuple[str, ...] = (),
) -> CompetencyQuestion:
    return CompetencyQuestion(question, kind, tools, tuple(t.lower() for t in terms))


COMPETENCY_QUESTIONS: dict[str, tuple[CompetencyQuestion, ...]] = {
    "Slides": (
        _q(
            "What can the Nexus Slides agent do for me?",
            "capabilities",
            terms=("deck", "slide"),
        ),
        _q(
            "How is PPTX export implemented in Nexus Slides? Read the code and cite the files.",
            "implementation",
            SOURCE_TOOLS,
            ("pptx",),
        ),
        _q(
            "In Nexus Slides, how do I start a new presentation from a template? Just explain the steps, do not create anything.",
            "operate",
            terms=("template",),
        ),
        _q(
            "Qu'est-ce que la source de vérité d'un deck Nexus Slides, le HTML ou le PPTX ?",
            "other",
            terms=("html",),
        ),
    ),
    "Apps": (
        _q(
            "What can I do with Apps in Nexus?",
            "capabilities",
            terms=("enable", "embed", "open"),
        ),
        _q(
            "How does Nexus discover which apps exist? Read the code and cite the files.",
            "implementation",
            SOURCE_TOOLS,
            ("manifest.json",),
        ),
        _q(
            "List the Nexus apps of this workspace and say which ones are enabled.",
            "operate",
            ("list_workspace_apps",),
            ("enabled", "disabled"),
        ),
        _q(
            "In Nexus Apps, why would a bundled app get a 401 on /app-html/? Check the code.",
            "other",
            SOURCE_TOOLS,
            ("token",),
        ),
        _q(
            "Comment activer une app Nexus dans cet espace de travail ? Explique seulement, n'active rien.",
            "operate",
            terms=("activ", "enable"),
        ),
    ),
    "Marketplace": (
        _q(
            "What can I do in the Nexus Marketplace?", "capabilities", terms=("module",)
        ),
        _q(
            "How does the Nexus Marketplace build its module catalog? Read the code and cite the files.",
            "implementation",
            SOURCE_TOOLS,
            ("modules/service.py", "list_modules"),
        ),
        _q(
            "Which ABI modules are installed in this Nexus deployment?",
            "operate",
            ("list_marketplace_modules",),
            ("installed",),
        ),
        _q(
            "How do I install a Nexus Marketplace module that is not installed yet?",
            "other",
            terms=("config.yaml",),
        ),
        _q(
            "Quelle différence entre la Marketplace et les Apps dans Nexus ?",
            "other",
            terms=("app",),
        ),
    ),
    "Ontology": (
        _q(
            "What can I do in the Nexus Ontology section?",
            "capabilities",
            terms=("class", "ontolog"),
        ),
        _q(
            "How does Nexus decide which ontologies a workspace sees? Read the code and cite the files.",
            "implementation",
            SOURCE_TOOLS,
            ("seed", "ontologies:"),
        ),
        _q(
            "List the ontologies in this Nexus workspace's ontology catalog.",
            "operate",
            ("list_workspace_ontologies",),
            (".ttl", "ontolog"),
        ),
        _q(
            "Following the Nexus BFO modeling rules, how should I model a new ontology class 'Supplier'?",
            "other",
            # Abi may route modeling to the Ontology Engineer, the BFO specialist.
            ("get_bfo_modeling_guidelines", "transfer_to_Ontology_Engineer"),
            ("owl:class", "skos:definition"),
        ),
        _q(
            "Comment importer une ontologie dans Nexus ?",
            "operate",
            terms=("import", ".ttl"),
        ),
    ),
    "Knowledge Graph": (
        _q(
            "What can I do with the Nexus knowledge graph?",
            "capabilities",
            terms=("graph",),
        ),
        _q(
            "How are Nexus knowledge graph KPIs cached? Read the code and cite the files.",
            "implementation",
            SOURCE_TOOLS,
            ("cache",),
        ),
        _q(
            "List the knowledge graphs of this Nexus workspace.",
            "operate",
            ("list_workspace_graphs",),
            ("graph",),
        ),
        _q(
            "Can the Nexus Knowledge Graph agent run raw SPARQL across all graphs? Why?",
            "other",
            terms=("workspace", "tenant"),
        ),
        _q(
            "Comment exporter un graphe de connaissances Nexus en Turtle ?",
            "operate",
            terms=("export", "turtle", "ttl"),
        ),
    ),
    "Files": (
        _q("What can I do in Nexus Files?", "capabilities", terms=("drive", "folder")),
        _q(
            "How are Nexus storage paths laid out for My drive and the workspace drive? Read the code and cite the files.",
            "implementation",
            SOURCE_TOOLS,
            ("workspace-drive", "my-drive"),
        ),
        _q(
            "List the files and folders at the root of this Nexus workspace drive.",
            "operate",
            ("list_files",),
            ("folder", "file", "empty"),
        ),
        _q(
            "What is the maximum upload size in Nexus Files and where is it enforced? Check the code.",
            "other",
            SOURCE_TOOLS,
            ("upload",),
        ),
        _q(
            "Comment partager un fichier avec tout l'espace de travail dans Nexus ?",
            "operate",
            terms=("drive",),
        ),
    ),
    "Datasets": (
        _q(
            "What can I do with Nexus Datasets?",
            "capabilities",
            terms=("sql", "dataset"),
        ),
        _q(
            "How does Nexus keep dataset SQL queries read-only? Read the code and cite the files.",
            "implementation",
            SOURCE_TOOLS,
            ("assert_read_only_sql", "sql_safe"),
        ),
        _q(
            "List the Nexus datasets available in this workspace.",
            "operate",
            ("list_datasets",),
            ("dataset",),
        ),
        _q(
            "Can I delete rows from a Nexus dataset with SQL?",
            "other",
            terms=("read-only", "read only", "select"),
        ),
        _q(
            "Comment voir le schéma d'un dataset Nexus ?",
            "operate",
            terms=("colonne", "column", "schéma", "schema"),
        ),
    ),
    "Search": (
        _q(
            "What can I search with Nexus Search?",
            "capabilities",
            terms=("wikipedia", "web"),
        ),
        _q(
            "Why does the Nexus workspace search endpoint return no results? Read the code.",
            "implementation",
            SOURCE_TOOLS,
            ("stub", "empty", "no results", "not implemented"),
        ),
        _q(
            "Use Nexus Search to search Wikipedia for 'Basic Formal Ontology'.",
            "operate",
            ("search_public_web",),
            ("ontology",),
        ),
        _q(
            "Quelles sources la recherche Nexus interroge-t-elle ?",
            "other",
            terms=("wikipedia", "ontolog"),
        ),
    ),
    "Maps": (
        _q(
            "Which Nexus map layers can I use?",
            "capabilities",
            ("list_map_layers",),
            ("earthquake",),
        ),
        _q(
            "Where does the Nexus Maps earthquakes layer get its data? Read the code and cite the files.",
            "implementation",
            SOURCE_TOOLS,
            ("usgs",),
        ),
        _q(
            "How do I add a custom map layer to Nexus Maps for my deployment?",
            "other",
            terms=("next_public_maps_custom_datasets",),
        ),
        _q(
            "Comment afficher les incendies sur la carte Nexus ?",
            "operate",
            terms=("wildfire", "incendie", "firms"),
        ),
    ),
    "Code": (
        _q("What can I do in Nexus Code?", "capabilities", terms=("repo",)),
        _q(
            "How does Nexus bind a chat turn to a Coder workspace for the open repo? Read the code and cite the files.",
            "implementation",
            SOURCE_TOOLS,
            ("lookup_code_bindings", "coding"),
        ),
        _q(
            "List the code repositories available in Nexus Code.",
            "operate",
            ("list_code_repositories",),
            ("repo",),
        ),
        _q(
            "Why is Nexus Code hidden for members by default?",
            "other",
            terms=("opt-in", "feature flag", "feature_flags"),
        ),
        _q(
            "Quelle différence entre un espace de travail business et un espace de code dans Nexus ?",
            "other",
            terms=("coder",),
        ),
    ),
    "Settings": (
        _q(
            "What can I do in Nexus workspace settings?",
            "capabilities",
            terms=("member", "secret"),
        ),
        _q(
            "How are the effective Nexus feature flags computed for a role? Read the code and cite the files.",
            "implementation",
            SOURCE_TOOLS + ("get_workspace_settings",),
            ("build_feature_flags", "role"),
        ),
        _q(
            "List the members of this Nexus workspace.",
            "operate",
            ("list_workspace_members",),
            ("owner", "member", "admin"),
        ),
        _q(
            "Which secrets are configured in this Nexus workspace? Names only.",
            "other",
            ("list_workspace_secret_names",),
            ("secret",),
        ),
        _q(
            "Quel est mon rôle dans cet espace de travail Nexus ?",
            "operate",
            # Grounded either way: the role tool, or the member list row marked is_you.
            ("get_workspace_settings", "list_workspace_members"),
            ("owner", "admin", "member", "propriétaire"),
        ),
    ),
    "Agent Catalog": (
        _q(
            "What can I do with agents and skills in Nexus?",
            "capabilities",
            terms=("skill", "agent"),
        ),
        _q(
            "How does a Nexus workspace roster decide which agents are enabled? Read the code and cite the files.",
            "implementation",
            SOURCE_TOOLS,
            ("agents:", "roster"),
        ),
        _q(
            "Which agents are on this Nexus workspace's roster?",
            "operate",
            ("list_workspace_agents",),
            ("agent",),
        ),
        _q(
            "How do I add the Nexus Apps agent to this workspace?",
            "other",
            terms=("naas_abi appsagent",),
        ),
        _q(
            "Comment créer une skill dans Nexus ?",
            "operate",
            terms=("create-skill", "skill"),
        ),
    ),
}


def grade(
    question: CompetencyQuestion,
    answer: str,
    tools_used: list[str],
    error: str | None = None,
) -> Grade:
    """Pass when the run did not fail, used an expected tool, and names an
    expected term."""
    reasons: list[str] = []
    if error:
        reasons.append(f"run failed: {error}")
    text = (answer or "").strip()
    lowered = text.lower()
    if not text:
        reasons.append("empty answer")
    marker = next((m for m in FAILURE_MARKERS if m in lowered), None)
    if marker:
        reasons.append(f"failure marker: {marker!r}")
    if question.expect_tools and not set(question.expect_tools) & set(tools_used):
        reasons.append(
            f"no expected tool used (wanted one of {list(question.expect_tools)})"
        )
    if question.expect_terms and not any(
        term in lowered for term in question.expect_terms
    ):
        reasons.append(
            f"no expected term (wanted one of {list(question.expect_terms)})"
        )
    return Grade(passed=not reasons, reasons=reasons)
