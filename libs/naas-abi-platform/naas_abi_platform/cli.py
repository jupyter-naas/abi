"""``abi-platform`` — a thin client for the ABI platform data services.

Runs inside a coding workspace. Reads two env vars (exported by the workspace at
provision): ``ABI_API_BASE`` (e.g. ``http://abi:9879``) and ``ABI_TOKEN`` (the
per-user bearer token). Bytes stream directly workspace ⇄ storage — never through
an LLM.

    abi-platform storage ls [PREFIX]
    abi-platform storage cp ./big.bin remote:datasets/big.bin   # upload
    abi-platform storage cp remote:datasets/big.bin ./big.bin   # download

``--root`` operates on the whole datastore instead of just your namespace
(full, unscoped access — spans every tenant and the platform's own objects):

    abi-platform storage ls --root                 # list the datastore root
    abi-platform storage ls --root users           # list every tenant namespace
    abi-platform storage cp remote:naas_abi/x ./x --root
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
@click.option(
    "-r",
    "--root",
    is_flag=True,
    help="List from the datastore root (all namespaces), not just yours.",
)
def storage_ls(prefix: str, root: bool) -> None:
    """List objects under PREFIX (relative to your namespace, or --root)."""
    params: dict[str, object] = {"prefix": prefix}
    if root:
        params["root"] = "true"
    with _client() as client:
        resp = client.get(_PREFIX + "/storage/ls", params=params)
        _raise(resp)
        for item in resp.json().get("items", []):
            click.echo(item)


@storage.command("cp")
@click.argument("src")
@click.argument("dst")
@click.option(
    "-r",
    "--root",
    is_flag=True,
    help="Interpret the remote key against the datastore root, not your namespace.",
)
def storage_cp(src: str, dst: str, root: bool) -> None:
    """Copy between the workspace and object storage.

    Exactly one of SRC/DST is a remote path written as ``remote:<key>``.
    """
    src_remote, dst_remote = src.startswith(_REMOTE), dst.startswith(_REMOTE)
    if src_remote == dst_remote:
        raise click.ClickException(
            "exactly one of SRC/DST must be a remote path (remote:<key>)."
        )
    extra = {"root": "true"} if root else {}
    with _client() as client:
        if dst_remote:  # upload: local -> remote
            key = dst[len(_REMOTE) :]
            with open(src, "rb") as fileobj:
                resp = client.post(
                    _PREFIX + "/storage/upload",
                    params={"path": key, **extra},
                    content=_file_chunks(fileobj),
                )
            _raise(resp)
            click.echo(f"uploaded {src} -> remote:{key}")
        else:  # download: remote -> local
            key = src[len(_REMOTE) :]
            with client.stream(
                "GET", _PREFIX + "/storage/download", params={"path": key, **extra}
            ) as resp:
                if not resp.is_success:
                    resp.read()
                    _raise(resp)
                with open(dst, "wb") as fileobj:
                    for chunk in resp.iter_bytes(chunk_size=_CHUNK):
                        fileobj.write(chunk)
            click.echo(f"downloaded remote:{key} -> {dst}")


if __name__ == "__main__":
    main()
