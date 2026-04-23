from __future__ import annotations

from abc import ABC, abstractmethod


class IEmailAdapter(ABC):
    @abstractmethod
    def send(
        self,
        *,
        to_email: str,
        subject: str,
        text_body: str,
        html_body: str | None = None,
        from_email: str,
        from_name: str | None = None,
        reply_to: str | None = None,
    ) -> None:
        raise NotImplementedError()
