"""The ``source_control`` action catalog (RFC §6.4, "source_control").

A repository is a placed container: ``repo/<owner>%2F<name>``, by the
service's own id, with its branches (``branch/<repo>/<name>``) and proposals
(``proposal/<repo>/<number>``) inside it. A forge user is personal. The user an
operation concerns is the call's user, never ``request.user_id``.
"""

from __future__ import annotations

from naas_abi_core.services.iam.catalog import ActionCatalog, ActionSpec, ResourceType

SERVICE = "source_control"
SUBJECT_PREFIX = "abi.svc.source_control.v1"


def _action(
    name: str,
    level: str,
    types: tuple[str, ...],
    *subjects: str,
    creates: bool = False,
    description: str = "",
) -> ActionSpec:
    return ActionSpec(
        name=name,
        level=level,  # type: ignore[arg-type]
        resource_types=types,
        creates=creates,
        subjects=tuple(
            s if s.startswith("abi.") else f"{SUBJECT_PREFIX}.{s}" for s in subjects
        ),
        description=description,
    )


CATALOG = ActionCatalog(
    service=SERVICE,
    version=1,
    resource_types=(
        ResourceType(
            "repo",
            id="opaque",
            placement="placed",
            container=True,
            description="A repository, by its id <owner>/<name>.",
        ),
        ResourceType("branch", id="path", placement="placed"),
        ResourceType("proposal", id="path", placement="placed"),
        ResourceType(
            "forge_user",
            id="opaque",
            placement="platform",
            personal=True,
            description="The forge account of a principal.",
        ),
    ),
    actions=(
        _action("ListRepos", "list", ("repo",), "list_repos"),
        _action("EnsureRepo", "write", ("repo",), "ensure_repo", creates=True),
        _action("DeleteRepo", "admin", ("repo",), "delete_repo"),
        _action("AddCollaborator", "admin", ("repo",), "add_collaborator"),
        _action("SetBranchProtection", "admin", ("branch",), "set_branch_protection"),
        _action("ListContents", "list", ("repo",), "list_contents"),
        _action("GetFile", "read", ("repo",), "get_file"),
        _action("UpsertFile", "write", ("branch", "repo"), "upsert_file"),
        _action("UpsertFiles", "write", ("branch", "repo"), "upsert_files"),
        _action("ListCommits", "list", ("repo",), "list_commits"),
        _action("ListBranches", "list", ("branch",), "list_branches"),
        _action("CreateBranch", "write", ("branch",), "create_branch"),
        _action("DeleteBranch", "write", ("branch",), "delete_branch"),
        _action("GetDiff", "read", ("repo",), "get_diff"),
        _action("ListProposals", "list", ("proposal",), "list_proposals"),
        _action("GetProposal", "read", ("proposal",), "get_proposal"),
        _action("GetProposalDiff", "read", ("proposal",), "get_proposal_diff"),
        _action("ListProposalCommits", "list", ("proposal",), "list_proposal_commits"),
        _action("ListComments", "list", ("proposal",), "list_comments"),
        _action("ListReviews", "list", ("proposal",), "list_reviews"),
        _action("ListChecks", "list", ("proposal",), "list_checks"),
        _action(
            "CreateProposal", "write", ("proposal",), "create_proposal", creates=True
        ),
        _action("AddComment", "write", ("proposal",), "add_comment"),
        _action("SubmitReview", "write", ("proposal",), "submit_review"),
        _action("Merge", "write", ("proposal",), "merge"),
        _action("ListWorkflowRuns", "list", ("repo",), "list_workflow_runs"),
        _action("EnsureUser", "admin", ("forge_user",), "ensure_user"),
        _action("MintGitToken", "write", ("forge_user",), "mint_git_token"),
    ),
)
