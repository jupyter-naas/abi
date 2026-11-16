"""Read a LinkedIn ``Connections.csv`` (from a member's data export).

Moved here from ``applications.linkedin`` with the connections pipeline that
uses it: turning an export into acts of connection is the people module's
work, and the LinkedIn application is a remote module now.
"""

from __future__ import annotations

import csv
import io

CONNECTIONS_COLUMNS = (
    "First Name",
    "Last Name",
    "URL",
    "Email Address",
    "Company",
    "Position",
    "Connected On",
)


def read_connections_csv(content: bytes) -> list[dict[str, str]]:
    """The rows of a LinkedIn ``Connections.csv``, from its bytes.

    LinkedIn puts a "Notes:" preamble above the header, so the header is found
    rather than assumed to be the first line. Values are stripped; a missing
    column reads as an empty string. Raises ``ValueError`` when no header is found.
    """
    text = None
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError("Connections.csv is not UTF-8 or Latin-1 text")
    lines = text.splitlines()
    start = next(
        (
            index
            for index, line in enumerate(lines)
            if line.startswith("First Name,") and "URL" in line
        ),
        None,
    )
    if start is None:
        raise ValueError("Connections.csv has no 'First Name,...,URL' header row")
    reader = csv.DictReader(io.StringIO("\n".join(lines[start:])))
    return [
        {column: (row.get(column) or "").strip() for column in CONNECTIONS_COLUMNS}
        for row in reader
        if any(
            (value or "").strip() for value in row.values() if isinstance(value, str)
        )
    ]
