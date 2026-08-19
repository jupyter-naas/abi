# S9 — external

## The question this bucket answers

> *How do we relate to people and bodies outside the organization?*

In the staff system, S9 is CIMIC / civil affairs: relations with government, civilian and
non-governmental bodies — everyone in the environment who is neither friendly force nor adversary.
In a civilian organization it covers community, brand, public affairs, partnerships and external
communications.

External is defined by the **counterparty**: a broad audience rather than a paying customer.

## What's here

```
external/
├── __init__.py                     # ABIModule, datastore_path = "external"
└── agents/
    ├── CommunityManagerAgent.py
    └── ContentCreatorAgent.py
```

| Module | Component | What it delivers |
|---|---|---|
| `ContentCreatorAgent` | `agents/` | Copywriting, social content, video scripts, creative campaigns |
| `CommunityManagerAgent` | `agents/` | Community building, engagement, social media, brand advocacy |

## What belongs here

- Community building, engagement and moderation
- Brand and public relations
- Public affairs, regulatory and institutional relations
- Partnership and ecosystem relations (non-commercial)
- Outward-facing content production and social presence

## Boundary tests

**vs [`operations/`](../operations/) (S3) — audience or customer.**
If the counterparty is a paying customer in a commercial relationship, it is operations. If it is a
broader audience, community, partner body or the public, it is external. Answering a support ticket
is S3; moderating the community forum is S9. A partnership that generates revenue is operations
(`BusinessDevelopmentRepresentativeAgent`); an ecosystem relationship that does not is external.

**vs [`intelligence/`](../intelligence/) (S2) — engage or observe.**
Both face outward. External *talks to* the outside; intelligence *watches* it without interacting.
Publishing a response is S9; monitoring what is being said is S2.

**vs [`training/`](../training/) (S7) — outward or inward.**
Producing content for an external audience is external. Producing it to build the organization's
own capability is training. Same skill, opposite direction.

**vs [`plans/`](../plans/) (S5) — produce or design.**
`ContentCreatorAgent` produces the artefacts and sits here; `ContentStrategistAgent` decides what
should be produced and sits in plans. The content cluster is deliberately split across three
buckets by function rather than kept together as a "marketing" team — see
[`../AGENT.md`](../AGENT.md), *Standing decisions*.

## Filing a module here

`external/<component>/<module>/`, where `<component>` is the module's dominant deliverable.
Single-agent modules may sit flat as `agents/<Name>Agent.py`. See [`../AGENT.md`](../AGENT.md) for
the full filing rules and [`../README.md`](../README.md) for the framework.
