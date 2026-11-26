"""What the move into the offer writes for the models (``models_offer``): every model,
in each access policy that names none, every other statement kept, once."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.iam import models_offer
from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_container, workspace_container
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import (
    Offer,
    offer_document,
    offer_of,
)
from naas_abi_core.services.iam.IAMPorts import IAMNotFoundError

W = workspace_container("acme", "ws-1")
ORG = org_container("acme")


@dataclass
class _Policy:
    id: str
    document: dict[str, Any]
    revision: int = 1


@dataclass
class _Iam:
    policies: dict[str, _Policy] = field(default_factory=dict)
    writes: list[str] = field(default_factory=list)

    def get_policy(self, policy_id: str) -> _Policy:
        if policy_id not in self.policies:
            raise IAMNotFoundError(policy_id)
        return self.policies[policy_id]

    def update_policy(self, policy_id: str, *, expected_revision: int, document: Any) -> None:
        assert expected_revision == self.policies[policy_id].revision
        self.policies[policy_id] = _Policy(policy_id, document, expected_revision + 1)
        self.writes.append(policy_id)


def test_every_recorded_access_policy_is_given_every_model_once():
    older = {
        "version": "2026-10-13",
        "statements": [
            {"sid": "Modules", "effect": "Allow", "actions": ["module:*"], "resources": ["x"]},
            *offer_document(Offer.of(features=["chat"]))["statements"],
        ],
    }
    chose = offer_document(Offer.of(models=["qwen-3.8"], default_model="qwen-3.8"))
    iam = _Iam({"o": _Policy("o", older), "w": _Policy("w", chose)})
    report = models_offer.apply(iam, {ORG: "o", W: "w", workspace_container("acme", "gone"): "x"})
    gone = workspace_container("acme", "gone")
    assert report.written == [ORG] and sorted(report.kept) == sorted([W, gone])
    written = iam.policies["o"].document
    assert [s["sid"] for s in written["statements"]] == ["Modules", "OfferFeatures", "OfferModels"]
    assert offer_of(written).models == {"*"}
    # A workspace that chose keeps its choice; a second pass writes nothing.
    assert offer_of(iam.policies["w"].document).models == {"qwen-3.8"}
    assert models_offer.apply(iam, {ORG: "o", W: "w"}).written == []
    assert iam.writes == ["o"]
