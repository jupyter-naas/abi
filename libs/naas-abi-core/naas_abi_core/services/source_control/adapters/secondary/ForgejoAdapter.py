from __future__ import annotations

import base64
import re
import secrets
from typing import Any
from urllib.parse import quote

from naas_abi_core.services.source_control.SourceControlPorts import (
    AccessDeniedError,
    Branch,
    BranchNameConflictError,
    BranchNotFoundError,
    Commit,
    ContentEntry,
    FileContent,
    Check,
    CHECK_FAILURE,
    CHECK_PENDING,
    CHECK_SUCCESS,
    Comment,
    Diff,
    DiffFile,
    ISourceControlAdapter,
    MergeBlockedError,
    MergeConflictError,
    MergeResult,
    PROPOSAL_CLOSED,
    PROPOSAL_MERGED,
    PROPOSAL_OPEN,
    Proposal,
    ProposalNotFoundError,
    Repo,
    RepoNotFoundError,
    REVIEW_APPROVED,
    REVIEW_CHANGES_REQUESTED,
    REVIEW_COMMENT,
    REVIEW_PENDING,
    Review,
    SourceControlError,
    ValidationError,
)

# Forgejo/Gitea commit-status state -> normalized check state.
_CHECK_SUCCESS = {"success"}
_CHECK_FAILURE = {"failure", "error"}

# Forgejo/Gitea review type -> normalized review state.
_REVIEW_STATES = {
    "APPROVED": REVIEW_APPROVED,
    "REQUEST_CHANGES": REVIEW_CHANGES_REQUESTED,
    "COMMENT": REVIEW_COMMENT,
    "PENDING": REVIEW_PENDING,
}

# Normalized review event -> Forgejo/Gitea review event verb.
_REVIEW_EVENTS = {
    REVIEW_APPROVED: "APPROVED",
    "approve": "APPROVED",
    REVIEW_CHANGES_REQUESTED: "REQUEST_CHANGES",
    "request_changes": "REQUEST_CHANGES",
    REVIEW_COMMENT: "COMMENT",
}


