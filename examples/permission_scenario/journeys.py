"""The user journeys of issue #1413, scripted with the issue's cast against a
running ``ENV=scenario abi dev up``: one or more checks per journey ID, each with
its evidence (the API's answers), and the issue's cross-cutting rules checked at
each layer (platform, organisation, workspace, member).

    python examples/permission_scenario/journeys.py --api URL --mail DIR --out journeys.json

The cast (``AGENTS.md``, "The #1413 journeys"): Root (the platform admin), Acme
with eight of ten features, ``dev.people`` (Recruiter, Scout, Onboarder, Coach,
app Directory), ``dev.market`` (Pricer, app Prices), Alpha and Bravo, Olivia,
Bob, Carol, Dave, Eve, Frank, Gina (an existing user, sub-case PE2 b), and Beta
Corp with Paul. Every name carries a tag, so the run may start again on the same
database.

Nexus has no Home, BaseMap or Workflows feature, and ``tasks`` is not enabled in
the repository's configuration: the run uses ``search`` for Home, ``graph`` for
BaseMap, ``documents`` for Tasks and ``datasets`` for Workflows (``FEATURE_OF``).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from runner import (
    ADMIN,
    VERSION,
    Api,
    Grammar,
    Refused,
    Report,
    agent_rows,
    chat,
    flags,
    principals,
    refused,
    simulate,
)

# The issue's ten features, as Nexus names them.
FEATURE_OF = {
    "Chat": "chat",
    "Files": "files",
    "Agents": "agents",
    "Apps": "apps",
    "Home": "search",
    "BaseMap": "graph",
    # ``tasks`` is not in this deployment's ``enabled_features``: it exists nowhere.
    "Tasks": "documents",
    "Settings": "settings",
    "Maps": "maps",
    "Workflows": "datasets",
}
ACME_FEATURES = [FEATURE_OF[f] for f in FEATURE_OF if f not in ("Maps", "Workflows")]
PEOPLE_AGENTS = ("Recruiter", "Scout", "Onboarder", "Coach")
AGENTS = {
    **{n: f"dev.people/{n}" for n in PEOPLE_AGENTS},
    "Pricer": "dev.market/Pricer",
}
APPS = {"Directory": ("dev.people", "directory"), "Prices": ("dev.market", "prices")}
# A route each feature gates (it answers 403 where the caller lacks the feature).
FEATURE_ROUTE = {
    "maps": "/api/maps/basemaps",
    "graph": "/api/view/list",
    "search": "/api/search/topics",
    "datasets": "/api/datasets/",
}
GRANT_NOT_HELD = "You cannot grant what you do not hold"
# What IAM answers a sub-policy naming what its chain allows nowhere (422).
OUTSIDE_PARENT = "it would grant nothing"


def refused_naming(found: dict, *names: str) -> bool:
    """Refused (403: not held; 422: outside the parent), the answer naming each."""
    return found["status"] in (403, 422) and all(
        n in str(found.get("detail")) for n in names
    )


# -- documents -------------------------------------------------------------------------


def statement(
    sid: str, actions: list[str], resources: list[str], effect: str = "Allow"
) -> dict:
    return {"sid": sid, "effect": effect, "actions": actions, "resources": resources}


def access_document(
    *,
    agents: list[str],
    apps: list[str],
    features: list[str],
    export: bool = True,
    deny: list[dict] | None = None,
) -> dict:
    """What a container's access (or a member policy) allows, one statement a type,
    as the policy builder writes it."""
    statements = []
    if agents:
        statements.append(
            statement(
                "Agents",
                ["module:UseAgent"],
                [
                    f"${{scope}}/module:agent/{AGENTS[a]}" if a in AGENTS else a
                    for a in agents
                ],
            )
        )
    if apps:
        statements.append(
            statement(
                "Apps",
                ["module:OpenApp"],
                [f"${{scope}}/module:app/{'/'.join(APPS[a])}" for a in apps],
            )
        )
    if export:
        statements.append(
            statement(
                "Reports", ["dev_people:ExportReport"], ["${scope}/dev_people:report/*"]
            )
        )
    if features:
        statements.append(
            statement(
                "Features",
                ["nexus:UseFeature"],
                [f"${{scope}}/nexus:feature/{f}" for f in features],
            )
        )
    statements += deny or []
    return {"version": VERSION, "statements": statements}


# -- the API, as each person ---------------------------------------------------------------


def policies_at(api: Api, email: str, scope: str) -> list[dict]:
    page = api.get(email, "/api/iam/admin/policies", scope=scope)
    return list(page.get("items", page) if isinstance(page, dict) else page)


def access_policy(api: Api, scope: str, owner: str, name: str) -> dict:
    """The access policy named ``name`` owned by ``owner``, as Root lists it."""
    for policy in policies_at(api, ADMIN, scope):
        if policy["name"] == name and policy["owner_scope"] == owner:
            return policy
    raise SystemExit(f"no policy {name!r} owned by {owner}")


def put_document(api: Api, email: str, policy_id: str, document: dict) -> dict:
    """Replace a policy's document as ``email``: ``{"status", "body"|"detail"}``."""
    current = api.get(ADMIN, f"/api/iam/admin/policies/{policy_id}")
    return api.attempt(
        email,
        "PUT",
        f"/api/iam/admin/policies/{policy_id}",
        {"document": document, "expected_revision": current["revision"]},
    )


