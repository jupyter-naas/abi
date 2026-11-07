# Permission scenario

Two SDK modules that stand in for People Intelligence and Market Intelligence, and a runner
that drives them, so the permission model (module scopes, container paths, sub-policies,
zero trust, grant only what you hold; core `services/iam/AGENTS.md`) can be checked end to
end in `abi dev up`, without Docker and without a model.

| Module | Package | What it exposes |
|---|---|---|
| P, `dev.people` | `scenario_people` | agents `Recruiter` (A) and `Scout` (B), `Onboarder` and `Coach`; app `directory` (`apps/directory`); its own catalog `dev_people` with `ExportReport` on `report`, and a container type, `project` (`GetProject`, `CreateProject`, `DeleteProject`), registered inside a workspace |
| M, `dev.market` | `scenario_market` | agent `Pricer`; app `prices` (`apps/prices`) |

The agents answer without a model. `Recruiter` acts for the user it runs for:

- `export <report>` enforces `dev_people:ExportReport` (`require_action`) in the workspace of
  the chat; `export <report> in <project>` makes the same call inside the project;
- `project <id>` registers a project in the workspace of the chat, through the SDK
  (`iam.register_container`: a create on `<W>/dev_people:project/<id>`, for the module and
  the user);
- `policy <scope> <type>/<module>/<name> [under <parent policy id>]` creates, over NATS, a
  policy owned by `scope` letting its holders use that item, a sub-policy of the parent if
  named. IAM refuses it as it refuses that user over REST ("Grant only what you hold",
  "Derive only from what you hold"), so the runner compares the two refusals.

P's manifest therefore asks for `iam:CreatePolicy` and `module:UseAgent` (a grant made for a
user is checked on both sides).

## Files

| File | Role |
|---|---|
| `scenario_people/`, `scenario_market/` | the modules (`python -m <package>`) |
| `launch.py` | runs a module as `abi dev up` starts it (`ABI_SERVICE_KEY`, `ABI_NATS_URL`, `ABI_DISCOVERY_PROJECT`) |
| `runner.py` | the scenario: over REST as each person (signed in with the code the built-in provider mails, `scripts/cli_smoke_checks.py`), over NATS through `Recruiter` |
| `journeys.py` | the user journeys of issue #1413 with the issue's cast, one or more checks per journey ID and per cross-cutting rule and layer (below) |
| `view_as.py` | the checks of "View as" (Nexus `services/view_as/AGENTS.md`), run after `journeys.py` on the same database, with its tag, cast and helpers (below) |
| `../../config.scenario.yaml` | the repository's `config.yaml` plus both modules under `dev.modules` |

## Run

```bash
ENV=scenario uv run abi dev up -d     # every abi dev command takes ENV=scenario
API=http://localhost:<api port>       # abi dev ports
.venv/bin/python examples/permission_scenario/runner.py run --api $API --mail storage/email --out results.json
```

`abi dev up` approves the modules' manifests (dev only). `run` makes a new organisation each
time, so it may run again on the same database. It writes every check with its evidence (the
API's answers) and exits non-zero when one fails. The invitation routes are rate limited (five
a window per inviting user): the runner waits the window out. Call the venv's Python, not
`uv run`: the dev API reloads on any change under the worktree, and `uv run` reinstalls the
editable packages into `.venv`.

### Step 1, the upgrade

A database the previous version (`feat/permission-system` before this job, with sets and
on/off toggles) ran #360's scenario on upgrades at the next start, and every person's decisions
stay the same:

```bash
# on the previous version's checkout, with these modules (ENV=scenario abi dev up -d):
runner.py legacy --api $OLD --mail <old>/storage/email --database <old>/storage/nexus.db --out before.json
# stop it; give this checkout its storage/, its .env and its ports (.abi/dev/instance.json,
# project_root set to this checkout), start this version, then:
runner.py decisions --api $API --mail storage/email --out after.json
runner.py compare before.json after.json --out upgrade.json
```

The ports matter: a person is linked to their account by the identity provider's issuer, whose
URL holds the port, so the same database behind another port signs nobody in
(`sso_error=email_in_use`). An install keeps its URL across an upgrade.

`legacy` builds organisation "Acme": its set {P, M} with six features, Alpha's set {P, M} with
chat, files and settings, Beta's {M}; members of Acme lose `files` (the role features page);
Alpha's admin makes group G and a policy for `Recruiter`, with Bob in G; `prices` turned on in
Alpha and off in Beta. `legacy` and `decisions` record, for every member of Acme and the
platform admin, in each workspace: every module item's use (IAM's simulator, and on the
previous version what the toggles turned off, read from its database by its readers' rules:
its routes list only a workspace's set, to the platform admin too), and every feature (the simulator, and the flags
the person's own workspace list shows). `compare` lists each change; the one the upgrade makes
on purpose is the platform admin reaching what a workspace had turned off
(Nexus `services/iam/AGENTS.md`, "The upgrade: sets and toggles become policies").

