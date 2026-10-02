"""Source control as a tree: owners, then repositories, then files and folders.

Ids are ``owner``, ``owner/repo`` and ``owner/repo/path`` (the path inside the
repository, on its default branch). Wraps the engine's ``SourceControlService``
(sync, so calls run in a worker thread). Files are read, downloaded, written
(one commit per write) and deleted (one commit); a repository is deleted whole.
Commits made here name the Nexus System app as their author.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, TypeVar

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    Action,
    InvalidResource,
    ResourceCapabilities,
    ResourceDetail,
    ResourceEntry,
    ResourceNotFound,
    ResourcePage,
    ResourceTooLarge,
    UnsupportedOperation,
    paginate,
    text_preview,
)
from naas_abi_core.services.source_control.SourceControlPorts import (
    AccessDeniedError,
    BranchNotFoundError,
    ContentEntry,
    FileWrite,
    Repo,
    RepoNotFoundError,
    SourceControlError,
    ValidationError,
)

SERVICE = "source_control"
AUTHOR = "Nexus System app"
FILE_ACTIONS: tuple[Action, ...] = ("read", "download", "write", "delete")
REPO_ACTIONS: tuple[Action, ...] = ("delete",)

T = TypeVar("T")


def _parts(resource_id: str) -> tuple[str, str, str]:
    """(owner, repo, path); missing levels are ``""``."""
    owner, _, rest = resource_id.partition("/")
    repo, _, path = rest.partition("/")
    return owner, repo, path


def _matches(name: str, query: str | None) -> bool:
    return not query or query.lower() in name.lower()


def _validate(resource_id: str) -> str:
    if (
        resource_id.startswith("/")
        or resource_id.endswith("/")
        or any(p in ("", ".", "..") for p in resource_id.split("/"))
        or "\\" in resource_id
        or "\x00" in resource_id
    ):
        raise InvalidResource(SERVICE, f"invalid path {resource_id!r}")
    return resource_id


class SourceControlResources:
    service = SERVICE
    # Search filters what the forge already returned for the listing: no extra calls.
    capabilities = ResourceCapabilities(
        browse=True,
        create=True,
        write_format="File content. Each write is one commit on the default branch.",
        search=True,
    )

    def __init__(self, source_control: Any) -> None:
        self._sc = source_control

    # --- error mapping -----------------------------------------------------------------

    def _guard(self, resource_id: str, call: Callable[[], T]) -> T:
        try:
            return call()
        except (RepoNotFoundError, BranchNotFoundError):
            raise ResourceNotFound(SERVICE, resource_id) from None
        except NotImplementedError as exc:
            raise UnsupportedOperation(SERVICE, str(exc) or "this operation") from exc
        except ValidationError as exc:
            raise InvalidResource(SERVICE, str(exc) or "rejected by the forge") from exc
        except AccessDeniedError as exc:
            raise SourceUnavailable(SERVICE, f"access denied by the forge: {exc}") from exc
        except SourceControlError as exc:
            raise SourceUnavailable(SERVICE, str(exc) or type(exc).__name__) from exc

    # --- sync helpers, run in a worker thread -------------------------------------------

    def _repos(self) -> list[Repo]:
        return list(self._sc.list_repos())

    def _repo(self, owner: str, name: str, resource_id: str) -> Repo:
        for repo in self._repos():
            if repo.owner == owner and repo.name == name:
                return repo
        raise ResourceNotFound(SERVICE, resource_id)

    @staticmethod
    def _owner_entry(owner: str, repos: int) -> ResourceEntry:
        noun = "repository" if repos == 1 else "repositories"
        return ResourceEntry(
            owner,
            owner,
            "container",
            attributes={"repositories": str(repos), "summary": f"{repos} {noun}"},
        )

    @staticmethod
    def _repo_entry(repo: Repo) -> ResourceEntry:
        visibility = "private" if repo.private else "public"
        attributes = {
            "default_branch": repo.default_branch,
            "visibility": visibility,
            "empty": "yes" if repo.empty else "no",
        }
        if repo.html_url:
            attributes["url"] = repo.html_url
        if repo.description:
            attributes["description"] = repo.description
        attributes["summary"] = repo.description or " · ".join(
            p for p in (repo.default_branch, visibility, "empty" if repo.empty else "") if p
        )
        return ResourceEntry(
            f"{repo.owner}/{repo.name}",
            repo.name,
            "container",
            REPO_ACTIONS,
            modified=repo.updated_at,
            attributes=attributes,
        )

    @staticmethod
    def _content_entry(repo_id: str, entry: ContentEntry) -> ResourceEntry:
        resource_id = f"{repo_id}/{entry.path.strip('/')}"
        if entry.type == "dir":
            return ResourceEntry(resource_id, entry.name, "container")
        return ResourceEntry(resource_id, entry.name, "item", FILE_ACTIONS, size=entry.size)

    def _contents(self, repo: Repo, path: str) -> list[ContentEntry]:
        if repo.empty:
            return []
        repo_id = f"{repo.owner}/{repo.name}"
        return list(self._sc.list_contents(repo_id=repo_id, path=path))

    def _stat(self, resource_id: str) -> ResourceEntry:
        if resource_id == "":
            return ResourceEntry("", "", "container")
        _validate(resource_id)
        owner, name, path = _parts(resource_id)
        if not name:
            count = sum(1 for r in self._repos() if r.owner == owner)
            if count:
                return self._owner_entry(owner, count)
            raise ResourceNotFound(SERVICE, resource_id)
        repo = self._repo(owner, name, resource_id)
        if not path:
            return self._repo_entry(repo)
        parent, _, leaf = path.rpartition("/")
        for entry in self._contents(repo, parent):
            if entry.name == leaf:
                return self._content_entry(f"{owner}/{name}", entry)
        raise ResourceNotFound(SERVICE, resource_id)

    def _list(
        self, parent: str, cursor: str | None, limit: int, query: str | None = None
    ) -> ResourcePage:
        if parent == "":
            counts: dict[str, int] = {}
            for repo in self._repos():
                counts[repo.owner] = counts.get(repo.owner, 0) + 1
            entries = [
                self._owner_entry(o, n) for o, n in sorted(counts.items()) if _matches(o, query)
            ]
            return paginate(parent, entries, cursor, limit)
        container = self._stat(parent)
        if container.kind != "container":
            raise InvalidResource(SERVICE, f"{parent!r} is a file")
        owner, name, path = _parts(parent)
        if not name:
            repos = sorted(
                (r for r in self._repos() if r.owner == owner and _matches(r.name, query)),
                key=lambda r: r.name,
            )
            return paginate(parent, [self._repo_entry(r) for r in repos], cursor, limit)
        repo = self._repo(owner, name, parent)
        # Folders first, then files, each by name.
        listed = sorted(
            (e for e in self._contents(repo, path) if _matches(e.name, query)),
            key=lambda e: (e.type != "dir", e.name),
        )
        entries = [self._content_entry(f"{owner}/{name}", e) for e in listed]
        return paginate(parent, entries, cursor, limit)

    def _file(self, resource_id: str) -> tuple[ResourceEntry, bytes]:
        entry = self._stat(resource_id)
        if entry.kind != "item":
            raise InvalidResource(SERVICE, f"{resource_id!r} is not a file")
        owner, name, path = _parts(resource_id)
        content = self._sc.get_file(repo_id=f"{owner}/{name}", path=path)
        if content.data is not None:
            raw = content.data
        else:
            raw = (content.text or "").encode()
        return entry, raw

    def _read(self, resource_id: str) -> ResourceDetail:
        entry, raw = self._file(resource_id)
        return ResourceDetail(entry, text_preview(raw, max(entry.size or 0, len(raw))))

    def _download(self, resource_id: str, max_bytes: int) -> bytes:
        entry = self._stat(resource_id)
        if entry.kind == "item" and entry.size is not None and entry.size > max_bytes:
            raise ResourceTooLarge(SERVICE, resource_id, entry.size, max_bytes)
        _, raw = self._file(resource_id)
        if len(raw) > max_bytes:
            raise ResourceTooLarge(SERVICE, resource_id, len(raw), max_bytes)
        return raw

    def _write(self, resource_id: str, content: bytes) -> ResourceEntry:
        _validate(resource_id)
        owner, name, path = _parts(resource_id)
        if not path:
            raise InvalidResource(SERVICE, "only files can be written (owner/repo/path)")
        repo = self._repo(owner, name, resource_id)
        try:
            existing: ResourceEntry | None = self._stat(resource_id)
        except ResourceNotFound:
            existing = None
        if existing is not None and existing.kind != "item":
            raise InvalidResource(SERVICE, f"{resource_id!r} is a folder")
        try:
            body: str | bytes = content.decode("utf-8")
        except UnicodeDecodeError:
            body = content
        verb = "Update" if existing else "Create"
        self._sc.upsert_file(
            repo_id=f"{owner}/{name}",
            path=path,
            content=body,
            message=f"{verb} {path} from the Nexus System app",
            branch=repo.default_branch or "main",
            author_name=AUTHOR,
        )
        return self._stat(resource_id)

    def _delete(self, resource_id: str) -> None:
        entry = self._stat(resource_id)
        owner, name, path = _parts(resource_id)
        if entry.kind == "container":
            if name and not path:
                self._sc.delete_repo(repo_id=f"{owner}/{name}")
                return
            raise UnsupportedOperation(SERVICE, "delete a folder or an owner")
        repo = self._repo(owner, name, resource_id)
        self._sc.upsert_files(
            repo_id=f"{owner}/{name}",
            files=[FileWrite(path=path, content=b"", delete=True)],
            message=f"Delete {path} from the Nexus System app",
            branch=repo.default_branch or "main",
            author_name=AUTHOR,
        )

    # --- ServiceResources --------------------------------------------------------------

    async def _run(self, resource_id: str, call: Callable[[], T]) -> T:
        return await asyncio.to_thread(self._guard, resource_id, call)

    async def list(
        self, parent: str = "", *, cursor: str | None = None, limit: int = 100, **options: Any
    ) -> ResourcePage:
        query = options.get("query")
        return await self._run(parent, lambda: self._list(parent, cursor, limit, query))

    async def stat(self, resource_id: str) -> ResourceEntry:
        return await self._run(resource_id, lambda: self._stat(resource_id))

    async def read(self, resource_id: str, *, reveal: bool = False) -> ResourceDetail:
        return await self._run(resource_id, lambda: self._read(resource_id))

    async def download(self, resource_id: str, *, max_bytes: int) -> bytes:
        return await self._run(resource_id, lambda: self._download(resource_id, max_bytes))

    async def write(self, resource_id: str, content: bytes) -> ResourceEntry:
        return await self._run(resource_id, lambda: self._write(resource_id, content))

    async def delete(self, resource_id: str) -> None:
        await self._run(resource_id, lambda: self._delete(resource_id))
