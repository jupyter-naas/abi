# Permission scenario

Two SDK modules that stand in for People Intelligence and Market Intelligence, so the
permission model (sets, module scopes, zero trust, grant only what you hold,
visibility; core `services/iam/AGENTS.md`) can be checked end to end in `abi dev up`,
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

1. The platform admin gives an org O the set {`dev.people`, `dev.market`}
   (Modules & features, or `PUT /api/iam/admin/sets/<O>`).
2. An admin of O gives workspace W the same set; adding another module is refused,
   naming it (`PUT /api/iam/admin/sets/<O>/workspaces/<W>`).
3. W's admin creates group G and a policy for agent `Recruiter` in W's Roles &
   permissions (the builder offers W's set only), attaches it to G at W, adds Bob.
4. Bob lists and uses `Recruiter` only; `Scout` and `prices` are refused; a member with
   no policy has no module scope.
5. W's admin granting `agent/naas_abi/AbiAgent` (outside the set) or an action they do
   not hold is refused with the item named: over REST, and over NATS by asking
   `Recruiter` for `policy abi:<O>:<W> agent/naas_abi/AbiAgent`.
6. The platform admin removes `dev.people` from O's set: Bob and W's admin lose it at
   once, the platform admin still uses it.
7. W's Settings › Apps lists `prices` only; turned off, it is refused to everyone in W.

The declared action: Bob asks `Recruiter` for `export q3` (refused, naming
`abi:<O>:<W>:dev_people:report/q3`), W's admin grants `ExportReport` to G in the builder,
Bob asks again (exported).

People sign in with the code the built-in provider mails (`abi dev code --email`);
invite them first (`POST /api/organizations/<O>/members/invite`, or the Users page).
