import pytest
from naas_abi.agents.feature.registry import (
    feature_office_agent_specs,
    spec_for_class_name,
)


def test_resolves_a_naas_abi_office_agent() -> None:
    spec = spec_for_class_name("naas_abi.agents.AppsAgent/AppsAgent")
    assert spec is not None
    assert spec.name == "Apps"
    assert spec.feature_keys == ("apps",)


@pytest.mark.parametrize(
    "spec", feature_office_agent_specs(), ids=lambda spec: spec.class_name
)
def test_every_office_agent_follows_its_feature(spec) -> None:
    # Documents and Sheets are outside the eval suite (FEATURE_AGENTS) but are
    # office agents all the same: unresolved, they stayed listed with the
    # feature off.
    key = f"naas_abi.agents.{spec.class_name}/{spec.class_name}"
    assert spec_for_class_name(key) == spec


def test_ignores_a_lookalike_from_another_module() -> None:
    assert spec_for_class_name("acme.agents.AppsAgent/AppsAgent") is None


def test_ignores_non_office_and_malformed_keys() -> None:
    assert spec_for_class_name("naas_abi.agents.AbiAgent/AbiAgent") is None
    assert spec_for_class_name("AppsAgent") is None
    assert spec_for_class_name(None) is None
    assert spec_for_class_name("") is None
