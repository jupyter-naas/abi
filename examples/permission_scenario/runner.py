"""The permission scenario, end to end, against a running ``abi dev up``
(``ENV=scenario``): the steps of ``AGENTS.md``, over REST as each person, and
over NATS through ``Recruiter`` where the step names it.

    python examples/permission_scenario/runner.py legacy    --api URL --mail DIR --database DB --out before.json
    python examples/permission_scenario/runner.py decisions --api URL --mail DIR --out after.json
    python examples/permission_scenario/runner.py compare   before.json after.json --out upgrade.json
    python examples/permission_scenario/runner.py run       --api URL --mail DIR --out results.json

* ``legacy`` runs on the previous version (sets and on/off toggles): it builds
  #360's scenario in organisation "Acme", then records every decision; its
  toggles are read from its Nexus database (``--database``, ``storage/nexus.db``).
* ``decisions`` records them on either version: for every member of "Acme" and
  the platform admin, every workspace of it, every module item (its use action,
  IAM's simulator, and what the previous version turned off) and every feature
  (the simulator, and the flags the person's own workspace list shows).
* ``compare`` says what changed; the only change the upgrade makes on purpose
  is the platform admin reaching what a workspace had turned off.
* ``run`` is steps 2 to 7, in a new organisation each time.

``--api`` is the Nexus API (``abi dev ports``), ``--mail`` the dev mail
folder (``storage/email``): people sign in with the code the built-in
provider mails, as ``scripts/cli_smoke_checks.py`` does.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from cli_smoke_checks import Session, sign_in  # noqa: E402

ADMIN = "admin@example.com"
USE_ACTIONS = {
    "agents": "module:UseAgent",
    "apps": "module:OpenApp",
    "workflows": "module:RunWorkflow",
    "pipelines": "module:RunPipeline",
}
FEATURES = (
    "maps", "chat", "files", "agents", "skills", "apps", "marketplace", "search",
    "ontology", "graph", "datasets", "settings", "code", "slides", "documents",
    "sheets", "tasks",
)  # fmt: skip
RECRUITER = "dev.people/Recruiter"
SCOUT = "dev.people/Scout"
PRICES = ("dev.market", "prices")
# The policy language a document is written in.
VERSION = "2026-10-13"


class Refused(Exception):
    def __init__(self, status: int, detail: Any) -> None:
        super().__init__(f"HTTP {status}: {detail}")
        self.status = status
        self.detail = detail


@dataclass
class Api:
    """Nexus over REST, signed in as each person once."""

    base: str
    mail: Path
    sessions: dict[str, Session] = field(default_factory=dict)

    def session(self, email: str) -> Session:
        if email not in self.sessions:
            self.sessions[email] = sign_in(self.base, self.mail, email, wait_seconds=90)
        return self.sessions[email]

    def call(self, email: str, method: str, path: str, body: Any = None) -> Any:
        while True:
            status, payload, _ = self.session(email).open(
                f"{self.base}{path}", method=method, body=body
            )
            if status != 429:
                break
            # The invitation routes are rate limited (``rate_limit_attempts`` a
            # window): wait for the window to pass.
            print(f"rate limited on {path}: waiting", flush=True)
            time.sleep(30)
        try:
            data = json.loads(payload) if payload else None
        except ValueError:
            data = payload[:300].decode("utf-8", "replace")
        if status >= 400:
            detail = data.get("detail", data) if isinstance(data, dict) else data
            raise Refused(status, detail)
        return data

    def get(self, email: str, path: str, **query: Any) -> Any:
        query = {k: v for k, v in query.items() if v is not None}
        return self.call(email, "GET", path + (f"?{urlencode(query)}" if query else ""))

    def post(self, email: str, path: str, body: Any = None) -> Any:
        return self.call(email, "POST", path, body if body is not None else {})

    def put(self, email: str, path: str, body: Any = None) -> Any:
        return self.call(email, "PUT", path, body)

    def patch(self, email: str, path: str, body: Any) -> Any:
        return self.call(email, "PATCH", path, body)

    def attempt(self, email: str, method: str, path: str, body: Any = None) -> dict:
        """A call whose refusal is the answer: ``{"status", "detail" | "body"}``."""
        try:
            return {"status": 200, "body": self.call(email, method, path, body)}
        except Refused as exc:
            return {"status": exc.status, "detail": exc.detail}


# -- names, in the grammar of the version that answers ----------------------------------


@dataclass(frozen=True)
class Grammar:
    legacy: bool

    def platform(self) -> str:
        return "abi:-:-" if self.legacy else "abi:"

    def org(self, org: str) -> str:
        return f"abi:{org}:-" if self.legacy else f"abi:nexus:organization/{quote(org)}"

    def below_org(self, org: str) -> str:
        return f"abi:{org}:*" if self.legacy else f"{self.org(org)}/*"

    def workspace(self, org: str, ws: str) -> str:
        if self.legacy:
            return f"abi:{org}:{ws}"
        return f"{self.org(org)}/nexus:workspace/{quote(ws)}"

    def inside(self, scope: str, rest: str) -> str:
        """``rest`` (``<svc>:<type>/<id>``) in the container ``scope``."""
        return f"{scope}:{rest}" if self.legacy else f"{scope}/{rest}"

    def item(self, org: str, ws: str, resource: str) -> str:
        """A module item's name from ``/api/modules/scopes`` (``${scope}…``)."""
        return resource.replace("${scope}", self.workspace(org, ws))


