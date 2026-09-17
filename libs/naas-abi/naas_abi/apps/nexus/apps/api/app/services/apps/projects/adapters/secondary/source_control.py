"""App projects on git: one branch per project in the Nexus coding repo.

Branch ``apps/<workspace>/<slug>``; the app's files under
``apps/<workspace>/<slug>/``; project settings in
``apps/<workspace>/<slug>.project.json``. Nexus writes with its service
token; users get no repo-wide write grant (Slides model).
"""

from __future__ import annotations

import json
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.apps.projects.port import (
    BRANCH_PREFIX,
    AppAuthor,
    AppCommit,
    AppProjectExistsError,
    AppProjectKey,
    AppProjectNotFoundError,
    AppProjectRepositoryPort,
    workspace_segment,
)
from naas_abi_core.services.source_control.SourceControlPorts import (
    BranchNameConflictError,
    FileWrite,
    RepoNotFoundError,
    SourceControlError,
)
from naas_abi_core.services.source_control.SourceControlService import (
    SourceControlService,
)


class AppProjectRepositoryGit(AppProjectRepositoryPort):
    def __init__(self, source_control: SourceControlService, repo_id: str) -> None:
        self.sc = source_control
        self.repo_id = repo_id

    def list_projects(self, workspace_id: str) -> list[tuple[str, str]]:
        prefix = f"{BRANCH_PREFIX}{workspace_segment(workspace_id)}/"
        out: list[tuple[str, str]] = []
        for branch in self.sc.list_branches(repo_id=self.repo_id):
            if not branch.name.startswith(prefix):
                continue
            slug = branch.name[len(prefix) :]
            if slug and "/" not in slug:
                out.append((slug, branch.commit_sha))
        return out

    def _default_branch(self) -> str:
        existing = [b.name for b in self.sc.list_branches(repo_id=self.repo_id)]
        default = "main"
        try:
            for repo in self.sc.list_repos():
                if f"{repo.owner}/{repo.name}" == self.repo_id and repo.default_branch:
                    default = repo.default_branch
                    break
        except SourceControlError:
            pass
        if default not in existing and existing:
            default = existing[0]
        return default

    def create(self, key: AppProjectKey) -> None:
        if any(b.name == key.branch for b in self.sc.list_branches(repo_id=self.repo_id)):
            raise AppProjectExistsError(f"App project {key.slug} already exists.")
        try:
            self.sc.create_branch(
                repo_id=self.repo_id, name=key.branch, from_ref=self._default_branch()
            )
        except BranchNameConflictError as exc:
            raise AppProjectExistsError(f"App project {key.slug} already exists.") from exc

    def read_meta(self, key: AppProjectKey) -> dict[str, Any] | None:
        try:
            content = self.sc.get_file(repo_id=self.repo_id, path=key.meta_path, ref=key.branch)
        except RepoNotFoundError:
            return None
        try:
            data = json.loads(content.text or "")
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    def head(self, key: AppProjectKey) -> str | None:
        for branch in self.sc.list_branches(repo_id=self.repo_id):
            if branch.name == key.branch:
                return branch.commit_sha
        return None

    def read_files(self, key: AppProjectKey) -> dict[str, bytes]:
        files: dict[str, bytes] = {}
        prefix = f"{key.root}/"
        pending = [key.root]
        seen: set[str] = set()
        while pending:
            directory = pending.pop()
            if directory in seen:
                continue
            seen.add(directory)
            try:
                entries = self.sc.list_contents(
                    repo_id=self.repo_id, path=directory, ref=key.branch
                )
            except RepoNotFoundError as exc:
                if directory == key.root:
                    raise AppProjectNotFoundError(key.slug) from exc
                continue
            for entry in entries:
                # Only the app directory: a listing never escapes key.root.
                if not entry.path.startswith(prefix) or entry.path[len(prefix) :] in files:
                    continue
                if entry.type == "dir":
                    pending.append(entry.path)
                    continue
                content = self.sc.get_file(repo_id=self.repo_id, path=entry.path, ref=key.branch)
                data = content.data
                if data is None:
                    data = (content.text or "").encode("utf-8")
                files[entry.path[len(key.root) + 1 :]] = data
        return files

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
        changes = [FileWrite(path=f"{key.root}/{p}", content=d) for p, d in writes.items()]
        changes += [FileWrite(path=f"{key.root}/{p}", content="", delete=True) for p in deletes]
        if meta is not None:
            changes.append(
                FileWrite(
                    path=key.meta_path,
                    content=json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
                )
            )
        commit = self.sc.upsert_files(
            repo_id=self.repo_id,
            files=changes,
            message=message,
            branch=key.branch,
            author_name=author.name or None,
            author_email=author.email or None,
        )
        return commit.sha

    def history(self, key: AppProjectKey, limit: int = 20) -> list[AppCommit]:
        return [
            AppCommit(sha=c.sha, message=c.message, author=c.author, date=c.date)
            for c in self.sc.list_commits(repo_id=self.repo_id, ref=key.branch, limit=limit)
        ]
