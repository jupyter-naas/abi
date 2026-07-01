"""Platform data-services API for coding workspaces.

Exposes the engine's object storage (KG / vector / KV to follow) so code and the
``abi-platform`` CLI running *inside a workspace* can move data directly —
without routing the bytes through an LLM's context. Auth is the same per-user
workspace bearer token the OpenAI shim uses. Every key is namespaced under
``users/<user id>/`` so one workspace can never read or write another's objects.

A ``root`` flag lifts that scoping to the whole datastore (all tenants *and*
platform-internal objects) — i.e. full, unscoped access. It is intentionally
UNGATED for now (single-operator dev); to lock it down for multi-tenant use,
gate ``_scope_base`` on ``current_user.is_superadmin`` (a ``require_superadmin``
dependency already exists in the auth adapter).

The domain service (``engine.services.object_storage``) is synchronous, so calls
run in a threadpool; downloads stream 1 MiB at a time so a multi-GB object never
buffers in memory.
"""

from __future__ import annotations

import pathlib
import posixpath
import tempfile
from collections.abc import Iterator
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import PlainTextResponse, StreamingResponse
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)

router = APIRouter(dependencies=[Depends(get_current_user_required)])

_CHUNK = 1024 * 1024  # 1 MiB


def _get_object_storage(request: Request):  # noqa: ANN202 - domain service, dynamically typed
    """Resolve the engine's object-storage service (cached on app state)."""
    svc = getattr(request.app.state, "object_storage", None)
    if svc is not None:
        return svc
    try:
        from naas_abi import ABIModule  # noqa: PLC0415

        svc = ABIModule.get_instance().engine.services.object_storage
        request.app.state.object_storage = svc
        return svc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail="Object storage is not initialized."
        ) from exc


def _tenant_root(user: User) -> str:
    """The per-user namespace every key is confined to."""
    return f"users/{user.id}"


def _scope_base(current_user: User, root: bool) -> str:
    """The prefix every key in this request is confined to.

    Per-user (``users/<id>``) by default. When ``root`` is set, operate on the
    datastore root instead — spanning every tenant's namespace *and* the
    platform's own objects. That is full, unscoped access; it is intentionally
    UNGATED for now (single-operator dev). To restrict it later, require
    ``current_user.is_superadmin`` here (raise 403 otherwise) — the
    ``require_superadmin`` dependency in the auth adapter does exactly that.

    Returning ``""`` maps to the object-storage ``base_prefix`` root (e.g.
    ``abi/datastore/``); the adapter always prepends ``base_prefix`` and
    ``_safe_rel`` neutralizes ``..``, so a key can never escape the datastore.
    """
    if root:
        return ""
    return _tenant_root(current_user)


def _safe_rel(path: str) -> str:
    """Normalize a client path and reject traversal / absolute escapes.

    ``posixpath.normpath`` resolves any ``..`` within the client-relative space,
    and the tenant root is prepended afterwards, so a key can never escape it.
    """
    p = posixpath.normpath("/" + path.strip()).lstrip("/")
    if not p or p == ".":
        raise HTTPException(status_code=400, detail="A path is required.")
    return p


@router.get("/storage/ls")
async def storage_ls(
    request: Request,
    prefix: str = Query(default=""),
    root: bool = Query(default=False),
    current_user: User = Depends(get_current_user_required),
) -> dict:
    """List object keys under ``prefix``.

    Scoped to the caller's ``users/<id>/`` namespace by default; with ``root``,
    lists from the datastore root across every namespace (see ``_scope_base``).
    Keys come back relative to the scope base.
    """
    storage = _get_object_storage(request)
    base = _scope_base(current_user, root)
    rel = _safe_rel(prefix) if prefix.strip() else ""
    scoped_prefix = posixpath.join(base, rel).strip("/")  # "" => datastore root
    try:
        keys = await run_in_threadpool(storage.list_objects, scoped_prefix)
    except Exception:  # noqa: BLE001 - absent/empty prefix -> empty listing
        keys = []
    strip = base + "/" if base else ""
    items = [k[len(strip) :] if strip and k.startswith(strip) else k for k in keys]
    return {"items": sorted(items)}


@router.get("/storage/download")
async def storage_download(
    request: Request,
    path: str = Query(..., min_length=1),
    root: bool = Query(default=False),
    current_user: User = Depends(get_current_user_required),
) -> StreamingResponse:
    """Stream an object back to the caller (1 MiB chunks; never buffered whole).

    ``path`` is relative to the caller's namespace, or the datastore root when
    ``root`` is set (see ``_scope_base``).
    """
    storage = _get_object_storage(request)
    scoped = posixpath.join(_scope_base(current_user, root), _safe_rel(path))
    obj_prefix, _, key = scoped.rpartition("/")
    if not key:
        raise HTTPException(status_code=400, detail="A file key is required.")
    # Surface a missing object as a clean 404 *before* the stream starts.
    try:
        await run_in_threadpool(storage.get_object_metadata, obj_prefix, key)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=f"Not found: {path}") from exc

    def _iter() -> Iterator[bytes]:
        with storage.get_object_stream(obj_prefix, key) as fh:
            while True:
                chunk = fh.read(_CHUNK)
                if not chunk:
                    break
                yield chunk

    filename = posixpath.basename(key)
    return StreamingResponse(
        _iter(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/storage/upload")
async def storage_upload(
    request: Request,
    path: str = Query(..., min_length=1),
    root: bool = Query(default=False),
    current_user: User = Depends(get_current_user_required),
) -> dict:
    """Stream the request body into an object at ``path``.

    Written to the caller's namespace by default, or anywhere under the datastore
    root when ``root`` is set (see ``_scope_base``). The body is spooled to a temp
    file (memory-safe — it spills to disk for large uploads) and then streamed to
    object storage. A true request→storage pipe (no temp file) is a later
    optimization.
    """
    storage = _get_object_storage(request)
    rel = _safe_rel(path)
    scoped = posixpath.join(_scope_base(current_user, root), rel)
    obj_prefix, _, key = scoped.rpartition("/")
    if not key:
        raise HTTPException(status_code=400, detail="A file key is required.")

    spool = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)
    try:
        async for chunk in request.stream():
            spool.write(chunk)
        spool.seek(0)
        await run_in_threadpool(storage.put_object_stream, obj_prefix, key, spool)
    finally:
        spool.close()
    return {"ok": True, "path": rel}


@lru_cache(maxsize=1)
def _cli_source() -> str:
    """The abi-platform CLI as a standalone, shebang'd script.

    The workspace installs it by curling this endpoint (there's no package index
    and the abi source isn't cloned into the workspace). The CLI is a single
    self-contained file, so serving it verbatim keeps it in sync with the repo.
    """
    for parent in pathlib.Path(__file__).resolve().parents:
        for cand in (
            parent / "naas-abi-platform" / "naas_abi_platform" / "cli.py",
            parent / "libs" / "naas-abi-platform" / "naas_abi_platform" / "cli.py",
        ):
            if cand.is_file():
                return "#!/usr/bin/env python3\n" + cand.read_text()
    raise HTTPException(status_code=500, detail="abi-platform CLI source not found.")


@router.get("/cli")
async def platform_cli(
    current_user: User = Depends(get_current_user_required),
) -> PlainTextResponse:
    """Serve the abi-platform CLI script (for the workspace to install)."""
    return PlainTextResponse(_cli_source())