def grammar_of(api: Api) -> Grammar:
    """The previous version has no publishers route (asked without its scope:
    422 here, 404 there)."""
    found = api.attempt(ADMIN, "GET", "/api/iam/admin/publishers")
    return Grammar(legacy=found["status"] == 404)


# -- people and places -------------------------------------------------------------------


def org_named(api: Api, name: str) -> dict | None:
    return next(
        (o for o in api.get(ADMIN, "/api/organizations") if o["name"] == name), None
    )


def workspaces_of(api: Api, org_id: str) -> dict[str, str]:
    """``{name: id}`` of an organisation's workspaces."""
    return {
        w["name"]: w["id"]
        for w in api.get(ADMIN, "/api/workspaces")
        if w.get("organization_id") == org_id
    }


def principals(api: Api) -> dict[str, str]:
    """``{email: IAM principal id}`` of every user."""
    found: dict[str, str] = {}
    after = None
    while True:
        page = api.get(ADMIN, "/api/iam/admin/principals", kind="user", after=after)
        for item in page["items"]:
            if item.get("email"):
                found[item["email"].lower()] = item["id"]
        after = page.get("next_after")
        if not after:
            return found


def invite(api: Api, org_id: str, email: str, role: str, **extra: Any) -> dict:
    """``email`` into an organisation (and a workspace), by the platform admin,
    who may create the account at the built-in provider; then they sign in.
    Someone already a member is left as they are (a run started again)."""
    found = api.attempt(
        ADMIN,
        "POST",
        f"/api/organizations/{org_id}/members/invite",
        {"email": email, "role": role, "name": email.split("@")[0].title(), **extra},
    )
    if found["status"] != 200 and "already" not in str(found.get("detail")).lower():
        raise Refused(found["status"], found.get("detail"))
    # They sign in: their first sign-in links them to their IAM user.
    api.session(email)
    return found.get("body") or {}


def agent_rows(api: Api, email: str, ws: str) -> dict[str, dict]:
    """The agents ``email`` sees in ``ws``, by ``<module>/<name>``."""
    rows = api.get(email, "/api/agents/", workspace_id=ws)
    return {str(r.get("class_name")): r for r in rows if r.get("class_name")}


def chat(api: Api, email: str, ws: str, agent_id: str, message: str) -> dict:
    found = api.attempt(
        email,
        "POST",
        "/api/chat/complete",
        {"workspace_id": ws, "message": message, "agent": agent_id},
    )
    if found["status"] == 200:
        return {"status": 200, "answer": found["body"]["message"]["content"]}
    return found


def open_app(api: Api, email: str, ws: str) -> dict:
    module, app = PRICES
    return api.attempt(
        email,
        "POST",
        "/api/apps/remote-grant",
        {"workspace_id": ws, "module_id": module, "app": app},
    )


def flags(api: Api, email: str, ws: str) -> dict[str, bool]:
    """The features ``email`` has in ``ws``, as their own workspace list shows."""
    for w in api.get(email, "/api/workspaces"):
        if w["id"] == ws:
            return dict(w.get("feature_flags") or {})
    return {}


# -- decisions ---------------------------------------------------------------------------


def module_items(api: Api, org: str) -> list[tuple[str, str, str]]:
    """``(kind, <module>/<name>, resource)`` of every module item, as the platform
    admin lists them at the organisation (at a workspace, this version lists
    only what may be granted there: not what the workspace denies)."""
    found = []
    for module in api.get(ADMIN, "/api/modules/scopes", organization_id=org)["modules"]:
        for kind in USE_ACTIONS:
            for item in module.get(kind) or []:
                found.append(
                    (kind, f"{module['module']}/{item['name']}", item["resource"])
                )
    return sorted(found)


