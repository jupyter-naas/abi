# S5 — plans

## The question this bucket answers

> *What should we do next, and how will we get there?*

In the staff system, S5 owns **future** operations — the plan that takes over when the current one
ends. In a civilian organization it covers strategy, roadmapping, campaign design and the planning
cycle itself.

The defining property is **time**: plans produces decisions about work that is not yet committed.
The moment work is committed and being executed, it belongs to [`operations/`](../operations/).

## What's here

```
plans/
├── __init__.py                     # ABIModule, datastore_path = "plans"
└── agents/
    └── ContentStrategistAgent.py
```

| Module | Component | What it delivers |
|---|---|---|
| `ContentStrategistAgent` | `agents/` | Content strategy, editorial planning, audience analysis, content optimization |

Thinly populated on purpose — most planning work in this marketplace is still done inside the
execution modules. New strategy, roadmap and scenario modules belong here.

## What belongs here

- Strategy formulation and option analysis
- Roadmapping and prioritization
- Campaign and programme **design** (not execution)
- Editorial and content calendars
- Budget and headcount planning proposals
- Scenario modelling, forecasting used to choose a course of action

## Boundary tests

**vs [`operations/`](../operations/) (S3) — the timeline test.**
The single most common mistake. Operations is *now*; plans is *next*. Designing next year's
campaign is plans; running this quarter's is operations. If the module acts on committed work it
is operations; if it produces a decision about work not yet committed it is plans.

This is why `ContentStrategistAgent` is here while `CampaignManagerAgent` and `ContentAnalystAgent`
are in operations — same content cluster, different point on the timeline.

**vs [`intelligence/`](../intelligence/) (S2) — decision or analysis.**
Intelligence establishes what is true. Plans chooses what to do about it. A market-sizing module
that only reports is intelligence; one that recommends which market to enter is plans.

**vs [`finance/`](../finance/) (S8) — the plan or the money.**
Deciding *what* to build next year is plans. Costing it, budgeting it and tracking spend against it
is finance. When a module does both, file it by its output: a decision → plans, a ledger → finance.

## Filing a module here

`plans/<component>/<module>/`, where `<component>` is the module's dominant deliverable.
Single-agent modules may sit flat as `agents/<Name>Agent.py`. See [`../AGENT.md`](../AGENT.md) for
the full filing rules and [`../README.md`](../README.md) for the framework.
