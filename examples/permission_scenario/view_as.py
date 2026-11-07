"""The checks of "View as", scripted against a running ``ENV=scenario abi dev up``, on the
database ``journeys.py`` ran on: it reuses the journeys' tag, cast and helpers, and each
check carries its evidence (the API's answers).

    python examples/permission_scenario/journeys.py --api URL --mail DIR --out journeys.json
    python examples/permission_scenario/view_as.py  --api URL --mail DIR --journeys journeys.json \
        --out view_as.json

1. Root views as Carol: Alpha is offered, Bravo is not; the view shows her features, the
   agents of ``dev.people``, Directory and Prices and the Alpha settings pages she may open;
   Bravo's pages and the platform's are "Outside this view"; her private content is empty.
2. Carol views as Dave: only what "Alpha minimal" gives; a chat message and a saved setting
   are refused ("Read-only"); nothing changed.
3. Refusals: Olivia and Bob (Carol holds less), and Root (nobody views as Root).
4. The audit shows each start, stop and refusal: who, whom and where.
5. The view ends 15 minutes after it starts, and at Stop the viewer is themselves again;
   Prices opened in a view ends with it, is revoked at Stop and takes no POST.

Each viewer signs in again for a view (their own browser session), so a view never reaches
the other checks, which use the sessions of ``journeys.py``'s helpers.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from cli_smoke_checks import NotYet, Session, sign_in  # noqa: E402
from journeys import (  # noqa: E402
    APPS,
    PEOPLE_AGENTS,
    agent_ids,
    agents_seen,
    module_apps,
    on,
    open_app,
)
from runner import (  # noqa: E402
    ADMIN,
    RATE_LIMIT_WAIT,
    Api,
    Grammar,
    Report,
    flags,
    principals,
)

VIEW_MINUTES = 15
READ_ONLY = "Read-only: you are viewing as"
OUTSIDE = "Outside this view: you are viewing as"
# How far the clock of this script and the server's may differ.
SLACK = timedelta(seconds=30)

# A page of the Alpha settings, by the read that decides it: the same call is made by the
# person and in the view, and must answer the same.
SETTINGS_PAGES = {
    "General": "/api/workspaces/{ws}",
    "Members": "/api/workspaces/{ws}/members",
    "Roles & permissions (what she holds)": "/api/iam/admin/access?scope={scope}",
    "Roles & permissions (policies)": "/api/iam/admin/policies?scope={scope}",
    "Roles & permissions (groups)": "/api/iam/admin/groups?scope={scope}",
    "Roles & permissions (attachments)": "/api/iam/admin/attachments?scope={scope}",
}
# Pages of other places: a workspace of the person's organisation, the organisation's own
# pages and the platform's.
OUTSIDE_PAGES = {
    "Bravo, its workspace": "/api/workspaces/{bravo}",
    "Bravo, its agents": "/api/agents/?workspace_id={bravo}",
    "Bravo, its files": "/api/files/?workspace_id={bravo}",
    "Bravo, its members": "/api/workspaces/{bravo}/members",
    "Acme, its settings": "/api/organizations/{acme}",
    "Acme, its members": "/api/organizations/{acme}/members",
    "Platform, its policies": "/api/iam/admin/policies",
    "Platform, its audit": "/api/iam/admin/audit",
    "Platform, its users": "/api/iam/admin/principals",
    "Platform, its system": "/api/admin/system/agents/runs",
}


# -- time ------------------------------------------------------------------------------------


def moment(text: str) -> datetime:
    """An ISO time as a UTC datetime (the server writes a naive time in UTC)."""
    found = datetime.fromisoformat(text)
    return found if found.tzinfo else found.replace(tzinfo=UTC)


def signed_in(api: Api, email: str) -> Session:
    """A new sign-in of ``email``. The identity provider limits sign-ins per address and per client
    (five minutes): a 429 is waited out, as the runner waits out the invitation routes."""
    deadline = time.monotonic() + RATE_LIMIT_WAIT
    while True:
        try:
            return sign_in(api.base, api.mail, email, wait_seconds=90)
        except NotYet as exc:
            if "429" not in str(exc) or time.monotonic() >= deadline:
                raise
            print(f"sign-in of {email} is rate limited: waiting", flush=True)
            time.sleep(30)


class PatientApi(Api):
    """``Api``, signing in with ``signed_in``: a rate limited sign-in waits."""

    def session(self, email: str) -> Session:
        if email not in self.sessions:
            self.sessions[email] = signed_in(self, email)
        return self.sessions[email]


# -- a view, as a browser lives it ----------------------------------------------------------


class Browser:
    """``email``'s own browser session, apart from the ones the other checks use. A view is
    kept on its session and ends with Stop (``viewing`` stops it), so the session is the viewer's
    own again afterwards and serves the next view: the identity provider limits sign-ins."""

    def __init__(self, api: Api, email: str) -> None:
        self.api = api
        self.email = email
        self.key = f"view-as:{email}"
        if self.key not in api.sessions:
            api.sessions[self.key] = signed_in(api, email)
        self.started: dict | None = None

    @property
    def session(self) -> Session:
        return self.api.sessions[self.key]

    def attempt(self, method: str, path: str, body: Any = None) -> dict:
        return self.api.attempt(self.key, method, path, body)

    def get(self, path: str) -> dict:
        return self.attempt("GET", path)

    def start(self, principal: str, workspace: str) -> dict:
        """``POST /api/iam/view-as``: ``{"status", "body"|"detail", "from", "until"}``,
        the times this script's clock had before and after."""
        before = datetime.now(UTC)
        found = self.attempt(
            "POST",
            "/api/iam/view-as",
            {"principal_id": principal, "workspace_id": workspace},
        )
        found["from"], found["until"] = before, datetime.now(UTC)
        if found["status"] == 200:
            self.started = found
        return found

    def stop(self) -> dict:
        self.started = None
        return self.attempt("DELETE", "/api/iam/view-as")

    def view(self) -> Any:
        """The ``view`` of ``GET /api/auth/oidc/session``: null outside a view."""
        found = self.get("/api/auth/oidc/session")
        return found["body"].get("view") if found["status"] == 200 else found


