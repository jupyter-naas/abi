"""The Nexus web images run a supported Node LTS, pinned by digest; the release
image serves as the `node` user."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
FROM = re.compile(r"^FROM node:(\d+)\.\d+\.\d+-alpine@sha256:[0-9a-f]{64}$", re.MULTILINE)
# Node majors past their end of life.
END_OF_LIFE = {16, 18, 20, 21, 23, 25}


@pytest.mark.parametrize("name", ["Dockerfile", "Dockerfile.release"])
def test_nexus_image_keeps_a_supported_node_pinned_by_digest(name: str) -> None:
    text = (HERE / name).read_text()
    froms = [line for line in text.splitlines() if line.startswith("FROM ")]
    assert len(froms) == 1
    match = FROM.match(froms[0])
    assert match, froms[0]
    major = int(match.group(1))
    assert major % 2 == 0 and major >= 24 and major not in END_OF_LIFE
    assert "pnpm@latest" not in text


def test_nexus_release_image_keeps_its_server_off_root() -> None:
    text = (HERE / "Dockerfile.release").read_text()
    users = re.findall(r"^USER (\S+)$", text, re.MULTILINE)
    assert users == ["node"]
    # Set before the server's settings and command, after the build.
    assert text.index("USER node") > text.index("RUN pnpm build")
    assert text.index("USER node") < text.index("ENTRYPOINT")
    # The entrypoint writes the runtime config: the one file `node` owns there.
    assert "chown node:node public/runtime-config.js .next/cache" in text