def turned_off(
    database: Path, ws: str, items: list[tuple[str, str, str]]
) -> set[tuple[str, str]]:
    """What the previous version's toggles turned off in ``ws``, read from its
    Nexus database by its readers' rules (``services/visibility``): an agent
    whose row is off; an app with no row on, unless the workspace's catalog
    seed names it; a workflow or pipeline whose row is off. Its routes do not
    say it: they list only the workspace's set, to the platform admin too."""
    db = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    agents_off = {
        (str(class_name), str(name), str(provider))
        for class_name, name, provider in db.execute(
            "SELECT class_name, name, provider FROM agent_configs"
            " WHERE workspace_id = ? AND enabled = 0",
            (ws,),
        )
    }
    apps_on = {
        str(app_id)
        for (app_id,) in db.execute(
            "SELECT app_id FROM app_configs WHERE workspace_id = ? AND enabled = 1",
            (ws,),
        )
    }
    apps_off = {
        str(app_id)
        for (app_id,) in db.execute(
            "SELECT app_id FROM app_configs WHERE workspace_id = ? AND enabled = 0",
            (ws,),
        )
    }
    seed = db.execute(
        "SELECT catalog_seed FROM workspaces WHERE id = ?", (ws,)
    ).fetchone()
    seeded = (
        set((json.loads(seed[0]) or {}).get("apps") or [])
        if seed and seed[0]
        else set()
    )
    processes_off = {
        (f"{kind}s", f"{module}/{name}")
        for kind, module, name in db.execute(
            "SELECT type, module_id, name FROM workflow_visibility"
            " WHERE workspace_id = ? AND enabled = 0",
            (ws,),
        )
    }
    db.close()

    def app_ids(module: str, name: str) -> set[str]:
        return {f"remote/{module}:{name}", f"{module}:{name}"}

    def app_on(module: str, name: str) -> bool:
        ids = {i for i in apps_on | apps_off | seeded if i.endswith(f":{name}")}
        ids = {
            i for i in ids if i.removeprefix("remote/").split(":")[0].startswith(module)
        }
        return bool(ids & apps_on) or bool(ids & seeded and not ids & apps_off)

    off: set[tuple[str, str]] = set()
    for kind, item, _ in items:
        module, name = item.split("/", 1)
        if kind == "agents":
            for class_name, row_name, provider in agents_off:
                own = (
                    class_name == item
                    if provider == "remote"
                    else row_name == name and class_name.startswith(f"{module}.")
                )
                if own:
                    off.add((kind, item))
        elif kind == "apps":
            if not app_on(module, name):
                off.add((kind, item))
        elif (kind, item) in processes_off:
            off.add((kind, item))
    return off


def simulate(api: Api, principal: str, action: str, resource: str) -> bool:
    return bool(
        api.post(
            ADMIN,
            "/api/iam/admin/simulate",
            {"principal_id": principal, "action": action, "resource": resource},
        )["allowed"]
    )


def record_decisions(
    api: Api, org_name: str, database: Path | None = None
) -> dict[str, Any]:
    """Every decision of "Acme"'s people (``database``: the previous version's
    Nexus database, for its toggles)."""
    grammar = grammar_of(api)
    if grammar.legacy and database is None:
        raise SystemExit("the previous version's decisions need its --database")
    org = org_named(api, org_name)
    if org is None:
        raise SystemExit(f"no organisation named {org_name}")
    spaces = workspaces_of(api, org["id"])
    people = principals(api)
    emails = sorted(
        {
            m["email"].lower()
            for m in api.get(ADMIN, f"/api/organizations/{org['id']}/members")
        }
        | {ADMIN}
    )
    decisions: dict[str, bool] = {}
    hidden: dict[str, list] = {}
    items = module_items(api, org["id"])
    for ws_name, ws in sorted(spaces.items()):
        off = turned_off(database, ws, items) if database is not None else set()
        hidden[ws_name] = sorted(map(list, off))
        for email in emails:
            principal = people[email]
            for kind, item, resource in items:
                allowed = simulate(
                    api,
                    principal,
                    USE_ACTIONS[kind],
                    grammar.item(org["id"], ws, resource),
                )
                # The toggles refused what was off to everyone in the workspace.
                decisions[f"{email}|{ws_name}|{kind}|{item}"] = (
                    allowed and (kind, item) not in off
                )
            scope = grammar.workspace(org["id"], ws)
            for key in FEATURES:
                decisions[f"{email}|{ws_name}|feature|{key}"] = simulate(
                    api,
                    principal,
                    "nexus:UseFeature",
                    grammar.inside(scope, f"nexus:feature/{key}"),
                )
            for key, on in flags(api, email, ws).items():
                decisions[f"{email}|{ws_name}|feature-flag|{key}"] = bool(on)
    return {
        "version": "previous" if grammar.legacy else "this",
        "organization": org["id"],
        "workspaces": spaces,
        "people": emails,
        "turned_off": hidden,
        "decisions": decisions,
    }


