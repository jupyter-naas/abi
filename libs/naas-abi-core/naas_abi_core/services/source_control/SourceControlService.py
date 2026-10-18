from __future__ import annotations

import re

from naas_abi_core.engine.call_context import (
    ANONYMOUS_PRINCIPAL,
    as_service_account,
    call_subject,
    vouched_by_first_party,
)
from naas_abi_core.services.iam.guard import PLACEMENT_WRITER, ServiceGuard
from naas_abi_core.services.ServiceBase import ServiceBase
from naas_abi_core.services.source_control.iam_catalog import CATALOG
from naas_abi_core.services.source_control.ontologies.modules.SourceControlEventOntology import (
    ProposalMergeBlocked,
    ProposalMerged,
    ProposalOpened,
    ReviewSubmitted,
)
from naas_abi_core.services.source_control.SourceControlPorts import (
    Branch,
    BranchNotFoundError,
    Check,
    Comment,
    Commit,
    ContentEntry,
    Diff,
    FileContent,
    FileWrite,
    ISourceControlAdapter,
    MergeBlockedError,
    MergeResult,
    Proposal,
    ProposalNotFoundError,
    Repo,
    RepoNotFoundError,
    Review,
    ValidationError,
    WorkflowRun,
)

# One path segment of a repository id (owner, name): the local adapter makes
# directories of them and the forge puts them in URLs, so never ``..`` or a
# separator, whoever asks (a module over NATS included).
_SEGMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def _segment_ok(value: str) -> bool:
    return bool(_SEGMENT.fullmatch(value)) and value not in (".", "..")


def _repo_id_ok(repo_id: str) -> bool:
    owner, sep, name = repo_id.partition("/")
    return bool(sep) and _segment_ok(owner) and _segment_ok(name)


def _repo_missing(repo_id: str):
    return lambda: RepoNotFoundError(f"Repository {repo_id} not found")


def _branch_missing(repo_id: str, name: str):
    return lambda: BranchNotFoundError(f"Branch {name} not found in {repo_id}")


def _proposal_missing(repo_id: str, number: int | str):
    return lambda: ProposalNotFoundError(f"Proposal {number} not found in {repo_id}")


def repo_key(repo_id: str) -> str:
    """A repository's id as IAM names and places it: lowercase, because forges
    look repositories up case-insensitively (``Acme/Repo`` is ``acme/repo``)."""
    return repo_id.lower()


def _branch(repo_id: str, name: str) -> list[str]:
    return [repo_key(repo_id), name]


def _proposal(repo_id: str, number: int | str) -> list[str]:
    return [repo_key(repo_id), str(number)]


