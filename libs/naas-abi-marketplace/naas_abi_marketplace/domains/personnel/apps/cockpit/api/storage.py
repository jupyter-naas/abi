"""Read cockpit datasets from the committed ``web/data`` tree."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from naas_abi_marketplace.domains.personnel.apps.cockpit.paths import WEB_DATA


def data_root() -> Path:
    return WEB_DATA


def read_json(relative_path: str) -> dict[str, Any]:
    path = data_root() / relative_path
    if not path.is_file():
        raise FileNotFoundError(relative_path)
    return json.loads(path.read_text(encoding="utf-8"))
