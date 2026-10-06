# Client vs. employer on an act of working

Status: Accepted

Date: 2026-09-30

## Context

`personnel:ActOfWorking` had one organization slot, `personnel:forOrganization`, documented as "the organization that participates as employer." That models a direct employee fine, but not a professional-services consultant: importing Alexis Tourneux's CV (Forvis Mazars, staffed across 17 client engagements — Allianz, EDF R&D, TotalEnergies, and others) forced a choice between two wrong shapes.

Organization = employer ("Forvis Mazars") for every engagement collapsed all 17 missions into one experience card with no way to tell them apart, since the app's `_experience()` grouping and `group_seq` assignment (`export_people_from_graph.py`) key on that field. Organization = client instead scattered Alexis's Forvis Mazars career across 13 separate top-level cards, one per client, which reads as 13 different employers rather than one consulting career, and every client shared the same `ActOfWorking` URI key (`slug(person, org, title)`) whenever a title repeated at that client, so unrelated missions with the same title silently merged into one node — the actual bug reported against this data (three TotalEnergies engagements sharing one "Data Architect" title merged into a single, date-conflated entry).

Missions also had a single free-text field, `personnel:mission_content`, holding whatever a source gave: an opening paragraph, a bullet list of activities, or both run together. A CV's own two-part structure — "Contexte" (the situation a mission responded to) and "Mission" (what was actually done, as bullets) — had nowhere distinct to go.

## Decision

`personnel:forOrganization` keeps its meaning: the employer. A new, optional object property, `personnel:forClient` (inverse `personnel:isClientOfWorking`), names the organization the work was performed for when the employer staffed the person there — unset for a direct role. The app's experience grouping continues to key on `organization` (the employer), so a consultant's engagements nest under one card the way the rest of the directory expects; `client` (with a logo, curated the same way as portraits) is carried per role inside that card.

The `ActOfWorking` URI key (`graph_builders.py add_working`) now folds the client into `slug(person, organization, client, title)`, so two engagements at the same client with the same title no longer collide onto one node regardless of how a source names them — the fix is structural, not a title-uniqueness convention CV data has to maintain by hand.

A new optional data property, `personnel:mission_context` (parallel to `mission_content`, both `Mission`-scoped), carries the situational paragraph. `mission_content` keeps its role as the mission's stated text, now documented as one line per activity when a source enumerates discrete tasks — no new multi-valued RDF property, so `find_working_experiences` (`PersonnelSparqlQueries.ttl`) stays a flat, one-row-per-`ActOfWorking` SELECT with two more OPTIONAL single-valued bindings (`?client`/`?clientLabel`, `?missionContext`) rather than one that fans out per task.

Client and employer logos are a curated local asset map (`data.organization_logos` in an instance's `config.yaml`, name → path under `web/`), the same pattern `offices.yaml` already uses for office addresses: nothing is fetched from a third party at render time, and a name with no entry falls back to an initials badge (`orgAvatarHtml` in `dom.js`, reusing the existing `avatarHtml` fallback-underneath pattern).

## Consequences

`ActOfWorkingPipelineParameters`, `WorkingRecordInput` and `ProfileBlockInput`'s working-record shape gain `client` and `mission_context`, both optional — every existing `data/person/*/index.json` across every instance keeps working unchanged, with `client` and `context` simply absent. The `people_experience` dataset table gains two nullable columns (`client`, `context`); a hand-rolled fixture that lists that table's columns explicitly (`datasets_test.py`) needed them added — anything using `build_rows()` or the demo/graph pipelines did not.

An instance that wants engagement bullets to render as a list rather than one paragraph writes `mission` as newline-separated tasks; the frontend (`sections.js`) splits on `\n`, so a single-line value (every profile as of this change) still renders as one line. Logo coverage is opt-in and manual: this ADR ships the plumbing and the fallback, not any actual logo files.
