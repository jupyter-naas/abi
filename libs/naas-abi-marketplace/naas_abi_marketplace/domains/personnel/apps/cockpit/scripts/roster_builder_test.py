from naas_abi_marketplace.domains.personnel.apps.cockpit.scripts.roster_builder import (
    build_roster_rows,
    derive_roster_rows,
)

WORKING = [
    {
        "personLabel": "Alice Dupont",
        "orgLabel": "Demo",
        "jobTitle": "COO",
        "role": "role/alice-coo",
        "temporalStart": "2023-04-01",
        "temporalEnd": None,
    },
    {
        "personLabel": "Alice Dupont",
        "orgLabel": "Demo",
        "jobTitle": "Analyst",
        "role": "role/alice-analyst",
        "temporalStart": "2019-01-01",
        "temporalEnd": "2023-03-31",
    },
    {
        "personLabel": "Alice Dupont",
        "orgLabel": "Acme Consulting",
        "jobTitle": "Consultant",
        "temporalStart": "2015-01-01",
        "temporalEnd": "2018-12-31",
    },
    {
        "personLabel": "Frank Moreau",
        "orgLabel": "Demo",
        "jobTitle": "Head of Growth",
        "role": "role/frank-growth",
        "temporalStart": "2020-01-01",
        "temporalEnd": "2022-12-31",
    },
    {
        "personLabel": "Zoe Extern",
        "orgLabel": "Other Corp",
        "jobTitle": "Designer",
        "temporalStart": "2021-01-01",
        "temporalEnd": None,
    },
]


def test_derives_one_row_per_person_at_the_organization():
    rows = derive_roster_rows(WORKING, org_label="Demo")
    assert [row["personLabel"] for row in rows] == ["Alice Dupont", "Frank Moreau"]


def test_current_act_supplies_title_and_earliest_start_is_hire_date():
    alice = derive_roster_rows(WORKING, org_label="Demo")[0]
    assert alice["job_title"] == "COO"
    assert alice["role"] == "role/alice-coo"
    assert alice["hire_date"] == "2019-01-01"
    assert alice["organizationLabel"] == "Demo"


def test_open_ended_act_is_active_and_closed_only_is_terminated():
    rows = {row["personLabel"]: row for row in derive_roster_rows(WORKING, org_label="Demo")}
    assert rows["Alice Dupont"]["status_value"] == "active"
    assert rows["Frank Moreau"]["status_value"] == "terminated"


def test_org_match_is_case_insensitive():
    assert derive_roster_rows(WORKING, org_label="demo")


def test_employment_records_win_when_the_graph_has_them():
    records = [{"personLabel": "Bob Martin", "employee_id": "E-1"}]
    rows, source = build_roster_rows(records, WORKING, org_label="Demo")
    assert rows == records
    assert source == "employment_records"


def test_falls_back_to_acts_of_working():
    rows, source = build_roster_rows([], WORKING, org_label="Demo")
    assert source == "acts_of_working"
    assert len(rows) == 2
