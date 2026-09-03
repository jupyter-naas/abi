from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import NoReturn

from naas_abi_core.services.source_control.SourceControlPorts import (
    Branch,
    BranchNameConflictError,
    BranchNotFoundError,
    Check,
    Comment,
    Commit,
    ContentEntry,
    Diff,
    FileContent,
    ISourceControlAdapter,
    MergeResult,
    Proposal,
    Repo,
    RepoNotFoundError,
    Review,
    SourceControlError,
    WorkflowRun,
)


def _git_env(author_name: str | None = None, author_email: str | None = None) -> dict[str, str]:
    env = os.environ.copy()
    if author_name:
        env["GIT_AUTHOR_NAME"] = author_name
        env["GIT_COMMITTER_NAME"] = author_name
    if author_email:
        env["GIT_AUTHOR_EMAIL"] = author_email
        env["GIT_COMMITTER_EMAIL"] = author_email
    return env


class LocalGitAdapter(ISourceControlAdapter):
    """Disk-backed git repos for local development (no Forgejo).

    Repositories live at ``{repos_root}/{owner}/{name}/`` as normal (non-bare)
    git checkouts. ``clone_url`` uses the ``file://`` scheme.
    """

    def __init__(self, *, repos_root: str) -> None:
        self._root = Path(repos_root).expanduser().resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        self._users: dict[str, str] = {}

    def _repo_path(self, repo_id: str) -> Path:
        owner, _, name = repo_id.partition("/")
        if not owner or not name:
            raise RepoNotFoundError(repo_id)
        return self._root / owner / name

    def _run(
        self,
        *args: str,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            env=env or os.environ.copy(),
            check=False,
        )
        if result.returncode != 0:
            message = (result.stderr or result.stdout or "git command failed").strip()
            raise SourceControlError(message)
        return result.stdout.strip()

    def _repo_exists(self, repo_id: str) -> bool:
        path = self._repo_path(repo_id)
        return (path / ".git").is_dir()

    def _resolve_ref(self, repo_id: str, ref: str | None) -> str:
        path = self._repo_path(repo_id)
        if not self._repo_exists(repo_id):
            raise RepoNotFoundError(repo_id)
        if ref:
            return ref
        return self._run("rev-parse", "--abbrev-ref", "HEAD", cwd=path)

    def _to_repo(self, repo_id: str) -> Repo:
        path = self._repo_path(repo_id)
        if not self._repo_exists(repo_id):
            raise RepoNotFoundError(repo_id)
        owner, _, name = repo_id.partition("/")
        default_branch = "main"
        try:
            default_branch = self._run("rev-parse", "--abbrev-ref", "HEAD", cwd=path)
        except SourceControlError:
            default_branch = "main"
        return Repo(
            id=repo_id,
            name=name,
            owner=owner,
            default_branch=default_branch,
            clone_url=path.as_uri(),
            html_url=path.as_uri(),
            private=True,
            empty=not any(path.iterdir()),
        )

    def _unsupported(self, feature: str) -> NoReturn:
        raise NotImplementedError(f"{feature} is not supported by the local_git adapter")

    def ensure_user(self, *, external_id: str, email: str, username: str) -> str:
        del email
        if username not in self._users:
            self._users[username] = external_id or username
        return self._users[username]

    def ensure_repo(
        self, *, owner: str, name: str, private: bool = True, auto_init: bool = True
    ) -> Repo:
        del private
        repo_id = f"{owner}/{name}"
        path = self._repo_path(repo_id)
        if not self._repo_exists(repo_id):
            path.mkdir(parents=True, exist_ok=True)
            self._run("init", "-b", "main", cwd=path)
            if auto_init:
                readme = path / "README.md"
                readme.write_text(f"# {name}\n", encoding="utf-8")
                env = _git_env("abi", "abi@local")
                self._run("add", "README.md", cwd=path, env=env)
                self._run("commit", "-m", "Initial commit", cwd=path, env=env)
        return self._to_repo(repo_id)

    def list_repos(self) -> list[Repo]:
        repos: list[Repo] = []
        if not self._root.is_dir():
            return repos
        for owner_dir in sorted(self._root.iterdir()):
            if not owner_dir.is_dir():
                continue
            for repo_dir in sorted(owner_dir.iterdir()):
                if not repo_dir.is_dir():
                    continue
                repo_id = f"{owner_dir.name}/{repo_dir.name}"
                if self._repo_exists(repo_id):
                    repos.append(self._to_repo(repo_id))
        return repos

    def add_collaborator(
        self, *, repo_id: str, username: str, permission: str = "write"
    ) -> None:
        del repo_id, username, permission

    def list_contents(
        self, *, repo_id: str, path: str = "", ref: str | None = None
    ) -> list[ContentEntry]:
        repo_path = self._repo_path(repo_id)
        if not self._repo_exists(repo_id):
            raise RepoNotFoundError(repo_id)
        ref_name = self._resolve_ref(repo_id, ref)
        tree_path = path.strip("/")
        args = ["ls-tree", "-l", ref_name, tree_path or "."]
        output = self._run(*args, cwd=repo_path)
        entries: list[ContentEntry] = []
        for line in output.splitlines():
            if not line.strip():
                continue
            meta, entry_path = line.split("\t", 1)
            parts = meta.split()
            if len(parts) < 4:
                continue
            mode = parts[0]
            size = int(parts[3]) if parts[3].isdigit() else 0
            entry_type = "dir" if mode.startswith("04") else "file"
            name = entry_path.rsplit("/", 1)[-1]
            entries.append(
                ContentEntry(name=name, path=entry_path, type=entry_type, size=size)
            )
        return sorted(entries, key=lambda entry: entry.name.lower())

    def get_file(
        self, *, repo_id: str, path: str, ref: str | None = None
    ) -> FileContent:
        repo_path = self._repo_path(repo_id)
        if not self._repo_exists(repo_id):
            raise RepoNotFoundError(repo_id)
        ref_name = self._resolve_ref(repo_id, ref)
        spec = f"{ref_name}:{path.lstrip('/')}"
        try:
            raw = subprocess.check_output(
                ["git", "show", spec],
                cwd=repo_path,
                stderr=subprocess.STDOUT,
            )
        except subprocess.CalledProcessError as exc:
            raise RepoNotFoundError(f"{repo_id}:{path}") from exc
        try:
            text = raw.decode("utf-8")
            is_binary = False
        except UnicodeDecodeError:
            text = None
            is_binary = True
        name = path.rsplit("/", 1)[-1]
        return FileContent(
            path=path,
            name=name,
            size=len(raw),
            text=text,
            is_binary=is_binary,
        )

    def upsert_file(
        self,
        *,
        repo_id: str,
        path: str,
        content: str,
        message: str,
        branch: str,
        author_name: str | None = None,
        author_email: str | None = None,
    ) -> Commit:
        repo_path = self._repo_path(repo_id)
        if not self._repo_exists(repo_id):
            raise RepoNotFoundError(repo_id)
        env = _git_env(author_name or "abi", author_email or "abi@local")
        self._run("checkout", branch, cwd=repo_path, env=env)
        target = repo_path / path.lstrip("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        self._run("add", path.lstrip("/"), cwd=repo_path, env=env)
        self._run("commit", "-m", message, cwd=repo_path, env=env)
        sha = self._run("rev-parse", "HEAD", cwd=repo_path, env=env)
        return Commit(sha=sha, message=message, author=author_name or "abi")

    def list_commits(
        self, *, repo_id: str, ref: str | None = None, limit: int = 20
    ) -> list[Commit]:
        repo_path = self._repo_path(repo_id)
        if not self._repo_exists(repo_id):
            raise RepoNotFoundError(repo_id)
        ref_name = self._resolve_ref(repo_id, ref)
        output = self._run(
            "log",
            ref_name,
            f"-n{limit}",
            "--pretty=format:%H%x09%s%x09%an%x09%ai",
            cwd=repo_path,
        )
        commits: list[Commit] = []
        for line in output.splitlines():
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            sha, message = parts[0], parts[1]
            author = parts[2] if len(parts) > 2 else ""
            date = parts[3] if len(parts) > 3 else None
            commits.append(
                Commit(sha=sha, message=message, author=author, date=date or None)
            )
        return commits

    def list_branches(self, *, repo_id: str) -> list[Branch]:
        repo_path = self._repo_path(repo_id)
        if not self._repo_exists(repo_id):
            raise RepoNotFoundError(repo_id)
        output = self._run(
            "for-each-ref",
            "--format=%(refname:short)\t%(objectname)",
            "refs/heads/",
            cwd=repo_path,
        )
        branches: list[Branch] = []
        for line in output.splitlines():
            if not line.strip():
                continue
            name, sha = line.split("\t", 1)
            branches.append(Branch(name=name, commit_sha=sha))
        return branches

    def create_branch(self, *, repo_id: str, name: str, from_ref: str) -> Branch:
        repo_path = self._repo_path(repo_id)
        if not self._repo_exists(repo_id):
            raise RepoNotFoundError(repo_id)
        existing = {branch.name for branch in self.list_branches(repo_id=repo_id)}
        if name in existing:
            raise BranchNameConflictError(name)
        self._run("branch", name, from_ref, cwd=repo_path)
        sha = self._run("rev-parse", name, cwd=repo_path)
        return Branch(name=name, commit_sha=sha)

    def delete_branch(self, *, repo_id: str, name: str) -> None:
        repo_path = self._repo_path(repo_id)
        if not self._repo_exists(repo_id):
            raise RepoNotFoundError(repo_id)
        existing = {branch.name for branch in self.list_branches(repo_id=repo_id)}
        if name not in existing:
            raise BranchNotFoundError(name)
        self._run("branch", "-D", name, cwd=repo_path)

    def get_diff(self, *, repo_id: str, base: str, head: str) -> Diff:
        del repo_id, base, head
        self._unsupported("get_diff")

    def create_proposal(
        self,
        *,
        repo_id: str,
        title: str,
        body: str,
        source_branch: str,
        target_branch: str,
        reviewers: list[str] | None = None,
    ) -> Proposal:
        del repo_id, title, body, source_branch, target_branch, reviewers
        self._unsupported("create_proposal")

    def list_proposals(self, *, repo_id: str, state: str = "open") -> list[Proposal]:
        del repo_id, state
        self._unsupported("list_proposals")

    def get_proposal(self, *, repo_id: str, number: int) -> Proposal:
        del repo_id, number
        self._unsupported("get_proposal")

    def get_proposal_diff(self, *, repo_id: str, number: int) -> Diff:
        del repo_id, number
        self._unsupported("get_proposal_diff")

    def list_proposal_commits(self, *, repo_id: str, number: int) -> list[Commit]:
        del repo_id, number
        self._unsupported("list_proposal_commits")

    def list_comments(self, *, repo_id: str, number: int) -> list[Comment]:
        del repo_id, number
        self._unsupported("list_comments")

    def list_reviews(self, *, repo_id: str, number: int) -> list[Review]:
        del repo_id, number
        self._unsupported("list_reviews")

    def add_comment(
        self,
        *,
        repo_id: str,
        number: int,
        body: str,
        path: str | None = None,
        line: int | None = None,
    ) -> Comment:
        del repo_id, number, body, path, line
        self._unsupported("add_comment")

    def submit_review(
        self, *, repo_id: str, number: int, event: str, body: str = ""
    ) -> Review:
        del repo_id, number, event, body
        self._unsupported("submit_review")

    def list_checks(self, *, repo_id: str, number: int) -> list[Check]:
        del repo_id, number
        self._unsupported("list_checks")

    def set_branch_protection(
        self,
        *,
        repo_id: str,
        branch: str,
        required_approvals: int,
        required_checks: list[str],
    ) -> None:
        del repo_id, branch, required_approvals, required_checks
        self._unsupported("set_branch_protection")

    def merge(self, *, repo_id: str, number: int, method: str = "merge") -> MergeResult:
        del repo_id, number, method
        self._unsupported("merge")

    def list_workflow_runs(self, *, repo_id: str, limit: int = 20) -> list[WorkflowRun]:
        del repo_id, limit
        self._unsupported("list_workflow_runs")

    def mint_git_token(self, *, user_id: str) -> str:
        del user_id
        return "local"
