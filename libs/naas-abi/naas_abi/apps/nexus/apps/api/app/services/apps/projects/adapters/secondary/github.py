"""Submit an app project to a GitHub repository as a review branch.

Git Data API, one commit: blobs for changed files, a tree on top of the
parent's, the commit, then the branch ref (created from the base branch, or
moved forward when a previous submit made it). Optionally a draft pull
request. Unchanged files are not re-uploaded; deletes only name files that
exist on the parent.

Configured by ``apps_submit_*`` settings; the token comes from the
environment (``APPS_SUBMIT_TOKEN``) and is never logged or returned.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import quote

from naas_abi.apps.nexus.apps.api.app.services.apps.projects.port import (
    AppAuthor,
    AppProjectError,
    AppRepoPublisherPort,
    AppSubmission,
)

logger = logging.getLogger(__name__)
_TIMEOUT = 30


def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data, usedforsecurity=False).hexdigest()


class GitHubAppRepoPublisher(AppRepoPublisherPort):
    def __init__(
        self,
        *,
        repo: str,
        token: str,
        base_branch: str = "main",
        api_base: str = "https://api.github.com",
        web_base: str = "https://github.com",
        open_pull_request: bool = True,
        opener: Any = None,
    ) -> None:
        self.repo = repo.strip().strip("/")
        self.token = token.strip()
        self.base_branch = base_branch.strip() or "main"
        self.api_base = api_base.rstrip("/")
        self.web_base = web_base.rstrip("/")
        self.open_pull_request = open_pull_request
        self._open = opener or urllib.request.urlopen

    def describe(self) -> dict[str, Any]:
        return {
            "configured": bool(self.repo and self.token),
            "repo": self.repo or None,
            "base_branch": self.base_branch if self.repo else None,
        }

    # -- HTTP -------------------------------------------------------------------

    def _call(self, method: str, path: str, body: dict | None = None) -> Any:
        request = urllib.request.Request(
            f"{self.api_base}/repos/{self.repo}{path}",
            data=json.dumps(body).encode() if body is not None else None,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
                "User-Agent": "nexus-apps-submit",
            },
        )
        try:
            with self._open(request, timeout=_TIMEOUT) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404 and method == "GET":
                return None
            detail = ""
            try:
                detail = json.loads(exc.read().decode("utf-8")).get("message", "")
            except (ValueError, AttributeError):
                pass
            logger.warning("GitHub %s %s failed: %s %s", method, path, exc.code, detail)
            raise AppProjectError(
                f"GitHub refused the submit ({exc.code}{': ' + detail if detail else ''})."
            ) from None
        except urllib.error.URLError as exc:
            raise AppProjectError("GitHub is not reachable from this platform.") from exc
        return json.loads(raw.decode("utf-8")) if raw else None

    def _ref_sha(self, branch: str) -> str | None:
        ref = self._call("GET", f"/git/ref/heads/{quote(branch, safe='/')}")
        if isinstance(ref, dict):
            return str(ref.get("object", {}).get("sha") or "") or None
        return None

    def _existing_blobs(self, tree_sha: str, target_path: str) -> dict[str, str]:
        """``{path under target: blob sha}`` on the parent commit."""
        sha = tree_sha
        for segment in [s for s in target_path.split("/") if s]:
            tree = self._call("GET", f"/git/trees/{sha}")
            match = next(
                (
                    e
                    for e in (tree or {}).get("tree", [])
                    if e.get("path") == segment and e.get("type") == "tree"
                ),
                None,
            )
            if match is None:
                return {}
            sha = match["sha"]
        tree = self._call("GET", f"/git/trees/{sha}?recursive=1") or {}
        return {e["path"]: e["sha"] for e in tree.get("tree", []) if e.get("type") == "blob"}

    # -- publish ----------------------------------------------------------------

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
        if not self.describe()["configured"]:
            raise AppProjectError("Submitting is not configured.")
        target = target_path.strip("/")
        existing_branch = self._ref_sha(branch)
        parent = existing_branch or self._ref_sha(self.base_branch)
        if parent is None:
            raise AppProjectError(f"Base branch {self.base_branch!r} not found in {self.repo}.")
        parent_commit = self._call("GET", f"/git/commits/{parent}") or {}
        base_tree = parent_commit.get("tree", {}).get("sha")
        existing = self._existing_blobs(base_tree, target) if base_tree else {}

        entries: list[dict[str, Any]] = []
        for path, data in sorted(writes.items()):
            if existing.get(path) == git_blob_sha(data):
                continue
            blob = self._call(
                "POST",
                "/git/blobs",
                {"content": base64.b64encode(data).decode("ascii"), "encoding": "base64"},
            )
            entries.append(
                {"path": f"{target}/{path}", "mode": "100644", "type": "blob", "sha": blob["sha"]}
            )
        for path in deletes:
            if path in existing:
                entries.append(
                    {"path": f"{target}/{path}", "mode": "100644", "type": "blob", "sha": None}
                )
        if not entries:
            raise AppProjectError(
                f"Nothing to submit: {target} already matches {branch if existing_branch else self.base_branch}."
            )

        tree = self._call("POST", "/git/trees", {"base_tree": base_tree, "tree": entries})
        commit_body: dict[str, Any] = {"message": message, "tree": tree["sha"], "parents": [parent]}
        if author.name and author.email:
            commit_body["author"] = {"name": author.name, "email": author.email}
        commit = self._call("POST", "/git/commits", commit_body)
        if existing_branch:
            self._call(
                "PATCH",
                f"/git/refs/heads/{quote(branch, safe='/')}",
                {"sha": commit["sha"], "force": False},
            )
        else:
            self._call("POST", "/git/refs", {"ref": f"refs/heads/{branch}", "sha": commit["sha"]})

        pr_url = self._pull_request(branch, title, body) if self.open_pull_request else None
        return AppSubmission(
            branch=branch,
            url=f"{self.web_base}/{self.repo}/tree/{quote(branch, safe='/')}",
            commit_sha=commit["sha"],
            pull_request_url=pr_url,
            target_path=target,
        )

    def _pull_request(self, branch: str, title: str, body: str) -> str | None:
        owner = self.repo.split("/", 1)[0]
        found = self._call("GET", f"/pulls?state=open&head={quote(f'{owner}:{branch}')}")
        if isinstance(found, list) and found:
            return found[0].get("html_url")
        try:
            created = self._call(
                "POST",
                "/pulls",
                {
                    "title": title,
                    "head": branch,
                    "base": self.base_branch,
                    "body": body,
                    "draft": True,
                },
            )
        except AppProjectError:
            # The branch is what the tech team reviews; a PR is a convenience.
            logger.warning("Draft pull request not opened for %s", branch)
            return None
        return (created or {}).get("html_url")
