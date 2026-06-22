"""
APQC PCF Cross-Industry v7.4 — Domain Agent Mapping
=====================================================
Maps each APQC PCF top-level category and its key process groups to the ABI
domain expert agents that own them.  Use this as the authoritative reference
when:

  - Wiring APQC process IDs into agent system prompts.
  - Deciding which workflows belong under which domain.
  - Generating agent blueprints from the PCF data file.

The full process tree lives in ``data/pcf_cross_industry_v7.4.json``.
The RDF/OWL representation lives in ``ontologies/APQCPCF.ttl``.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PCFCategory:
    pcf_id: int
    hierarchy_id: str
    name: str
    domain_agents: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass(frozen=True)
class PCFProcess:
    pcf_id: int
    hierarchy_id: str
    name: str
    primary_agent: str
    secondary_agents: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Category-to-agent mapping  (13 PCF top-level categories)
# ---------------------------------------------------------------------------

CATEGORY_MAPPING: list[PCFCategory] = [
    PCFCategory(
        pcf_id=10002,
        hierarchy_id="1.0",
        name="Develop Vision and Strategy",
        domain_agents=["content-strategist"],
        notes="Vision/mission definition and strategic initiative management.",
    ),
    PCFCategory(
        pcf_id=10003,
        hierarchy_id="2.0",
        name="Develop and Manage Products and Services",
        domain_agents=["software-engineer", "data-engineer"],
        notes="Product/service ideation, roadmap, and lifecycle management.",
    ),
    PCFCategory(
        pcf_id=10004,
        hierarchy_id="3.0",
        name="Market and Sell Products and Services",
        domain_agents=[
            "campaign-manager",
            "content-creator",
            "content-strategist",
            "account-executive",
            "sales-development-representative",
            "business-development-representative",
            "inside-sales-representative",
        ],
        notes="Covers 3.1 market intelligence through 3.6 sales partner management.",
    ),
    PCFCategory(
        pcf_id=20022,
        hierarchy_id="4.0",
        name="Manage Supply Chain for Physical Products",
        domain_agents=[],
        notes="No current domain agent. Candidate for a future Supply Chain domain.",
    ),
    PCFCategory(
        pcf_id=20025,
        hierarchy_id="5.0",
        name="Deliver Services",
        domain_agents=["project-manager", "devops-engineer"],
        notes="Service delivery governance, strategy, and resource management.",
    ),
    PCFCategory(
        pcf_id=20085,
        hierarchy_id="6.0",
        name="Manage Customer Service",
        domain_agents=["customer-success-manager", "support"],
        notes="Pre- and post-delivery customer management, warranties, and recalls.",
    ),
    PCFCategory(
        pcf_id=10007,
        hierarchy_id="7.0",
        name="Develop and Manage Human Capital",
        domain_agents=["human-resources-manager"],
        notes=(
            "Full HR lifecycle: workforce planning, recruiting, development, "
            "relations, rewards, redeployment, and HR information systems."
        ),
    ),
    PCFCategory(
        pcf_id=20607,
        hierarchy_id="8.0",
        name="Manage Information Technology (IT)",
        domain_agents=["software-engineer", "devops-engineer", "data-engineer"],
        notes=(
            "IT customer relationships, IT strategy, IT resilience, "
            "information management, and service/solution delivery."
        ),
    ),
    PCFCategory(
        pcf_id=17058,
        hierarchy_id="9.0",
        name="Manage Financial Resources",
        domain_agents=["accountant", "financial-controller", "treasurer"],
        notes=(
            "Planning and management accounting, revenue accounting, "
            "general ledger, payroll, AP/AR, treasury, tax, and global trade."
        ),
    ),
    PCFCategory(
        pcf_id=19207,
        hierarchy_id="10.0",
        name="Acquire, Construct, and Manage Assets",
        domain_agents=[],
        notes="No current domain agent. Candidate for a future Facilities/Asset Management domain.",
    ),
    PCFCategory(
        pcf_id=16437,
        hierarchy_id="11.0",
        name="Manage Enterprise Risk, Compliance, Remediation, and Resiliency",
        domain_agents=[],
        notes=(
            "No current domain agent. Risk, compliance, and resiliency are "
            "cross-cutting; consider a dedicated Risk & Compliance domain."
        ),
    ),
    PCFCategory(
        pcf_id=10012,
        hierarchy_id="12.0",
        name="Manage External Relationships",
        domain_agents=[],
        notes=(
            "Investor, government, board, and public stakeholder relations. "
            "No current domain agent; overlap with community-manager for public relations."
        ),
    ),
    PCFCategory(
        pcf_id=10013,
        hierarchy_id="13.0",
        name="Develop and Manage Business Capabilities",
        domain_agents=["project-manager"],
        notes=(
            "BPM governance, portfolio/program/project management, quality, "
            "change management, benchmarking, EHS, and knowledge management."
        ),
    ),
]


# ---------------------------------------------------------------------------
# Key process-group-to-agent mapping (second-level, most agent-relevant)
# ---------------------------------------------------------------------------

PROCESS_GROUP_MAPPING: list[PCFProcess] = [
    # --- 7.0 Human Capital ---
    PCFProcess(10418, "7.1.1.1", "Identify strategic HR needs", "human-resources-manager"),
    PCFProcess(10419, "7.1.1.2", "Define HR and business function roles and accountability", "human-resources-manager"),
    PCFProcess(10420, "7.1.1.5", "Determine HR costs", "human-resources-manager"),
    PCFProcess(10421, "7.1.1.6", "Establish HR measures", "human-resources-manager"),

    # --- 9.0 Financial Resources ---
    PCFProcess(10738, "9.1.1", "Perform planning/budgeting/forecasting", "financial-controller", ["accountant"]),
    PCFProcess(10739, "9.1.2", "Perform cost accounting and control", "accountant", ["financial-controller"]),
    PCFProcess(10771, "9.1.1.1", "Develop and maintain budget policies and procedures", "financial-controller"),
    PCFProcess(10772, "9.1.1.2", "Prepare periodic budgets and plans", "accountant"),
    PCFProcess(10773, "9.1.1.4", "Prepare periodic financial forecasts", "accountant"),

    # --- 3.0 Market and Sell ---
    PCFProcess(10106, "3.1.1", "Perform customer and market intelligence analysis", "campaign-manager", ["content-analyst"]),
    PCFProcess(10108, "3.1.1.1", "Conduct customer and market research", "campaign-manager"),
    PCFProcess(10109, "3.1.1.2", "Identify market segments", "campaign-manager"),
    PCFProcess(10110, "3.1.1.3", "Analyze market and industry trends", "content-analyst", ["campaign-manager"]),

    # --- 8.0 Information Technology ---
    PCFProcess(20608, "8.1", "Develop and manage IT customer relationships", "software-engineer", ["devops-engineer"]),
    PCFProcess(20609, "8.1.1", "Understand IT customer needs", "software-engineer"),

    # --- 6.0 Customer Service ---
    PCFProcess(10378, "6.1", "Develop customer service strategy", "customer-success-manager"),
    PCFProcess(10382, "6.1.4", "Define customer service policies and procedures", "customer-success-manager", ["support"]),
    PCFProcess(10383, "6.1.5", "Establish target service level for each customer segment", "customer-success-manager"),
]


# ---------------------------------------------------------------------------
# Coverage analysis helpers
# ---------------------------------------------------------------------------

def get_uncovered_categories() -> list[PCFCategory]:
    """Return PCF top-level categories not yet owned by any domain agent."""
    return [c for c in CATEGORY_MAPPING if not c.domain_agents]


def get_agents_for_category(hierarchy_id: str) -> list[str]:
    """Return domain agent slugs responsible for a given PCF category hierarchy ID."""
    for cat in CATEGORY_MAPPING:
        if cat.hierarchy_id == hierarchy_id:
            return cat.domain_agents
    return []


def get_categories_for_agent(agent_slug: str) -> list[PCFCategory]:
    """Return all PCF categories owned (fully or partially) by a given domain agent."""
    return [c for c in CATEGORY_MAPPING if agent_slug in c.domain_agents]