def invite_to_org(
    api: Api, by: str, org: str, email: str, role: str, **extra: Any
) -> dict:
    found = api.attempt(
        by,
        "POST",
        f"/api/organizations/{org}/members/invite",
        {
            "email": email,
            "role": role,
            "name": email.split("@")[0].split("-")[0].title(),
            **extra,
        },
    )
    if found["status"] != 200 and "already" not in str(found.get("detail")).lower():
        raise Refused(found["status"], found.get("detail"))
    api.session(email)  # they sign in: their first sign-in links their IAM user
    return found


def invite_to_workspace(
    api: Api, by: str, ws: str, email: str, role: str, **extra: Any
) -> dict:
    found = api.attempt(
        by,
        "POST",
        f"/api/workspaces/{ws}/members/invite",
        {
            "email": email,
            "role": role,
            "name": email.split("@")[0].split("-")[0].title(),
            **extra,
        },
    )
    if found["status"] != 200 and "already" not in str(found.get("detail")).lower():
        raise Refused(found["status"], found.get("detail"))
    api.session(email)
    return found


def iam_actions(api: Api, email: str, scope: str | None = None) -> list[str]:
    """The ``iam:`` actions ``GET /access`` says ``email`` holds (the settings pages
    show Roles & permissions on any of them)."""
    found = api.attempt(
        email, "GET", "/api/iam/admin/access" + (f"?scope={_q(scope)}" if scope else "")
    )
    if found["status"] != 200:
        return []
    actions = found["body"].get("actions", {})
    return sorted(a for a, ok in actions.items() if ok and a.startswith("iam:"))


def _q(value: str) -> str:
    from urllib.parse import quote

    return quote(value, safe="")


def module_apps(api: Api, email: str, ws: str) -> set[str]:
    found = api.attempt(email, "GET", f"/api/apps/?workspace_id={ws}")
    if found["status"] != 200:
        return set()
    return {
        # A remote module's app is ``remote/<module>:<app>``.
        f"{a.get('module_name')}/{str(a.get('app_id')).rsplit(':', 1)[-1]}"
        for a in found["body"].get("apps", [])
        if a.get("module_name")
    }


def open_app(api: Api, email: str, ws: str, app: str) -> dict:
    module, name = APPS[app]
    return api.attempt(
        email,
        "POST",
        "/api/apps/remote-grant",
        {"workspace_id": ws, "module_id": module, "app": name},
    )


def feature_route(api: Api, email: str, ws: str, feature: str) -> dict:
    return api.attempt(email, "GET", f"{FEATURE_ROUTE[feature]}?workspace_id={ws}")


def agent_ids(api: Api, ws: str) -> dict[str, str]:
    """``{agent name: row id}`` of the cast's agents in ``ws``, as Root lists them
    after a sync (the chat route takes a row id)."""
    api.post(ADMIN, f"/api/agents/sync?workspace_id={ws}")
    rows = agent_rows(api, ADMIN, ws)
    return {name: rows[key]["id"] for name, key in AGENTS.items() if key in rows}


def talk(
    api: Api, email: str, ws: str, ids: dict[str, str], agent: str, message: str
) -> dict:
    """``email`` asks ``agent`` (by name) in ``ws``: ``{"status", "answer"|"detail"}``."""
    if agent not in ids:
        return {"status": 404, "detail": f"{agent} has no row in {ws}"}
    return chat(api, email, ws, ids[agent], message)


def agents_seen(api: Api, email: str, ws: str) -> set[str]:
    """The cast's agents ``email`` lists in ``ws``, by name."""
    found = api.attempt(email, "GET", f"/api/agents/?workspace_id={ws}")
    if found["status"] != 200:
        return set()
    names = {str(r.get("class_name")) for r in found["body"] if r.get("class_name")}
    return {name for name, key in AGENTS.items() if key in names}


def member_ids(api: Api, group_id: str) -> set[str]:
    found = api.get(ADMIN, f"/api/iam/admin/groups/{group_id}")
    return {m["id"] for m in found.get("members", [])}


def on(found: dict[str, bool]) -> set[str]:
    return {k for k, v in found.items() if v}


def plain(text: Any) -> str:
    return re.sub(r"pol_[0-9a-z]+", "pol_…", str(text))


# -- decisions, for "reduction never widens" -------------------------------------------------


def decisions(
    api: Api,
    grammar: Grammar,
    org: str,
    people: dict[str, str],
    workspaces: dict[str, str],
) -> dict[str, bool]:
    """``person|workspace|item -> allowed`` for every agent, app and feature of the
    cast, asked of IAM's simulator as Root."""
    ids = principals(api)
    found: dict[str, bool] = {}
    for who, email in people.items():
        principal = ids.get(email.lower())
        if principal is None:
            continue
        for place, ws in workspaces.items():
            scope = grammar.workspace(org, ws)
            for name, key in AGENTS.items():
                resource = f"{scope}/module:agent/{key}"
                found[f"{who}|{place}|agent {name}"] = simulate(
                    api, principal, "module:UseAgent", resource
                )
            for name, (module, app) in APPS.items():
                resource = f"{scope}/module:app/{module}/{app}"
                found[f"{who}|{place}|app {name}"] = simulate(
                    api, principal, "module:OpenApp", resource
                )
            for label, feature in FEATURE_OF.items():
                resource = f"{scope}/nexus:feature/{feature}"
                found[f"{who}|{place}|feature {label}"] = simulate(
                    api, principal, "nexus:UseFeature", resource
                )
    return found


def widened(before: dict[str, bool], after: dict[str, bool]) -> list[str]:
    return sorted(k for k, v in after.items() if v and not before.get(k, False))


def narrowed(before: dict[str, bool], after: dict[str, bool]) -> list[str]:
    return sorted(k for k, v in before.items() if v and not after.get(k, False))


