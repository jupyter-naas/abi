"""Policies of shared graphs are found by name from one scan, not one scan per lookup."""

from __future__ import annotations

from types import SimpleNamespace

from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.graph_grants import (
    GraphGrants,
    policy_name,
)
from naas_abi_core.services.iam.IAMPorts import IAMNotFoundError


class FakeIam:
    def __init__(self, names: dict[str, str]) -> None:
        self.policies = dict(names)  # name -> id
        self.scans = 0

    def list_policies(self, *, limit: int, after: str | None):
        self.scans += 1
        items = [SimpleNamespace(name=name, id=pid) for name, pid in self.policies.items()]
        return SimpleNamespace(items=items, next_after=None)

    def get_policy(self, policy_id: str):
        for name, pid in self.policies.items():
            if pid == policy_id:
                return SimpleNamespace(name=name)
        raise IAMNotFoundError(policy_id)


def test_a_missing_policy_is_remembered_not_scanned_for_again() -> None:
    iam = FakeIam({policy_name("ws-1", "read"): "pol_1"})
    grants = GraphGrants()
    assert grants._find(iam, policy_name("ws-2", "read")) is None
    assert grants._find(iam, policy_name("ws-3", "write")) is None
    assert grants._find(iam, policy_name("ws-2", "read")) is None
    assert iam.scans == 1


def test_a_known_policy_is_checked_by_id_and_rescanned_only_when_gone() -> None:
    name = policy_name("ws-1", "read")
    iam = FakeIam({name: "pol_1"})
    grants = GraphGrants()
    assert grants._find(iam, name) == "pol_1"
    assert grants._find(iam, name) == "pol_1"
    assert iam.scans == 1
    # Deleted by another process, recreated under a new id: found with one more scan.
    iam.policies[name] = "pol_2"
    assert grants._find(iam, name) == "pol_2"
    assert iam.scans == 2