@contextmanager
def viewing(
    api: Api, viewer: str, principal: str, workspace: str
) -> Iterator[tuple[Browser, dict]]:
    """A view of ``principal`` in ``workspace`` from a new browser of ``viewer``, ended
    at the end of the block if the check did not."""
    browser = Browser(api, viewer)
    started = browser.start(principal, workspace)
    try:
        yield browser, started
    finally:
        if browser.started is not None:
            browser.stop()


def named(found: dict, text: str) -> bool:
    """A refusal (403) whose message starts with ``text``."""
    return found["status"] == 403 and str(found.get("detail", "")).startswith(text)


def same_answer(own: dict, seen: dict) -> bool:
    """What the person gets and what the view gets: the same status and, for a 200, the
    same body."""
    return own["status"] == seen["status"] and (
        own["status"] != 200 or own.get("body") == seen.get("body")
    )


# -- the audit and the links ----------------------------------------------------------------


def audit(api: Api, operation: str) -> list[dict]:
    """The audit's records of ``view_as_<operation>``, newest first, as Root reads them
    (Platform settings › Roles & permissions › Audit)."""
    found = api.get(ADMIN, "/api/iam/admin/audit", limit=500)
    return [i for i in found["items"] if i["operation"] == f"view_as_{operation}"]


def records(
    api: Api,
    operation: str,
    *,
    actor: str,
    person: str,
    since: datetime,
    phase: str | None = None,
    detail: str | None = None,
) -> list[dict]:
    """The records of ``view_as_<operation>`` by ``actor`` (the viewer's Nexus id, as the
    audit names them) about ``person`` (their IAM id) since ``since``, of one ``phase``
    (``requested``, then ``succeeded`` or ``failed``) and with ``detail`` in their detail."""
    return [
        r
        for r in audit(api, operation)
        if r["actor_id"] == actor
        and r["resource_id"] == person
        and moment(r["at"]) >= since - SLACK
        and (phase is None or r["phase"] == phase)
        and (detail is None or detail in r["detail"])
    ]


def links_since(database: Path, since: datetime) -> list[dict]:
    """The links a view made since ``since``, read from IAM's keys (their description
    carries the view's mark): when each ends and whether it is revoked."""
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "SELECT key_id, kind, description, created_at, expires_at, revoked_at "
            "FROM iam_keys WHERE description LIKE 'view-as:%' ORDER BY created_at"
        ).fetchall()
    finally:
        connection.close()
    return [
        {
            "key": key,
            "kind": kind,
            "description": description[:80],
            "created_at": moment(created),
            "expires_at": moment(expires) if expires else None,
            "revoked_at": moment(revoked) if revoked else None,
        }
        for key, kind, description, created, expires, revoked in rows
        if moment(created) >= since - SLACK
    ]