### Steps 2 to 7 (`run`)

2. The platform admin creates "O access" (platform-owned), allowing P's agents, M's apps and
   the features chat and files below organisation O (`<O>/*`), and attaches it there to O's
   admin.
3. O's admin creates workspace W and uses P and M there at once. A member of W with no policy
   uses and lists nothing: no agent, app, workflow or feature.
4. O's admin creates "W analysts", a sub-policy of "O access" owned by W, allowing `Recruiter`
   and chat; attaches it to group G at W and adds Bob. Bob lists and uses `Recruiter` and has
   chat; `Scout`, `prices` and files are refused to him and not listed.
5. W's admin (an admin of W only) is given `Recruiter` by the platform admin, so they can ask
   it. Deriving from "O access" and granting `Scout` are refused naming the parent and the
   item, over REST and over NATS (`policy … under …` to `Recruiter`), with the same error.
6. The platform admin removes P from "O access": Bob loses `Recruiter` at once, O's admin
   loses P and keeps M, "W analysts" grants chat only, the platform admin still uses P.
7. `Recruiter` registers project `p1` in W for the platform admin (`project p1`, through the
   SDK); W lists it (`/api/iam/admin/resources`). A policy attached at the project gives
   Carol `GetProject` on it and `ExportReport` on what it holds. She reaches the project's
   reports and nothing else of W (no agent, app, feature, report of W). Given `Recruiter` to
   ask it, her `export q3 in p1` is exported and her `export q3` (in W itself) refused.

The UI parts (the builder by publisher, sub-policies, the settings pages) are checked in a
browser against the same database.

## The #1413 journeys (`journeys.py`)

```bash
ENV=scenario uv run abi dev up -d
.venv/bin/python examples/permission_scenario/journeys.py --api $API --mail storage/email --out journeys.json
```

Every journey ID of issue #1413 (UJ-P1 to P4, O1 to O5, W1 to W5, A1, PE1 to PE3) is checked with the issue's cast,
each check with its evidence, and the issue's cross-cutting rules (parent bounds child, feature off means absent,
visibility and IAM agree, reduction never widens) at the platform, organization, workspace and member layers
(`rule:<rule>:<layer>`; "reduction never widens" compares IAM's simulator for every person, agent, app and feature in
Alpha and Bravo before and after each narrowing). The output names each journey and rule with whether all of its
checks passed. Every name carries a tag: the run may start again on the same database.

The cast: Root (the platform admin, `admin@example.com`); Acme, whose access ("Acme access", made with it) Root
widens to `dev.people`'s agents, apps Directory and Prices, and eight features; Alpha and Bravo, made by Olivia (Acme's
org admin), Alpha given the four agents and both apps, Bravo Prices only; Bob (Alpha's owner, given "Acme access" at
Alpha by Olivia, so he may show again what Alpha hides), Carol (Alpha's admin, in group "Alpha analysts"), Dave
(invited by Bob, in group "Alpha minimal": Recruiter, Prices, chat and Home, a Deny of BaseMap), Eve (an Acme member),
Frank (an Acme member, Alpha viewer), Gina (an existing user of Bravo, added by Carol: PE2 b); Beta Corp with Paul,
renamed, refused deletion while it has a workspace (409), then deleted.

Nexus has no Home, BaseMap or Workflows feature, and `tasks` is not in the repository configuration's
`enabled_features` (so it exists nowhere): the run uses `search` for Home, `graph` for BaseMap, `documents` for Tasks
and `datasets` for Workflows (`FEATURE_OF`). An agent is used in a chat, so "Alpha minimal" grants `chat` with
Recruiter. An organization role is owner, admin or member: Frank's read-only is his Alpha role (viewer); Bob becomes
Alpha's owner through the members route (an org invitation gives a workspace role up to admin).

Where the run follows the owner's rule rather than the issue's words (each person acts only on what they hold): Bob,
who holds Acme's grant at Alpha, still sees the agents Alpha hides (UJ-W3, "nobody sees Onboarder or Coach" holds for
everyone below "Alpha access"); Carol cannot expose Onboarder herself (UJ-PE3), Bob does. UI journeys (O1, W1, the
builder narrowing "<W> access") are checked in a browser against the same database.

## View as (`view_as.py`)

```bash
ENV=scenario uv run abi dev up -d
.venv/bin/python examples/permission_scenario/runner.py   run --api $API --mail storage/email --out results.json
.venv/bin/python examples/permission_scenario/journeys.py --api $API --mail storage/email --out journeys.json
.venv/bin/python examples/permission_scenario/view_as.py  --api $API --mail storage/email --journeys journeys.json --out view_as.json
```

