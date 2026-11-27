# The chat models a workspace uses are in its offer

- **Status:** Accepted
- **Date:** 2026-11-26
- **Builds on:** `20261120_access_levels_and_groups.md` (levels, offers, model sets), `20261125_offer_gives_outside_resources.md`.

## Context

Which chat models a person may use is decided at the platform: the model sets (`services/iam/model_sets.py`) are platform policies on `abi:model_registry:model/<canonical id>`, held by the level groups without a scope. An agent's own models are lent to whoever may use the agent during its turn (core `model_registry/agent_models.py`). Nothing is decided per workspace.

An organization needs to keep a workspace to some models: one workspace may use only one model, whichever agent answers. The offer "<W> access" is where every per-workspace choice lives, but it cannot narrow the model sets as IAM evaluates them:

- the bound of a workspace narrows what is attached at `${my workspaces}`, and the model sets are attached unscoped;
- a given statement (an Allow on absolute names in a bound) widens, it never narrows;
- a Deny in the bound applies to the workspace's people everywhere, not only in the workspace.

And the model is chosen in several places that IAM does not see as one decision: the chat's picker, a turn's routed model (slides and documents raise it), the model an in-process agent and each of its sub-agents were built with, the model a remote module resolves over NATS, and agents with a provider of their own.

## Decision

1. **A Models section in the offer.** `OfferModels` names the chat models the workspace uses, by canonical id (`${scope}/nexus:model/<id>`, `nexus:UseModel`), `*` for every one; `OfferDefaultModel` names its default model. No section, or `*`, is every model the people's model sets allow: today's behaviour. A list needs one of its models as its default. The levels that chat grant `${scope}/nexus:model/*` ("Member access", "Workspace admin access"; a Viewer does not chat), bounded by the offer and its organization's (catalog 22: `model`, policy-only). The move `models_offer_v1` writes `*` into every recorded access policy; a new workspace is made with `*`.
2. **The offer that applies is the conversation's workspace,** the workspace the turn runs in, not the agent's own.
3. **An agent on a model the workspace does not offer switches to its default.** A picked or routed model (the office overrides included) not offered runs on the default; with none picked, the agent and each of its sub-agents built on a model not offered are rebound to the default on the turn's copy; the loan of an agent's own models is narrowed to the offered ones. The model announced to the chat and stored with the answer is the one the turn runs on.
4. **Remote modules are included.** Core's model registry takes one substitute from its host (`register_model_substitute(container, canonical id) -> canonical id`); the NATS endpoint asks it with the request's container before it resolves a chat model, and drops the pinned provider and variant when it switches. Nexus registers it at start and reads the offer on its own loop. Core knows nothing of offers.
5. **An agent with a provider of its own is refused** when its model is not offered (workspace keys, Ollama, an ABI server's agent): there is no model of that provider to switch to. The refusal says which model and whom to ask.
6. **Embeddings stay out.** Search and a chat's files keep their embedding models; the substitute never touches an embedding.

Nexus keeps a turn to the models where it knows the workspace: `/agents` in W (the picker's models narrowed, the model shown on the default), chat streaming and completion (before the model is announced and stored), the in-process runtime, the OpenAI-compatible gateway (the workspace the turn is decided in) and, through the engine, a remote module's resolution.

## Consequences

- **The model sets still decide who may use a model;** the offer decides which of those a workspace uses. A person outside a model's set is not given it by the offer.
- **A remote module's turn follows the workspace it runs in.** Nexus runs a remote agent in the agent's own workspace (its container); when that differs from the conversation's, the substitute reads the agent's workspace. The submit request carries no model or second container to change that.
- **A turn the runtime cannot place in a workspace is not narrowed:** no container and no turn models (a background job, an engine task).
- **The offer cache applies:** a change of the Models section reaches a running process within the offer cache's 30 seconds, at once in the process that made it.
- **One more Nexus catalog type and level statement,** and one more move at start.

## Rejected

- **Narrowing the model sets inside IAM per workspace** (bound or Deny): the sets are unscoped; a Deny in the bound refuses the model in every workspace of the person.
- **A given statement naming models:** it widens what the workspace's people hold; it cannot keep them to a list.
- **Switching a provider of its own's model:** another provider means other keys and endpoints; refusing is the only honest answer.
- **Adding a model field to the remote submit:** a protocol change for every module, when the engine already resolves each model call with the request's container.