def compare(before: dict, after: dict) -> dict[str, Any]:
    """Every decision before and after; the changes, split into those the
    upgrade makes on purpose (the platform admin reaching what a workspace had
    turned off) and the others."""
    changed, expected, missing = [], [], []
    for key, was in sorted(before["decisions"].items()):
        if key not in after["decisions"]:
            missing.append(key)
            continue
        now = after["decisions"][key]
        if now == was:
            continue
        email, ws, kind, item = key.split("|", 3)
        row = {"key": key, "before": was, "after": now}
        if email == ADMIN and now and [kind, item] in before["turned_off"].get(ws, []):
            expected.append(row)
        else:
            changed.append(row)
    return {
        "compared": len(before["decisions"]),
        "allowed_before": sum(before["decisions"].values()),
        "allowed_after": sum(
            after["decisions"][k]
            for k in before["decisions"]
            if k in after["decisions"]
        ),
        "unexpected": changed,
        "expected": expected,
        "missing_after": missing,
        "new_after": sorted(set(after["decisions"]) - set(before["decisions"])),
        "ok": not changed and not missing,
    }


# -- the previous version: #360's scenario -----------------------------------------------


def legacy(api: Api, database: Path) -> dict[str, Any]:
    """#360's scenario on the previous version, in organisation "Acme": its set
    and its workspaces' (Alpha narrows the features, Beta the modules), a group's
    policy for ``Recruiter`` in Alpha made by Alpha's admin, ``prices`` turned on
    in Alpha and off in Beta, and members' features narrowed by the organisation."""
    grammar = grammar_of(api)
    if not grammar.legacy:
        raise SystemExit("legacy runs on the previous version (with sets)")
    org = org_named(api, "Acme") or api.post(
        ADMIN, "/api/organizations", {"name": "Acme", "slug": "acme"}
    )
    o = org["id"]
    spaces = workspaces_of(api, o)
    for name in ("Alpha", "Beta"):
        if name not in spaces:
            created = api.post(
                ADMIN,
                "/api/workspaces",
                {"name": name, "slug": f"acme-{name.lower()}", "organization_id": o},
            )
            spaces[name] = created["id"]
    alpha, beta = spaces["Alpha"], spaces["Beta"]
    invite(api, o, "acme-admin@example.com", "admin")
    invite(
        api,
        o,
        "alpha-admin@example.com",
        "member",
        workspace_id=alpha,
        workspace_role="admin",
    )
    for email in ("bob@example.com", "mallory@example.com"):
        invite(api, o, email, "member", workspace_id=alpha, workspace_role="member")
    invite(
        api, o, "beth@example.com", "member", workspace_id=beta, workspace_role="member"
    )
    invite(
        api, o, "vic@example.com", "member", workspace_id=alpha, workspace_role="viewer"
    )

    # 1-2. The sets: the organisation's, then each workspace's within it.
    api.put(
        ADMIN,
        f"/api/iam/admin/sets/{o}",
        {
            "modules": ["dev.people", "dev.market"],
            "features": ["chat", "files", "documents", "maps", "datasets", "settings"],
        },
    )
    api.put(
        "acme-admin@example.com",
        f"/api/iam/admin/sets/{o}/workspaces/{alpha}",
        {
            "modules": ["dev.people", "dev.market"],
            "features": ["chat", "files", "settings"],
        },
    )
    api.put(
        "acme-admin@example.com",
        f"/api/iam/admin/sets/{o}/workspaces/{beta}",
        {"modules": ["dev.market"], "features": None},
    )
    # Members of Acme lose ``files`` (the role features page).
    baseline = api.get(
        "acme-admin@example.com", f"/api/organizations/{o}/roles/features"
    )["role_baseline"]
    baseline["member"] = [key for key in baseline["member"] if key != "files"]
    api.put(
        "acme-admin@example.com",
        f"/api/organizations/{o}/roles/features",
        {"role_baseline": baseline},
    )
    # 3. Alpha's admin: group G, a policy for Recruiter, Bob in G.
    wadmin = "alpha-admin@example.com"
    scope = grammar.workspace(o, alpha)
    policy = api.post(
        wadmin,
        "/api/iam/admin/policies",
        {
            "name": "Recruiter for analysts",
            "scope": scope,
            "document": {
                "version": VERSION,
                "statements": [
                    {
                        "effect": "Allow",
                        "actions": ["module:UseAgent"],
                        "resources": [f"${{scope}}:module:agent/{RECRUITER}"],
                    }
                ],
            },
        },
    )
    group = api.post(wadmin, "/api/iam/admin/groups", {"name": "G", "scope": scope})
    api.post(
        wadmin,
        "/api/iam/admin/attachments",
        {"policy_id": policy["id"], "principal_id": group["id"], "scope": scope},
    )
    bob = principals(api)["bob@example.com"]
    api.put(wadmin, f"/api/iam/admin/groups/{group['id']}/members/{bob}")
    # 7. ``prices``: on in Alpha, turned off in Beta.
    module, app = PRICES
    app_id = f"remote/{module}:{app}"
    api.patch(ADMIN, f"/api/apps/{alpha}/{app_id}", {"enabled": True})
    api.patch(ADMIN, f"/api/apps/{beta}/{app_id}", {"enabled": False})
    return record_decisions(api, "Acme", database)


