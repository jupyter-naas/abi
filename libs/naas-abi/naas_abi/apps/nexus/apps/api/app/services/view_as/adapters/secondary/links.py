"""``ViewLinks`` on Nexus's links (``apps/links.py``): the links a view made are IAM grants
of the person, marked with the view; they are revoked when it ends."""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.view_as.port import ViewLinks, ViewRecord, view_mark


class ViewAsSecondaryAdapterLinks(ViewLinks):
    async def revoke(self, person_user_id: str, view: ViewRecord) -> int:
        # Imported here: the links module reads the view of the request (``view_as.active``).
        from naas_abi.apps.nexus.apps.api.app.services.apps import links

        try:
            return await links.arevoke_view_links(person_user_id, view_mark(view))
        except links.LinksUnavailable:
            return 0  # no engine IAM, so no link was ever made
