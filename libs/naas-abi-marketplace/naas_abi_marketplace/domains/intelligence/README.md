# S2 — intelligence

## The question this bucket answers

> *What is true about the world outside us?*

In the staff system, S2 collects and analyses information about the environment and about
adversaries, and turns it into a picture the commander can act on. In a civilian organization it
covers market and competitor research, OSINT, due diligence, risk assessment and situational
awareness.

Intelligence **observes**. It does not decide what to do (that is [`plans/`](../plans/)) and it does
not act on the finding (that is [`operations/`](../operations/)).

## What's here

```
intelligence/
├── __init__.py                         # ABIModule, datastore_path = "intelligence"
├── agents/
│   ├── OSINTResearcherAgent.py
│   └── PrivateInvestigatorAgent.py
└── modules/                            # loadable modules, each with its own ABIModule
    ├── organizations/                  # organization vocabulary
    ├── people/                         # people intelligence + People Search
    └── wsr/                            # World Situation Room
```

| Module | Component | What it delivers |
|---|---|---|
| `OSINTResearcherAgent` | `agents/` | Open-source collection, threat analysis, digital forensics |
| `PrivateInvestigatorAgent` | `agents/` | Investigation planning, evidence analysis, case documentation |
| [`organizations/`](modules/organizations/) | `modules/` | Organization vocabulary + alliance/restructuring processes + 10 SPARQL query tools |
| [`people/`](modules/people/) | `modules/` | People vocabulary (acts of working, studying, certification; skills, languages, profiles), its pipelines, `PeopleAgent`, People Search and the 7-bucket person graph |
| [`wsr/`](modules/wsr/) | `modules/` | World Situation Room — live 3D globe (satellites, flights, seismic, conflict zones) with `WSRAgent` and its own credentials |

Enable each module next to the bucket:

```yaml
- module: naas_abi_marketplace.domains.intelligence
  enabled: true
- module: naas_abi_marketplace.domains.intelligence.modules.organizations
  enabled: true
- module: naas_abi_marketplace.domains.intelligence.modules.people
  enabled: true
- module: naas_abi_marketplace.domains.intelligence.modules.wsr
  enabled: true
  config:
    opensky_client_id: ""
```

`organizations/` and `people/` are the vocabularies intelligence reasons **over**: who an
organization is, how it allies and restructures; who a person is, where they worked and studied,
what they know. They are filed here because their subject matter is the world outside us - a
person is in `people/` whoever employs them, including your own staff. What the organization
records about its own staff (employee roles, contracts, grades, service lines) is personnel (S1),
which specializes the people vocabulary.

## What belongs here

- Open-source and public-record collection
- Competitor, market and sector monitoring
- Due diligence and counterparty research
- Risk and threat assessment
- Situational-awareness dashboards
- Vocabulary describing entities **outside** the organization

## Boundary tests

**vs [`signals/`](../signals/) (S6) — outside or inside.**
Intelligence is about the world outside the organization; signals is about information moving
inside it. A competitor-monitoring module is intelligence; a document-ingestion pipeline serving
every internal team is signals — even though both end up producing searchable text.

**vs [`plans/`](../plans/) (S5) — analysis or decision.**
Intelligence tells you what is true. Plans decides what to do about it. A module that measures
content performance is intelligence; a module that sets the next content calendar is plans.

**vs [`external/`](../external/) (S9) — observe or engage.**
Both look outward. Intelligence *watches* the outside without interacting with it. External
*talks to* it — community, partners, public. Monitoring a competitor's launch is S2; replying to
their announcement on your channel is S9.

**vs [`personnel/`](../personnel/) (S1) — anyone's facts or our records.**
What can be known about a person - career, studies, skills, published profile - is intelligence
(`modules/people`), even for your own staff. What the organization records about its own staff
(employee role, contract, grade, service line) is personnel, which specializes the people
vocabulary and is never referred to from here.

**vs [`operations/`](../operations/) (S3) — knowing or acting.**
Researching a prospect before the call is intelligence; running the call and the deal is
operations.

## Filing a module here

`intelligence/<component>/<module>/`, where `<component>` is the module's dominant deliverable.
Single-agent modules may sit flat as `agents/<Name>Agent.py`. A self-contained unit with its own
vocabulary, agent or configuration that other modules build on is a loadable module under
`modules/<module>/`. See [`../AGENT.md`](../AGENT.md) for
the full filing rules and [`../README.md`](../README.md) for the framework.
