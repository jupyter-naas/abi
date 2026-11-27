"""The engine readies the built-in IdP before it connects (#1643).

The manifest the engine approves is computed from the installed naas_abi_idp,
the same way the IdP computes the one it submits: the IdP then finds it in
force at once, with no `abi iam` step.
"""

from __future__ import annotations

import pytest
from naas_abi_core.engine.Engine import _builtin_idp_manifest
from naas_abi_core.services.iam import keys
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_core.services.iam.tests.iam_harness import IAMHarness

pytest.importorskip("naas_abi_idp")


def test_the_engine_computes_the_idp_s_own_manifest() -> None:
    from naas_abi_idp.module import ABIModule
    from naas_abi_sdk.permissions import module_manifest

    assert _builtin_idp_manifest() == module_manifest(ABIModule)


def test_the_idp_finds_its_key_and_permissions_ready() -> None:
    from naas_abi_idp.module import ABIModule
    from naas_abi_sdk.permissions import module_manifest

    iam = IAMService(IAMStoreMemory())
    iam.bootstrap()
    h = IAMHarness(iam)
    key = keys.generate_key("service").value

    iam.provision_first_party_module(
        "demo", "idp", key=key, manifest=_builtin_idp_manifest()
    )

    account, _ = iam.authenticate_key(key)
    with h.as_(account):
        submitted = iam.submit_manifest("idp", "demo", module_manifest(ABIModule))
    assert submitted.manifest.status == "approved"
    assert submitted.in_force and not submitted.approved_now


def test_no_manifest_without_the_idp_package(monkeypatch) -> None:
    # A project made before `abi new project` added naas-abi-idp: the engine
    # cannot compute the manifest (it then warns, and the IdP's one waits).
    import sys

    monkeypatch.setitem(sys.modules, "naas_abi_idp.module", None)
    assert _builtin_idp_manifest() is None