def plain(rows: list[dict]) -> list[dict]:
    return [
        {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in r.items()}
        for r in rows
    ]


# -- the checks -------------------------------------------------------------------------------


def run(
    api: Api, journeys: dict[str, Any], iam_database: Path | None
) -> dict[str, Any]:
    report = Report()
    facts: dict[str, Any] = {"tag": journeys["tag"]}
    try:
        checks(api, journeys, iam_database, report, facts)
    except Exception as exc:  # noqa: BLE001 - reported with what came before
        report.check("-", f"the run stopped: {type(exc).__name__}", False, str(exc))
    by_step: dict[str, bool] = {}
    for check in report.checks:
        for step in check["step"].split(","):
            by_step[step] = by_step.get(step, True) and check["ok"]
    return {
        **facts,
        "steps": by_step,
        "checks": report.checks,
        "ok": all(c["ok"] for c in report.checks),
    }


def checks(
    api: Api,
    journeys: dict[str, Any],
    iam_database: Path | None,
    report: Report,
    facts: dict[str, Any],
) -> None:
    check = report.check
    root = ADMIN
    email = journeys["people"]
    carol, dave, olivia, bob = (email[n] for n in ("carol", "dave", "olivia", "bob"))
    acme, alpha, bravo = journeys["acme"]["id"], journeys["alpha"], journeys["bravo"]
    grammar = Grammar(legacy=False)
    alpha_scope = grammar.workspace(acme, alpha)
    ids = principals(api)
    root_id, carol_id, dave_id = ids[root], ids[carol], ids[dave]
    olivia_id, bob_id = ids[olivia], ids[bob]
    facts.update(alpha=alpha, bravo=bravo, acme=acme, people=email)
    began = datetime.now(UTC)

    def page(path: str) -> str:
        return path.format(
            ws=alpha, bravo=bravo, acme=acme, scope=quote(alpha_scope, safe="")
        )

    # A group of Bravo, read by id as Root (outside any view): a view of Alpha must not reach it.
    bravo_scope = grammar.workspace(acme, bravo)
    bravo_groups = [
        g["id"]
        for g in api.get(root, "/api/iam/admin/groups", scope=bravo_scope)["items"]
        if g.get("owner_scope") == bravo_scope
    ]
    # What Carol owns outside any view, so that "empty" in a view means hidden, not absent.
    seeded = seed_private_content(api, carol, alpha, report)
    own = {
        "agents": sorted(agents_seen(api, carol, alpha)),
        "apps": sorted(module_apps(api, carol, alpha)),
        "flags": sorted(on(flags(api, carol, alpha))),
        "pages": {
            n: api.attempt(carol, "GET", page(p)) for n, p in SETTINGS_PAGES.items()
        },
    }
    facts["carol"] = {k: v for k, v in own.items() if k != "pages"}

    # -- 1. Root views as Carol ----------------------------------------------------------
    offered_alpha = api.attempt(
        root, "GET", f"/api/iam/view-as/workspaces?principal_id={carol_id}"
    )
    offered = {w["id"] for w in offered_alpha.get("body", [])}
    check(
        "view-1",
        "Root is offered Alpha for Carol, and not Bravo",
        alpha in offered and bravo not in offered,
        offered_alpha,
    )
    with viewing(api, root, carol_id, alpha) as (root_view, start):
        check(
            "view-1",
            "Root starts a view of Carol in Alpha: the person, the workspace, the end time",
            start["status"] == 200
            and start["body"]["person"]["id"]
            and start["body"]["workspace"]["id"] == alpha
            and "ends_at" in start["body"],
            start,
        )
        facts["root_view_start"] = start
        session = root_view.view()
        check(
            "view-1",
            "the session answers the view, still about Root",
            isinstance(session, dict)
            and session.get("workspace", {}).get("id") == alpha
            and root_view.get("/api/auth/oidc/session")["body"]["user"]["email"]
            == root,
            session,
        )
        me = root_view.get("/api/auth/me")
        check(
            "view-1",
            "the shell shows the person: /api/auth/me is Carol",
            me["status"] == 200 and me["body"]["email"] == carol,
            me,
        )

        listed = root_view.get("/api/workspaces")
        listed_ids = [w["id"] for w in listed.get("body", [])]
        seen_flags = sorted(
            on((listed.get("body") or [{}])[0].get("feature_flags") or {})
        )
        check(
            "view-1",
            "/api/workspaces lists Alpha only, with Carol's own feature flags",
            listed_ids == [alpha] and seen_flags == own["flags"] and bool(seen_flags),
            {
                "workspaces": listed_ids,
                "flags": seen_flags,
                "carol's own": own["flags"],
            },
        )
        agents = root_view.get(f"/api/agents/?workspace_id={alpha}")
        in_view_agents = sorted(
            {
                n
                for n in PEOPLE_AGENTS
                if f"dev.people/{n}"
                in {str(r.get("class_name")) for r in agents.get("body", [])}
            }
        )
        check(
            "view-1",
            "the agents are dev.people's, as Carol lists them (no Pricer)",
            in_view_agents == own["agents"]
            and bool(in_view_agents)
            and "dev.market/Pricer"
            not in {str(r.get("class_name")) for r in agents.get("body", [])},
            {"in the view": in_view_agents, "carol's own": own["agents"]},
        )
        apps = root_view.get(f"/api/apps/?workspace_id={alpha}")
        in_view_apps = sorted(
            f"{a.get('module_name')}/{str(a.get('app_id')).rsplit(':', 1)[-1]}"
            for a in apps.get("body", {}).get("apps", [])
            if a.get("module_name")
        )
        check(
            "view-1",
            "the apps are Directory and Prices, as Carol lists them",
            in_view_apps == own["apps"]
            and set(own["apps"]) == {"/".join(v) for v in APPS.values()},
            {"in the view": in_view_apps, "carol's own": own["apps"]},
        )
        pages = {n: root_view.get(page(p)) for n, p in SETTINGS_PAGES.items()}
        differing = {
            n: {"carol": own["pages"][n]["status"], "view": pages[n]["status"]}
            for n in SETTINGS_PAGES
            if not same_answer(own["pages"][n], pages[n])
        }
        check(
            "view-1",
            "the Alpha settings pages Carol may open open in the view, the others stay refused",
            not differing and any(p["status"] == 200 for p in pages.values()),
            {
                "answers": {n: p["status"] for n, p in pages.items()},
                "different": differing,
            },
        )

        alpha_groups = root_view.get(page("/api/iam/admin/groups?scope={scope}"))
        alpha_group_ids = [
            g["id"]
            for g in alpha_groups.get("body", {}).get("items", [])
            if g.get("owner_scope") == alpha_scope
        ]
        one_group = root_view.get(
            f"/api/iam/admin/groups/{(alpha_group_ids or ['-'])[0]}"
        )
        check(
            "view-1",
            "the groups of Alpha are read by id: the Roles & permissions page lists their members",
            bool(alpha_group_ids)
            and one_group["status"] == 200
            and bool(one_group["body"].get("members")),
            {
                "alpha groups": len(alpha_group_ids),
                "one of them": one_group["status"],
                "members": len(one_group.get("body", {}).get("members", [])),
            },
        )

        outside = {n: root_view.get(page(p)) for n, p in OUTSIDE_PAGES.items()}
        check(
            "view-1",
            "Bravo's pages and the platform's are refused: \"Outside this view\"",
            all(named(found, OUTSIDE) for found in outside.values()),
            {n: [f["status"], f.get("detail")] for n, f in outside.items()},
        )
        check(
            "view-1",
            "the refusal names the person and the workspace",
            all(
                "Alpha" in found.get("detail", "")
                and "Carol" in found.get("detail", "")
                for found in outside.values()
            ),
            next(iter(outside.values())),
        )

        private = private_content(root_view, alpha, seeded)
        check(
            "view-1",
            "her conversations, My Drive, secrets and API keys come back empty "
            "(and the single items not found), though she holds each",
            all(seeded[k] for k in ("conversation", "secret", "key", "file"))
            and all(private["ok"].values()),
            {"seeded": seeded, "in the view": private["answers"]},
        )
        stopped = root_view.stop()
        check(
            "view-1",
            "Root stops the view",
            stopped["status"] == 200 and stopped["body"] == {"stopped": True},
            stopped,
        )

    # The view is one workspace even for someone who reaches more: Olivia (Acme's admin) reads
    # a group of Bravo herself, and the view of her in Alpha refuses it.
    olivia_reads = api.attempt(
        olivia, "GET", f"/api/iam/admin/groups/{(bravo_groups or ['-'])[0]}"
    )
    with viewing(api, root, olivia_id, alpha) as (olivia_view, start):
        in_view = olivia_view.get(f"/api/iam/admin/groups/{(bravo_groups or ['-'])[0]}")
        bravo_listing = olivia_view.get(
            f"/api/iam/admin/groups?scope={quote(bravo_scope, safe='')}"
        )
        check(
            "view-1",
            "the view is one workspace for someone who reaches more: Olivia reads a group of "
            "Bravo herself, her view in Alpha refuses it and Bravo's list",
            start["status"] == 200
            and olivia_reads["status"] == 200
            and named(in_view, OUTSIDE)
            and named(bravo_listing, OUTSIDE),
            {
                "olivia herself": olivia_reads["status"],
                "the group, in the view": [in_view["status"], in_view.get("detail")],
                "the list of Bravo, in the view": [
                    bravo_listing["status"],
                    bravo_listing.get("detail"),
                ],
            },
        )
        olivia_view.stop()

    # -- 2. Carol views as Dave ----------------------------------------------------------
    dave_own = {
        "agents": sorted(agents_seen(api, dave, alpha)),
        "apps": sorted(module_apps(api, dave, alpha)),
        "flags": sorted(on(flags(api, dave, alpha))),
    }
    ids_of_agents = agent_ids(api, alpha)
    dave_conversations = api.attempt(
        dave, "GET", f"/api/chat/conversations?workspace_id={alpha}"
    )
    carol_conversations = api.attempt(
        carol, "GET", f"/api/chat/conversations?workspace_id={alpha}"
    )
    alpha_before = api.get(carol, f"/api/workspaces/{alpha}")
    secrets_before = api.get(carol, f"/api/secrets/{alpha}")
    with viewing(api, carol, dave_id, alpha) as (carol_view, start):
        check(
            "view-2",
            "Carol (Alpha's admin) starts a view of Dave in Alpha",
            start["status"] == 200
            and start["body"]["person"]["name"].startswith("Dave"),
            start,
        )
        d_agents = carol_view.get(f"/api/agents/?workspace_id={alpha}")
        d_names = sorted(
            n
            for n in (*PEOPLE_AGENTS, "Pricer")
            if any(
                str(r.get("class_name")).endswith(f"/{n}")
                for r in d_agents.get("body", [])
            )
        )
        d_apps = carol_view.get(f"/api/apps/?workspace_id={alpha}")
        d_app_names = sorted(
            f"{a.get('module_name')}/{str(a.get('app_id')).rsplit(':', 1)[-1]}"
            for a in d_apps.get("body", {}).get("apps", [])
            if a.get("module_name")
        )
        d_listed = carol_view.get("/api/workspaces")
        d_flags = sorted(
            on((d_listed.get("body") or [{}])[0].get("feature_flags") or {})
        )
        minimal = {
            "agents": ["Recruiter"],
            "apps": ["dev.market/prices"],
            "flags": ["chat", "search"],
        }
        check(
            "view-2",
            'the view shows only what "Alpha minimal" gives: Recruiter, Prices, chat and Home',
            {"agents": d_names, "apps": d_app_names, "flags": d_flags} == minimal
            and minimal == dave_own,
            {
                "in the view": {
                    "agents": d_names,
                    "apps": d_app_names,
                    "flags": d_flags,
                },
                "dave's own": dave_own,
            },
        )
        basemap = carol_view.get(f"/api/view/list?workspace_id={alpha}")
        check(
            "view-2",
            "no BaseMap: the feature is absent and its route refused",
            "graph" not in d_flags and basemap["status"] in (403, 404),
            {"flags": d_flags, "basemap": basemap},
        )
        message = carol_view.attempt(
            "POST",
            "/api/chat/complete",
            {
                "workspace_id": alpha,
                "message": "hello from a view",
                "agent": ids_of_agents["Recruiter"],
            },
        )
        check(
            "view-2",
            'sending a chat message is refused: 403 "Read-only: you are viewing as Dave"',
            named(message, READ_ONLY) and "Dave" in message["detail"],
            message,
        )
        saved = carol_view.attempt(
            "PATCH", f"/api/workspaces/{alpha}", {"description": "saved in a view"}
        )
        refresh = carol_view.attempt("POST", "/api/settings-cache/refresh", {})
        check(
            "view-2",
            'saving a setting is refused: 403 "Read-only: you are viewing as Dave" '
            "(and the settings cache's refresh with it)",
            named(saved, READ_ONLY) and named(refresh, READ_ONLY),
            {"setting": saved, "refresh": refresh},
        )
        carol_view.stop()
    dave_after = api.attempt(
        dave, "GET", f"/api/chat/conversations?workspace_id={alpha}"
    )
    carol_after = api.attempt(
        carol, "GET", f"/api/chat/conversations?workspace_id={alpha}"
    )
    alpha_after = api.get(carol, f"/api/workspaces/{alpha}")
    secrets_after = api.get(carol, f"/api/secrets/{alpha}")
    check(
        "view-2",
        "nothing changed: Dave's and Carol's conversations, Alpha's setting and its secrets",
        dave_after["body"] == dave_conversations["body"]
        and carol_after["body"] == carol_conversations["body"]
        and alpha_after.get("description") == alpha_before.get("description")
        and alpha_after == alpha_before
        and secrets_after == secrets_before,
        {
            "dave conversations": [
                len(dave_conversations["body"]),
                len(dave_after["body"]),
            ],
            "carol conversations": [
                len(carol_conversations["body"]),
                len(carol_after["body"]),
            ],
            "alpha description": [
                alpha_before.get("description"),
                alpha_after.get("description"),
            ],
        },
    )

    # -- 3. Refusals ---------------------------------------------------------------------
    refusals = Browser(api, carol)
    olivia_offer = refusals.get(f"/api/iam/view-as/workspaces?principal_id={olivia_id}")
    as_olivia = refusals.start(olivia_id, alpha)
    check(
        "view-3",
        "Carol viewing as Olivia (Acme's admin) is refused, naming what Olivia holds",
        as_olivia["status"] == 403
        and olivia_offer["body"] == []
        and all(
            text in as_olivia["detail"]
            for text in ("Olivia holds", "builtin.admin", "which you do not hold")
        ),
        {"offered": olivia_offer, "start": as_olivia},
    )
    as_bob = refusals.start(bob_id, alpha)
    bob_offer = refusals.get(f"/api/iam/view-as/workspaces?principal_id={bob_id}")
    check(
        "view-3",
        "Carol viewing as Bob (Alpha's owner) is refused too, naming what Bob holds",
        as_bob["status"] == 403
        and bob_offer["body"] == []
        and all(
            text in as_bob["detail"]
            for text in ("holds", "builtin.owner", "which you do not hold")
        ),
        {"offered": bob_offer, "start": as_bob},
    )
    root_offer = refusals.get(f"/api/iam/view-as/workspaces?principal_id={root_id}")
    carol_as_root = refusals.start(root_id, alpha)
    olivia_browser = Browser(api, olivia)
    olivia_as_root = olivia_browser.start(root_id, alpha)
    root_browser = Browser(api, root)
    root_as_root = root_browser.start(root_id, alpha)
    check(
        "view-3",
        "nobody views as Root: Carol, Olivia and Root himself are refused",
        all(
            "builtin.platform_admin" in r["detail"] and r["status"] == 403
            for r in (carol_as_root, olivia_as_root)
        )
        and root_as_root["status"] == 403
        and root_offer["body"] == [],
        {
            "carol": carol_as_root,
            "olivia": olivia_as_root,
            "root": root_as_root,
            "offered": root_offer,
        },
    )
    facts["refusals"] = {
        "olivia": as_olivia,
        "bob": as_bob,
        "root": carol_as_root,
    }

    # -- 5. Ending, and apps (before the audit, which reads what these did) ---------------
    with viewing(api, root, carol_id, alpha) as (ending, start):
        ends_at = moment(start["body"]["ends_at"])
        lasts = ends_at - start["from"]
        check(
            "view-5",
            f"the view's end is its start plus {VIEW_MINUTES} minutes",
            timedelta(minutes=VIEW_MINUTES) - SLACK
            <= ends_at - start["from"]
            <= timedelta(minutes=VIEW_MINUTES)
            + (start["until"] - start["from"])
            + SLACK,
            {"ends_at": start["body"]["ends_at"], "lasts": str(lasts)},
        )
        grant_began = datetime.now(UTC)
        granted = opening_prices(ending, alpha)
        own_grant = open_app(api, root, alpha, "Prices")
        path = granted.get("body", {}).get("path", "")
        reached = plain_get(api, path)
        posted = plain_post(api, path)
        links = links_since(iam_database, grant_began) if iam_database else []
        mine = [link for link in links if link["revoked_at"] is None]
        check(
            "view-5",
            "Prices opened in a view: its link ends no later than the view's end",
            granted["status"] == 200
            and reached["status"] == 200
            and len(mine) >= 1
            and all(
                link["expires_at"] is not None and link["expires_at"] <= ends_at + SLACK
                for link in mine
            ),
            {
                "grant": {k: v for k, v in granted.items() if k != "body"},
                "own link, outside a view": own_grant["body"]["expires_in"]
                if own_grant["status"] == 200
                else own_grant,
                "get through it": reached["status"],
                "the view ends": ends_at.isoformat(),
                "links": plain(links),
            },
        )
        check(
            "view-5",
            'a POST through the link is refused: 403 "Read-only: you are viewing as Carol"',
            posted["status"] == 403 and READ_ONLY in posted["text"],
            posted,
        )
        stopped = ending.stop()
        after_stop = plain_get(api, path)
        revoked = links_since(iam_database, grant_began) if iam_database else []
        check(
            "view-5",
            "the link is revoked at Stop: the app no longer opens through it",
            stopped["status"] == 200
            and after_stop["status"] in (401, 403, 404)
            and bool(revoked)
            and all(link["revoked_at"] is not None for link in revoked),
            {
                "stop": stopped,
                "get after stop": after_stop["status"],
                "links": plain(revoked),
            },
        )
        after_session = ending.view()
        listed_after = ending.get("/api/workspaces")
        me_after = ending.get("/api/auth/me")
        check(
            "view-5",
            "after Stop the viewer is Root again: no view, his workspaces, his own account",
            after_session is None
            and me_after["body"]["email"] == root
            and {alpha, bravo} <= {w["id"] for w in listed_after["body"]},
            {
                "view": after_session,
                "me": me_after["body"]["email"],
                "workspaces": len(listed_after["body"]),
            },
        )

    # -- 4. The audit --------------------------------------------------------------------
    # The audit names the viewer by their Nexus id and the person by their IAM id.
    actor = {e: api.get(e, "/api/auth/me")["id"] for e in (root, carol, olivia)}

    def shows(operation: str, viewer: str, person: str, **kw: str) -> list[dict]:
        return records(
            api, operation, actor=actor[viewer], person=person, since=began, **kw
        )

    root_started = shows("start", root, carol_id, phase="succeeded", detail=alpha)
    root_stopped = shows("stop", root, carol_id, phase="succeeded", detail="stop")
    check(
        "view-4",
        "the audit shows Root's views of Carol in Alpha: each start (who, whom, where, "
        "until when) and each stop",
        len(root_started) == len(root_stopped) == 2  # this run's two views of Carol
        and all("ends" in r["detail"] for r in root_started),
        plain_records([*root_started, *root_stopped]),
    )
    carol_started = shows("start", carol, dave_id, phase="succeeded", detail=alpha)
    carol_stopped = shows("stop", carol, dave_id, phase="succeeded", detail="stop")
    check(
        "view-4",
        "the audit shows Carol's view of Dave in Alpha, started and stopped",
        len(carol_started) == 1 and len(carol_stopped) == 1,
        plain_records([*carol_started, *carol_stopped]),
    )
    refusals_seen = {
        "Carol as Olivia": shows(
            "start", carol, olivia_id, phase="failed", detail=alpha
        ),
        "Carol as Bob": shows("start", carol, bob_id, phase="failed", detail=alpha),
        "Carol as Root": shows("start", carol, root_id, phase="failed", detail=alpha),
        "Olivia as Root": shows("start", olivia, root_id, phase="failed", detail=alpha),
        "Root as Root": shows("start", root, root_id, phase="failed", detail=alpha),
    }
    check(
        "view-4",
        "the audit shows each refusal: who asked, whom, where, and the error",
        all(refusals_seen.values()),
        {n: plain_records(rows) for n, rows in refusals_seen.items()},
    )
    opened = shows("open_app", root, carol_id, phase="succeeded")
    check(
        "view-4",
        "the audit shows the app opened in the view: the viewer, the person, the app, the workspace",
        any("prices" in r["detail"] and alpha in r["detail"] for r in opened),
        plain_records(opened),
    )


