"""The act-of-certification query, run against a graph the pipelines built."""

from __future__ import annotations

from datetime import date

from naas_abi_marketplace.domains.personnel.apps.people.scripts import (
    sparql_queries as sq,
)
from naas_abi_marketplace.domains.personnel.pipelines.ActOfCertificationPipeline import (
    ActOfCertificationPipeline,
    ActOfCertificationPipelineConfiguration,
    ActOfCertificationPipelineParameters,
)
from naas_abi_marketplace.domains.personnel.pipelines.utils.graph_builders import (
    PersonnelGraphContext,
)


def _rows() -> list[dict]:
    context = PersonnelGraphContext()
    pipeline = ActOfCertificationPipeline(
        ActOfCertificationPipelineConfiguration(
            triple_store=None, persist=False, context=context
        )
    )
    pipeline.run(
        ActOfCertificationPipelineParameters(
            first_name="Ada",
            last_name="Lovelace",
            name="Certified Auditor",
            issuer="ISACA",
            issue_date=date(2019, 3, 1),
            site="Chicago",
            skills=["IT Audit"],
        )
    )
    pipeline.run(
        ActOfCertificationPipelineParameters(
            first_name="Ada", last_name="Lovelace", name="Chartered Accountant"
        )
    )
    return sq.run_query(
        context.graph, sq.load_queries()["find_acts_of_certification"], limit=50
    )


def test_every_act_is_returned_even_when_the_source_said_little() -> None:
    names = {row["certificationName"] for row in _rows()}
    assert names == {"Certified Auditor", "Chartered Accountant"}


def test_the_bare_act_states_nothing_it_was_not_told() -> None:
    # unbound variables are left out of a row, not returned as None
    row = next(r for r in _rows() if r["certificationName"] == "Chartered Accountant")
    assert row.get("orgLabel") is None
    assert row.get("siteLabel") is None
    assert row.get("awardedOn") is None
    assert row.get("skillLabel") is None
    assert row["roleLabel"] == "Candidate - Chartered Accountant"


def test_the_full_act_answers_who_where_when_and_what() -> None:
    row = next(r for r in _rows() if r["certificationName"] == "Certified Auditor")
    assert row["personLabel"] == "Ada Lovelace"
    assert row["orgLabel"] == "ISACA"
    assert row["siteLabel"] == "Chicago"
    assert row["awardedOn"] == "2019-03-01"
    assert row["temporalLabel"] == "Awarded Mar 2019"
    assert row["skillLabel"] == "IT Audit"
