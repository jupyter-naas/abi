"""``Content-Disposition`` values that survive any filename.

Starlette encodes header values as latin-1, so ``filename="{name}"`` raises for
names outside it (macOS decomposed accents, emoji, CJK) and breaks the header on
quotes or line breaks. RFC 6266 sends an ASCII ``filename`` fallback plus the
exact name as RFC 5987 ``filename*``; browsers prefer the latter.
"""

from __future__ import annotations

import os
import re
import unicodedata
from urllib.parse import quote

# RFC 5987 attr-char punctuation; everything else is percent-encoded.
_ATTR_CHAR_SAFE = "!#$&+-.^_`|~"
_UNSAFE_FALLBACK = re.compile(r'["\\\x00-\x1f\x7f]')


def _ascii_fallback(filename: str) -> str:
    stem, ext = os.path.splitext(filename)

    def to_ascii(value: str) -> str:
        decomposed = unicodedata.normalize("NFKD", value)
        ascii_only = decomposed.encode("ascii", "ignore").decode("ascii")
        return _UNSAFE_FALLBACK.sub("_", ascii_only)

    ascii_stem = to_ascii(stem).strip()
    return f"{ascii_stem or 'download'}{to_ascii(ext)}"


def content_disposition(disposition: str, filename: str) -> str:
    """``inline``/``attachment`` header value for ``filename``, ASCII-only."""
    fallback = _ascii_fallback(filename)
    header = f'{disposition}; filename="{fallback}"'
    if fallback == filename:
        return header
    return f"{header}; filename*=UTF-8''{quote(filename, safe=_ATTR_CHAR_SAFE)}"
