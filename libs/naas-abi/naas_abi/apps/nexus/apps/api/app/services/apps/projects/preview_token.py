"""Links for ``/app-preview/<token>/<path>``: IAM grants (``apps/links.py``).

The token sits in the preview URL, where the previewed app's own JavaScript
can read it. So it is never a session:

* it is an IAM grant (``abi_gk_<id>_<secret>``) of the user who opened the
  preview, for the audience ``abi:delegated:preview`` only;
* it is bound to one project's draft (``resource``) and allows nothing at the
  kernel (``scope`` empty): it reads one project's draft until it expires;
* IAM stores it hashed; eight hours at most, revocable, ended with its owner.
"""

from __future__ import annotations

from dataclasses import dataclass

from naas_abi.apps.nexus.apps.api.app.services.apps import links
from naas_abi_core.engine.nats_auth import PREVIEW_AUDIENCE


@dataclass(frozen=True)
class PreviewGrant:
    user_id: str
    workspace_id: str
    slug: str


def mint_preview_token(*, user_id: str, workspace_id: str, slug: str, minutes: int = 60) -> str:
    value, _ = links.mint_link(
        user_id=user_id,
        audience=PREVIEW_AUDIENCE,
        resource=links.preview_resource(workspace_id, slug),
        scope=(),
        minutes=minutes,
        description=f"preview: {workspace_id}/{slug}"[:200],
    )
    return value


def read_preview_token(token: str) -> PreviewGrant | None:
    link = links.open_link(token, PREVIEW_AUDIENCE)
    if link is None:
        return None
    prefix = f"{links.PREVIEW}/"
    if not link.resource.startswith(prefix):
        return None
    workspace_id, _, slug = link.resource.removeprefix(prefix).partition("/")
    if not (workspace_id and slug):
        return None
    return PreviewGrant(user_id=link.user_id, workspace_id=workspace_id, slug=slug)
