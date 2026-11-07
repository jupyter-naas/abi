"""The sign-in code `abi dev up` mails to nobody: it goes to ``storage/email``.

The dev stack's email adapter keeps every message as a ``.eml`` file there
(``FilesystemAdapter``), so the code the built-in identity provider "sent" is a
file. ``abi dev code`` reads the newest one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from email.message import EmailMessage
from email.parser import BytesParser
from email.policy import default as default_policy
from pathlib import Path

# "Your ABI sign-in code is: 123456": the built-in identity provider's mail
# (``naas_abi_idp.pages.code_text``).
_CODE = re.compile(r"sign-in code is:\s*(\d{4,10})")


@dataclass(frozen=True)
class SignInCode:
    code: str
    to: str
    subject: str
    file: Path


def latest_sign_in_code(directory: Path, email: str | None) -> SignInCode | None:
    """The newest sign-in code mailed to ``email`` (anyone when None), or None."""
    if not directory.is_dir():
        return None
    wanted = email.strip().lower() if email else None
    # ``<epoch ms>-<id>.eml``: the names sort in sending order.
    for path in sorted(directory.glob("*.eml"), reverse=True):
        read = _read(path)
        if read is None:
            continue
        message, to, text = read
        if wanted is not None and wanted not in to.lower():
            continue
        found = _CODE.search(text)
        if found:
            return SignInCode(found.group(1), to, str(message.get("Subject", "")), path)
    return None


def _read(path: Path) -> tuple[EmailMessage, str, str] | None:
    """The message, its recipients and its text; None for a file that is no mail."""
    try:
        message = BytesParser(policy=default_policy).parsebytes(path.read_bytes())
        body = message.get_body(preferencelist=("plain", "html"))
        text = body.get_content() if body is not None else ""
    except Exception:  # noqa: BLE001 - a broken file is not a mail to read
        return None
    return message, str(message.get("To", "")), str(text)
