"""Model sets: which models a person may chat with directly (ADR
``20261120_access_levels_and_groups``, decision 6).

Being a workspace's viewer or member reaches no model (core ``roles.py``: no
``model_registry`` row in ``builtin.platform.*``). A model set is a policy, owned
by the platform, on ``abi:model_registry:model/<canonical id>``:

| Policy | Grants | Held by (S2) |
|---|---|---|
| "Models · member" | ``ListModels``, ``Resolve``, ``Chat``, ``ChatStream`` on each id of ``nexus_config.models.member_set`` | the level group "Members" |
| "Models · all" | the same on ``model/*`` | workspace and org admins; the capability group "Models · all" |
| "Models · embeddings" | ``Embed`` on ``model/*``, ``Resolve`` on each embedding model | every Member and Viewer (search) |

An agent's own model is always allowed, whatever the set: the turn of a module
agent lends it (core ``model_registry/agent_models.py``, ``provider_runtime``).

The policies are made, found again (by owner, name and description) and kept in
step with the configuration at each start (``ensure_model_policies``); nothing is
attached here. ``level_model_policy_ids`` is what S2 attaches to the level groups.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from naas_abi_core import logger
from naas_abi_core.services.iam.names import resource_name
from naas_abi_core.services.iam.policy import POLICY_VERSION

SERVICE = "model_registry"
CHAT_ACTIONS = tuple(f"{SERVICE}:{a}" for a in ("ListModels", "Resolve", "Chat", "ChatStream"))
EMBED = f"{SERVICE}:Embed"
RESOLVE = f"{SERVICE}:Resolve"
MEMBER_SET = "member"
ALL = "all"
EMBEDDINGS = "embeddings"
DESCRIPTIONS = {
    MEMBER_SET: (
        "The models a Member chats with directly: nexus_config.models.member_set. Kept in "
        "step with the configuration at each start."
    ),
    ALL: "Every model: workspace and organization admins, and the group Models · all.",
    EMBEDDINGS: (
        "The embedding models, for search: every Member and Viewer. Kept in step with the "
        "registered models at each start."
    ),
}
Level = Literal["viewer", "member", "admin"]


def set_name(name: str) -> str:
    return f"Models · {name}"


def model_resource(canonical_id: str) -> str:
    """``abi:model_registry:model/<canonical id>``."""
    return resource_name(SERVICE, "model", canonical_id)


def every_model() -> str:
    """``abi:model_registry:model/*``."""
    return model_resource("-").rsplit("/", 1)[0] + "/*"


# An Allow no model id matches: a set of nothing (an id holds no NUL).
_NO_MODEL = model_resource("\x00")


def set_document(canonical_ids: Iterable[str]) -> dict[str, Any]:
    """The chat actions on each model of the set (none matches for an empty set)."""
    ids = sorted({str(i).strip() for i in canonical_ids if str(i).strip()})
    return {
        "version": POLICY_VERSION,
        "statements": [
            {
                "sid": "ModelSet",
                "effect": "Allow",
                "actions": list(CHAT_ACTIONS),
                "resources": [model_resource(i) for i in ids] or [_NO_MODEL],
            }
        ],
    }


def all_document() -> dict[str, Any]:
    return {
        "version": POLICY_VERSION,
        "statements": [
            {
                "sid": "EveryModel",
                "effect": "Allow",
                "actions": list(CHAT_ACTIONS),
                "resources": [every_model()],
            }
        ],
    }


def embeddings_document(embedding_ids: Iterable[str]) -> dict[str, Any]:
    """``Embed`` on every model (only an embedding model embeds) and ``Resolve``
    on each embedding model: in process an embedding model is resolved, then used."""
    ids = sorted({str(i).strip() for i in embedding_ids if str(i).strip()})
    statements: list[dict[str, Any]] = [
        {"sid": "Embed", "effect": "Allow", "actions": [EMBED], "resources": [every_model()]}
    ]
    if ids:
        statements.append(
            {
                "sid": "ResolveEmbeddingModels",
                "effect": "Allow",
                "actions": [RESOLVE],
                "resources": [model_resource(i) for i in ids],
            }
        )
    return {"version": POLICY_VERSION, "statements": statements}


@dataclass(frozen=True)
class ModelPolicies:
    member: str
    all: str
    embeddings: str


_ENSURED: ModelPolicies | None = None


def _pages(listing: Any) -> list[Any]:
    found: list[Any] = []
    after: str | None = None
    while True:
        page = listing(limit=500, after=after)
        found += list(page.items)
        after = page.next_after
        if not after:
            return found


def _same(document: Any, wanted: dict[str, Any]) -> bool:
    have = [(s.sid, s.effect, tuple(s.actions), tuple(s.resources)) for s in document.statements]
    want = [
        (s["sid"], s["effect"], tuple(s["actions"]), tuple(s["resources"]))
        for s in wanted["statements"]
    ]
    return have == want


def _ensure(iam: Any, name: str, description: str, document: dict[str, Any], found: Any) -> str:
    """The platform's policy ``name``: made, or its document brought in step."""
    from naas_abi_core.services.iam.names import PLATFORM

    for policy in found:
        if (policy.owner_scope, policy.name, policy.description) == (PLATFORM, name, description):
            if not _same(policy.document, document):
                iam.update_policy(policy.id, expected_revision=policy.revision, document=document)
            return str(policy.id)
    return str(iam.create_policy(name, document, description=description).id)


def ensure_model_policies(
    iam: Any, member_set: Sequence[str], embedding_ids: Sequence[str]
) -> ModelPolicies:
    """ "Models · member", "Models · all" and "Models · embeddings", made or kept
    in step (``member_set``: the configuration's ids; ``embedding_ids``: the
    registered embedding models). Idempotent. As ``api``; remembered for
    ``level_model_policy_ids``."""
    global _ENSURED
    found = _pages(iam.list_policies)
    policies = ModelPolicies(
        member=_ensure(
            iam, set_name(MEMBER_SET), DESCRIPTIONS[MEMBER_SET], set_document(member_set), found
        ),
        all=_ensure(iam, set_name(ALL), DESCRIPTIONS[ALL], all_document(), found),
        embeddings=_ensure(
            iam,
            set_name(EMBEDDINGS),
            DESCRIPTIONS[EMBEDDINGS],
            embeddings_document(embedding_ids),
            found,
        ),
    )
    _ENSURED = policies
    return policies


def configured_member_set() -> list[str]:
    from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import live_settings

    models = getattr(live_settings(), "models", None)
    return list(getattr(models, "member_set", None) or [])


def registered_embedding_ids() -> list[str]:
    """The engine's embedding models (and its default one), read as the engine."""
    try:
        from naas_abi import ABIModule
        from naas_abi_core.engine.call_context import as_service_account
        from naas_abi_core.models.Model import EmbeddingModel

        registry = ABIModule.get_instance().engine.services.model_registry
        with as_service_account("engine"):
            ids = [
                cid
                for cid, model in registry.list_registered_models()
                if isinstance(model, EmbeddingModel)
            ]
        default = registry.default_embedding_model_id
        return sorted({*ids, *([default] if default else [])})
    except Exception:  # noqa: BLE001 - no engine: only Embed, which every model refuses but one
        logger.debug("No model registry to read the embedding models from", exc_info=True)
        return []


def ensure_configured(iam: Any) -> ModelPolicies:
    """``ensure_model_policies`` with the configuration's member set and the
    registered embedding models. As ``api``."""
    return ensure_model_policies(iam, configured_member_set(), registered_embedding_ids())


def model_policies(iam: Any) -> ModelPolicies:
    """The model-set policies, ensured once in this process."""
    return _ENSURED if _ENSURED is not None else ensure_configured(iam)


def level_model_policy_ids(iam: Any, level: Level) -> list[str]:
    """The model-set policies a level's group holds (S2 attaches them, without a
    scope: their names are the platform's): a Viewer embeds only, a Member has
    the member set too, an admin every model."""
    policies = model_policies(iam)
    if level == "viewer":
        return [policies.embeddings]
    if level == "member":
        return [policies.member, policies.embeddings]
    if level == "admin":
        return [policies.all, policies.embeddings]
    raise ValueError(f"{level!r} is not viewer, member or admin")


def forget() -> None:
    """Tests: ensure again at the next call."""
    global _ENSURED
    _ENSURED = None


__all__ = [
    "ModelPolicies",
    "embeddings_document",
    "ensure_configured",
    "ensure_model_policies",
    "level_model_policy_ids",
    "model_policies",
    "set_document",
    "set_name",
]