class SourceControlService(ServiceBase):
    """Domain service for git + in-app code review.

    Business logic knows nothing about Forgejo/Gitea; it depends only on the
    port. The operation is always the source of truth — event publishing is
    fail-safe and must never break a (potentially expensive) forge call.

    Every operation is authorized (``source_control:*``, RFC §6.4) once the
    service is wired with IAM: a repository is a placed container
    (``repo/<owner>%2F<name>``) holding its branches and proposals; a forge user
    is personal (``forge_user/<principal id>``). The principal an operation
    concerns is the call's user, or the actor when the call is on behalf of no
    one, never a request field.
    """

    def __init__(self, adapter: ISourceControlAdapter):
        super().__init__()
        self._adapter = adapter
        self._guard = ServiceGuard.of(CATALOG, self)

    @property
    def adapter(self) -> ISourceControlAdapter:
        """The wrapped secondary adapter -- public so callers (e.g.
        ``EngineNATSLoader``) can check what kind of adapter this service is
        backed by, mirroring ``ObjectStorageService.adapter``."""
        return self._adapter

    def __publish_event(self, event: object) -> None:
        if not self.services_wired:
            return
        if not self.services.events_available():
            return
        # The forge call is the source of truth; emit never raises.
        self.services.events.emit(event)

    @staticmethod
    def _principal() -> str:
        """Whom a personal operation concerns (``call_subject``); an anonymous
        call concerns the anonymous principal, which IAM allows nothing."""
        return call_subject() or ANONYMOUS_PRINCIPAL.id

    # -- checks -----------------------------------------------------------------

    @staticmethod
    def _known_repo_id(repo_id: str) -> None:
        """No repository has an id that is not ``<owner>/<name>`` of plain
        segments: it is not found, whatever the caller may do."""
        if not _repo_id_ok(repo_id):
            raise _repo_missing(repo_id)()

    def _repo(self, action: str, repo_id: str) -> None:
        self._known_repo_id(repo_id)
        self._guard.require(
            action, "repo", repo_key(repo_id), not_found=_repo_missing(repo_id)
        )

    def _on_branch(self, action: str, repo_id: str, name: str) -> None:
        self._known_repo_id(repo_id)
        self._guard.require(
            action,
            "branch",
            _branch(repo_id, name),
            not_found=_branch_missing(repo_id, name),
        )

    def _on_proposal(self, action: str, repo_id: str, number: int | str) -> None:
        self._known_repo_id(repo_id)
        self._guard.require(
            action,
            "proposal",
            _proposal(repo_id, number),
            not_found=_proposal_missing(repo_id, number),
        )

    def _visible_repo(self, repo_id: str) -> None:
        """A repository's items are listed only once the repository itself is
        visible: not found otherwise (RFC §5.5)."""
        self._known_repo_id(repo_id)
        iam = self._guard.iam
        if iam is None:
            return
        name = self._guard.name("repo", repo_key(repo_id))
        if not iam.authorize("source_control:ListContents", name).visible:
            raise _repo_missing(repo_id)()

    # -- forge users ---------------------------------------------------------------

    def ensure_user(
        self, *, email: str, username: str, external_id: str | None = None
    ) -> str:
        """Ensure the forge user ``username`` of the call's principal.

        ``external_id`` is ignored once the service checks: the principal is the
        call's (``EnsureUser`` on its own ``forge_user``, which every user holds).
        """
        if not self._guard.enforcing:
            # A facade: the owner it calls binds the call's principal.
            return self._adapter.ensure_user(
                external_id=external_id or self._principal(),
                email=email,
                username=username,
            )
        principal = self._principal()
        self._guard.require("EnsureUser", "forge_user", principal)
        return self._adapter.ensure_user(
            external_id=principal,
            email=email,
            username=username,
            # Only a first party's word about its user's email can claim an
            # account that predates the binding.
            vouched_email=vouched_by_first_party(),
        )

    def mint_git_token(self, *, user_id: str | None = None) -> str:
        """A git token for the call's principal's forge user (``ensure_user``
        first). ``user_id`` is ignored: never take the user from a request."""
        if not self._guard.enforcing:
            return self._adapter.mint_git_token(user_id=user_id or "")
        principal = self._principal()
        self._guard.require("MintGitToken", "forge_user", principal)
        username = self._adapter.find_user(external_id=principal)
        if username is None:
            raise ValidationError(
                "The caller has no forge user yet: call ensure_user first"
            )
        return self._adapter.mint_git_token(user_id=username, external_id=principal)

    # -- repositories ----------------------------------------------------------------

    def ensure_repo(
        self, *, owner: str, name: str, private: bool = True, auto_init: bool = True
    ) -> Repo:
        """Create the repository, placed in the call's target workspace (RFC §4.4).

        Re-ensuring a repository that exists is not a create: it needs
        ``EnsureRepo`` on the repository as placed. One with no placement
        predates IAM: it is recorded on the platform, so no workspace claims it.
        """
        repo_id = self._new_repo_id(owner, name)
        iam = self._guard.iam
        if iam is not None and self._exists(repo_id):
            # Not a create: an existing repository is ensured where it is
            # placed, whatever the call's target workspace.
            canonical = self._guard.canonical_id("repo", repo_key(repo_id))
            if iam.placement_of("source_control", canonical) is None:
                # It predates IAM: the platform's, so no workspace claims it.
                with as_service_account(PLACEMENT_WRITER):
                    iam.put_placement("source_control", canonical)
                    iam.put_placement("source_control", f"{canonical}/*")
            self._repo("EnsureRepo", repo_id)
            return self._adapter.ensure_repo(
                owner=owner, name=name, private=private, auto_init=auto_init
            )
        creation = self._guard.create(
            "EnsureRepo", "repo", repo_key(repo_id), not_found=_repo_missing(repo_id)
        )
        repo = self._adapter.ensure_repo(
            owner=owner, name=name, private=private, auto_init=auto_init
        )
        creation.record()
        return repo

    def create_repo(
        self, *, owner: str, name: str, private: bool = True, auto_init: bool = True
    ) -> Repo:
        """Create a new repository, placed in the call's target workspace.

        Unlike ``ensure_repo``, it never hands back a repository that exists:
        one with that id in any letter case raises ``RepoExistsError``, and
        nothing is placed. A caller may then place or grant access to what it
        gets back, knowing it created it.
        """
        repo_id = self._new_repo_id(owner, name)
        creation = self._guard.create(
            "EnsureRepo", "repo", repo_key(repo_id), not_found=_repo_missing(repo_id)
        )
        repo = self._adapter.create_repo(
            owner=owner, name=name, private=private, auto_init=auto_init
        )
        creation.record()
        return repo

    @staticmethod
    def _new_repo_id(owner: str, name: str) -> str:
        if not (_segment_ok(owner) and _segment_ok(name)):
            raise ValidationError(
                "A repository's owner and name are letters, digits, '.', '_' "
                "and '-', starting with a letter or a digit"
            )
        return f"{owner}/{name}"

    def _exists(self, repo_id: str) -> bool:
        try:
            self._adapter.list_branches(repo_id=repo_id)
        except RepoNotFoundError:
            return False
        return True

    def list_repos(self) -> list[Repo]:
        return self._guard.filter(
            "ListRepos",
            "repo",
            self._adapter.list_repos(),
            lambda repo: repo_key(f"{repo.owner}/{repo.name}"),
        )

    def delete_repo(self, *, repo_id: str) -> None:
        self._repo("DeleteRepo", repo_id)
        self._adapter.delete_repo(repo_id=repo_id)
        self._guard.forget("repo", repo_key(repo_id))

    def add_collaborator(
        self, *, repo_id: str, username: str, permission: str = "write"
    ) -> None:
        """Grant a forge user access: ``AddCollaborator``, an admin action."""
        self._repo("AddCollaborator", repo_id)
        self._adapter.add_collaborator(
            repo_id=repo_id, username=username, permission=permission
        )

    def list_contents(
        self, *, repo_id: str, path: str = "", ref: str | None = None
    ) -> list[ContentEntry]:
        self._repo("ListContents", repo_id)
        return self._adapter.list_contents(repo_id=repo_id, path=path, ref=ref)

    def get_file(
        self, *, repo_id: str, path: str, ref: str | None = None
    ) -> FileContent:
        self._repo("GetFile", repo_id)
        return self._adapter.get_file(repo_id=repo_id, path=path, ref=ref)

    def upsert_file(
        self,
        *,
        repo_id: str,
        path: str,
        content: str | bytes,
        message: str,
        branch: str,
        author_name: str | None = None,
        author_email: str | None = None,
    ) -> Commit:
        self._on_branch("UpsertFile", repo_id, branch)
        return self._adapter.upsert_file(
            repo_id=repo_id,
            path=path,
            content=content,
            message=message,
            branch=branch,
            author_name=author_name,
            author_email=author_email,
        )

    def upsert_files(
        self,
        *,
        repo_id: str,
        files: list[FileWrite],
        message: str,
        branch: str,
        author_name: str | None = None,
        author_email: str | None = None,
    ) -> Commit:
        self._on_branch("UpsertFiles", repo_id, branch)
        return self._adapter.upsert_files(
            repo_id=repo_id,
            files=files,
            message=message,
            branch=branch,
            author_name=author_name,
            author_email=author_email,
        )

    def list_commits(
        self, *, repo_id: str, ref: str | None = None, limit: int = 20
    ) -> list[Commit]:
        self._repo("ListCommits", repo_id)
        return self._adapter.list_commits(repo_id=repo_id, ref=ref, limit=limit)

    def list_branches(self, *, repo_id: str) -> list[Branch]:
        self._visible_repo(repo_id)
        return self._guard.filter(
            "ListBranches",
            "branch",
            self._adapter.list_branches(repo_id=repo_id),
            lambda branch: _branch(repo_id, branch.name),
        )

    def create_branch(self, *, repo_id: str, name: str, from_ref: str) -> Branch:
        self._on_branch("CreateBranch", repo_id, name)
        return self._adapter.create_branch(
            repo_id=repo_id, name=name, from_ref=from_ref
        )

    def delete_branch(self, *, repo_id: str, name: str) -> None:
        self._on_branch("DeleteBranch", repo_id, name)
        self._adapter.delete_branch(repo_id=repo_id, name=name)

    def get_diff(self, *, repo_id: str, base: str, head: str) -> Diff:
        self._repo("GetDiff", repo_id)
        return self._adapter.get_diff(repo_id=repo_id, base=base, head=head)

    # -- proposals ----------------------------------------------------------------------

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
        # Inside an existing repository: it takes the repository's placement.
        self._on_proposal("CreateProposal", repo_id, "-")
        proposal = self._adapter.create_proposal(
            repo_id=repo_id,
            title=title,
            body=body,
            source_branch=source_branch,
            target_branch=target_branch,
            reviewers=reviewers,
        )
        self.__publish_event(
            ProposalOpened(
                repo_id=repo_id,
                number=proposal.number,
                title=proposal.title,
                source_branch=proposal.source_branch,
                target_branch=proposal.target_branch,
                author=proposal.author,
            )
        )
        return proposal

    def list_proposals(self, *, repo_id: str, state: str = "open") -> list[Proposal]:
        self._visible_repo(repo_id)
        return self._guard.filter(
            "ListProposals",
            "proposal",
            self._adapter.list_proposals(repo_id=repo_id, state=state),
            lambda proposal: _proposal(repo_id, proposal.number),
        )

    def get_proposal(self, *, repo_id: str, number: int) -> Proposal:
        self._on_proposal("GetProposal", repo_id, number)
        return self._adapter.get_proposal(repo_id=repo_id, number=number)

    def get_proposal_diff(self, *, repo_id: str, number: int) -> Diff:
        self._on_proposal("GetProposalDiff", repo_id, number)
        return self._adapter.get_proposal_diff(repo_id=repo_id, number=number)

    def list_proposal_commits(self, *, repo_id: str, number: int) -> list[Commit]:
        self._on_proposal("ListProposalCommits", repo_id, number)
        return self._adapter.list_proposal_commits(repo_id=repo_id, number=number)

    def list_comments(self, *, repo_id: str, number: int) -> list[Comment]:
        self._on_proposal("ListComments", repo_id, number)
        return self._adapter.list_comments(repo_id=repo_id, number=number)

    def list_reviews(self, *, repo_id: str, number: int) -> list[Review]:
        self._on_proposal("ListReviews", repo_id, number)
        return self._adapter.list_reviews(repo_id=repo_id, number=number)

    def list_workflow_runs(self, *, repo_id: str, limit: int = 20) -> list[WorkflowRun]:
        self._repo("ListWorkflowRuns", repo_id)
        return self._adapter.list_workflow_runs(repo_id=repo_id, limit=limit)

    def add_comment(
        self,
        *,
        repo_id: str,
        number: int,
        body: str,
        path: str | None = None,
        line: int | None = None,
    ) -> Comment:
        self._on_proposal("AddComment", repo_id, number)
        return self._adapter.add_comment(
            repo_id=repo_id, number=number, body=body, path=path, line=line
        )

    def submit_review(
        self, *, repo_id: str, number: int, event: str, body: str = ""
    ) -> Review:
        self._on_proposal("SubmitReview", repo_id, number)
        review = self._adapter.submit_review(
            repo_id=repo_id, number=number, event=event, body=body
        )
        self.__publish_event(
            ReviewSubmitted(
                repo_id=repo_id,
                number=number,
                state=review.state,
                author=review.author,
            )
        )
        return review

    def list_checks(self, *, repo_id: str, number: int) -> list[Check]:
        self._on_proposal("ListChecks", repo_id, number)
        return self._adapter.list_checks(repo_id=repo_id, number=number)

    def set_branch_protection(
        self,
        *,
        repo_id: str,
        branch: str,
        required_approvals: int,
        required_checks: list[str],
    ) -> None:
        self._on_branch("SetBranchProtection", repo_id, branch)
        self._adapter.set_branch_protection(
            repo_id=repo_id,
            branch=branch,
            required_approvals=required_approvals,
            required_checks=required_checks,
        )

    def merge(self, *, repo_id: str, number: int, method: str = "merge") -> MergeResult:
        self._on_proposal("Merge", repo_id, number)
        try:
            result = self._adapter.merge(repo_id=repo_id, number=number, method=method)
        except MergeBlockedError as exc:
            self.__publish_event(
                ProposalMergeBlocked(repo_id=repo_id, number=number, reason=str(exc))
            )
            raise
        if result.merged:
            self.__publish_event(
                ProposalMerged(repo_id=repo_id, number=number, sha=result.sha)
            )
        return result