# -- helpers of the checks ------------------------------------------------------------------


def plain_records(rows: list[dict]) -> list[dict]:
    return [
        {
            k: r[k]
            for k in (
                "at",
                "actor",
                "operation",
                "resource_id",
                "detail",
                "phase",
                "error",
            )
        }
        for r in rows
    ]


def opening_prices(browser: Browser, workspace: str) -> dict:
    module, app = APPS["Prices"]
    return browser.attempt(
        "POST",
        "/api/apps/remote-grant",
        {"workspace_id": workspace, "module_id": module, "app": app},
    )


def plain_get(api: Api, path: str) -> dict:
    """A GET to an app's link without the browser's cookies: the link is its credential."""
    status, payload, _ = Session().open(f"{api.base}{path}") if path else (0, b"", "")
    return {"status": status, "text": payload[:200].decode("utf-8", "replace")}


def plain_post(api: Api, path: str) -> dict:
    status, payload, _ = (
        Session().open(f"{api.base}{path}", method="POST", body={"x": 1})
        if path
        else (0, b"", "")
    )
    text = payload.decode("utf-8", "replace")
    try:
        text = str(json.loads(text).get("detail", text))
    except ValueError:
        pass
    return {"status": status, "text": text[:300]}


def seed_private_content(api: Api, carol: str, alpha: str, report: Report) -> dict:
    """Carol's own conversation, secret, API key and My Drive file in Alpha: what a view
    must keep private. Made again on every run, under a name that cannot collide."""
    stamp = datetime.now(UTC).strftime("%H%M%S")
    made: dict[str, Any] = {}
    conversation = api.attempt(
        carol,
        "POST",
        "/api/chat/conversations",
        {"workspace_id": alpha, "title": f"Carol's private chat {stamp}"},
    )
    made["conversation"] = (
        conversation["body"]["id"] if conversation["status"] == 200 else None
    )
    secret = api.attempt(
        carol,
        "POST",
        "/api/secrets",
        {"workspace_id": alpha, "key": f"VIEW_AS_{stamp}", "value": "not-for-a-view"},
    )
    made["secret"] = secret["status"] in (200, 201)
    key = api.attempt(
        carol, "POST", "/api/iam/api-keys", {"name": f"carol-key-{stamp}"}
    )
    made["key"] = key["status"] in (200, 201)
    path = f"private-{stamp}.txt"
    file = api.attempt(
        carol,
        "POST",
        "/api/files/",
        {
            "path": path,
            "workspace_id": alpha,
            "scope": "my_drive",
            "content": "private",
        },
    )
    made["file"] = path if file["status"] in (200, 201) else None
    report.check(
        "view-1",
        "Carol holds a conversation, a secret, an API key and a My Drive file of her own",
        all(made.values()),
        {
            "conversation": conversation,
            "secret": secret["status"],
            "key": key["status"],
            "file": file["status"],
            **made,
        },
    )
    return made


