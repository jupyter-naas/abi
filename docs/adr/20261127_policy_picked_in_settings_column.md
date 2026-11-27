# The policy a workspace's Features and Access pages set is picked in the Settings column

- **Status:** Accepted
- **Date:** 2026-11-27
- **Builds on:** `20261126_access_levels.md` (another policy of the workspace, edited as its offer), `20261126_models_in_the_offer.md`, `20261125_offer_gives_outside_resources.md`.

## Context

Access › Features, Core Services and Modules each had a Policy dropdown in the page: "<W> access" (the workspace's offer) by default, or another policy the workspace owns (what it grants its holders, within the offer), kept in the URL (`?policy=`). The pages under Features (Datasets, Files, Models, Search, Graphs, Ontologies) edit parts of the same document, "<W> access", but had no way to edit another policy: their routes (`PUT /offer/files`, `/offer/models`, `/offer/search-sources`, `GET` / `PUT /offer/datasets`) always wrote "<W> access". One policy set by three dropdowns and six pages that could not follow it (#1647).

## Decision

1. **One Policy picker, in the Settings column** of a workspace, under the Features heading, a search dropdown like the Organization and Workspace pickers atop it (`SettingsPolicyPicker`). It lists the workspace's policies as `/feature-access` answers them ("<W> access" first). The pick is the URL's `?policy=` (no `?policy=`: "<W> access"); every link of the column to Access › Features, Core Services, Modules and the pages under Features carries it (`components/settings/settings-policy.ts`). The three Access pages drop their in-page dropdown in a workspace's Settings (`policyPicker={false}`); Organization and Platform settings keep theirs.
2. **With another policy picked, the Features group lists the pages of the features it grants** (a row Granted in `/feature-access?policy=`; Files by its `files` feature); a page that shows no feature (Workflows) stays. With "<W> access", the group is what the workspace offers, as before.
3. **The offer's sub-routes take `?policy=`** as `/offer`, `/feature-access` and `/access-levels` already did: `PUT /offer/search-sources`, `/offer/models`, `/offer/files`, and `GET` / `PUT /offer/datasets`. The service resolves the policy with `_target` (one the workspace owns, not managed by IAM; any other is 404) and writes that document as the caller; the answer reads the same policy. For datasets, another policy works within "<W> access": a namespace the workspace (or its organization) closes is closed above it and is not reopened there.
4. **Graphs and Ontologies stay the workspace's own**: `/resource-access/{kind}` has its own revisioned assignments, held by no policy. With another policy picked, their pages say they set them for everyone in the workspace.

## Consequences

- One place says which policy the Features and Access pages set, and the URL can be shared or reloaded on it.
- The front end calls the sub-routes with `?policy=` only when a policy is picked: "<W> access" calls are unchanged; the Organization's routes (`/organizations/{id}/offer/datasets`) take no policy.
- A page's unsaved drafts (Access › Features) are dropped when another policy is picked in the column: the page opens afresh on it.
- Ontology files offered through `PUT /offer/ontologies` and the graphs given stay on "<W> access" only.