`view_as.py` reads the tag, the cast (Root, Olivia, Bob, Carol, Dave, "Alpha minimal") and Alpha, Bravo and Acme from the
`--out` of `journeys.py`, reuses its helpers (`agents_seen`, `module_apps`, `agent_ids`, `open_app`) and `runner.py`'s
(`Api`, `Grammar`, `Report`, `flags`, `principals`), and writes each check with its evidence (the API's answers); it exits
non-zero when one fails. It signs each viewer in once, on a session of its own (a view is kept on its session, and every
`viewing` ends with Stop, so the session is the viewer's again afterwards). The identity provider limits sign-ins per
address and per client for five minutes: a rate limited sign-in waits. The end of an app's link is read from IAM's keys
(`--iam-database`, `storage/iam/iam.sqlite`, opened read only), as the grant's answer (`expires_in`) is the link's own
lifetime, not the view's.

| Step | What is checked, each with its evidence |
|---|---|
| `view-1` Root views as Carol | Alpha is offered for Carol, Bravo is not. The view answers as Carol: `/api/auth/me` is Carol, `/api/workspaces` lists Alpha only with her feature flags, her agents (`dev.people`'s, no Pricer) and apps (Directory, Prices), and every Alpha settings page she may open answers as it does for her (General, Members, and Roles & permissions: what she holds, policies, groups, attachments). The groups of Alpha are read by id. Bravo's pages and the platform's (workspace, agents, files, members, Acme's settings and members, policies, audit, users, system) are 403 "Outside this view: you are viewing as <name> in <workspace>". Carol holds a conversation, a secret, an API key and a My Drive file, and the view answers empty (a single item 404). Olivia, who reads a group of Bravo herself, is refused it in a view of Alpha. Stop. |
| `view-2` Carol views as Dave | Dave's view is "Alpha minimal": Recruiter, Prices, chat and Home (`chat`, `search`), no BaseMap (the route is refused). A chat message and a saved setting (and the settings cache's refresh) are 403 "Read-only: you are viewing as Dave". Nothing changed: Dave's and Carol's conversations, Alpha's description, Alpha's secrets. |
| `view-3` Refusals | Carol as Olivia: "Olivia holds Admin (builtin.admin), attached below <Acme>, which you do not hold: …". Carol as Bob: "… Owner (builtin.owner), attached at <Alpha>, which you do not hold: …". Carol and Olivia as Root: "… holds builtin.platform_admin: nobody views as the platform admin"; Root as Root: "You cannot view as yourself". None of them is offered a workspace. |
| `view-4` Audit | Platform settings › Roles & permissions › Audit (`GET /api/iam/admin/audit`) shows, with who (the viewer's Nexus id), whom (the person's IAM id) and where (the workspace and the end time): each start and stop of Root's views, Carol's view of Dave, each refusal (`failed`, with its error), and the app opened. |
| `view-5` Ending, and apps | The end is the start plus 15 minutes. After Stop the session has no view and is Root's: his own account and his workspaces. Prices opened in a view: its link (a key marked `view-as:`) ends no later than the view, a GET through it answers, a POST through it is 403 "Read-only: you are viewing as Carol", and after Stop the link is revoked (the key's `revoked_at`) and the app no longer opens. |

The 15 minutes at the clock (a view that ends by itself) is a server test (`services/view_as/view_as_http_test.py`, with a
clock), not a wait here.

### In a browser

Against the same database (the Nexus web at `abi dev ports`' `nexus-web`), signed in with the code the provider mails
(`abi dev code`):

1. Platform settings › Roles & permissions › People & roles › Carol: "View as Carol" and the picker (Alpha preselected).
2. Start: the web loads Alpha's Home with the banner "Viewing as Carol (read-only) in Alpha · 15 min left · Stop", then a
   workspace page, Alpha's settings (Roles & permissions, with the people, groups and policies Carol sees) and the account page.
3. Private pages: the account's API keys ("Private to Carol"), Alpha's secrets, and the chat's history.
4. Carol, signed in as herself, views as Dave from Alpha's Roles & permissions: a save of the account page and a chat message
   are refused with "Read-only: you are viewing as Dave", in the bubble and as a notice.
5. Stop: back to the person's page, and `GET /api/auth/oidc/session` has no `view`.

### The acceptance run (#612)

On fresh storage (`storage/` emptied, `ENV=scenario abi dev up -d`): `runner.py run` 35 checks, `journeys.py` 46 checks and
`view_as.py` 33 checks, all passing. What the run found and fixed:

- Alpha's Roles & permissions page (and the settings menu that reads it) read IAM's admin routes with `scope=<the
  workspace's container>`, which a view refused: the page could not open. A GET under `/api/iam/admin/` that declares `scope` is
  answered when every scope given is the viewed container or below, and a group is read by id held to the container
  (Nexus `services/view_as/AGENTS.md`).
- Start landed on `/workspace/<id>`, which has no page (404): it lands on the workspace's Home.
- A chat message a view refused showed "API error: 403": it shows the server's message.

Left open (`services/view_as/AGENTS.md`, "Not done"): the calls a workspace page makes that a view refuses, shown as notices.
