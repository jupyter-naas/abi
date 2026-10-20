"""App projects: ports, records and errors.

An app project is a static app (``manifest.json`` plus HTML/CSS/JS, no build)
that a workspace creates or copies from a module app and edits in Nexus.

* ``AppProjectRepositoryPort``: the durable, versioned copy (a git branch).
* ``AppDraftStorePort``: the live working copy the editor, the preview and
  the Apps agent read and write between saves.
* ``ModuleAppSourcePort``: the module apps on disk that "Edit" duplicates.
* ``AppRepoPublisherPort``: submits a project to the app's source repository
  as a new branch for review.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any

BRANCH_PREFIX = "apps/"
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SEGMENT_RE = re.compile(r"[^a-zA-Z0-9._-]+")


class AppProjectError(Exception):
    """Base error for app projects."""


class AppProjectNotFoundError(AppProjectError):
    pass


class AppProjectExistsError(AppProjectError):
    pass


class AppFileError(AppProjectError):
    """A path or file the rules refuse (traversal, dotfile, secret, size)."""


class AppFileNotFoundError(AppProjectError):
    pass


class AppSubmitUnavailableError(AppProjectError):
    """Submitting needs a configured publisher (source repo + token)."""


def workspace_segment(workspace_id: str) -> str:
    seg = _SEGMENT_RE.sub("-", (workspace_id or "").strip()).strip("-._")
    if not seg:
        raise AppProjectError("Invalid workspace_id")
    return seg


@dataclass(frozen=True)
class AppProjectKey:
    workspace_id: str
    slug: str

    def __post_init__(self) -> None:
        if not SLUG_RE.match(self.slug or ""):
            raise AppProjectError("Slug must be lowercase kebab-case (a-z, 0-9, hyphens).")
        workspace_segment(self.workspace_id)

    @property
    def branch(self) -> str:
        return f"{BRANCH_PREFIX}{workspace_segment(self.workspace_id)}/{self.slug}"

    @property
    def root(self) -> str:
        """Repo directory holding exactly the app's files."""
        return f"apps/{workspace_segment(self.workspace_id)}/{self.slug}"

    @property
    def meta_path(self) -> str:
        """Project settings, beside (not inside) the app directory."""
        return f"{self.root}.project.json"


@dataclass(frozen=True)
class AppAuthor:
    user_id: str
    name: str
    email: str


@dataclass(frozen=True)
class AppFile:
    path: str
    size: int = 0


@dataclass(frozen=True)
class AppCommit:
    sha: str
    message: str
    author: str
    date: str | None = None


@dataclass(frozen=True)
class AppOrigin:
    """The module app a project was duplicated from."""

    app_id: str
    module_path: str
    app_name: str
    # Directory in the source repository, e.g. ``src/bob/apps/sheets/budget``.
    repo_path: str | None
    source_commit: str | None
    # "bundled" (``html:`` entry served by Nexus) or "external" (own site).
    kind: str
    url: str | None = None
    # Files copied at import: a submit only deletes what the user removed.
    imported_files: tuple[str, ...] = ()


@dataclass(frozen=True)
class AppSubmission:
    branch: str
    url: str | None
    commit_sha: str | None
    pull_request_url: str | None = None
    target_path: str = ""
    submitted_at: str | None = None


@dataclass
class AppProjectMeta:
    slug: str
    workspace_id: str
    title: str
    description: str = ""
    icon_emoji: str = ""
    created_by: str = ""
    updated_at: str | None = None
    archived: bool = False
    origin: AppOrigin | None = None
    submission: AppSubmission | None = None

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        if self.origin is not None:
            data["origin"]["imported_files"] = list(self.origin.imported_files)
        return data

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> AppProjectMeta:
        origin_raw = data.get("origin")
        origin = None
        if isinstance(origin_raw, dict) and origin_raw.get("app_id"):
            origin = AppOrigin(
                app_id=str(origin_raw["app_id"]),
                module_path=str(origin_raw.get("module_path") or ""),
                app_name=str(origin_raw.get("app_name") or ""),
                repo_path=origin_raw.get("repo_path") or None,
                source_commit=origin_raw.get("source_commit") or None,
                kind=str(origin_raw.get("kind") or "bundled"),
                url=origin_raw.get("url") or None,
                imported_files=tuple(origin_raw.get("imported_files") or ()),
            )
        submission_raw = data.get("submission")
        submission = None
        if isinstance(submission_raw, dict) and submission_raw.get("branch"):
            submission = AppSubmission(
                branch=str(submission_raw["branch"]),
                url=submission_raw.get("url") or None,
                commit_sha=submission_raw.get("commit_sha") or None,
                pull_request_url=submission_raw.get("pull_request_url") or None,
                target_path=str(submission_raw.get("target_path") or ""),
                submitted_at=submission_raw.get("submitted_at") or None,
            )
        return cls(
            slug=str(data.get("slug") or ""),
            workspace_id=str(data.get("workspace_id") or ""),
            title=str(data.get("title") or data.get("slug") or ""),
            description=str(data.get("description") or ""),
            icon_emoji=str(data.get("icon_emoji") or ""),
            created_by=str(data.get("created_by") or ""),
            updated_at=data.get("updated_at") or None,
            archived=bool(data.get("archived")),
            origin=origin,
            submission=submission,
        )