def private_content(browser: Browser, alpha: str, seeded: dict) -> dict[str, Any]:
    conversations = browser.get(f"/api/chat/conversations?workspace_id={alpha}")
    one = browser.get(f"/api/chat/conversations/{seeded['conversation']}")
    drive = browser.get(f"/api/files/?workspace_id={alpha}&scope=my_drive")
    file = browser.get(
        f"/api/files/{seeded['file']}?workspace_id={alpha}&scope=my_drive"
    )
    secrets = browser.get(f"/api/secrets/{alpha}")
    keys = browser.get("/api/iam/api-keys")
    entries = (drive.get("body") or {}).get(
        "entries", (drive.get("body") or {}).get("files")
    )
    answers = {
        "conversations": conversations,
        "one conversation": one,
        "My Drive": drive,
        "a My Drive file": file,
        "secrets": secrets,
        "API keys": keys,
    }
    return {
        "answers": {
            n: {
                "status": a["status"],
                "body": str(a.get("body", a.get("detail")))[:120],
            }
            for n, a in answers.items()
        },
        "ok": {
            "conversations": conversations["status"] == 200
            and conversations["body"] == [],
            "one conversation": one["status"] == 404,
            "My Drive": drive["status"] == 200 and not entries,
            "a My Drive file": file["status"] == 404,
            "secrets": secrets["status"] == 200 and secrets["body"] == [],
            "API keys": keys["status"] == 200 and keys["body"] == [],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", required=True)
    parser.add_argument("--mail", required=True, type=Path)
    parser.add_argument(
        "--journeys", required=True, type=Path, help="the --out of journeys.py"
    )
    parser.add_argument(
        "--iam-database",
        type=Path,
        default=Path("storage/iam/iam.sqlite"),
        help="IAM's SQLite file (read only): where the end of an app's link is read",
    )
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    journeys = json.loads(args.journeys.read_text())
    database = args.iam_database if args.iam_database.exists() else None
    result = run(PatientApi(args.api.rstrip("/"), args.mail), journeys, database)
    text = json.dumps(result, indent=2, default=str)
    if args.out:
        args.out.write_text(text)
    passed = sum(c["ok"] for c in result["checks"])
    print(f"{passed}/{len(result['checks'])} checks passed")
    for step, ok in sorted(result["steps"].items()):
        print(f"  {'ok  ' if ok else 'FAIL'} {step}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
