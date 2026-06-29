from abc import ABC, abstractmethod

import pytest

REQUIRED_METHODS = (
    "ensure_user",
    "ensure_repo",
    "list_repos",
    "add_collaborator",
    "list_contents",
    "get_file",
    "list_commits",
    "list_branches",
    "create_branch",
    "delete_branch",
    "get_diff",
    "create_proposal",
    "list_proposals",
    "get_proposal",
    "get_proposal_diff",
    "list_proposal_commits",
    "list_comments",
    "list_reviews",
    "add_comment",
    "submit_review",
    "list_checks",
    "set_branch_protection",
    "merge",
    "mint_git_token",
)


class GenericSourceControlSecondaryAdapterTest(ABC):
    @pytest.fixture
    @abstractmethod
    def adapter_class(self):
        raise NotImplementedError()

    def test_adapter_has_required_methods(self, adapter_class):
        for method in REQUIRED_METHODS:
            assert callable(getattr(adapter_class, method, None)), (
                f"adapter is missing required method: {method}"
            )
