from __future__ import annotations

from naas_abi_core import logger
from naas_abi_core.services.ServiceBase import ServiceBase
from naas_abi_core.services.source_control.ontologies.modules.SourceControlEventOntology import (
    ProposalMergeBlocked,
    ProposalMerged,
    ProposalOpened,
    ReviewSubmitted,
)
from naas_abi_core.services.source_control.SourceControlPorts import (
    Branch,
    Commit,
    ContentEntry,
    FileContent,
    Check,
    Comment,
    Diff,
    ISourceControlAdapter,
    MergeBlockedError,
    MergeResult,
    Proposal,
    Repo,
    Review,
    WorkflowRun,
)


class SourceControlService(ServiceBase):
    """Domain service for git + in-app code review.

    Business logic knows nothing about Forgejo/Gitea; it depends only on the
    port. The operation is always the source of truth — event publishing is
    fail-safe and must never break a (potentially expensive) forge call.
    """

    def __init__(self, adapter: ISourceControlAdapter):
        super().__init__()
        self._adapter = adapter

    def __publish_event(self, event: object) -> None:
        if not self.services_wired:
            return
        if not self.services.events_available():
            return
        try:
            self.services.events.publish(event)
        except Exception as exc:
            # The forge call is the source of truth; event logging must never
            # break it.
            logger.warning(
                f"SourceControlService: failed to publish event: {exc}"
            )

    def ensure_user(self, *, external_id: str, email: str, username: str) -> str:
        return self._adapter.ensure_user(
            external_id=external_id, email=email, username=username
        )

    def ensure_repo(
        self, *, owner: str, name: str, private: bool = True, auto_init: bool = True
    ) -> Repo:
        return self._adapter.ensure_repo(
            owner=owner, name=name, private=private, auto_init=auto_init
        )

    def list_repos(self) -> list[Repo]:
        return self._adapter.list_repos()

    def add_collaborator(
        self, *, repo_id: str, username: str, permission: str = "write"
    ) -> None:
        self._adapter.add_collaborator(
            repo_id=repo_id, username=username, permission=permission
        )

    def list_contents(
        self, *, repo_id: str, path: str = "", ref: str | None = None
    ) -> list[ContentEntry]:
        return self._adapter.list_contents(repo_id=repo_id, path=path, ref=ref)

    def get_file(
        self, *, repo_id: str, path: str, ref: str | None = None
    ) -> FileContent:
        return self._adapter.get_file(repo_id=repo_id, path=path, ref=ref)

    def list_commits(
        self, *, repo_id: str, ref: str | None = None, limit: int = 20
    ) -> list[Commit]:
        return self._adapter.list_commits(repo_id=repo_id, ref=ref, limit=limit)

    def list_branches(self, *, repo_id: str) -> list[Branch]:
        return self._adapter.list_branches(repo_id=repo_id)

    def create_branch(self, *, repo_id: str, name: str, from_ref: str) -> Branch:
        return self._adapter.create_branch(
            repo_id=repo_id, name=name, from_ref=from_ref
        )

    def delete_branch(self, *, repo_id: str, name: str) -> None:
        self._adapter.delete_branch(repo_id=repo_id, name=name)

    def get_diff(self, *, repo_id: str, base: str, head: str) -> Diff:
        return self._adapter.get_diff(repo_id=repo_id, base=base, head=head)

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
        return self._adapter.list_proposals(repo_id=repo_id, state=state)

    def get_proposal(self, *, repo_id: str, number: int) -> Proposal:
        return self._adapter.get_proposal(repo_id=repo_id, number=number)

    def get_proposal_diff(self, *, repo_id: str, number: int) -> Diff:
        return self._adapter.get_proposal_diff(repo_id=repo_id, number=number)

    def list_proposal_commits(self, *, repo_id: str, number: int) -> list[Commit]:
        return self._adapter.list_proposal_commits(repo_id=repo_id, number=number)

    def list_comments(self, *, repo_id: str, number: int) -> list[Comment]:
        return self._adapter.list_comments(repo_id=repo_id, number=number)

    def list_reviews(self, *, repo_id: str, number: int) -> list[Review]:
        return self._adapter.list_reviews(repo_id=repo_id, number=number)

    def list_workflow_runs(self, *, repo_id: str, limit: int = 20) -> list[WorkflowRun]:
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
        return self._adapter.add_comment(
            repo_id=repo_id, number=number, body=body, path=path, line=line
        )

    def submit_review(
        self, *, repo_id: str, number: int, event: str, body: str = ""
    ) -> Review:
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
        return self._adapter.list_checks(repo_id=repo_id, number=number)

    def set_branch_protection(
        self,
        *,
        repo_id: str,
        branch: str,
        required_approvals: int,
        required_checks: list[str],
    ) -> None:
        self._adapter.set_branch_protection(
            repo_id=repo_id,
            branch=branch,
            required_approvals=required_approvals,
            required_checks=required_checks,
        )

    def merge(self, *, repo_id: str, number: int, method: str = "merge") -> MergeResult:
        try:
            result = self._adapter.merge(
                repo_id=repo_id, number=number, method=method
            )
        except MergeBlockedError as exc:
            self.__publish_event(
                ProposalMergeBlocked(
                    repo_id=repo_id, number=number, reason=str(exc)
                )
            )
            raise
        if result.merged:
            self.__publish_event(
                ProposalMerged(repo_id=repo_id, number=number, sha=result.sha)
            )
        return result

    def mint_git_token(self, *, user_id: str) -> str:
        return self._adapter.mint_git_token(user_id=user_id)
