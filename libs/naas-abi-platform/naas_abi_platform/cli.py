"""``abi-platform`` — a thin client for the ABI platform data services.

Runs inside a coding workspace. Reads two env vars (exported by the workspace at
provision): ``ABI_API_BASE`` (e.g. ``http://abi:9879``) and ``ABI_TOKEN`` (the
per-user bearer token). Bytes stream directly workspace ⇄ storage — never through
an LLM.

    abi-platform storage ls [PREFIX]
    abi-platform storage cp ./big.bin remote:datasets/big.bin   # upload
    abi-platform storage cp remote:datasets/big.bin ./big.bin   # download
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import BinaryIO, Optional

import click
import httpx

_REMOTE = "remote:"
_CHUNK = 1024 * 1024  # 1 MiB
_PREFIX = "/api/platform"

# Test hook: tests set this to an httpx.MockTransport so no network is needed.
_TEST_TRANSPORT: Optional[httpx.BaseTransport] = None


def _client() -> httpx.Client:
    base = os.environ.get("ABI_API_BASE", "").rstrip("/")
    token = os.environ.get("ABI_TOKEN", "")
    if not base:
        raise click.ClickException("ABI_API_BASE is not set.")
    if not token:
        raise click.ClickException("ABI_TOKEN is not set.")
    return httpx.Client(
        base_url=base,
        headers={"Authorization": f"Bearer {token}"},
        timeout=None,
        transport=_TEST_TRANSPORT,
    )


def _raise(resp: httpx.Response) -> None:
    if resp.is_success:
        return
    detail = ""
    try:
        detail = str(resp.json().get("detail", ""))
    except Exception:  # noqa: BLE001 - non-JSON error body
        detail = resp.text[:200]
    raise click.ClickException(f"{resp.status_code}: {detail}")


def _file_chunks(fileobj: BinaryIO) -> Iterator[bytes]:
    while True:
        chunk = fileobj.read(_CHUNK)
        if not chunk:
            break
        yield chunk


@click.group()
def main() -> None:
    """ABI platform client (workspace-facing)."""


@main.group()
def storage() -> None:
    """Object storage: list and copy files."""


@storage.command("ls")
@click.argument("prefix", default="")
def storage_ls(prefix: str) -> None:
    """List objects under PREFIX (relative to your namespace)."""
    with _client() as client:
        resp = client.get(_PREFIX + "/storage/ls", params={"prefix": prefix})
        _raise(resp)
        for item in resp.json().get("items", []):
            click.echo(item)


@storage.command("cp")
@click.argument("src")
@click.argument("dst")
def storage_cp(src: str, dst: str) -> None:
    """Copy between the workspace and object storage.

    Exactly one of SRC/DST is a remote path written as ``remote:<key>``.
    """
    src_remote, dst_remote = src.startswith(_REMOTE), dst.startswith(_REMOTE)
    if src_remote == dst_remote:
        raise click.ClickException(
            "exactly one of SRC/DST must be a remote path (remote:<key>)."
        )
    with _client() as client:
        if dst_remote:  # upload: local -> remote
            key = dst[len(_REMOTE) :]
            with open(src, "rb") as fileobj:
                resp = client.post(
                    _PREFIX + "/storage/upload", params={"path": key}, content=_file_chunks(fileobj)
                )
            _raise(resp)
            click.echo(f"uploaded {src} -> remote:{key}")
        else:  # download: remote -> local
            key = src[len(_REMOTE) :]
            with client.stream("GET", _PREFIX + "/storage/download", params={"path": key}) as resp:
                if not resp.is_success:
                    resp.read()
                    _raise(resp)
                with open(dst, "wb") as fileobj:
                    for chunk in resp.iter_bytes(chunk_size=_CHUNK):
                        fileobj.write(chunk)
            click.echo(f"downloaded remote:{key} -> {dst}")


if __name__ == "__main__":
    main()
