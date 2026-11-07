from naas_abi.apps.nexus.apps.api.app.services.iam_admin.narrowing import (
    is_unchanged,
    narrowing_errors,
)
from naas_abi_core.services.iam.policy import PolicyDocument


def doc(*statements: dict) -> PolicyDocument:
    return PolicyDocument.from_dict({"version": "2026-10-13", "statements": list(statements)})


def allow(actions: list[str], resources: list[str], sid: str | None = None) -> dict:
    return {"sid": sid, "effect": "Allow", "actions": actions, "resources": resources}


DENY = {"effect": "Deny", "actions": ["x:Drop"], "resources": ["abi:x:t/*"]}
SUBMITTED = doc(
    allow(["x:Get", "x:List"], ["abi:x:t/a", "abi:x:t/b"]),
    allow(["y:Put"], ["abi:y:t/*"]),
    DENY,
)


def test_removing_actions_resources_and_statements_narrows():
    narrowed = doc(allow(["x:Get"], ["abi:x:t/a"]), DENY)
    assert narrowing_errors(SUBMITTED, narrowed) == []
    assert not is_unchanged(SUBMITTED, narrowed)


def test_the_same_document_is_unchanged():
    assert narrowing_errors(SUBMITTED, SUBMITTED) == []
    assert is_unchanged(SUBMITTED, SUBMITTED)


def test_adding_an_action_a_resource_or_a_statement_widens():
    for widened in (
        doc(allow(["x:Get", "x:Drop"], ["abi:x:t/a"]), DENY),
        doc(allow(["x:Get"], ["abi:x:t/*"]), DENY),
        doc(allow(["z:Any"], ["abi:z:t/1"]), DENY),
    ):
        errors = narrowing_errors(SUBMITTED, widened)
        assert errors and "more than the module submitted" in errors[0]


def test_one_statement_cannot_borrow_from_two():
    merged = doc(allow(["x:Get", "y:Put"], ["abi:x:t/a"]), DENY)
    assert narrowing_errors(SUBMITTED, merged)


def test_a_deny_stays_exactly_as_submitted():
    assert "Deny" in narrowing_errors(SUBMITTED, doc(allow(["x:Get"], ["abi:x:t/a"])))[0]
    shrunk = {**DENY, "resources": ["abi:x:t/only"]}
    assert narrowing_errors(SUBMITTED, doc(allow(["x:Get"], ["abi:x:t/a"]), shrunk))
