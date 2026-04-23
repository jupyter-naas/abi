from __future__ import annotations

from naas_abi_core.services.email.EmailService import EmailService
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
