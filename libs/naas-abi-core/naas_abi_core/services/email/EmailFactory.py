from __future__ import annotations

from naas_abi_core.services.email.EmailService import EmailService
from naas_abi_core.services.email.adapters.secondary.FilesystemAdapter import (
    FilesystemAdapter,
)
from naas_abi_core.services.email.adapters.secondary.MicrosoftOutlookAdapter import (
    MicrosoftOutlookAdapter,
)
from naas_abi_core.services.email.adapters.secondary.SESAdapter import SESAdapter
from naas_abi_core.services.email.adapters.secondary.SendGridAdapter import (
    SendGridAdapter,
)
from naas_abi_core.services.email.adapters.secondary.SMTPAdapter import SMTPAdapter


class EmailFactory:
    @staticmethod
    def EmailServiceSMTP(
        *,
        host: str,
        port: int,
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = False,
        use_ssl: bool = False,
        timeout: int = 10,
    ) -> EmailService:
        return EmailService(
            SMTPAdapter(
                host=host,
                port=port,
                username=username,
                password=password,
                use_tls=use_tls,
                use_ssl=use_ssl,
                timeout=timeout,
            )
        )

    @staticmethod
    def EmailServiceFilesystem(*, directory: str) -> EmailService:
        return EmailService(FilesystemAdapter(directory=directory))

    @staticmethod
    def EmailServiceSES(
        *,
        region_name: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        aws_session_token: str | None = None,
    ) -> EmailService:
        return EmailService(
            SESAdapter(
                region_name=region_name,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                aws_session_token=aws_session_token,
            )
        )

    @staticmethod
    def EmailServiceSendGrid(
        *,
        api_key: str,
        base_url: str = "https://api.sendgrid.com/v3",
    ) -> EmailService:
        return EmailService(
            SendGridAdapter(
                api_key=api_key,
                base_url=base_url,
            )
        )

    @staticmethod
    def EmailServiceMicrosoftOutlook(
        *,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        user: str,
    ) -> EmailService:
        return EmailService(
            MicrosoftOutlookAdapter(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
                user=user,
            )
        )
