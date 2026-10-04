"""Remove credentials from text before it leaves the process as telemetry.

Exception messages and stack traces end up on spans (and so in Jaeger, a second
copy of the logs). A provider's 401 often quotes the key, a database error the
DSN. ``scrub_secrets`` replaces the credential itself with ``[REDACTED]`` and
keeps the rest of the message readable. Stdlib only; core and Nexus use it too.
"""

from __future__ import annotations

import re

REDACTED = "[REDACTED]"

# The value of a key=value or key: value pair, unless already redacted.
_VALUE = r"(?!\[REDACTED\])[^\s&,;\"'}\]]+"
# Names whose value is a credential, as words: api_key, access_token,
# client_secret, X-Amz-Signature, aws_secret_access_key, password...
_SECRET_NAME = (
    r"(?:[a-z0-9]+[_-])*(?:api[_-]?key|apikey|access[_-]?key|secret[_-]?key"
    r"|private[_-]?key|token|secret|password|passwd|pwd|signature|credential)"
)

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # scheme://user:password@host -> scheme://[REDACTED]@host
    (
        re.compile(r"\b([a-zA-Z][a-zA-Z0-9+.\-]*://)[^\s/@:]+:[^\s/@]+@"),
        rf"\1{REDACTED}@",
    ),
    # Authorization: [scheme] <credentials>
    (
        re.compile(
            r"(?i)(\bauthorization[\"']?\s*[:=]\s*[\"']?"
            r"(?:(?:bearer|basic|token|digest)\s+)?)" + _VALUE
        ),
        rf"\1{REDACTED}",
    ),
    (re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9\-._~+/]+=*"), rf"\1 {REDACTED}"),
    # JSON web tokens (NATS service tokens are JWTs).
    (
        re.compile(r"\beyJ[A-Za-z0-9_\-]{5,}\.eyJ[A-Za-z0-9_\-]{5,}\.[A-Za-z0-9_\-]*"),
        REDACTED,
    ),
    # Provider key shapes.
    (
        re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"),
        REDACTED,
    ),  # OpenAI, OpenRouter, Anthropic
    (re.compile(r"\b[sr]k_(?:live|test)_[A-Za-z0-9]{10,}"), REDACTED),  # Stripe
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"), REDACTED),  # GitHub tokens
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"), REDACTED),
    (re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"), REDACTED),  # AWS access key ids
    (re.compile(r"\bxox[abposr]-[A-Za-z0-9\-]{10,}"), REDACTED),  # Slack
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}"), REDACTED),  # Google API keys
    # key=value (query strings, form bodies); a bare "key" only with "=".
    (
        re.compile(rf"(?i)(\b(?:{_SECRET_NAME}|key)\s*=\s*[\"']?){_VALUE}"),
        rf"\1{REDACTED}",
    ),
    # name: value and "name": "value" (headers, JSON, YAML).
    (
        re.compile(rf"(?i)([\"']?\b{_SECRET_NAME}[\"']?\s*:\s*[\"']?){_VALUE}"),
        rf"\1{REDACTED}",
    ),
]


def scrub_secrets(text: str) -> str:
    """``text`` with credentials replaced by ``[REDACTED]``."""
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text