# -- this version: steps 2 to 7 ----------------------------------------------------------


@dataclass
class Report:
    checks: list[dict] = field(default_factory=list)

    def check(self, step: str, name: str, ok: bool, evidence: Any = None) -> bool:
        self.checks.append(
            {"step": step, "check": name, "ok": bool(ok), "evidence": evidence}
        )
        print(f"{'ok  ' if ok else 'FAIL'} {step}: {name}", flush=True)
        if not ok:
            print(f"     {json.dumps(evidence, default=str)[:800]}", flush=True)
        return ok


def refused(found: dict) -> bool:
    return found["status"] in (403, 404)


def same_refusal(rest: dict, nats: dict) -> bool:
    """IAM's refusal over REST is the one ``Recruiter`` reports over NATS, but
    the id of the policy each attempt was creating."""

    def plain(text: Any) -> str:
        return re.sub(r"pol_[0-9a-z]+", "pol_…", str(text))

    return bool(rest.get("detail")) and plain(rest["detail"]) in plain(
        nats.get("answer")
    )


def run(api: Api) -> dict[str, Any]:
    """Steps 2 to 7, each check with its evidence; a step that raises ends the
    run with what was checked so far."""
    grammar = grammar_of(api)
    if grammar.legacy:
        raise SystemExit("run is this version's scenario")
    report = Report()
    facts: dict[str, Any] = {}
    try:
        steps(api, grammar, report, facts)
    except Exception as exc:  # noqa: BLE001 - reported with what came before
        report.check("-", f"the run stopped: {type(exc).__name__}", False, str(exc))
    return {**facts, "checks": report.checks, "ok": all(c["ok"] for c in report.checks)}


