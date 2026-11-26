# A workspace's offer gives what lies outside it

- **Status:** Accepted
- **Date:** 2026-11-25
- **Amends:** `20261120_access_levels_and_groups.md`, decision 10 (Platform Files) and the shared-graph note of decision 4.

## Context

"<W> access" is W's offer and its ceiling. Its sections name what lies **in** W: its modules' agents, apps, workflows and pipelines, its features, and its search sources (`${scope}/...`). A level grants a type; the offer, held by "<W> workspace" at W as W's **bound**, says which items of that type.

A workspace also uses what lies **outside** it, and no section can say so:

| What | Where it lives | How W's people reach it today |
|---|---|---|
| Platform Files | `abi:nexus:platform_file/*`, `naas_abi/platform-drive` | A platform group per workspace, "Platform Files · <W> (<id>)", holding a platform policy; Nexus keeps its members equal to W's people. |
| System Files | every key of the object storage | Only the platform admin. |
| Organization Files | `<O>/nexus:file/organization/*` | Only people with a role at the organization; W cannot give it. |
| Another workspace's or the platform's graphs | `abi:triple_store:graph/<iri>` | Two policies per workspace (`workspace.<ws>.graphs.read|write`) attached to each person, without scope; Nexus keeps the holders in step (`graph_grants`). A policy past 100 patterns fails (two workspaces of a deployment). |
| Map layers, feeds and basemaps of the platform | `nexus:layout|feed_layer|basemap/<id>` | `maps_grants.workspace_ids`, filtered by Nexus. |

Each is a second mechanism beside the offer, edited on its own page, kept in step by Nexus, and drifting when IAM is changed around Nexus. Administrators expect to read and change what a workspace may use in one place: its offer.

The reason they are not in the offer is the bound rule (#1585). What a membership group holds at its own container bounds that container and grants nothing, and IAM refuses an unscoped attachment to a group a workspace owns. Decision 10 rejected a core exception (option b) and chose a group per workspace.

## Decision

1. **"Given" sections.** "<W> access" may hold Allow statements whose resources are named **outside** W: absolute names, not `${scope}/`. IAM reads them as **grants** to the people of W, held while they belong to W. Its `${scope}/` statements stay W's bound, as today.
   - Sids: `GivenPlatformFiles`, `GivenSystemFiles`, `GivenOrgFiles`, `GivenGraphs`, `GivenMaps`. Past `MAX_PATTERNS`, a section is written in parts (`GivenGraphs2`...), as the offer's sections are.
   - The people of W are the members of its membership groups, "<W> workspace" and "<W> admins". Leaving W ends the grant at once. Nothing is kept in step by Nexus.
2. **Grant only what you hold.** Writing a given section is held-checked like any grant: the writer must hold each action on each resource. As a result:
   - only the platform admin gives Platform Files and System Files;
   - an org admin gives their organization's files, and the graphs they hold;
   - a workspace admin may take a given section away (narrowing), never add one.
3. **The level still decides what is done.** A given statement's action counts for a person only when their level in W grants that action's level: a Viewer reads, a Member writes, a Workspace admin administers. "Read and write" Platform Files therefore lets a Viewer of W read them, not write them.
4. **One editor.** The policy page's Configuration of "<W> access" shows the given sections beside the offer's:
   - **Files**: My Files and Workspace Files (on by default); Organization Files, Platform Files (Off / Read / Read and write); System Files (Off / Read).
   - **Graphs**: read and write, by graph.
   - **Maps**: by layer, feed and basemap.

   General › Platform Files, the graph assignments and Maps' "which workspaces" become this editor, or read from it.

   *Amended 2026-11-26:* the editor is the workspace's settings pages, one part each. Access › Features and Access › Modules choose what the workspace offers (features; the agents, apps, workflows and pipelines of each module, whole or item by item); the pages under Features then show what is offered, and Files, Search, Graphs, Maps, Ontologies and Models (its models and default) edit their own part. The policy page of "<W> access" no longer has a Configuration tab: it shows the document (Advanced, Builder, Code), so each part has one editor. Features and Modules are policy wrappers: a Policy dropdown picks another policy the workspace owns, and the same switches write its sections (what it grants its holders, within the offer).
5. **Migration** (`offer_gives_v1`), run once and reported:
   - Each "Platform Files · <W>" group becomes `GivenPlatformFiles` in "<W> access", in the same mode. The groups and the two platform policies are deleted.
   - Each `workspace.<ws>.graphs.read|write` becomes `GivenGraphs` statements. The per-person attachments and the policies go. The two workspaces past 100 patterns get their grants for the first time: they are reported as widenings.
   - `maps_grants` and the maps' `hidden_*` become `GivenMaps`. Hidden items stay a display choice of the workspace.
   - `workspace_drive_flags_legacy.system_drive_enabled` is reported, not converted, as decision 10 did.

## Decided with the product owner (2026-11-25)

- **Writing a graph W is given:** Members of W write it, as they write W's own; Viewers read it.
- **The level caps what is given** (decision 3), confirmed.
- **My Files** is always on for Members and Workspace admins. A workspace may turn it off for its **Viewers** only (`GivenMyFiles` names who keeps it).

## Maps (decided on implementation, 2026-11-26)

- **What is given.** The Maps items a workspace uses without owning them: the deployment's feeds (`layout`) and
  basemaps (seeds, copied into each workspace that uses them) and the ones another workspace shares with it. A
  feed's layers follow their feed; built-in feeds and graph layers are not in it.
- **Sections.** `GivenMaps` (feeds: `ListLayouts`, `GetLayout`) and `GivenBasemaps` (`ListBasemaps`, `GetBasemap`),
  Allows on absolute names: `abi:nexus:<kind>/*` (every deployment item, the ones added later too),
  `abi:nexus:<kind>/<id>`, or `<V>/nexus:<kind>/<id>` for V's item. And `OfferMapsDeny`, `OfferBasemapsDeny`, Denies
  of W's bound on `${scope}/nexus:<kind>/<id>`: a deployment item W does not use though every one is given (a row
  of `maps_grants` narrowing it away). List and read only: W administers its own copies through its roles.
- **Who gives.** Settings › Maps › Access stays item by item, and writes the offer of each workspace a change
  touches, as the caller: the platform admin gives a deployment item; V's item is given by whoever holds it in V
  and may change W's offer; a workspace admin closes a deployment item in W and never reopens it.
- **Hidden** (`maps_settings.hidden_*`) stays the workspace's display choice: not in the offer.
- **New workspaces** are given every deployment feed and basemap (what no `maps_grants` row meant).
- **Migration** `maps_offer_v1` (not part of `offer_gives_v1`): every deployment item, those narrowed away closed,
  and the shared items by name. `maps_grants` stays for the workspaces whose access policy is no allow-list yet;
  a change one of them would need is refused (409) until it is converted.

## Open question

- **The core change** is one rule in the evaluation of a membership group's own bound (absolute names become grants to its members, capped by their level, decision 3), and one in the held check. It needs the core security tests: a given statement never reaches a non-member, never outlives the membership, never exceeds the person's level, and never beyond the writer's holdings.

## Consequences

- One place says what a workspace may use, in it or outside it. IAM's `explain` names "<W> access" for both.
- The Platform Files groups, the per-person graph attachments and their sync code go. A membership change made in IAM, around Nexus, is followed at once.
- The 100-pattern failures of graph grants go: sections are written in parts.
- The bound rule gains an exception, which decision 10 avoided. It is narrow: Allow statements only, on absolute names, in a membership group's own container policy, capped by the level.
- Organization Files can be given to a workspace, which is not possible today.