@dataclass(frozen=True)
class AppIssue:
    level: str  # "error" | "warning" | "info"
    message: str
    path: str | None = None


@dataclass
class AppProjectInfo:
    meta: AppProjectMeta
    branch: str
    root: str
    entry: str | None
    dirty: bool = False
    commit_sha: str | None = None
    files: list[AppFile] = field(default_factory=list)


@dataclass(frozen=True)
class ModuleAppSource:
    origin: AppOrigin
    manifest: dict[str, Any]
    files: dict[str, bytes]
    # Paths left out of the copy (dotfiles, node_modules, secrets, oversize).
    skipped: tuple[str, ...] = ()


class AppProjectRepositoryPort(ABC):
    @abstractmethod
    def list_projects(self, workspace_id: str) -> list[tuple[str, str]]:
        """``(slug, head_sha)`` of every project branch of the workspace."""

    @abstractmethod
    def create(self, key: AppProjectKey) -> None:
        """Create the project branch. Raises ``AppProjectExistsError``."""

    @abstractmethod
    def read_meta(self, key: AppProjectKey) -> dict[str, Any] | None: ...

    @abstractmethod
    def head(self, key: AppProjectKey) -> str | None: ...

    @abstractmethod
    def read_files(self, key: AppProjectKey) -> dict[str, bytes]:
        """Every file of the saved app, keyed by path relative to ``key.root``."""

    @abstractmethod
    def commit(
        self,
        key: AppProjectKey,
        *,
        writes: dict[str, bytes],
        deletes: list[str],
        meta: dict[str, Any] | None,
        message: str,
        author: AppAuthor,
    ) -> str:
        """One commit on the project branch; returns its sha."""

    @abstractmethod
    def history(self, key: AppProjectKey, limit: int = 20) -> list[AppCommit]: ...


class AppDraftStorePort(ABC):
    """Working copy per project, shared by the workspace's editors and agent."""

    @abstractmethod
    def read_state(self, key: AppProjectKey) -> dict[str, Any] | None:
        """``None`` until the draft is hydrated from the repository."""

    @abstractmethod
    def write_state(self, key: AppProjectKey, state: dict[str, Any]) -> None: ...

    @abstractmethod
    def list_files(self, key: AppProjectKey) -> list[AppFile]: ...

    @abstractmethod
    def read_file(self, key: AppProjectKey, path: str) -> bytes | None: ...

    @abstractmethod
    def write_file(self, key: AppProjectKey, path: str, data: bytes) -> None: ...

    @abstractmethod
    def delete_file(self, key: AppProjectKey, path: str) -> None: ...

    @abstractmethod
    def clear(self, key: AppProjectKey) -> None:
        """Drop the files and the state (discard back to the saved copy)."""

    @abstractmethod
    def replace_all(self, key: AppProjectKey, files: dict[str, bytes]) -> None:
        """Clear, then write every file in one pass (seed and hydrate)."""


class ModuleAppSourcePort(ABC):
    @abstractmethod
    def get(self, app_id: str) -> ModuleAppSource | None: ...

    @abstractmethod
    def module_targets(self) -> dict[str, str]:
        """Module name -> repo directory where its new apps go (``.../apps``)."""


class AppRepoPublisherPort(ABC):
    @abstractmethod
    def describe(self) -> dict[str, Any]:
        """``{"configured": bool, "repo": str | None, "base_branch": str | None}``."""

    @abstractmethod
    def publish(
        self,
        *,
        branch: str,
        target_path: str,
        writes: dict[str, bytes],
        deletes: list[str],
        message: str,
        author: AppAuthor,
        title: str,
        body: str,
    ) -> AppSubmission:
        """Create ``branch`` from the base branch with one commit under ``target_path``."""
