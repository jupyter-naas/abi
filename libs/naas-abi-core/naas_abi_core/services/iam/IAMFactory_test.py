import pytest

from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam import IAMFactory


def test_helpers_build_bootstrapped_services(tmp_path):
    for service in (
        IAMFactory.IAMServiceMemory(),
        IAMFactory.IAMServiceSQLite(str(tmp_path / "iam.sqlite")),
    ):
        assert service.authorizer.name == "policy"
        with as_service_account("engine"):
            assert service.authorize("iam:CreatePolicy", "abi:-:-:iam:policy/p").allowed
        service.close()


def test_allow_all_is_only_ever_asked_for_by_name():
    assert IAMFactory.IAMServiceMemory("allow_all").authorizer.name == "allow_all"
    with pytest.raises(ValueError):
        IAMFactory.authorizer_factory("none")  # type: ignore[arg-type]
