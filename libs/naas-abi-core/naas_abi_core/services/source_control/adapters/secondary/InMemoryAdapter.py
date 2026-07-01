from __future__ import annotations

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
    MergeBlockedError,
    MergeResult,
    PROPOSAL_MERGED,
    PROPOSAL_OPEN,
    Proposal,
    ProposalNotFoundError,
    Repo,
    RepoNotFoundError,
    REVIEW_APPROVED,
    REVIEW_CHANGES_REQUESTED,
    REVIEW_COMMENT,
    Review,
    WorkflowRun,
)

# Forge review "event" verbs -> normalized review state.
_REVIEW_EVENTS = {
    "APPROVED": REVIEW_APPROVED,
    "APPROVE": REVIEW_APPROVED,
    "REQUEST_CHANGES": REVIEW_CHANGES_REQUESTED,
    "REQUEST_CHANGE": REVIEW_CHANGES_REQUESTED,
    "COMMENT": REVIEW_COMMENT,
}


class InMemoryAdapter(ISourceControlAdapter):
    """In-process fake git forge.

    Fully functional for unit-testing the domain and for driving the prototype
    frontend without a live Forgejo/Gitea. Repositories, branches, proposals,
    comments, reviews and branch protection all live in memory.
    """

    def __init__(self) -> None:
        self._users: dict[str, str] = {}  # username -> user id
        self._repos: dict[str, dict] = {}  # repo_id -> record
        self._counter = 0

    def _next_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}-{self._counter}"

    def _repo(self, repo_id: str) -> dict:
        if repo_id not in self._repos:
            raise RepoNotFoundError(repo_id)
        return self._repos[repo_id]

    def _proposal(self, repo_id: str, number: int) -> dict:
        repo = self._repo(repo_id)
        for proposal in repo["proposals"]:
            if proposal["number"] == number:
                return proposal
        raise ProposalNotFoundError(f"{repo_id}#{number}")

    # -- Port implementation ------------------------------------------------

    def ensure_user(self, *, external_id: str, email: str, username: str) -> str:
        if username not in self._users:
            self._users[username] = self._next_id("user")
        return self._users[username]

    def ensure_repo(
        self, *, owner: str, name: str, private: bool = True, auto_init: bool = True
    ) -> Repo:
        repo_id = f"{owner}/{name}"
        if repo_id not in self._repos:
            branches = (
                {"main": {"name": "main", "commit_sha": self._next_id("sha")}}
                if auto_init
                else {}
            )
            self._repos[repo_id] = {
                "id": self._next_id("repo"),
                "owner": owner,
                "name": name,
                "default_branch": "main" if auto_init else "",
                "branches": branches,
                "proposals": [],
                "protection": {},  # branch -> {required_approvals, required_checks}
                "private": private,
                "empty": not auto_init,
                "files": {"README.md": f"# {name}\n"} if auto_init else {},
            }
        return self._to_repo(self._repos[repo_id])

    def list_contents(
        self, *, repo_id: str, path: str = "", ref: str | None = None
    ) -> list[ContentEntry]:
        files = self._repo(repo_id).get("files", {})
        # Flat fake tree: only top-level files are modelled.
        return sorted(
            (
                ContentEntry(name=p, path=p, type="file", size=len(c))
                for p, c in files.items()
            ),
            key=lambda e: e.name.lower(),
        )

    def get_file(
        self, *, repo_id: str, path: str, ref: str | None = None
    ) -> FileContent:
        files = self._repo(repo_id).get("files", {})
        if path not in files:
            raise RepoNotFoundError(f"{repo_id}:{path}")
        text = files[path]
        return FileContent(
            path=path, name=path.rsplit("/", 1)[-1], size=len(text), text=text
        )

    def list_commits(
        self, *, repo_id: str, ref: str | None = None, limit: int = 20
    ) -> list[Commit]:
        self._repo(repo_id)
        return []

    def list_repos(self) -> list[Repo]:
        return [self._to_repo(record) for record in self._repos.values()]

    def add_collaborator(
        self, *, repo_id: str, username: str, permission: str = "write"
    ) -> None:
        self._repo(repo_id).setdefault("collaborators", {})[username] = permission

    @staticmethod
    def _to_repo(record: dict) -> Repo:
        repo_id = f"{record['owner']}/{record['name']}"
        return Repo(
            id=record["id"],
            name=record["name"],
            owner=record["owner"],
            default_branch=record["default_branch"],
            clone_url=f"https://forge.local/{repo_id}.git",
            html_url=f"https://forge.local/{repo_id}",
            private=bool(record.get("private", True)),
            empty=bool(record.get("empty", False)),
        )

    def list_branches(self, *, repo_id: str) -> list[Branch]:
        repo = self._repo(repo_id)
        return [
            Branch(
                name=b["name"],
                commit_sha=b["commit_sha"],
                protected=b["name"] in repo["protection"],
            )
            for b in repo["branches"].values()
        ]

    def create_branch(self, *, repo_id: str, name: str, from_ref: str) -> Branch:
        repo = self._repo(repo_id)
        if name in repo["branches"]:
            raise BranchNameConflictError(f"branch '{name}' already exists")
        sha = self._next_id("sha")
        repo["branches"][name] = {"name": name, "commit_sha": sha}
        return Branch(name=name, commit_sha=sha, protected=name in repo["protection"])

    def delete_branch(self, *, repo_id: str, name: str) -> None:
        repo = self._repo(repo_id)
        if name not in repo["branches"]:
            raise BranchNotFoundError(f"{repo_id}@{name}")
        del repo["branches"][name]

    def get_diff(self, *, repo_id: str, base: str, head: str) -> Diff:
        self._repo(repo_id)
        return Diff(files=tuple())

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
        repo = self._repo(repo_id)
        number = len(repo["proposals"]) + 1
        record = {
            "id": self._next_id("pr"),
            "number": number,
            "title": title,
            "body": body,
            "state": PROPOSAL_OPEN,
            "source_branch": source_branch,
            "target_branch": target_branch,
            "author": "in-memory",
            "comments": [],
            "reviews": [],
            "merge_sha": None,
        }
        repo["proposals"].append(record)
        return self._to_proposal(repo_id, record)

    def _to_proposal(self, repo_id: str, record: dict) -> Proposal:
        approvals = sum(
            1 for r in record["reviews"] if r["state"] == REVIEW_APPROVED
        )
        return Proposal(
            id=record["id"],
            number=record["number"],
            title=record["title"],
            body=record["body"],
            state=record["state"],
            source_branch=record["source_branch"],
            target_branch=record["target_branch"],
            author=record["author"],
            mergeable=record["state"] == PROPOSAL_OPEN,
            approvals=approvals,
            html_url=f"https://forge.local/{repo_id}/pulls/{record['number']}",
        )

    def list_proposals(self, *, repo_id: str, state: str = "open") -> list[Proposal]:
        repo = self._repo(repo_id)
        return [
            self._to_proposal(repo_id, record)
            for record in repo["proposals"]
            if state == "all" or record["state"] == state
        ]

    def get_proposal(self, *, repo_id: str, number: int) -> Proposal:
        return self._to_proposal(repo_id, self._proposal(repo_id, number))

    def get_proposal_diff(self, *, repo_id: str, number: int) -> Diff:
        self._proposal(repo_id, number)
        return Diff(files=tuple())

    def list_proposal_commits(self, *, repo_id: str, number: int) -> list[Commit]:
        self._proposal(repo_id, number)
        return []

    def list_workflow_runs(self, *, repo_id: str, limit: int = 20) -> list[WorkflowRun]:
        self._repo(repo_id)
        return []

    def list_comments(self, *, repo_id: str, number: int) -> list[Comment]:
        record = self._proposal(repo_id, number)
        return [
            Comment(
                id=c["id"],
                path=c["path"],
                line=c["line"],
                body=c["body"],
                author=c["author"],
                created_at=c["created_at"],
            )
            for c in record["comments"]
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
        record = self._proposal(repo_id, number)
        comment = Comment(
            id=self._next_id("comment"),
            path=path,
            line=line,
            body=body,
            author="in-memory",
            created_at=None,
        )
        record["comments"].append(
            {
                "id": comment.id,
                "path": comment.path,
                "line": comment.line,
                "body": comment.body,
                "author": comment.author,
                "created_at": comment.created_at,
            }
        )
        return comment

    def list_reviews(self, *, repo_id: str, number: int) -> list[Review]:
        record = self._proposal(repo_id, number)
        return [
            Review(
                id=r["id"],
                state=r["state"],
                body=r.get("body", ""),
                author=r.get("author", "in-memory"),
                submitted_at=r.get("submitted_at"),
            )
            for r in record["reviews"]
        ]

    def submit_review(
        self, *, repo_id: str, number: int, event: str, body: str = ""
    ) -> Review:
        record = self._proposal(repo_id, number)
        state = _REVIEW_EVENTS.get(event.upper(), REVIEW_COMMENT)
        review = Review(
            id=self._next_id("review"),
            state=state,
            body=body,
            author="in-memory",
            submitted_at=None,
        )
        record["reviews"].append(
            {
                "id": review.id,
                "state": state,
                "body": review.body,
                "author": review.author,
                "submitted_at": review.submitted_at,
            }
        )
        return review

    def list_checks(self, *, repo_id: str, number: int) -> list[Check]:
        self._proposal(repo_id, number)
        return []

    def set_branch_protection(
        self,
        *,
        repo_id: str,
        branch: str,
        required_approvals: int,
        required_checks: list[str],
    ) -> None:
        repo = self._repo(repo_id)
        repo["protection"][branch] = {
            "required_approvals": required_approvals,
            "required_checks": list(required_checks),
        }

    def merge(self, *, repo_id: str, number: int, method: str = "merge") -> MergeResult:
        repo = self._repo(repo_id)
        record = self._proposal(repo_id, number)
        protection = repo["protection"].get(record["target_branch"])
        if protection is not None:
            required = protection["required_approvals"]
            approvals = sum(
                1 for r in record["reviews"] if r["state"] == REVIEW_APPROVED
            )
            if approvals < required:
                raise MergeBlockedError(
                    f"merge blocked: {approvals}/{required} required approvals"
                )
        sha = self._next_id("sha")
        record["state"] = PROPOSAL_MERGED
        record["merge_sha"] = sha
        return MergeResult(merged=True, sha=sha, message="merged")

    def mint_git_token(self, *, user_id: str) -> str:
        return self._next_id("git-token")
