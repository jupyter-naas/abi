"""``InvitationMailer`` through the engine's email service."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace

from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.services.invites.invitation_email import (
    render_invitation,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.port import (
    InvitationMail,
    InvitationMailer,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.sign_in_email import (
    apply_dev_subject_prefix,
    resolve_email_service,
)
from naas_abi_core.engine.call_context import as_service_account, use_call_context
from naas_abi_core.services.email.EmailService import EmailService
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)


class EngineInvitationMailer(InvitationMailer):
    def __init__(self, email: Callable[[], EmailService | None] = resolve_email_service) -> None:
        self._email = email

    async def send(self, mail: InvitationMail) -> bool:
        service = self._email()
        if service is None:
            logger.info("Email service unavailable: no invitation email for %s", mail.to_email)
            return False
        subject, text, html = render_invitation(mail, app_name=settings.magic_link_email_app_name)

        def send() -> None:
            # Nexus's own mail, as its account: an invitation is not the
            # inviting person's mail, and belongs to no workspace.
            with (
                as_service_account("api") as context,
                use_call_context(replace(context, workspace_id=None)),
            ):
                service.send(
                    to_email=mail.to_email,
                    subject=apply_dev_subject_prefix(subject),
                    text_body=text,
                    html_body=html,
                    from_email=str(settings.email_from_address),
                    from_name=settings.email_from_name,
                )

        await run_in_threadpool(send)
        return True
