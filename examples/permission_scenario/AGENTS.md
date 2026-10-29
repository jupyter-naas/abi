# Permission scenario

Two SDK modules that stand in for People Intelligence and Market Intelligence, so the
permission model (module scopes, sub-policies, zero trust, grant only what you hold;
core `services/iam/AGENTS.md`) can be checked end to end in `abi dev up`,
without Docker and without a model.

| Module | Package | What it exposes |
|---|---|---|
| P, `dev.people` | `scenario_people` | agents `Recruiter` (A) and `Scout` (B); its own catalog `dev_people` with `ExportReport` on `report` |
| M, `dev.market` | `scenario_market` | app `prices` (`apps/prices`) |

The agents answer without a model. `Recruiter` acts for the user it runs for:
`export <report>` enforces `dev_people:ExportReport` (`require_action`), and
`policy <scope> <type>/<module>/<name>` creates, over NATS, a policy owned by `scope`
letting its holders use that item, which IAM refuses as it refuses that user over REST
when they could not grant it. P's manifest therefore asks for `iam:CreatePolicy` and
`module:UseAgent` (a grant made for a user must be held on both sides).

## Files

| File | Role |
|---|---|
| `scenario_people/`, `scenario_market/` | the modules (`python -m <package>`) |
| `runner.py` | runs one as `abi dev up` starts it (`ABI_SERVICE_KEY`, `ABI_NATS_URL`, `ABI_DISCOVERY_PROJECT`) |
| `../../config.scenario.yaml` | the repository's `config.yaml` plus both under `dev.modules` |

## Run

```bash
ENV=scenario uv run abi dev up -d     # every abi dev command takes ENV=scenario
ENV=scenario uv run abi dev code --email bob@example.com
```

`abi dev up` approves the modules' manifests (dev only). Then, as in the brief of the
permission work:

1. The platform admin creates the policy "O access" allowing P and M under organisation O
   (Platform settings › Roles & permissions) and attaches it org-wide to O's admins.
2. An admin of O uses P and M in W at once; a member of W with no policy uses nothing,
   and neither does an admin or owner of a workspace with no policy (no role holds a
   module scope).
3. The O admin creates "W analysts", a sub-policy of "O access" allowing `Recruiter`,
   attaches it to group G at W, adds Bob.
4. Bob lists and uses `Recruiter` only; `Scout` and `prices` are refused and not listed.
5. W's admin, not an admin of O, deriving from "O access" or granting what they do not
   hold (`agent/naas_abi/AbiAgent`) is refused with the item named: over REST, and over
   NATS by asking `Recruiter` for `policy abi:<O>:<W> agent/naas_abi/AbiAgent`.
6. The platform admin removes P from "O access": Bob and the O admin lose it at once,
   "W analysts" grants nothing of P, the platform admin still uses it.
7. Settings › Apps lists what the caller may open; there is no on/off switch: a
   workspace that should not offer `prices` denies it in a policy.

A database the previous version ran this scenario on (sets, an app turned off, a
group's policy) upgrades at the next start: the sets and the switches become "<O>
access" and "<W> access" policies, and every decision stays the same
(`libs/naas-abi/.../services/iam/policy_tree.py`).

The declared action: Bob asks `Recruiter` for `export q3` (refused, naming
`abi:<O>:<W>:dev_people:report/q3`), W's admin grants `ExportReport` to G in the builder,
Bob asks again (exported).

People sign in with the code the built-in provider mails (`abi dev code --email`);
invite them first (`POST /api/organizations/<O>/members/invite`, or the Users page).
