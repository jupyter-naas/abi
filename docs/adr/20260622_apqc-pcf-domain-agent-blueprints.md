# ADR — APQC PCF as the Process Taxonomy Backing Domain Expert Agent Blueprints

**Status:** Accepted
**Date:** 2026-06-22
**Issue:** [jupyter-naas/abi#1032](https://github.com/jupyter-naas/abi/issues/1032)
**Authors:** @jravenel

---

## Context

The ABI marketplace contains 24 domain expert agent modules. Today their
`SYSTEM_PROMPT` fields enumerate expertise and capabilities in free-form
prose, with no shared vocabulary or standard that ties them to
industry-recognised business processes. This makes it difficult to:

- Decide which workflows belong under which domain agent.
- Assess coverage gaps (processes with no owning agent).
- Communicate agent scope to users in terms they already know.
- Generate consistent, auditable blueprints for future workflow development.

The APQC Process Classification Framework (PCF) Cross-Industry v7.4 is a
vendor-neutral, hierarchical taxonomy of 1,921 business processes organised
into 13 top-level categories. It is widely adopted in enterprise BPM, process
mining, and benchmarking contexts. Each process element carries a stable
numeric PCF ID that can serve as a permanent reference key.

---

## Decision

Use APQC PCF Cross-Industry v7.4 as the authoritative process taxonomy for
defining the scope and blueprints of ABI domain expert agents.

Specifically:

1. **Data artifact.** The full PCF taxonomy is extracted from the official
   APQC Excel file into a machine-readable JSON file at
   `domains/apqc/data/pcf_cross_industry_v7.4.json` (1,921 process elements,
   four hierarchy levels).

2. **RDF ontology.** An OWL/Turtle ontology at
   `domains/apqc/ontologies/APQCPCF.ttl` models PCF categories as OWL
   individuals, links them to `apqc:DomainAgent` individuals via
   `apqc:hasDomainAgent`, and provides SPARQL-queryable coverage data.

3. **Python mapping module.** `domains/apqc/APQCDomainMapping.py` provides a
   typed, importable mapping from each of the 13 PCF categories (and key
   second-level process groups) to the domain agent slug(s) responsible for
   them.

4. **Agent system prompts.** Each domain agent's `SYSTEM_PROMPT` includes an
   explicit "APQC PCF Process Ownership" section that lists the PCF IDs and
   hierarchy IDs for which that agent is the primary owner. Four agents are
   updated in this initial PR:
   - `accountant` (PCF 9.0 — Manage Financial Resources)
   - `human-resources-manager` (PCF 7.0 — Develop and Manage Human Capital)
   - `software-engineer` (PCF 2.0 + 8.0 — Products and IT)
   - `campaign-manager` (PCF 3.0 — Market and Sell)

5. **Coverage gaps.** Four categories are not yet covered by any current
   domain agent:
   - **4.0** Manage Supply Chain for Physical Products
   - **10.0** Acquire, Construct, and Manage Assets
   - **11.0** Manage Enterprise Risk, Compliance, Remediation, and Resiliency
   - **12.0** Manage External Relationships

   These represent candidates for future domain modules.

---

## Consequences

**Positive:**
- Domain agent scope is now grounded in a universally recognised standard,
  making capabilities legible to enterprise buyers.
- The PCF ID (e.g., `PCF 9.1.1`) gives every future workflow a stable anchor
  for documentation, tracing, and metrics alignment (APQC provides benchmark
  KPIs for processes with `metrics_available: true`).
- Coverage gaps are explicit and auditable via `get_uncovered_categories()` in
  the mapping module.
- The ontology enables SPARQL queries against the triple store to retrieve
  which agent handles a given business process at runtime.

**Negative / trade-offs:**
- APQC PCF is designed for physical-products and services companies; some
  categories (4.0 Supply Chain) are largely irrelevant for software-centric
  deployments. Process mapping at depth 3-4 will require manual review.
- Updating all 24 agent `SYSTEM_PROMPT` entries is a sustained effort; this
  ADR scopes the first four.
- The PCF ID set may shift between APQC versions; the `version` field in the
  JSON artifact must be updated if the framework is upgraded.

**Follow-up tasks:**
- [ ] Extend PCF ownership sections to all remaining 20 domain agents.
- [ ] Map key PCF process groups (depth 2) to existing workflow files within
  each domain.
- [ ] Add SPARQL views to the triple store that materialise agent-to-process
  coverage for discovery queries.
- [ ] Evaluate whether PCF categories 4.0, 10.0, 11.0, and 12.0 warrant new
  domain agent modules.
- [ ] Align APQC benchmark metrics (from `Metrics` sheet) with agent KPI
  dashboards.
