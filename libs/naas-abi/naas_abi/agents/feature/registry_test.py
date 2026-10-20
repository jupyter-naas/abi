from naas_abi.agents.feature.registry import spec_for_class_name


def test_resolves_a_naas_abi_office_agent() -> None:
    spec = spec_for_class_name("naas_abi.agents.AppsAgent/AppsAgent")
    assert spec is not None
    assert spec.name == "Apps"
    assert spec.feature_keys == ("apps",)


def test_ignores_a_lookalike_from_another_module() -> None:
    assert spec_for_class_name("acme.agents.AppsAgent/AppsAgent") is None


def test_ignores_non_office_and_malformed_keys() -> None:
    assert spec_for_class_name("naas_abi.agents.AbiAgent/AbiAgent") is None
    assert spec_for_class_name("AppsAgent") is None
    assert spec_for_class_name(None) is None
    assert spec_for_class_name("") is None