def steps(api: Api, grammar: Grammar, report: Report, facts: dict[str, Any]) -> None:
    tag = uuid.uuid4().hex[:6]
    oadmin, wadmin = f"o-admin-{tag}@example.com", f"w-admin-{tag}@example.com"
    bob, mallory, carol = (
        f"{n}-{tag}@example.com" for n in ("bob", "mallory", "carol")
    )

    # -- 2. "O access", by the platform admin, attached to O's admins below O:
    #    ``${scope}`` is then O and each container in it, the workspaces where
    #    module scopes and features are named.
    org = api.post(
        ADMIN, "/api/organizations", {"name": f"O {tag}", "slug": f"o-{tag}"}
    )
    o = org["id"]
    facts.update(
        organization=o,
        people={
            "o_admin": oadmin,
            "w_admin": wadmin,
            "bob": bob,
            "mallory": mallory,
            "carol": carol,
        },
        policies={},
    )
    invite(api, o, oadmin, "admin")
    people = principals(api)
    below_o = grammar.below_org(o)
    o_access_doc = {
        "version": VERSION,
        "statements": [
            {
                "sid": "P",
                "effect": "Allow",
                "actions": ["module:UseAgent"],
                "resources": ["${scope}/module:agent/dev.people/*"],
            },
            {
                "sid": "M",
                "effect": "Allow",
                "actions": ["module:OpenApp"],
                "resources": ["${scope}/module:app/dev.market/*"],
            },
            {
                "sid": "Features",
                "effect": "Allow",
                "actions": ["nexus:UseFeature"],
                "resources": [
                    "${scope}/nexus:feature/chat",
                    "${scope}/nexus:feature/files",
                ],
            },
        ],
    }
    o_access = api.post(
        ADMIN,
        "/api/iam/admin/policies",
        {"name": "O access", "scope": grammar.platform(), "document": o_access_doc},
    )
    api.post(
        ADMIN,
        "/api/iam/admin/attachments",
        {"policy_id": o_access["id"], "principal_id": people[oadmin], "scope": below_o},
    )
    facts["policies"]["O access"] = o_access["id"]
    report.check(
        "2",
        'the platform admin creates "O access" and attaches it below O to O\'s admin',
        True,
        {"policy": o_access["id"], "scope": below_o},
    )

    # -- 3. The O admin creates W; uses P and M there at once.
    ws = api.post(
        oadmin,
        "/api/workspaces",
        {"name": f"W {tag}", "slug": f"w-{tag}", "organization_id": o},
    )
    w = ws["id"]
    facts["workspace"] = w
    w_scope = grammar.workspace(o, w)
    invite(api, o, wadmin, "member", workspace_id=w, workspace_role="admin")
    for email in (bob, mallory, carol):
        invite(api, o, email, "member", workspace_id=w, workspace_role="member")
    people = principals(api)
    api.post(oadmin, f"/api/agents/sync?workspace_id={w}")
    agents = agent_rows(api, oadmin, w)
    report.check(
        "3",
        "the O admin lists P's agents in W",
        {RECRUITER, SCOUT} <= set(agents),
        sorted(agents),
    )
    recruiter, scout = agents[RECRUITER]["id"], agents[SCOUT]["id"]
    for name, agent in (("A", recruiter), ("B", scout)):
        answer = chat(api, oadmin, w, agent, "hello")
        report.check(
            "3",
            f"the O admin uses agent {name} in W at once",
            answer["status"] == 200,
            answer,
        )
    report.check(
        "3", "the O admin opens M's app in W", open_app(api, oadmin, w)["status"] == 200
    )
    o_flags = flags(api, oadmin, w)
    report.check(
        "3",
        "the O admin has chat and files in W, nothing else",
        {k for k, v in o_flags.items() if v} == {"chat", "files"},
        o_flags,
    )

    seen = agent_rows(api, mallory, w)
    report.check("3", "a member with no policy lists no agent", not seen, sorted(seen))
    answers = {
        name: chat(api, mallory, w, agent, "hello")
        for name, agent in (("A", recruiter), ("B", scout))
    }
    report.check(
        "3",
        "a member with no policy uses no agent",
        all(refused(a) for a in answers.values()),
        answers,
    )
    app = open_app(api, mallory, w)
    report.check("3", "a member with no policy opens no app", refused(app), app)
    apps = api.get(mallory, "/api/apps/", workspace_id=w)["apps"]
    report.check(
        "3",
        "a member with no policy lists no module app",
        not [a for a in apps if a.get("module_name")],
        [a.get("app_id") for a in apps],
    )
    flows = api.attempt(mallory, "GET", f"/api/workspaces/{w}/workflows")
    report.check(
        "3",
        "a member with no policy lists no workflow",
        refused(flows) or not flows["body"].get("workflows"),
        flows,
    )
    m_flags = flags(api, mallory, w)
    report.check(
        "3",
        "a member with no policy has no feature",
        not any(m_flags.values()),
        m_flags,
    )

    # -- 4. "W analysts", a sub-policy of "O access", to group G at W, with Bob.
    analysts = api.post(
        oadmin,
        "/api/iam/admin/policies",
        {
            "name": "W analysts",
            "scope": w_scope,
            "parent": o_access["id"],
            "document": {
                "version": VERSION,
                "statements": [
                    {
                        "effect": "Allow",
                        "actions": ["module:UseAgent"],
                        "resources": [f"${{scope}}/module:agent/{RECRUITER}"],
                    },
                    {
                        "effect": "Allow",
                        "actions": ["nexus:UseFeature"],
                        "resources": ["${scope}/nexus:feature/chat"],
                    },
                ],
            },
        },
    )
    facts["policies"]["W analysts"] = analysts["id"]
    group = api.post(
        oadmin, "/api/iam/admin/groups", {"name": f"G {tag}", "scope": w_scope}
    )
    api.post(
        oadmin,
        "/api/iam/admin/attachments",
        {"policy_id": analysts["id"], "principal_id": group["id"], "scope": w_scope},
    )
    api.put(oadmin, f"/api/iam/admin/groups/{group['id']}/members/{people[bob]}")
    parent = api.get(ADMIN, f"/api/iam/admin/policies/{o_access['id']}")
    report.check(
        "4",
        '"O access" names "W analysts" as its sub-policy',
        analysts["id"] in [s["id"] for s in parent.get("sub_policies", [])],
        parent.get("sub_policies"),
    )
    seen = agent_rows(api, bob, w)
    report.check("4", "Bob lists A only", set(seen) == {RECRUITER}, sorted(seen))
    answer = chat(api, bob, w, recruiter, "hello")
    report.check("4", "Bob uses A", answer["status"] == 200, answer)
    answer = chat(api, bob, w, scout, "hello")
    report.check("4", "B is refused to Bob", refused(answer), answer)
    app = open_app(api, bob, w)
    report.check("4", "M's app is refused to Bob", refused(app), app)
    apps = api.get(bob, "/api/apps/", workspace_id=w)["apps"]
    report.check(
        "4",
        "M's app is not listed to Bob",
        not [a for a in apps if a.get("module_name")],
        [a.get("app_id") for a in apps],
    )
    b_flags = flags(api, bob, w)
    report.check(
        "4",
        "Bob has chat, not files",
        b_flags.get("chat") is True and not b_flags.get("files"),
        b_flags,
    )

    # -- 5. W's admin, not an admin of O: deriving, and granting what they lack.
    #    The platform admin lets them ask A (a sub-policy of "O access" at W: A
    #    and chat, which a chat needs), so they can ask Recruiter over NATS.
    ask_a = {
        "version": VERSION,
        "statements": [
            {
                "effect": "Allow",
                "actions": ["module:UseAgent"],
                "resources": [f"${{scope}}/module:agent/{RECRUITER}"],
            },
            {
                "effect": "Allow",
                "actions": ["nexus:UseFeature"],
                "resources": ["${scope}/nexus:feature/chat"],
            },
        ],
    }
    tools = api.post(
        ADMIN,
        "/api/iam/admin/policies",
        {
            "name": "W admin uses A",
            "scope": w_scope,
            "parent": o_access["id"],
            "document": ask_a,
        },
    )
    api.post(
        ADMIN,
        "/api/iam/admin/attachments",
        {"policy_id": tools["id"], "principal_id": people[wadmin], "scope": w_scope},
    )
    use_b = {
        "version": VERSION,
        "statements": [
            {
                "effect": "Allow",
                "actions": ["module:UseAgent"],
                "resources": [f"${{scope}}/module:agent/{SCOUT}"],
            }
        ],
    }
    use_a = {
        "version": VERSION,
        "statements": [
            {
                "effect": "Allow",
                "actions": ["module:UseAgent"],
                "resources": [f"${{scope}}/module:agent/{RECRUITER}"],
            }
        ],
    }
    derive_rest = api.attempt(
        wadmin,
        "POST",
        "/api/iam/admin/policies",
        {
            "name": "Derived",
            "scope": w_scope,
            "parent": o_access["id"],
            "document": use_a,
        },
    )
    grant_rest = api.attempt(
        wadmin,
        "POST",
        "/api/iam/admin/policies",
        {"name": "Use B", "scope": w_scope, "document": use_b},
    )
    derive_nats = chat(
        api,
        wadmin,
        w,
        recruiter,
        f"policy {w_scope} agent/{RECRUITER} under {o_access['id']}",
    )
    grant_nats = chat(api, wadmin, w, recruiter, f"policy {w_scope} agent/{SCOUT}")
    report.check(
        "5",
        'deriving from "O access" is refused over REST, naming it',
        derive_rest["status"] == 403 and o_access["id"] in str(derive_rest["detail"]),
        derive_rest,
    )
    report.check(
        "5",
        "granting B is refused over REST, naming it",
        grant_rest["status"] == 403 and SCOUT in str(grant_rest["detail"]),
        grant_rest,
    )
    report.check(
        "5",
        "deriving is refused over NATS, with the same error",
        same_refusal(derive_rest, derive_nats),
        derive_nats,
    )
    report.check(
        "5",
        "granting B is refused over NATS, with the same error",
        same_refusal(grant_rest, grant_nats),
        grant_nats,
    )

    # -- 6. The platform admin removes P from "O access".
    current = api.get(ADMIN, f"/api/iam/admin/policies/{o_access['id']}")
    narrowed = {
        "version": VERSION,
        "statements": [s for s in o_access_doc["statements"] if s["sid"] != "P"],
    }
    api.put(
        ADMIN,
        f"/api/iam/admin/policies/{o_access['id']}",
        {"expected_revision": current["revision"], "document": narrowed},
    )
    answer = chat(api, bob, w, recruiter, "hello")
    report.check("6", "Bob loses A at once", refused(answer), answer)
    seen = agent_rows(api, bob, w)
    report.check("6", "Bob lists no agent", not seen, sorted(seen))
    answers = {
        name: chat(api, oadmin, w, agent, "hello")
        for name, agent in (("A", recruiter), ("B", scout))
    }
    report.check(
        "6", "the O admin loses P", all(refused(a) for a in answers.values()), answers
    )
    report.check("6", "the O admin keeps M", open_app(api, oadmin, w)["status"] == 200)
    grants = {
        "A": simulate(
            api,
            people[bob],
            "module:UseAgent",
            grammar.inside(w_scope, f"module:agent/{RECRUITER}"),
        ),
        "chat": simulate(
            api,
            people[bob],
            "nexus:UseFeature",
            grammar.inside(w_scope, "nexus:feature/chat"),
        ),
    }
    b_flags = flags(api, bob, w)
    report.check(
        "6",
        '"W analysts" grants chat only',
        grants == {"A": False, "chat": True}
        and {k for k, v in b_flags.items() if v} == {"chat"},
        {"simulated": grants, "bob's flags": b_flags},
    )
    answer = chat(api, ADMIN, w, recruiter, "hello")
    report.check(
        "6", "the platform admin still reaches P", answer["status"] == 200, answer
    )

    # -- 7. A project of P in W, made through the SDK; a policy at the project.
    # A container's id is unique within its type: one project per run.
    p1 = f"p1-{tag}"
    answer = chat(api, ADMIN, w, recruiter, f"project {p1}")
    project = grammar.inside(w_scope, f"dev_people:project/{p1}")
    report.check(
        "7",
        "Recruiter registers project p1 in W through the SDK",
        answer["status"] == 200 and project in str(answer.get("answer")),
        answer,
    )
    listed = api.get(
        ADMIN,
        "/api/iam/admin/resources",
        scope=w_scope,
        service="dev_people",
        type="project",
    )
    report.check(
        "7",
        "W lists the project",
        project in [i["name"] for i in listed["items"]],
        listed["items"],
    )
    at_project = api.post(
        ADMIN,
        "/api/iam/admin/policies",
        {
            "name": "Project p1 reports",
            "scope": project,
            "document": {
                "version": VERSION,
                "statements": [
                    {
                        "effect": "Allow",
                        "actions": ["dev_people:GetProject"],
                        "resources": ["${scope}"],
                    },
                    {
                        "effect": "Allow",
                        "actions": ["dev_people:ExportReport"],
                        "resources": ["${scope}/dev_people:report/*"],
                    },
                ],
            },
        },
    )
    api.post(
        ADMIN,
        "/api/iam/admin/attachments",
        {
            "policy_id": at_project["id"],
            "principal_id": people[carol],
            "scope": project,
        },
    )
    reach = {
        "report in p1": simulate(
            api,
            people[carol],
            "dev_people:ExportReport",
            grammar.inside(project, "dev_people:report/q3"),
        ),
        "report in W": simulate(
            api,
            people[carol],
            "dev_people:ExportReport",
            grammar.inside(w_scope, "dev_people:report/q3"),
        ),
        "agent A in W": simulate(
            api,
            people[carol],
            "module:UseAgent",
            grammar.inside(w_scope, f"module:agent/{RECRUITER}"),
        ),
        "app of M in W": simulate(
            api,
            people[carol],
            "module:OpenApp",
            grammar.inside(w_scope, "module:app/dev.market/prices"),
        ),
        "chat in W": simulate(
            api,
            people[carol],
            "nexus:UseFeature",
            grammar.inside(w_scope, "nexus:feature/chat"),
        ),
    }
    report.check(
        "7",
        "Carol reaches what is in the project, nothing else of W",
        reach
        == {
            "report in p1": True,
            "report in W": False,
            "agent A in W": False,
            "app of M in W": False,
            "chat in W": False,
        },
        reach,
    )
    c_flags = flags(api, carol, w)
    report.check("7", "Carol has no feature in W", not any(c_flags.values()), c_flags)
    # Through the module: Carol needs A and chat to ask it (a policy of its own, at W).
    use = api.post(
        ADMIN,
        "/api/iam/admin/policies",
        {"name": "Carol uses A", "scope": w_scope, "document": ask_a},
    )
    api.post(
        ADMIN,
        "/api/iam/admin/attachments",
        {"policy_id": use["id"], "principal_id": people[carol], "scope": w_scope},
    )
    inside_p1 = chat(api, carol, w, recruiter, f"export q3 in {p1}")
    in_w = chat(api, carol, w, recruiter, "export q3")
    report.check(
        "7",
        "Recruiter exports q3 from p1 for Carol",
        f"exported from project {p1}" in str(inside_p1.get("answer")),
        inside_p1,
    )
    report.check(
        "7",
        "Recruiter refuses q3 in W itself to Carol",
        "refused" in str(in_w.get("answer")),
        in_w,
    )
    facts["policies"]["project"] = at_project["id"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("legacy", "decisions", "run"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--api", required=True)
        cmd.add_argument("--mail", required=True, type=Path)
        cmd.add_argument("--out", required=True, type=Path)
        if name == "decisions":
            cmd.add_argument("--organization", default="Acme")
        if name in ("legacy", "decisions"):
            # The previous version's Nexus database (storage/nexus.db): its toggles.
            cmd.add_argument("--database", required=name == "legacy", type=Path)
    cmd = sub.add_parser("compare")
    cmd.add_argument("before", type=Path)
    cmd.add_argument("after", type=Path)
    cmd.add_argument("--out", type=Path)
    args = parser.parse_args()

    started = time.monotonic()
    if args.command == "compare":
        result = compare(
            json.loads(args.before.read_text()), json.loads(args.after.read_text())
        )
        print(
            f"{result['compared']} decisions, {result['allowed_before']} allowed before, "
            f"{result['allowed_after']} after; {len(result['expected'])} expected changes, "
            f"{len(result['unexpected'])} unexpected, {len(result['missing_after'])} missing"
        )
        for row in result["unexpected"]:
            print(f"  changed: {row['key']} {row['before']} -> {row['after']}")
    else:
        api = Api(args.api.rstrip("/"), args.mail)
        if args.command == "legacy":
            result = legacy(api, args.database)
        elif args.command == "decisions":
            result = record_decisions(api, args.organization, args.database)
        else:
            result = run(api)
        print(f"{args.command}: {time.monotonic() - started:.0f}s")
    if getattr(args, "out", None):
        args.out.write_text(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
