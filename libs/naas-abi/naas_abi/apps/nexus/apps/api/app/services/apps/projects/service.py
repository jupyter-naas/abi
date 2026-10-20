"""AppProjectsService: create, edit, preview, save and submit static apps.

Domain rules only; storage sits behind the ports in ``port.py``:

* every edit (editor, Apps agent) lands in the draft working copy;
* ``save`` turns the draft's changes into one commit on the project branch;
* ``submit`` sends the saved app to its source repository as a new branch
  for review. An app duplicated from a module goes back to its own
  directory; only files the user removed are deleted there.
"""

from __future__ import annotations

import hashlib
import json
import posixpath
import re
import unicodedata
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.apps.projects.port import (
    SLUG_RE,
    AppAuthor,
    AppCommit,
    AppDraftStorePort,
    AppFile,
    AppFileError,
    AppFileNotFoundError,
    AppIssue,
    AppProjectError,
    AppProjectInfo,
    AppProjectKey,
    AppProjectMeta,
    AppProjectNotFoundError,
    AppProjectRepositoryPort,
    AppRepoPublisherPort,
    AppSubmission,
    AppSubmitUnavailableError,
    ModuleAppSourcePort,
    workspace_segment,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.starter import (
    starter_files,
)

MANIFEST = "manifest.json"
SUBMIT_BRANCH_PREFIX = "nexus-apps/"
DEFAULT_SUBMIT_MODULE = "bob"
# Path segments the HTTP adapter uses next to /{slug}.
RESERVED_SLUGS = frozenset({"import", "submit-config"})
_MAX_PATH = 200
_MAX_DEPTH = 10
_SKIPPED_DIRS = {"node_modules", "__pycache__"}
_SECRET_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".keystore", ".jks")
_SECRET_NAMES = re.compile(r"^(id_rsa|id_ed25519|id_ecdsa)(\.pub)?$")
_REF_RE = re.compile(r"""(?:src|href)\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def _reason_refused(path: str) -> str | None:
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return "Relative segments (., ..) and empty segments are not allowed."
    if any(part.startswith(".") for part in parts):
        return "Dotfiles and dot-directories (.env, .dev.vars, .git) stay out of apps."
    if any(part in _SKIPPED_DIRS for part in parts):
        return "Dependency and cache directories stay out of apps."
    name = parts[-1].lower()
    if name.endswith(_SECRET_SUFFIXES) or _SECRET_NAMES.match(name):
        return "Key and certificate files stay out of apps."
    return None


def normalize_app_path(path: str) -> str:
    """A safe path relative to the app root, or ``AppFileError``."""
    raw = (path or "").replace("\\", "/").strip()
    if any(ord(ch) < 32 for ch in raw):
        raise AppFileError("Path contains control characters.")
    while raw.startswith("./"):
        raw = raw[2:]
    clean = raw.lstrip("/")
    if not clean:
        raise AppFileError("Path is empty.")
    if len(clean) > _MAX_PATH or clean.count("/") >= _MAX_DEPTH:
        raise AppFileError("Path is too long or too deep.")
    reason = _reason_refused(clean)
    if reason:
        raise AppFileError(f"{path!r}: {reason}")
    return clean


def skipped_on_import(path: str) -> bool:
    """True for files an import leaves behind (secrets, tooling, caches)."""
    try:
        normalize_app_path(path)
    except AppFileError:
        return True
    return False


def slugify(title: str) -> str:
    ascii_title = unicodedata.normalize("NFKD", title or "").encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")
    return slug[:48].strip("-") or "app"


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _manifest_of(files: dict[str, bytes] | None, raw: bytes | None = None) -> dict:
    data = raw if raw is not None else (files or {}).get(MANIFEST)
    if data is None:
        return {}
    try:
        parsed = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def entry_for(manifest: dict[str, Any], paths: list[str]) -> str | None:
    """The HTML page the preview opens first."""
    url = str(manifest.get("url") or "")
    if url.startswith("html:"):
        target = url[len("html:") :].lstrip("/")
        if target in paths:
            return target
    if "index.html" in paths:
        return "index.html"
    pages = sorted(p for p in paths if p.endswith((".html", ".htm")))
    return pages[0] if pages else None


class AppProjectsService:
    max_file_bytes = 10 * 1024 * 1024
    max_project_bytes = 60 * 1024 * 1024
    max_files = 800

    def __init__(
        self,
        *,
        repository: AppProjectRepositoryPort,
        drafts: AppDraftStorePort,
        module_source: ModuleAppSourcePort | None = None,
        publisher: AppRepoPublisherPort | None = None,
        now: Callable[[], str] | None = None,
    ) -> None:
        self.repository = repository
        self.drafts = drafts
        self.module_source = module_source
        self.publisher = publisher
        self._now = now or (lambda: datetime.now(UTC).isoformat())

    # -- projects ---------------------------------------------------------------

    def list_projects(
        self, workspace_id: str, *, include_archived: bool = False
    ) -> list[AppProjectInfo]:
        out: list[AppProjectInfo] = []
        for slug, head in self.repository.list_projects(workspace_id):
            if not SLUG_RE.match(slug):
                continue
            key = AppProjectKey(workspace_id, slug)
            meta = self._meta_or_none(key)
            if meta is None or (meta.archived and not include_archived):
                continue
            state = self.drafts.read_state(key) or {}
            out.append(
                AppProjectInfo(
                    meta=meta,
                    branch=key.branch,
                    root=key.root,
                    entry=None,
                    dirty=bool(state.get("dirty")),
                    commit_sha=head,
                )
            )
        out.sort(key=lambda p: (p.meta.updated_at or "", p.meta.slug), reverse=True)
        return out

    def get_project(self, key: AppProjectKey) -> AppProjectInfo:
        meta = self._meta(key)
        state = self._ensure_draft(key)
        files = self.drafts.list_files(key)
        manifest = _manifest_of(None, self.drafts.read_file(key, MANIFEST))
        return AppProjectInfo(
            meta=meta,
            branch=key.branch,
            root=key.root,
            entry=entry_for(manifest, [f.path for f in files]),
            dirty=bool(state.get("dirty")),
            commit_sha=self.repository.head(key),
            files=files,
        )

    def create_project(
        self,
        workspace_id: str,
        *,
        title: str,
        author: AppAuthor,
        description: str = "",
        icon_emoji: str = "✨",
    ) -> AppProjectInfo:
        title = (title or "").strip() or "Untitled app"
        files = starter_files(
            title=title,
            description=description.strip(),
            icon_emoji=icon_emoji or "✨",
            author=author.name,
        )
        meta = AppProjectMeta(
            slug="",
            workspace_id=workspace_id,
            title=title,
            description=description.strip(),
            icon_emoji=icon_emoji or "✨",
            created_by=author.user_id,
        )
        return self._seed(workspace_id, meta, files, author, "feat(apps): create {slug}")

    def import_module_app(
        self,
        workspace_id: str,
        *,
        app_id: str,
        author: AppAuthor,
        title: str | None = None,
    ) -> AppProjectInfo:
        """Duplicate a module app into a new project (edit works like create)."""
        source = self.module_source.get(app_id) if self.module_source else None
        if source is None:
            raise AppProjectNotFoundError(f"Unknown module app: {app_id}")
        files = {
            normalize_app_path(path): data
            for path, data in source.files.items()
            if not skipped_on_import(path)
        }
        origin = replace(source.origin, imported_files=tuple(sorted(files)))
        name = str(source.manifest.get("name") or origin.app_name)
        meta = AppProjectMeta(
            slug="",
            workspace_id=workspace_id,
            title=(title or name).strip(),
            description=str(source.manifest.get("description") or ""),
            icon_emoji=str(source.manifest.get("icon_emoji") or ""),
            created_by=author.user_id,
            origin=origin,
        )
        return self._seed(
            workspace_id,
            meta,
            files,
            author,
            f"feat(apps): copy {app_id} into {{slug}}",
            preferred_slug=slugify(origin.app_name),
        )

    def update_project(
        self,
        key: AppProjectKey,
        *,
        author: AppAuthor,
        title: str | None = None,
        archived: bool | None = None,
    ) -> AppProjectMeta:
        meta = self._meta(key)
        if title is not None and title.strip():
            meta.title = title.strip()
        if archived is not None:
            meta.archived = bool(archived)
        meta.updated_at = self._now()
        self.repository.commit(
            key,
            writes={},
            deletes=[],
            meta=meta.to_json(),
            message=f"chore(apps): update {key.slug} settings",
            author=author,
        )
        return meta

    # -- files ------------------------------------------------------------------

    def list_files(self, key: AppProjectKey) -> list[AppFile]:
        self._meta(key)
        self._ensure_draft(key)
        return self.drafts.list_files(key)

    def read_file(self, key: AppProjectKey, path: str) -> bytes:
        clean = normalize_app_path(path)
        self._meta(key)
        self._ensure_draft(key)
        data = self.drafts.read_file(key, clean)
        if data is None:
            raise AppFileNotFoundError(clean)
        return data

    def write_file(self, key: AppProjectKey, path: str, content: bytes | str) -> AppFile:
        clean = normalize_app_path(path)
        data = content.encode("utf-8") if isinstance(content, str) else content
        if len(data) > self.max_file_bytes:
            raise AppFileError(f"{clean} is {len(data)} bytes; the limit is {self.max_file_bytes}.")
        self._meta(key)
        state = self._ensure_draft(key)
        files = self.drafts.list_files(key)
        others = [f for f in files if f.path != clean]
        if len(others) + 1 > self.max_files:
            raise AppFileError(f"An app holds at most {self.max_files} files.")
        if sum(f.size for f in others) + len(data) > self.max_project_bytes:
            raise AppFileError(
                f"An app holds at most {self.max_project_bytes // (1024 * 1024)} MB."
            )
        self.drafts.write_file(key, clean, data)
        self._mark_dirty(key, state)
        return AppFile(clean, len(data))

    def delete_file(self, key: AppProjectKey, path: str) -> None:
        clean = normalize_app_path(path)
        self._meta(key)
        state = self._ensure_draft(key)
        if self.drafts.read_file(key, clean) is None:
            raise AppFileNotFoundError(clean)
        self.drafts.delete_file(key, clean)
        self._mark_dirty(key, state)

    # -- versions ---------------------------------------------------------------

    def save(
        self, key: AppProjectKey, *, author: AppAuthor, message: str | None = None
    ) -> AppCommit | None:
        """Commit the draft's changes; ``None`` when there is nothing to save."""
        meta = self._meta(key)
        state = self._ensure_draft(key)
        saved: dict[str, str] = dict(state.get("saved") or {})
        current = {
            f.path: self.drafts.read_file(key, f.path) or b"" for f in self.drafts.list_files(key)
        }
        writes = {path: data for path, data in current.items() if saved.get(path) != _digest(data)}
        deletes = sorted(path for path in saved if path not in current)
        if not writes and not deletes:
            if state.get("dirty"):
                self.drafts.write_state(key, {**state, "dirty": False})
            return None
        meta.updated_at = self._now()
        commit_message = (message or "").strip() or f"feat(apps): update {key.slug}"
        sha = self.repository.commit(
            key,
            writes=writes,
            deletes=deletes,
            meta=meta.to_json(),
            message=commit_message,
            author=author,
        )
        self.drafts.write_state(
            key,
            {
                "base": sha,
                "saved": {path: _digest(data) for path, data in current.items()},
                "dirty": False,
            },
        )
        return AppCommit(sha=sha, message=commit_message, author=author.name)

    def discard(self, key: AppProjectKey) -> None:
        self._meta(key)
        self.drafts.clear(key)
        self._ensure_draft(key)

    def history(self, key: AppProjectKey, limit: int = 20) -> list[AppCommit]:
        self._meta(key)
        return self.repository.history(key, limit=limit)

    # -- preview and checks -------------------------------------------------------

    def entry(self, key: AppProjectKey) -> str | None:
        return self.get_project(key).entry

    def preview_file(self, key: AppProjectKey, path: str) -> tuple[bytes, str]:
        """``(content, path)``; an empty path serves the entry page."""
        target = (path or "").strip().lstrip("/")
        if not target or target.endswith("/"):
            entry = self.entry(key) if not target else None
            if entry is None and target:
                candidate = f"{target}index.html"
                return self.read_file(key, candidate), candidate
            if entry is None:
                raise AppFileNotFoundError("This app has no HTML page yet.")
            target = entry
        clean = normalize_app_path(target)
        return self.read_file(key, clean), clean

    def check(self, key: AppProjectKey) -> list[AppIssue]:
        self._meta(key)
        self._ensure_draft(key)
        paths = [f.path for f in self.drafts.list_files(key)]
        pathset = set(paths)
        issues: list[AppIssue] = []

        raw_manifest = self.drafts.read_file(key, MANIFEST)
        manifest: dict[str, Any] = {}
        if raw_manifest is None:
            issues.append(
                AppIssue("error", "manifest.json is missing: the Apps catalog needs it.", MANIFEST)
            )
        else:
            manifest = _manifest_of(None, raw_manifest)
            if not manifest:
                issues.append(AppIssue("error", "manifest.json is not a JSON object.", MANIFEST))
            elif not str(manifest.get("name") or "").strip():
                issues.append(AppIssue("error", 'manifest.json needs a "name".', MANIFEST))
        url = str(manifest.get("url") or "")
        if url.startswith("html:"):
            target = url[len("html:") :].lstrip("/")
            if target not in pathset:
                issues.append(
                    AppIssue(
                        "error",
                        f'manifest.json url points to "{target}", which does not exist.',
                        MANIFEST,
                    )
                )
        elif url.startswith(("http://", "https://")):
            issues.append(
                AppIssue(
                    "info",
                    f"This app is published as its own site ({url}); the Nexus "
                    "preview shows its static files.",
                    MANIFEST,
                )
            )
        elif manifest:
            issues.append(
                AppIssue(
                    "warning",
                    'manifest.json has no "url"; use "html:index.html" so Nexus can open it.',
                    MANIFEST,
                )
            )
        if entry_for(manifest, paths) is None:
            issues.append(AppIssue("error", "The app has no HTML page to open."))
        if any(p.startswith("functions/") for p in paths):
            issues.append(
                AppIssue(
                    "info",
                    "functions/ holds server code (Cloudflare Pages Functions); it "
                    "does not run in the Nexus preview.",
                    "functions/",
                )
            )

        for page in (p for p in paths if p.endswith((".html", ".htm"))):
            text = (self.drafts.read_file(key, page) or b"").decode("utf-8", "replace")
            base = posixpath.dirname(page)
            for ref in _REF_RE.findall(text):
                ref = ref.strip()
                if not ref or ref.startswith(("#", "//", "{{", "${")) or _SCHEME_RE.match(ref):
                    continue
                target = ref.split("#", 1)[0].split("?", 1)[0]
                if not target:
                    continue
                if target.startswith("/"):
                    issues.append(
                        AppIssue(
                            "warning",
                            f'"{ref}" is an absolute path; inside Nexus it does not '
                            "resolve to the app. Use a relative path.",
                            page,
                        )
                    )
                    continue
                resolved = posixpath.normpath(posixpath.join(base, target))
                if resolved.endswith("/") or resolved in pathset:
                    continue
                if f"{resolved}/index.html" in pathset:
                    continue
                issues.append(
                    AppIssue("warning", f'"{ref}" does not match a file in the app.', page)
                )
        return issues

    # -- submit -------------------------------------------------------------------

    def submit_config(self) -> dict[str, Any]:
        described = (
            self.publisher.describe()
            if self.publisher is not None
            else {"configured": False, "repo": None, "base_branch": None}
        )
        modules = sorted(self.module_source.module_targets()) if self.module_source else []
        return {**described, "modules": modules, "default_module": DEFAULT_SUBMIT_MODULE}

    def submit(
        self, key: AppProjectKey, *, author: AppAuthor, module: str | None = None
    ) -> AppSubmission:
        """Save, then open a review branch in the app's source repository."""
        if self.publisher is None or not self.publisher.describe().get("configured"):
            raise AppSubmitUnavailableError(
                "Submitting to the source repository is not configured on this "
                "platform. The project stays saved in Nexus."
            )
        self.save(key, author=author, message=f"feat(apps): {key.slug} ready for review")
        meta = self._meta(key)

        current = {
            f.path: self.drafts.read_file(key, f.path) or b"" for f in self.drafts.list_files(key)
        }
        if meta.origin is not None and meta.origin.repo_path:
            target_path = meta.origin.repo_path.strip("/")
            deletes = sorted(set(meta.origin.imported_files) - set(current))
            verb = f"update {meta.origin.app_name}"
        else:
            targets = self.module_source.module_targets() if self.module_source else {}
            chosen = module or DEFAULT_SUBMIT_MODULE
            if chosen not in targets:
                raise AppProjectError(
                    f"Unknown module {chosen!r}. Choose one of: {', '.join(sorted(targets))}."
                )
            target_path = f"{targets[chosen].strip('/')}/{key.slug}"
            deletes = []
            verb = f"add {key.slug}"

        branch = f"{SUBMIT_BRANCH_PREFIX}{workspace_segment(key.workspace_id)}/{key.slug}"
        body_lines = [
            f"Submitted from Nexus by {author.name} <{author.email}> for review.",
            "",
            f"- App: {meta.title}",
            f"- Target: `{target_path}`",
            f"- Nexus project: `{key.branch}`",
            f"- Files written: {len(current)}; files removed: {len(deletes)}",
        ]
        if meta.origin is not None:
            body_lines.append(
                f"- Copied from `{meta.origin.app_id}`"
                + (f" at `{meta.origin.source_commit[:12]}`" if meta.origin.source_commit else "")
            )
        submission = self.publisher.publish(
            branch=branch,
            target_path=target_path,
            writes=current,
            deletes=deletes,
            message=f"feat(apps): {verb} from Nexus",
            author=author,
            title=f"feat(apps): {verb} from Nexus",
            body="\n".join(body_lines),
        )
        submission = replace(submission, submitted_at=self._now(), target_path=target_path)
        meta.submission = submission
        meta.updated_at = self._now()
        self.repository.commit(
            key,
            writes={},
            deletes=[],
            meta=meta.to_json(),
            message=f"chore(apps): {key.slug} submitted as {branch}",
            author=author,
        )
        return submission

    # -- internals ----------------------------------------------------------------

    def _seed(
        self,
        workspace_id: str,
        meta: AppProjectMeta,
        files: dict[str, bytes],
        author: AppAuthor,
        message: str,
        preferred_slug: str | None = None,
    ) -> AppProjectInfo:
        if not files:
            raise AppFileError("Nothing to copy: the app has no files.")
        if sum(len(d) for d in files.values()) > self.max_project_bytes:
            raise AppFileError(
                f"The app is larger than {self.max_project_bytes // (1024 * 1024)} MB."
            )
        oversize = [p for p, d in files.items() if len(d) > self.max_file_bytes]
        if oversize:
            raise AppFileError(f"Files over the size limit: {', '.join(sorted(oversize))}")
        taken = {slug for slug, _ in self.repository.list_projects(workspace_id)}
        taken |= RESERVED_SLUGS
        base = preferred_slug or slugify(meta.title)
        slug = base
        n = 2
        while slug in taken:
            slug = f"{base}-{n}"
            n += 1
        key = AppProjectKey(workspace_id, slug)
        # A concurrent create of the same slug raises AppProjectExistsError.
        self.repository.create(key)
        meta.slug = slug
        meta.updated_at = self._now()
        sha = self.repository.commit(
            key,
            writes=files,
            deletes=[],
            meta=meta.to_json(),
            message=message.format(slug=slug),
            author=author,
        )
        self.drafts.replace_all(key, files)
        self.drafts.write_state(
            key,
            {
                "base": sha,
                "saved": {p: _digest(d) for p, d in files.items()},
                "dirty": False,
            },
        )
        return self.get_project(key)

    def _meta_or_none(self, key: AppProjectKey) -> AppProjectMeta | None:
        raw = self.repository.read_meta(key)
        if not raw:
            return None
        meta = AppProjectMeta.from_json(raw)
        # Workspace ids that sanitize to the same segment share a branch name;
        # the stored owner decides.
        if meta.workspace_id != key.workspace_id:
            return None
        meta.slug = meta.slug or key.slug
        return meta

    def _meta(self, key: AppProjectKey) -> AppProjectMeta:
        meta = self._meta_or_none(key)
        if meta is None:
            raise AppProjectNotFoundError(f"App project {key.slug} not found.")
        return meta

    def _ensure_draft(self, key: AppProjectKey) -> dict[str, Any]:
        state = self.drafts.read_state(key)
        if state is not None:
            return state
        files = self.repository.read_files(key)
        self.drafts.replace_all(key, files)
        state = {
            "base": self.repository.head(key),
            "saved": {p: _digest(d) for p, d in files.items()},
            "dirty": False,
        }
        self.drafts.write_state(key, state)
        return state

    def _mark_dirty(self, key: AppProjectKey, state: dict[str, Any]) -> None:
        if not state.get("dirty"):
            self.drafts.write_state(key, {**state, "dirty": True})