class ForgejoAdapter(ISourceControlAdapter):
    """Secondary adapter for Forgejo/Gitea over its REST API (v1).

    Headless: a backend service holds the deployment admin token and acts on
    behalf of users. The ``session`` is injectable (anything with a
    ``requests``-style ``.request()``), so the adapter is unit-testable without
    a network. ``repo_id`` is the ``"owner/name"`` string.
    """

    def __init__(
        self,
        *,
        base_url: str,
        admin_token: str,
        organization: str = "",
        timeout: int = 30,
        session: Any | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._admin_token = admin_token
        self._organization = organization
        self._timeout = timeout
        self._session = session if session is not None else _default_session()

    # -- HTTP plumbing ------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        extra_headers: dict[str, str] | None = None,
        basic_auth: tuple[str, str] | None = None,
        raw: bool = False,
    ) -> Any:
        url = f"{self._base_url}/api/v1{path}"
        if basic_auth is not None:
            creds = f"{basic_auth[0]}:{basic_auth[1]}".encode()
            authorization = f"Basic {base64.b64encode(creds).decode()}"
        else:
            authorization = f"token {self._admin_token}"
        headers = {
            "Authorization": authorization,
            "Content-Type": "application/json",
            "Accept": "text/plain" if raw else "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)
        response = self._session.request(
            method, url, headers=headers, json=json, timeout=self._timeout
        )
        status = getattr(response, "status_code", 0)
        if status >= 400:
            self._raise_for_status(status, _safe_text(response), path)
        if raw:
            return getattr(response, "text", "") or ""
        if not getattr(response, "content", b""):
            return {}
        return response.json()

    @staticmethod
    def _raise_for_status(status: int, detail: str, path: str) -> None:
        if status in (401, 403):
            raise AccessDeniedError(detail or "access denied", status=status)
        if status == 404:
            if "/pulls/" in path or path.endswith("/pulls"):
                raise ProposalNotFoundError(detail or "proposal not found", status=status)
            if "/branches" in path:
                raise BranchNotFoundError(detail or "branch not found", status=status)
            raise RepoNotFoundError(detail or "repo not found", status=status)
        if status == 405:
            # The merge endpoint returns 405 when branch protection forbids the
            # merge (insufficient approvals / failing required checks / not ready).
            raise MergeBlockedError(detail or "merge blocked", status=status)
        if status == 409:
            # On the merge endpoint a 409 is a merge conflict; elsewhere (branch
            # creation) it is a branch-name conflict.
            if path.endswith("/merge"):
                raise MergeConflictError(detail or "merge conflict", status=status)
            raise BranchNameConflictError(detail or "name conflict", status=status)
        if status == 422:
            raise ValidationError(detail or "validation error", status=status)
        raise SourceControlError(
            f"Forgejo API request failed ({status}): {detail}", status=status
        )

    # -- Port implementation ------------------------------------------------

    def ensure_user(self, *, external_id: str, email: str, username: str) -> str:
        try:
            user = self._request("GET", f"/users/{username}")
            return str(user["id"])
        except SourceControlError as exc:
            if exc.status != 404:
                raise
        created = self._request(
            "POST",
            "/admin/users",
            json={
                "email": email,
                "username": username,
                # POST /admin/users requires a password even though the user
                # authenticates via minted git tokens, not this password.
                "password": secrets.token_urlsafe(32),
                "must_change_password": False,
            },
        )
        return str(created["id"])

    def ensure_repo(
        self, *, owner: str, name: str, private: bool = True, auto_init: bool = True
    ) -> Repo:
        try:
            repo = self._request("GET", f"/repos/{owner}/{name}")
            return self._to_repo(repo)
        except SourceControlError as exc:
            if exc.status != 404:
                raise
        created = self._request(
            "POST",
            f"/admin/users/{owner}/repos",
            json={"name": name, "private": private, "auto_init": auto_init},
        )
        return self._to_repo(created)

    def list_repos(self) -> list[Repo]:
        result = self._request("GET", "/repos/search?limit=100")
        items = result.get("data", []) if isinstance(result, dict) else result
        return [self._to_repo(r) for r in (items or [])]

    def add_collaborator(
        self, *, repo_id: str, username: str, permission: str = "write"
    ) -> None:
        # PUT is idempotent: Forgejo returns 204 whether or not the user is
        # already a collaborator. ``repo_id`` is "owner/name".
        self._request(
            "PUT",
            f"/repos/{repo_id}/collaborators/{username}",
            json={"permission": permission},
        )

    def list_contents(
        self, *, repo_id: str, path: str = "", ref: str | None = None
    ) -> list[ContentEntry]:
        query = f"?ref={quote(ref, safe='')}" if ref else ""
        result = self._request(
            "GET", f"/repos/{repo_id}/contents/{path.lstrip('/')}{query}"
        )
        items = result if isinstance(result, list) else [result]
        entries = [
            ContentEntry(
                name=e.get("name", ""),
                path=e.get("path", ""),
                type=e.get("type", "file"),
                size=int(e.get("size", 0) or 0),
            )
            for e in items
            if isinstance(e, dict)
        ]
        # dirs first, then files, each alphabetical — the familiar listing order.
        return sorted(entries, key=lambda x: (x.type != "dir", x.name.lower()))

    def get_file(
        self, *, repo_id: str, path: str, ref: str | None = None
    ) -> FileContent:
        query = f"?ref={quote(ref, safe='')}" if ref else ""
        result = self._request(
            "GET", f"/repos/{repo_id}/contents/{path.lstrip('/')}{query}"
        )
        raw = result.get("content") or ""
        text: str | None = None
        is_binary = False
        if (result.get("encoding") == "base64") and raw:
            data = base64.b64decode(raw)
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                is_binary = True
        return FileContent(
            path=result.get("path", path),
            name=result.get("name", path.rsplit("/", 1)[-1]),
            size=int(result.get("size", 0) or 0),
            text=text,
            is_binary=is_binary,
        )

    def list_commits(
        self, *, repo_id: str, ref: str | None = None, limit: int = 20
    ) -> list[Commit]:
        query = f"?limit={limit}" + (f"&sha={quote(ref, safe='')}" if ref else "")
        result = self._request("GET", f"/repos/{repo_id}/commits{query}")
        items = result if isinstance(result, list) else []
        return [self._to_commit(c) for c in items]

    def list_branches(self, *, repo_id: str) -> list[Branch]:
        branches = self._request("GET", f"/repos/{repo_id}/branches")
        items = branches if isinstance(branches, list) else []
        return [self._to_branch(b) for b in items]

    def create_branch(self, *, repo_id: str, name: str, from_ref: str) -> Branch:
        branch = self._request(
            "POST",
            f"/repos/{repo_id}/branches",
            json={"new_branch_name": name, "old_ref_name": from_ref},
        )
        return self._to_branch(branch)

    def delete_branch(self, *, repo_id: str, name: str) -> None:
        # The branch name may contain slashes (feature/x); Forgejo's route is a
        # wildcard, so it must stay raw (not percent-encoded).
        self._request("DELETE", f"/repos/{repo_id}/branches/{name}")

    def get_diff(self, *, repo_id: str, base: str, head: str) -> Diff:
        compare = self._request(
            "GET", f"/repos/{repo_id}/compare/{base}...{head}"
        )
        files = compare.get("files", []) if isinstance(compare, dict) else []
        return Diff(files=tuple(self._to_diff_file(f) for f in files))

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
        payload: dict[str, Any] = {
            "title": title,
            "body": body,
            "head": source_branch,
            "base": target_branch,
        }
        if reviewers:
            payload["assignees"] = reviewers
        pull = self._request("POST", f"/repos/{repo_id}/pulls", json=payload)
        return self._to_proposal(repo_id, pull)

    def list_proposals(self, *, repo_id: str, state: str = "open") -> list[Proposal]:
        pulls = self._request(
            "GET", f"/repos/{repo_id}/pulls?state={state}"
        )
        items = pulls if isinstance(pulls, list) else []
        return [self._to_proposal(repo_id, p) for p in items]

    def get_proposal(self, *, repo_id: str, number: int) -> Proposal:
        pull = self._request("GET", f"/repos/{repo_id}/pulls/{number}")
        return self._to_proposal(repo_id, pull, self._count_approvals(repo_id, number))

    def _count_approvals(self, repo_id: str, number: int) -> int:
        reviews = self._request("GET", f"/repos/{repo_id}/pulls/{number}/reviews")
        items = reviews if isinstance(reviews, list) else []
        return sum(
            1 for r in items if r.get("state") == "APPROVED" and not r.get("dismissed")
        )

    def get_proposal_diff(self, *, repo_id: str, number: int) -> Diff:
        files = self._request("GET", f"/repos/{repo_id}/pulls/{number}/files")
        items = files if isinstance(files, list) else []
        # The files endpoint returns metadata only (no `patch` hunks), so fetch
        # the raw unified diff and attach each file's hunks by path.
        try:
            raw = self._request("GET", f"/repos/{repo_id}/pulls/{number}.diff", raw=True)
        except SourceControlError:
            raw = ""
        patches = _split_unified_diff(raw if isinstance(raw, str) else "")
        return Diff(files=tuple(self._to_diff_file(f, patches) for f in items))

    def list_proposal_commits(self, *, repo_id: str, number: int) -> list[Commit]:
        result = self._request("GET", f"/repos/{repo_id}/pulls/{number}/commits")
        items = result if isinstance(result, list) else []
        return [self._to_commit(c) for c in items]

    def list_comments(self, *, repo_id: str, number: int) -> list[Comment]:
        comments = self._request(
            "GET", f"/repos/{repo_id}/issues/{number}/comments"
        )
        items = comments if isinstance(comments, list) else []
        return [self._to_comment(c) for c in items]

    def list_reviews(self, *, repo_id: str, number: int) -> list[Review]:
        reviews = self._request("GET", f"/repos/{repo_id}/pulls/{number}/reviews")
        items = reviews if isinstance(reviews, list) else []
        # Keep only meaningful, current review events: drop dismissed/stale ones
        # and the "review requested" placeholders that carry no submitted state.
        return [
            self._to_review(r)
            for r in items
            if not r.get("dismissed") and r.get("state") in _REVIEW_STATES
        ]

    def add_comment(
        self,
        *,
        repo_id: str,
        number: int,
        body: str,
        path: str | None = None,
        line: int | None = None,
    ) -> Comment:
        if path is not None:
            review = self._request(
                "POST",
                f"/repos/{repo_id}/pulls/{number}/reviews",
                json={
                    "event": "COMMENT",
                    "body": body,
                    "comments": [
                        {"path": path, "body": body, "new_position": line}
                    ],
                },
            )
            return Comment(
                id=str(review.get("id", "")),
                path=path,
                line=line,
                body=body,
                author=self._actor(review),
                created_at=review.get("submitted_at"),
            )
        comment = self._request(
            "POST",
            f"/repos/{repo_id}/issues/{number}/comments",
            json={"body": body},
        )
        return self._to_comment(comment)

    def submit_review(
        self, *, repo_id: str, number: int, event: str, body: str = ""
    ) -> Review:
        forge_event = _REVIEW_EVENTS.get(event.lower(), event.upper())
        review = self._request(
            "POST",
            f"/repos/{repo_id}/pulls/{number}/reviews",
            json={"event": forge_event, "body": body},
        )
        return self._to_review(review)

    def list_checks(self, *, repo_id: str, number: int) -> list[Check]:
        pull = self._request("GET", f"/repos/{repo_id}/pulls/{number}")
        sha = (pull.get("head", {}) or {}).get("sha")
        if not sha:
            return []
        statuses = self._request("GET", f"/repos/{repo_id}/commits/{sha}/statuses")
        items = statuses if isinstance(statuses, list) else []
        return [self._to_check(s) for s in items]

    def set_branch_protection(
        self,
        *,
        repo_id: str,
        branch: str,
        required_approvals: int,
        required_checks: list[str],
    ) -> None:
        self._request(
            "POST",
            f"/repos/{repo_id}/branch_protections",
            json={
                "branch_name": branch,
                "enable_approvals_whitelist": False,
                "required_approvals": required_approvals,
                "enable_status_check": bool(required_checks),
                "status_check_contexts": required_checks,
            },
        )

    def merge(self, *, repo_id: str, number: int, method: str = "merge") -> MergeResult:
        result = self._request(
            "POST",
            f"/repos/{repo_id}/pulls/{number}/merge",
            json={"Do": method},
        )
        if isinstance(result, dict) and result.get("sha"):
            return MergeResult(
                merged=True, sha=result.get("sha"), message=result.get("message")
            )
        return MergeResult(merged=True, sha=None, message=None)

    def mint_git_token(self, *, user_id: str) -> str:
        # ``user_id`` is the forge USERNAME. Forgejo/Gitea's token endpoint
        # requires BASIC auth as the user and rejects admin-token + Sudo
        # ("auth required"). So the admin resets a throwaway password, then we
        # basic-auth as the user to mint a scoped token (the password is never
        # persisted or returned). Token names must be unique per user.
        password = secrets.token_urlsafe(24)
        self._request(
            "PATCH",
            f"/admin/users/{user_id}",
            json={
                "login_name": user_id,
                "source_id": 0,
                "password": password,
                "must_change_password": False,
            },
        )
        token = self._request(
            "POST",
            f"/users/{user_id}/tokens",
            json={
                "name": f"abi-{user_id}-{secrets.token_hex(4)}",
                "scopes": ["write:repository"],
            },
            basic_auth=(user_id, password),
        )
        return str(token.get("sha1") or token.get("token") or "")

    # -- mappers ------------------------------------------------------------

    @staticmethod
    def _to_repo(repo: dict) -> Repo:
        owner = (repo.get("owner", {}) or {}).get("login", "")
        return Repo(
            id=str(repo.get("id", "")),
            name=repo.get("name", ""),
            owner=owner,
            default_branch=repo.get("default_branch", ""),
            clone_url=repo.get("clone_url", ""),
            html_url=repo.get("html_url", ""),
            description=repo.get("description") or "",
            private=bool(repo.get("private", True)),
            empty=bool(repo.get("empty", False)),
            updated_at=repo.get("updated_at"),
        )

    @staticmethod
    def _to_branch(branch: dict) -> Branch:
        return Branch(
            name=branch.get("name", ""),
            commit_sha=(branch.get("commit", {}) or {}).get("id", ""),
            protected=bool(branch.get("protected", False)),
        )

    @staticmethod
    def _to_diff_file(file: dict, patches: dict[str, str] | None = None) -> DiffFile:
        patches = patches or {}
        path = file.get("filename", file.get("path", ""))
        old = file.get("previous_filename")
        patch = file.get("patch") or patches.get(path) or (patches.get(old) if old else None)
        return DiffFile(
            path=path,
            status=file.get("status", ""),
            additions=int(file.get("additions", 0)),
            deletions=int(file.get("deletions", 0)),
            patch=patch,
            old_path=old,
        )

    @classmethod
    def _to_proposal(cls, repo_id: str, pull: dict, approvals: int = 0) -> Proposal:
        return Proposal(
            id=str(pull.get("id", "")),
            number=int(pull.get("number", 0)),
            title=pull.get("title", ""),
            body=pull.get("body", "") or "",
            state=cls._normalize_state(pull),
            source_branch=(pull.get("head", {}) or {}).get("ref", ""),
            target_branch=(pull.get("base", {}) or {}).get("ref", ""),
            author=cls._actor(pull),
            mergeable=bool(pull.get("mergeable", False)),
            approvals=approvals,
            html_url=pull.get("html_url", ""),
        )

    @staticmethod
    def _normalize_state(pull: dict) -> str:
        if pull.get("merged"):
            return PROPOSAL_MERGED
        if pull.get("state") == "closed":
            return PROPOSAL_CLOSED
        return PROPOSAL_OPEN

    @staticmethod
    def _to_commit(entry: dict) -> Commit:
        commit = entry.get("commit", {}) or {}
        author = commit.get("author", {}) or {}
        return Commit(
            sha=entry.get("sha", ""),
            message=(commit.get("message", "") or "").split("\n", 1)[0],
            author=author.get("name", ""),
            date=author.get("date"),
        )

    @classmethod
    def _to_comment(cls, comment: dict) -> Comment:
        return Comment(
            id=str(comment.get("id", "")),
            path=comment.get("path"),
            line=comment.get("line"),
            body=comment.get("body", ""),
            author=cls._actor(comment),
            created_at=comment.get("created_at"),
        )

    @classmethod
    def _to_review(cls, review: dict) -> Review:
        return Review(
            id=str(review.get("id", "")),
            state=_REVIEW_STATES.get(review.get("state", ""), REVIEW_COMMENT),
            body=review.get("body", "") or "",
            author=cls._actor(review),
            submitted_at=review.get("submitted_at"),
        )

    @staticmethod
    def _to_check(status: dict) -> Check:
        state = status.get("status", status.get("state", ""))
        if state in _CHECK_SUCCESS:
            normalized = CHECK_SUCCESS
        elif state in _CHECK_FAILURE:
            normalized = CHECK_FAILURE
        else:
            normalized = CHECK_PENDING
        return Check(
            name=status.get("context", ""),
            status=normalized,
            conclusion=status.get("description"),
        )

    @staticmethod
    def _actor(payload: dict) -> str:
        user = payload.get("user", {}) or {}
        return user.get("login", "") or payload.get("author", "")


def _default_session() -> Any:
    import requests

    return requests.Session()


def _safe_text(response: Any) -> str:
    text = getattr(response, "text", "") or ""
    return text.strip()


def _split_unified_diff(text: str) -> dict[str, str]:
    """Split a raw unified diff into per-file hunks, keyed by both the old and
    new path so a DiffFile can be matched by filename. The returned patch starts
    at the first ``@@`` hunk (the file header is dropped), matching what the
    Gitea/Forgejo ``patch`` field would contain when present."""
    patches: dict[str, str] = {}
    if not text:
        return patches
    for chunk in re.split(r"(?m)^(?=diff --git )", text):
        if not chunk.startswith("diff --git"):
            continue
        header = chunk.splitlines()[0]
        m = re.match(r"diff --git a/(.+?) b/(.+)$", header)
        at = chunk.find("\n@@")
        if not m or at == -1:
            continue
        patch = chunk[at + 1 :]
        patches[m.group(1).strip()] = patch
        patches[m.group(2).strip()] = patch
    return patches