# -- the journeys ----------------------------------------------------------------------------


def run(api: Api) -> dict[str, Any]:
    report = Report()
    facts: dict[str, Any] = {"feature_of": FEATURE_OF}
    try:
        journeys(api, Grammar(legacy=False), report, facts)
    except Exception as exc:  # noqa: BLE001 - reported with what came before
        report.check("-", f"the run stopped: {type(exc).__name__}", False, str(exc))
    by_journey: dict[str, bool] = {}
    for check in report.checks:
        for journey in check["step"].split(","):
            by_journey[journey] = by_journey.get(journey, True) and check["ok"]
    return {
        **facts,
        "journeys": by_journey,
        "checks": report.checks,
        "ok": all(c["ok"] for c in report.checks),
    }


def journeys(api: Api, grammar: Grammar, report: Report, facts: dict[str, Any]) -> None:
    tag = uuid.uuid4().hex[:6]
    email = {
        n: f"{n}-{tag}@example.com"
        for n in ("olivia", "bob", "carol", "dave", "eve", "frank", "gina", "paul")
    }
    root = ADMIN
    check = report.check
    facts.update(tag=tag, people=email)

    # -- P1 (create, rename), P4 (an org admin): Beta Corp with Paul ---------------------------
    beta = api.post(
        root, "/api/organizations", {"name": f"Beta Corp {tag}", "slug": f"beta-{tag}"}
    )
    renamed = api.patch(
        root, f"/api/organizations/{beta['id']}", {"name": f"Beta Corporation {tag}"}
    )
    check(
        "UJ-P1",
        "Root creates Beta Corp and renames it Beta Corporation",
        renamed["name"] == f"Beta Corporation {tag}",
        {"id": beta["id"], "name": renamed["name"]},
    )
    invite_to_org(api, root, beta["id"], email["paul"], "admin")
    beta_role = api.get(email["paul"], f"/api/organizations/{beta['id']}").get(
        "current_user_role"
    )
    check(
        "UJ-P1,UJ-P4",
        "Root assigns Paul as Beta's org admin",
        beta_role == "admin",
        beta_role,
    )

    # -- P2, P3: Acme, eight of ten features, dev.people's agents, both apps --------------------
    acme_row = api.post(
        root, "/api/organizations", {"name": f"Acme {tag}", "slug": f"acme-{tag}"}
    )
    acme = acme_row["id"]
    acme_scope = grammar.org(acme)
    acme_access = access_policy(
        api, grammar.platform(), grammar.platform(), f"Acme {tag} access"
    )
    facts["acme"] = {"id": acme, "access_policy": acme_access["id"]}
    check(
        "UJ-P2",
        'a new organization comes with "<O> access", the platform\'s, allowing nothing',
        [s.get("sid") for s in acme_access["document"]["statements"]] == ["Nothing"],
        acme_access["document"],
    )
    acme_doc = access_document(
        agents=["${scope}/module:agent/dev.people/*"],
        apps=["Directory", "Prices"],
        features=ACME_FEATURES,
    )
    put = put_document(api, root, acme_access["id"], acme_doc)
    check(
        "UJ-P2,UJ-P3",
        "Root grants Acme 8 features, dev.people's agents only, Directory and Prices",
        put["status"] == 200,
        {"status": put["status"], "document": acme_doc},
    )

    # -- P4: Olivia, Acme's org admin, created by Root; no rights on Beta ------------------------
    invite_to_org(api, root, acme, email["olivia"], "admin")
    olivia = email["olivia"]
    orgs = {o["id"] for o in api.get(olivia, "/api/organizations")}
    beta_get = api.attempt(olivia, "GET", f"/api/organizations/{beta['id']}")
    check(
        "UJ-P4",
        "Root makes Olivia org admin of Acme; she has no rights on Beta Corporation",
        acme in orgs
        and beta["id"] not in orgs
        and refused(beta_get)
        and not iam_actions(api, olivia, grammar.org(beta["id"])),
        {"orgs": sorted(orgs), "beta": beta_get},
    )

    # -- O3: Olivia creates Alpha and Bravo -------------------------------------------------------
    alpha = api.post(
        olivia,
        "/api/workspaces",
        {"name": f"Alpha {tag}", "slug": f"alpha-{tag}", "organization_id": acme},
    )["id"]
    bravo = api.post(
        olivia,
        "/api/workspaces",
        {"name": f"Bravo {tag}", "slug": f"bravo-{tag}", "organization_id": acme},
    )["id"]
    alpha_scope, bravo_scope = (
        grammar.workspace(acme, alpha),
        grammar.workspace(acme, bravo),
    )
    places = {"Alpha": alpha, "Bravo": bravo}
    alpha_access = access_policy(api, alpha_scope, alpha_scope, f"Alpha {tag} access")
    bravo_access = access_policy(api, bravo_scope, bravo_scope, f"Bravo {tag} access")
    facts.update(
        alpha=alpha,
        bravo=bravo,
        policies={
            "Acme access": acme_access["id"],
            "Alpha access": alpha_access["id"],
            "Bravo access": bravo_access["id"],
        },
    )
    check(
        "UJ-O3",
        'each new workspace comes with "<W> access", its own, a sub-policy of Acme\'s',
        alpha_access["parent_id"] == bravo_access["parent_id"] == acme_access["id"],
        {"alpha": alpha_access["parent_id"], "bravo": bravo_access["parent_id"]},
    )
    entitled = access_document(
        agents=list(PEOPLE_AGENTS), apps=["Directory", "Prices"], features=ACME_FEATURES
    )
    set_alpha = put_document(api, olivia, alpha_access["id"], entitled)
    bravo_doc = access_document(
        agents=[], apps=["Prices"], features=["chat", "apps"], export=False
    )
    set_bravo = put_document(api, olivia, bravo_access["id"], bravo_doc)
    check(
        "UJ-O3",
        "Olivia gives Alpha the four dev.people agents and both apps, Bravo Prices only",
        set_alpha["status"] == set_bravo["status"] == 200,
        {"alpha": set_alpha["status"], "bravo": set_bravo["status"]},
    )
    pricer = put_document(
        api,
        olivia,
        bravo_access["id"],
        access_document(
            agents=["Pricer"], apps=["Prices"], features=["chat", "apps"], export=False
        ),
    )
    check(
        "UJ-O3",
        "Olivia cannot attach Pricer to Bravo: refused, naming it",
        refused_naming(pricer, "dev.market/Pricer"),
        pricer,
    )
    api.post(olivia, f"/api/agents/sync?workspace_id={alpha}")
    api.post(olivia, f"/api/agents/sync?workspace_id={bravo}")
    alpha_ids = agent_ids(api, alpha)

    # -- O2: Olivia within the platform's grant -------------------------------------------------
    maps_acme = put_document(
        api,
        olivia,
        acme_access["id"],
        {
            **acme_doc,
            "statements": [
                *acme_doc["statements"],
                statement(
                    "Maps", ["nexus:UseFeature"], ["${scope}/nexus:feature/maps"]
                ),
            ],
        },
    )
    maps_alpha = put_document(
        api,
        olivia,
        alpha_access["id"],
        access_document(
            agents=list(PEOPLE_AGENTS),
            apps=["Directory", "Prices"],
            features=[*ACME_FEATURES, "maps"],
        ),
    )
    tasks_bravo = put_document(
        api,
        olivia,
        bravo_access["id"],
        access_document(
            agents=[],
            apps=["Prices"],
            features=["chat", "apps", FEATURE_OF["Tasks"]],
            export=False,
        ),
    )
    check(
        "UJ-O2",
        "Olivia cannot enable Maps for Acme (its access is the platform's)",
        refused(maps_acme),
        maps_acme,
    )
    check(
        "UJ-O2",
        "Olivia cannot enable Maps in Alpha: refused, naming maps",
        refused_naming(maps_alpha, "nexus:feature/maps"),
        maps_alpha,
    )
    check(
        "UJ-O2",
        "Olivia can enable Tasks (in the platform's eight) in Bravo",
        tasks_bravo["status"] == 200,
        tasks_bravo["status"],
    )

    # -- P2, P3 as Olivia sees them (platform layer of the cross-cutting rules) --------------------
    olivia_flags = flags(api, olivia, alpha)
    maps_route = feature_route(api, olivia, alpha, "maps")
    datasets_route = feature_route(api, olivia, alpha, "datasets")
    check(
        "UJ-P2",
        "Olivia has the eight features in Alpha, never Maps or Workflows",
        on(olivia_flags) == set(ACME_FEATURES),
        olivia_flags,
    )
    check(
        "UJ-P2,rule:feature-off-absent:platform",
        "the API refuses Maps and Workflows to Olivia (403/404), never an empty answer",
        refused(maps_route) and refused(datasets_route),
        {"maps": maps_route, "datasets": datasets_route},
    )
    seen = agents_seen(api, olivia, alpha)
    pricer_chat = talk(api, olivia, alpha, alpha_ids, "Pricer", "hello")
    check(
        "UJ-P3,rule:visibility-iam:platform",
        "Pricer never appears for Acme: not listed, refused in the API",
        "Pricer" not in seen and set(PEOPLE_AGENTS) <= seen and refused(pricer_chat),
        {"seen": sorted(seen), "chat": pricer_chat},
    )

    # -- O4, O5: roles; Eve and Frank ------------------------------------------------------------
    invite_to_org(
        api,
        olivia,
        acme,
        email["bob"],
        "member",
        workspace_id=alpha,
        workspace_role="member",
    )
    invite_to_org(
        api,
        olivia,
        acme,
        email["carol"],
        "member",
        workspace_id=alpha,
        workspace_role="admin",
    )
    invite_to_org(api, olivia, acme, email["eve"], "member")
    # Olivia created Alpha, so she owns it: an owner makes owners (an org admin's
    # role below the organization does not).
    made_owner = api.attempt(
        olivia,
        "PATCH",
        f"/api/workspaces/{alpha}/members/{principals(api)[email['bob']]}",
        {"role": "owner"},
    )
    invite_to_org(
        api,
        olivia,
        acme,
        email["frank"],
        "member",  # an org role is owner, admin or member: read-only is his Alpha role
        workspace_id=alpha,
        workspace_role="viewer",
    )
    invite_to_org(
        api,
        olivia,
        acme,
        email["gina"],
        "member",
        workspace_id=bravo,
        workspace_role="member",
    )
    ids = principals(api)
    members = {
        m.get("email", "").lower(): m.get("role")
        for m in api.get(olivia, f"/api/workspaces/{alpha}/members")
    }
    check(
        "UJ-O4",
        "Olivia makes Bob owner and Carol admin of Alpha",
        members.get(email["bob"]) == "owner" and members.get(email["carol"]) == "admin",
        {"members": members, "owner change": made_owner["status"]},
    )
    groups = {
        g["name"]: g
        for g in api.get(root, "/api/iam/admin/groups", scope=alpha_scope).get(
            "items", []
        )
        if g.get("owner_scope") == alpha_scope
    }
    alpha_admins = groups.get(f"Alpha {tag} admins", {})
    admins_members = member_ids(api, alpha_admins["id"]) if alpha_admins else set()
    check(
        "UJ-O4",
        '"Alpha admins" follows the roles: Olivia (its creator), Bob and Carol',
        {ids[olivia], ids[email["bob"]], ids[email["carol"]]} <= admins_members
        and ids[email["frank"]] not in admins_members,
        {"groups": sorted(groups), "admins": sorted(admins_members)},
    )
    # Olivia lets Bob manage within Acme's grant in Alpha (show again what Alpha hides).
    api.post(
        olivia,
        "/api/iam/admin/attachments",
        {
            "policy_id": acme_access["id"],
            "principal_id": ids[email["bob"]],
            "scope": alpha_scope,
        },
    )
    frank_before = (
        agents_seen(api, email["frank"], alpha),
        module_apps(api, email["frank"], alpha),
    )
    check(
        "UJ-O5",
        "Frank (org-wide read-only) sees no agent or app in Alpha",
        frank_before == (set(), set()),
        [sorted(s) for s in frank_before],
    )

    # -- O1: Organization settings -------------------------------------------------------------
    org_view = {
        who: (
            iam_actions(api, email[who], acme_scope),
            api.attempt(email[who], "GET", f"/api/organizations/{acme}/members")[
                "status"
            ],
        )
        for who in ("olivia", "eve", "bob")
    }
    check(
        "UJ-O1",
        "Olivia may open Organization settings; Eve and Bob may not (API)",
        bool(org_view["olivia"][0])
        and org_view["olivia"][1] == 200
        and all(not org_view[w][0] and org_view[w][1] == 403 for w in ("eve", "bob")),
        org_view,
    )

    # -- PE1: Carol, the analyst ----------------------------------------------------------------
    bob = email["bob"]
    analysts = api.post(
        bob,
        "/api/iam/admin/policies",
        {
            "name": "Alpha analysts",
            "scope": alpha_scope,
            "parent": alpha_access["id"],
            "document": access_document(
                agents=["${scope}/module:agent/dev.people/*"],
                apps=["Directory", "Prices"],
                features=ACME_FEATURES,
            ),
        },
    )
    analysts_group = api.post(
        bob, "/api/iam/admin/groups", {"name": "Alpha analysts", "scope": alpha_scope}
    )
    api.post(
        bob,
        "/api/iam/admin/attachments",
        {
            "policy_id": analysts["id"],
            "principal_id": analysts_group["id"],
            "scope": alpha_scope,
        },
    )
    api.put(
        bob,
        f"/api/iam/admin/groups/{analysts_group['id']}/members/{ids[email['carol']]}",
    )
    carol = email["carol"]
    carol_view = {
        "agents": sorted(agents_seen(api, carol, alpha)),
        "apps": sorted(module_apps(api, carol, alpha)),
        "flags": sorted(on(flags(api, carol, alpha))),
    }
    check(
        "UJ-PE1",
        "Carol has Home and BaseMap, the agents and both apps Alpha exposes",
        {"search", "graph"} <= set(carol_view["flags"])
        and set(PEOPLE_AGENTS) <= set(carol_view["agents"])
        and set(carol_view["apps"]) == {"dev.people/directory", "dev.market/prices"},
        carol_view,
    )
    check(
        "UJ-PE1",
        "Carol sees no Platform or Organization roles and permissions",
        not iam_actions(api, carol) and not iam_actions(api, carol, acme_scope),
        {
            "platform": iam_actions(api, carol),
            "org": iam_actions(api, carol, acme_scope),
        },
    )

    # -- W1: Workspace settings -----------------------------------------------------------------
    settings = {
        who: iam_actions(api, email[who], alpha_scope) for who in ("bob", "carol")
    }
    check(
        "UJ-W1",
        "Bob and Carol may open Alpha's settings (Roles & permissions there)",
        all(
            "iam:ListPolicies" in a and "iam:CreatePolicy" in a
            for a in settings.values()
        ),
        settings,
    )

    # -- PE2: Bob invites Dave with "Alpha minimal" (a), Carol adds Gina (b, PE3) ------------------
    minimal_doc = access_document(
        agents=["Recruiter"],
        apps=["Prices"],
        # Recruiter is used in a chat: the chat feature comes with it.
        features=["chat", "search"],
        deny=[
            statement(
                "NoBaseMap",
                ["nexus:UseFeature"],
                ["${scope}/nexus:feature/graph"],
                effect="Deny",
            )
        ],
    )
    minimal = api.post(
        bob,
        "/api/iam/admin/policies",
        {
            "name": "Alpha minimal",
            "scope": alpha_scope,
            "parent": alpha_access["id"],
            "document": minimal_doc,
        },
    )
    minimal_group = api.post(
        bob, "/api/iam/admin/groups", {"name": "Alpha minimal", "scope": alpha_scope}
    )
    api.post(
        bob,
        "/api/iam/admin/attachments",
        {
            "policy_id": minimal["id"],
            "principal_id": minimal_group["id"],
            "scope": alpha_scope,
        },
    )
    dave = email["dave"]
    invite_to_workspace(api, bob, alpha, dave, "member")
    ids = principals(api)
    api.put(bob, f"/api/iam/admin/groups/{minimal_group['id']}/members/{ids[dave]}")
    facts["policies"].update(
        {"Alpha analysts": analysts["id"], "Alpha minimal": minimal["id"]}
    )
    dave_view = {
        "agents": sorted(agents_seen(api, dave, alpha)),
        "apps": sorted(module_apps(api, dave, alpha)),
        "flags": sorted(on(flags(api, dave, alpha))),
    }
    check(
        "UJ-PE2",
        '(a) Dave, new, invited by Bob, through group "Alpha minimal": Recruiter, Prices, Home; no BaseMap',
        dave_view
        == {
            "agents": ["Recruiter"],
            "apps": ["dev.market/prices"],
            "flags": ["chat", "search"],
        },
        dave_view,
    )

    # PE3: Carol opens Alpha's settings and runs PE2 for Gina, who already exists (Bravo).
    gina = email["gina"]
    gina_before = principals(api)[gina]
    invite_to_workspace(api, carol, alpha, gina, "member")
    api.put(carol, f"/api/iam/admin/groups/{minimal_group['id']}/members/{gina_before}")
    gina_after = [p for e, p in principals(api).items() if e == gina]
    gina_view = {
        "agents": sorted(agents_seen(api, gina, alpha)),
        "apps": sorted(module_apps(api, gina, alpha)),
        "flags": sorted(on(flags(api, gina, alpha))),
    }
    check(
        "UJ-PE2,UJ-PE3",
        "(b) Carol adds Gina, an existing user: same identity, same result as Dave",
        gina_after == [gina_before] and gina_view == dave_view,
        {"principal": gina_after, "view": gina_view},
    )

    # -- W3: Bob exposes Recruiter and Scout only ---------------------------------------------
    exposed = access_document(
        agents=["Recruiter", "Scout"],
        apps=["Directory", "Prices"],
        features=ACME_FEATURES,
    )
    before_w3 = decisions(api, grammar, acme, email, places)
    narrowed_alpha = put_document(api, bob, alpha_access["id"], exposed)
    after_w3 = decisions(api, grammar, acme, email, places)
    facts["w3"] = {"narrowed": narrowed(before_w3, after_w3)}
    seen = {
        who: sorted(agents_seen(api, email[who], alpha))
        for who in ("bob", "carol", "dave")
    }
    hidden = {
        who: {
            a: talk(api, email[who], alpha, alpha_ids, a, "hello")["status"]
            for a in ("Onboarder", "Coach")
        }
        for who in ("carol", "dave")
    }
    check(
        "UJ-W3",
        "Bob narrows Alpha's access to Recruiter and Scout",
        narrowed_alpha["status"] == 200,
        narrowed_alpha["status"],
    )
    check(
        "UJ-W3,rule:visibility-iam:workspace",
        "Carol lists Recruiter and Scout, Dave Recruiter; neither lists nor uses Onboarder or Coach",
        seen["carol"] == ["Recruiter", "Scout"]
        and seen["dave"] == ["Recruiter"]
        and all(s in (403, 404) for h in hidden.values() for s in h.values()),
        {"seen": seen, "chat": hidden},
    )
    check(
        "UJ-W3",
        "Bob, who holds Acme's grant in Alpha, still sees the four (he may expose them again)",
        seen["bob"] == sorted(PEOPLE_AGENTS),
        seen["bob"],
    )
    check(
        "rule:reduction-never-widens:workspace",
        "narrowing Alpha widens nobody",
        not widened(before_w3, after_w3),
        {"widened": widened(before_w3, after_w3), "narrowed": facts["w3"]["narrowed"]},
    )

    # -- W2: within the organization's grant ----------------------------------------------------
    w2_maps = put_document(
        api,
        bob,
        alpha_access["id"],
        {
            **exposed,
            "statements": [
                *exposed["statements"],
                statement(
                    "Maps", ["nexus:UseFeature"], ["${scope}/nexus:feature/maps"]
                ),
            ],
        },
    )
    check(
        "UJ-W2,rule:parent-bounds-child:workspace",
        "Bob cannot enable Maps on Alpha: refused, naming maps",
        refused_naming(w2_maps, "nexus:feature/maps"),
        w2_maps,
    )

    # -- W4: Bob hides BaseMap, then shows it again ---------------------------------------------
    no_basemap = access_document(
        agents=["Recruiter", "Scout"],
        apps=["Directory", "Prices"],
        features=[f for f in ACME_FEATURES if f != "graph"],
    )
    hide = put_document(api, bob, alpha_access["id"], no_basemap)
    hidden_view = {
        who: (
            FEATURE_OF["BaseMap"] in on(flags(api, email[who], alpha)),
            feature_route(api, email[who], alpha, "graph")["status"],
        )
        for who in ("carol", "dave")
    }
    show = put_document(api, bob, alpha_access["id"], exposed)
    shown_view = {
        who: (
            FEATURE_OF["BaseMap"] in on(flags(api, email[who], alpha)),
            feature_route(api, email[who], alpha, "graph")["status"],
        )
        for who in ("carol", "dave")
    }
    check(
        "UJ-W4,rule:feature-off-absent:workspace",
        "Bob hides BaseMap: Carol loses it (flag and API 403)",
        hide["status"] == 200
        and hidden_view["carol"][0] is False
        and hidden_view["carol"][1] in (403, 404),
        {"hide": hide["status"], "view": hidden_view},
    )
    check(
        "UJ-W4",
        "Bob shows BaseMap again: Carol has it back; Dave never has it",
        show["status"] == 200
        and shown_view["carol"] == (True, 200)
        and hidden_view["dave"][0] is False
        and shown_view["dave"][0] is False
        and shown_view["dave"][1] in (403, 404),
        {"show": show["status"], "view": shown_view},
    )
    maps_alpha_route = {
        who: feature_route(api, email[who], alpha, "maps")["status"]
        for who in ("bob", "carol", "dave")
    }
    check(
        "UJ-W4",
        "Maps is never available on Alpha",
        all(s in (403, 404) for s in maps_alpha_route.values()),
        maps_alpha_route,
    )

    # -- W5: Dave, minimally scoped -----------------------------------------------------------
    w5 = {
        "agents": sorted(agents_seen(api, dave, alpha)),
        "apps": sorted(module_apps(api, dave, alpha)),
        "flags": sorted(on(flags(api, dave, alpha))),
        "open Directory": open_app(api, dave, alpha, "Directory")["status"],
        "open Prices": open_app(api, dave, alpha, "Prices")["status"],
        "chat Scout": talk(api, dave, alpha, alpha_ids, "Scout", "hello")["status"],
        "chat Recruiter": talk(api, dave, alpha, alpha_ids, "Recruiter", "hello")[
            "status"
        ],
        "graph": feature_route(api, dave, alpha, "graph")["status"],
        "settings": iam_actions(api, dave, alpha_scope),
        "policies": api.attempt(
            dave, "GET", f"/api/iam/admin/policies?scope={_q(alpha_scope)}"
        )["status"],
        "invite": api.attempt(
            dave,
            "POST",
            f"/api/workspaces/{alpha}/members/invite",
            {"email": f"x-{tag}@example.com", "role": "member"},
        )["status"],
    }
    check(
        "UJ-W5,rule:visibility-iam:member",
        "Dave lists and uses Recruiter, Prices and Home only; the rest is refused, never listed",
        w5["agents"] == ["Recruiter"]
        and w5["apps"] == ["dev.market/prices"]
        and w5["flags"] == ["chat", "search"]
        and w5["open Prices"] == 200
        and w5["chat Recruiter"] == 200
        and all(w5[k] in (403, 404) for k in ("open Directory", "chat Scout", "graph")),
        w5,
    )
    check(
        "UJ-W1",
        "Dave sees no settings and the settings API refuses him",
        not w5["settings"] and w5["policies"] == 403 and w5["invite"] == 403,
        {k: w5[k] for k in ("settings", "policies", "invite")},
    )

    # -- O5: Bob attaches an Alpha policy to Frank -----------------------------------------------
    api.put(
        bob,
        f"/api/iam/admin/groups/{minimal_group['id']}/members/{ids[email['frank']]}",
    )
    frank_after = (
        sorted(agents_seen(api, email["frank"], alpha)),
        sorted(module_apps(api, email["frank"], alpha)),
    )
    check(
        "UJ-O5",
        'once Bob gives Frank "Alpha minimal", Frank sees Recruiter and Prices',
        frank_after == (["Recruiter"], ["dev.market/prices"]),
        frank_after,
    )

    # -- A1: Bob removes ExportReport from Recruiter's reach in Alpha ----------------------------
    exported = talk(api, dave, alpha, alpha_ids, "Recruiter", "export q3")
    before_a1 = decisions(api, grammar, acme, email, places)
    no_export = access_document(
        agents=["Recruiter", "Scout"],
        apps=["Directory", "Prices"],
        features=ACME_FEATURES,
        export=False,
    )
    removed = put_document(api, bob, alpha_access["id"], no_export)
    after_a1 = decisions(api, grammar, acme, email, places)
    refused_export = talk(api, dave, alpha, alpha_ids, "Recruiter", "export q3")
    still_chats = talk(api, dave, alpha, alpha_ids, "Recruiter", "hello")
    check(
        "UJ-A1",
        "Dave exports with Recruiter; once Bob removes ExportReport, export is refused and chat goes on",
        "exported" in str(exported.get("answer"))
        and removed["status"] == 200
        and "refused" in str(refused_export.get("answer"))
        and still_chats["status"] == 200,
        {"before": exported, "after": refused_export, "chat": still_chats},
    )
    beyond = put_document(
        api,
        bob,
        alpha_access["id"],
        {
            **no_export,
            "statements": [
                *no_export["statements"],
                statement(
                    "Delete",
                    ["dev_people:DeleteProject"],
                    ["${scope}/dev_people:project/*"],
                ),
            ],
        },
    )
    check(
        "UJ-A1,rule:parent-bounds-child:member",
        "Bob cannot add an action Acme's policy does not allow (DeleteProject)",
        refused_naming(beyond, "dev_people:DeleteProject"),
        beyond,
    )
    check(
        "rule:reduction-never-widens:member",
        "removing ExportReport widens nobody",
        not widened(before_a1, after_a1),
        {"widened": widened(before_a1, after_a1)},
    )

    # -- PE3: Carol's two hats ---------------------------------------------------------------
    carol_chat = sorted(agents_seen(api, carol, alpha))
    expose = put_document(
        api,
        carol,
        alpha_access["id"],
        access_document(
            agents=list(PEOPLE_AGENTS),
            apps=["Directory", "Prices"],
            features=ACME_FEATURES,
            export=False,
        ),
    )
    check(
        "UJ-PE3",
        "Carol, admin and analyst, still sees only Recruiter and Scout in Chat",
        carol_chat == ["Recruiter", "Scout"],
        carol_chat,
    )
    check(
        "UJ-PE3",
        "Carol cannot expose Onboarder or Coach herself: she does not hold them (owner's rule)",
        expose["status"] == 403
        and any(a in str(expose.get("detail")) for a in ("Onboarder", "Coach")),
        expose,
    )
    by_bob = put_document(
        api,
        bob,
        alpha_access["id"],
        access_document(
            agents=["Recruiter", "Scout", "Onboarder"],
            apps=["Directory", "Prices"],
            features=ACME_FEATURES,
            export=False,
        ),
    )
    exposed_view = {
        who: sorted(agents_seen(api, email[who], alpha)) for who in ("carol", "dave")
    }
    check(
        "UJ-PE3",
        "Bob exposes Onboarder: Carol has it, Dave's stricter policy still holds",
        by_bob["status"] == 200
        and "Onboarder" in exposed_view["carol"]
        and exposed_view["dave"] == ["Recruiter"],
        exposed_view,
    )
    put_document(
        api,
        bob,
        alpha_access["id"],
        access_document(
            agents=["Recruiter", "Scout"],
            apps=["Directory", "Prices"],
            features=ACME_FEATURES,
            export=False,
        ),
    )

    # -- the organization layer of the rules: Olivia narrows Bravo ---------------------------------
    before_o = decisions(api, grammar, acme, email, places)
    narrowed_bravo = put_document(
        api,
        olivia,
        bravo_access["id"],
        access_document(agents=[], apps=["Prices"], features=["chat"], export=False),
    )
    after_o = decisions(api, grammar, acme, email, places)
    check(
        "rule:reduction-never-widens:organization",
        "Olivia narrows Bravo; nobody gains anything",
        narrowed_bravo["status"] == 200 and not widened(before_o, after_o),
        {
            "widened": widened(before_o, after_o),
            "narrowed": narrowed(before_o, after_o),
        },
    )
    named_pricer = put_document(
        api,
        root,
        alpha_access["id"],
        access_document(
            agents=["Recruiter", "Scout", "Pricer"],
            apps=["Directory", "Prices"],
            features=ACME_FEATURES,
            export=False,
        ),
    )
    pricer_bob = talk(api, bob, alpha, alpha_ids, "Pricer", "hello")
    check(
        "rule:parent-bounds-child:organization",
        "naming Pricer in Alpha's access is refused even to Root (Acme's does not allow it), and Bob cannot use it",
        refused_naming(named_pricer, "dev.market/Pricer") and refused(pricer_bob),
        {"put": named_pricer, "chat": pricer_bob},
    )
    bravo_flags = on(flags(api, olivia, bravo))
    check(
        "rule:feature-off-absent:organization",
        "Workflows (datasets) is absent in Bravo too: no flag, the API refuses",
        "datasets" not in bravo_flags
        and refused(feature_route(api, olivia, bravo, "datasets")),
        sorted(bravo_flags),
    )

    # -- the platform layer: Root narrows Acme ------------------------------------------------------
    before_p = decisions(api, grammar, acme, email, places)
    narrowed_acme = put_document(
        api,
        root,
        acme_access["id"],
        access_document(
            agents=[
                "${scope}/module:agent/dev.people/Recruiter",
                "${scope}/module:agent/dev.people/Scout",
                "${scope}/module:agent/dev.people/Onboarder",
            ],
            apps=["Directory", "Prices"],
            features=ACME_FEATURES,
        ),
    )
    after_p = decisions(api, grammar, acme, email, places)
    coach_lost = [k for k in narrowed(before_p, after_p) if k.endswith("agent Coach")]
    check(
        "rule:reduction-never-widens:platform,rule:parent-bounds-child:platform",
        "Root removes Coach from Acme: everyone below loses it at once, nobody gains",
        narrowed_acme["status"] == 200
        and not widened(before_p, after_p)
        and bool(coach_lost),
        {"lost Coach": coach_lost, "widened": widened(before_p, after_p)},
    )

    # -- P1: Beta Corporation removed once it has no workspace -------------------------------------
    paul = email["paul"]
    lab = api.post(
        paul,
        "/api/workspaces",
        {
            "name": f"Beta lab {tag}",
            "slug": f"beta-lab-{tag}",
            "organization_id": beta["id"],
        },
    )["id"]
    blocked = api.attempt(root, "DELETE", f"/api/organizations/{beta['id']}")
    check(
        "UJ-P1",
        "removing Beta while it has a workspace is refused (409), naming it",
        blocked["status"] == 409 and f"Beta lab {tag}" in str(blocked.get("detail")),
        blocked,
    )
    api.call(paul, "DELETE", f"/api/workspaces/{lab}")
    beta_access_before = [
        p["id"]
        for p in policies_at(api, root, grammar.platform())
        if p["name"] == f"Beta Corp {tag} access"
    ]
    removed_beta = api.attempt(root, "DELETE", f"/api/organizations/{beta['id']}")
    gone = api.attempt(root, "GET", f"/api/organizations/{beta['id']}")
    paul_orgs = [o["id"] for o in api.get(paul, "/api/organizations")]
    beta_access_after = [
        p["id"]
        for p in policies_at(api, root, grammar.platform())
        if p["id"] in beta_access_before
    ]
    check(
        "UJ-P1",
        "Root removes Beta Corporation once it has no workspace: gone, with its access policy",
        removed_beta["status"] == 200
        and gone["status"] in (403, 404)
        and beta["id"] not in paul_orgs
        and beta_access_before
        and not beta_access_after,
        {
            "delete": removed_beta,
            "get": gone["status"],
            "access policy": beta_access_before,
            "left": beta_access_after,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", required=True)
    parser.add_argument("--mail", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = run(Api(args.api.rstrip("/"), args.mail))
    text = json.dumps(result, indent=2, default=str)
    if args.out:
        args.out.write_text(text)
    passed = sum(c["ok"] for c in result["checks"])
    print(f"{passed}/{len(result['checks'])} checks passed")
    for journey, ok in sorted(result["journeys"].items()):
        print(f"  {'ok  ' if ok else 'FAIL'} {journey}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
