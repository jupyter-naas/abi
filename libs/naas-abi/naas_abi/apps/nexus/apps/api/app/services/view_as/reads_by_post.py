"""The reads Nexus takes by POST (a query too large or too structured for a URL).

One list, read by two things: the route matrix test (a write method that authorizes
only a read must be on it) and the view's read-only guard (every other write is refused
in a view; these are decided here, each with its reason).

Each entry says what it reads (``reads``), and what a view does with it:

* ``allowed``: the view answers it, as the person. ``workspace`` says where the request
  names its workspace, and the guard holds it to the viewed one: ``body`` (a JSON object
  with ``workspace_id``), ``query`` (the route's declared query parameter, judged as a
  GET is), or ``None`` (the request names none: what it reads is decided by IAM for the
  person alone);
* ``refused``: the view says "Read-only: you are viewing as <name>": the route runs
  something for the person (an agent, a voice, a portal sign-in) or reads what is private
  to them, however little it stores.

Add a route here with its reason when it reads and travels as POST: never to make a
refusal go away.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# Where an allowed request names its workspace.
BODY = "body"
QUERY = "query"


@dataclass(frozen=True)
class ReadByPost:
    path: str
    reads: str  # why it is a read: the route matrix's reason
    in_view: Literal["allowed", "refused"]
    why_in_view: str  # what a view does with it, and why
    workspace: Literal["body", "query"] | None = None  # allowed ones only
    method: str = "POST"

    @property
    def key(self) -> tuple[str, str]:
        return (self.method, self.path)

    @property
    def allowed(self) -> bool:
        return self.in_view == "allowed"


def _graph(path: str, reads: str) -> ReadByPost:
    return ReadByPost(
        path,
        reads,
        "allowed",
        "a read of the workspace's graphs, as the person: the pages of the workspace need it",
        BODY,
    )


READS_BY_POST: tuple[ReadByPost, ...] = (
    _graph("/api/graph/explorer/catalog", "reads graphs: the body names the workspace and graphs"),
    _graph("/api/graph/explorer/overview", "reads graphs: the body names the workspace and graphs"),
    _graph(
        "/api/graph/explorer/instances", "reads graphs: the body names the workspace and graphs"
    ),
    _graph("/api/graph/explorer/network", "reads graphs: the body names the workspace and graphs"),
    ReadByPost(
        "/api/graph/analyze",
        "counts the triples of an uploaded file in memory; stores nothing",
        "refused",
        "a file the viewer would upload, in the import flow, which a view cannot do; its body is "
        "a multipart upload the guard does not read, so it cannot be held to the workspace",
    ),
    _graph("/api/graph/discovery/relation-targets", "reads graphs: the body names the filters"),
    _graph("/api/graph/discovery/properties", "reads graphs: the body names the filters"),
    _graph("/api/graph/discovery/instances", "reads graphs: the body names the filters"),
    _graph("/api/graph/discovery/instance-detail", "reads graphs: the body names the individual"),
    _graph("/api/graph/discovery/relation-types", "reads graphs: the body names the filters"),
    _graph("/api/graph/discovery/relations", "reads graphs: the body names the filters"),
    ReadByPost(
        "/api/graph/discovery/triples-export",
        "serializes the triples the body carries; reads nothing",
        "allowed",
        "the graph pages' export of what they show: a conversion of the body, nothing is read "
        "or stored",
        BODY,
    ),
    _graph("/api/graph/network/node-properties", "reads graphs: the body names the node"),
    _graph("/api/graph/network/node-instances", "reads graphs: the body names the node"),
    _graph("/api/graph/query", "read-only query over graphs: the body carries the spec"),
    _graph("/api/graph/query/facets", "read-only query over graphs: the body carries the spec"),
    ReadByPost(
        "/api/view/filters/preview",
        "previews triples of graphs: the body carries the filters",
        "allowed",
        "a read of the workspace's graphs, as the person: the views' filter editor needs it",
        BODY,
    ),
    ReadByPost(
        "/api/datasets/{namespace}/query",
        "read-only SQL: the body carries the query",
        "allowed",
        "a read of the workspace's datasets, as the person",
        BODY,
    ),
    ReadByPost(
        "/api/search/private",
        "a search of the workspace's sources: the body carries the query",
        "allowed",
        "a read of the workspace's sources, as the person: the search page needs it",
        BODY,
    ),
    ReadByPost(
        "/api/search/topics/preview",
        "previews a topic query's result: the body carries the query; nothing is stored",
        "allowed",
        "the topic pages' preview of a query, as the person; the cache it may fill is not "
        "written in a view",
        BODY,
    ),
    ReadByPost(
        "/api/maps/layouts/preview",
        "previews a map layout's points: the body carries the layout; nothing is stored",
        "allowed",
        "the map pages' preview of a layout, as the person",
        BODY,
    ),
    ReadByPost(
        "/api/maps/feeds/preview",
        "previews a map layout's points: the body carries the layout; nothing is stored",
        "allowed",
        "the map pages' preview of a layout, as the person (the same route under its older name)",
        BODY,
    ),
    ReadByPost(
        "/api/sheets/evaluate",
        "evaluates the formulas of a sheet's HTML in memory: the body carries the sheet",
        "allowed",
        "the sheet pages' calculation of the sheet they show; stores nothing",
        BODY,
    ),
    ReadByPost(
        "/api/iam/admin/simulate",
        "explains a decision (iam:Explain): changes nothing",
        "allowed",
        "the person's own rights decide it, as everything else; it names no workspace",
        None,
    ),
    ReadByPost(
        "/api/iam/admin/policies/validate",
        "checks a policy document and answers its problems: stores nothing",
        "allowed",
        "a check of the text sent, as the person; reads nothing of the workspace and names none",
        None,
    ),
    ReadByPost(
        "/api/agents/sync",
        "lists the agents the caller may use; reconciles the roster only for who may change it",
        "allowed",
        "in a view it only lists: the roster is never reconciled (a write the person's rights "
        "would otherwise allow)",
        QUERY,
    ),
    ReadByPost(
        "/api/apps/access-token",
        "mints a link to an app the caller may use",
        "allowed",
        "the person's apps open in a view: the link is the person's, ends with the view, "
        "is revoked with it, and its proxy forwards only GET and HEAD",
        BODY,
    ),
    ReadByPost(
        "/api/apps/remote-grant",
        "mints a link to an app the caller may use",
        "allowed",
        "the person's apps open in a view: the link is the person's, ends with the view, "
        "is revoked with it, and its proxy forwards only GET and HEAD",
        BODY,
    ),
    ReadByPost(
        "/api/app-projects/{slug}/preview-token",
        "mints a link to view a draft",
        "allowed",
        "a draft of the person's apps opens in a view: the same link as an app's",
        BODY,
    ),
    ReadByPost(
        "/api/apps/sso-token",
        "mints a sign-in token for a portal the caller may use",
        "refused",
        "a sign-in to a portal as the person: no portal sign-in in a view",
    ),
    ReadByPost(
        "/api/chat/conversations/{conversation_id}/export",
        "downloads a conversation the caller owns",
        "refused",
        "the person's conversation is private to them",
    ),
    ReadByPost(
        "/api/v1/chat/completions",
        "runs an agent for the caller (UseAgent); the gateway stores nothing",
        "refused",
        "no message reaches an agent in a view: it would run as the person",
    ),
    ReadByPost(
        "/api/speech",
        "synthesizes speech for the caller; stores nothing",
        "refused",
        "no speech in a view: it runs a model for the person",
    ),
    ReadByPost(
        "/api/speech/",
        "synthesizes speech for the caller; stores nothing",
        "refused",
        "no speech in a view: it runs a model for the person",
    ),
    ReadByPost(
        "/api/transcribe",
        "transcribes audio for the caller; stores nothing",
        "refused",
        "no transcription in a view: it runs a model for the person",
    ),
    ReadByPost(
        "/api/transcribe/",
        "transcribes audio for the caller; stores nothing",
        "refused",
        "no transcription in a view: it runs a model for the person",
    ),
)

BY_ROUTE: dict[tuple[str, str], ReadByPost] = {entry.key: entry for entry in READS_BY_POST}
