from __future__ import annotations

import secrets
from typing import Any

from naas_abi_core.services.source_control.SourceControlPorts import (
    AccessDeniedError,
    Branch,
    BranchNameConflictError,
    BranchNotFoundError,
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
    ) -> Any:
        url = f"{self._base_url}/api/v1{path}"
        headers = {
            "Authorization": f"token {self._admin_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)
        response = self._session.request(
            method, url, headers=headers, json=json, timeout=self._timeout
        )
        status = getattr(response, "status_code", 0)
        if status >= 400:
            self._raise_for_status(status, _safe_text(response), path)
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

    def ensure_repo(self, *, owner: str, name: str, private: bool = True) -> Repo:
        try:
            repo = self._request("GET", f"/repos/{owner}/{name}")
            return self._to_repo(repo)
        except SourceControlError as exc:
            if exc.status != 404:
                raise
        created = self._request(
            "POST",
            f"/admin/users/{owner}/repos",
            json={"name": name, "private": private, "auto_init": True},
        )
        return self._to_repo(created)

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
        return Diff(files=tuple(self._to_diff_file(f) for f in items))

    def list_comments(self, *, repo_id: str, number: int) -> list[Comment]:
        comments = self._request(
            "GET", f"/repos/{repo_id}/issues/{number}/comments"
        )
        items = comments if isinstance(comments, list) else []
        return [self._to_comment(c) for c in items]

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
        # NOTE: ``user_id`` must be the forge USERNAME — Gitea/Forgejo's token
        # endpoint is keyed by username, not the numeric id. The admin acts as
        # that user via the ``Sudo`` header (admin impersonation); verify the
        # exact mechanism against the live instance before relying on it.
        token = self._request(
            "POST",
            f"/users/{user_id}/tokens",
            json={"name": f"abi-{user_id}", "scopes": ["write:repository"]},
            extra_headers={"Sudo": user_id},
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
        )

    @staticmethod
    def _to_branch(branch: dict) -> Branch:
        return Branch(
            name=branch.get("name", ""),
            commit_sha=(branch.get("commit", {}) or {}).get("id", ""),
            protected=bool(branch.get("protected", False)),
        )

    @staticmethod
    def _to_diff_file(file: dict) -> DiffFile:
        return DiffFile(
            path=file.get("filename", file.get("path", "")),
            status=file.get("status", ""),
            additions=int(file.get("additions", 0)),
            deletions=int(file.get("deletions", 0)),
            patch=file.get("patch"),
            old_path=file.get("previous_filename"),
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
