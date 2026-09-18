from naas_abi_core.proto.common.v1 import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Repo(_message.Message):
    __slots__ = ("id", "name", "owner", "default_branch", "clone_url", "html_url", "description", "private", "empty", "updated_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    OWNER_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_BRANCH_FIELD_NUMBER: _ClassVar[int]
    CLONE_URL_FIELD_NUMBER: _ClassVar[int]
    HTML_URL_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    PRIVATE_FIELD_NUMBER: _ClassVar[int]
    EMPTY_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    owner: str
    default_branch: str
    clone_url: str
    html_url: str
    description: str
    private: bool
    empty: bool
    updated_at: str
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., owner: _Optional[str] = ..., default_branch: _Optional[str] = ..., clone_url: _Optional[str] = ..., html_url: _Optional[str] = ..., description: _Optional[str] = ..., private: _Optional[bool] = ..., empty: _Optional[bool] = ..., updated_at: _Optional[str] = ...) -> None: ...

class ContentEntry(_message.Message):
    __slots__ = ("name", "path", "type", "size")
    NAME_FIELD_NUMBER: _ClassVar[int]
    PATH_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    SIZE_FIELD_NUMBER: _ClassVar[int]
    name: str
    path: str
    type: str
    size: int
    def __init__(self, name: _Optional[str] = ..., path: _Optional[str] = ..., type: _Optional[str] = ..., size: _Optional[int] = ...) -> None: ...

class FileContent(_message.Message):
    __slots__ = ("path", "name", "size", "text", "is_binary", "data")
    PATH_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    SIZE_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    IS_BINARY_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    path: str
    name: str
    size: int
    text: str
    is_binary: bool
    data: bytes
    def __init__(self, path: _Optional[str] = ..., name: _Optional[str] = ..., size: _Optional[int] = ..., text: _Optional[str] = ..., is_binary: _Optional[bool] = ..., data: _Optional[bytes] = ...) -> None: ...

class FileWrite(_message.Message):
    __slots__ = ("path", "text_content", "binary_content")
    PATH_FIELD_NUMBER: _ClassVar[int]
    TEXT_CONTENT_FIELD_NUMBER: _ClassVar[int]
    BINARY_CONTENT_FIELD_NUMBER: _ClassVar[int]
    path: str
    text_content: str
    binary_content: bytes
    def __init__(self, path: _Optional[str] = ..., text_content: _Optional[str] = ..., binary_content: _Optional[bytes] = ...) -> None: ...

class Commit(_message.Message):
    __slots__ = ("sha", "message", "author", "date")
    SHA_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    AUTHOR_FIELD_NUMBER: _ClassVar[int]
    DATE_FIELD_NUMBER: _ClassVar[int]
    sha: str
    message: str
    author: str
    date: str
    def __init__(self, sha: _Optional[str] = ..., message: _Optional[str] = ..., author: _Optional[str] = ..., date: _Optional[str] = ...) -> None: ...

class Branch(_message.Message):
    __slots__ = ("name", "commit_sha", "protected")
    NAME_FIELD_NUMBER: _ClassVar[int]
    COMMIT_SHA_FIELD_NUMBER: _ClassVar[int]
    PROTECTED_FIELD_NUMBER: _ClassVar[int]
    name: str
    commit_sha: str
    protected: bool
    def __init__(self, name: _Optional[str] = ..., commit_sha: _Optional[str] = ..., protected: _Optional[bool] = ...) -> None: ...

class DiffFile(_message.Message):
    __slots__ = ("path", "status", "additions", "deletions", "patch", "old_path")
    PATH_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    ADDITIONS_FIELD_NUMBER: _ClassVar[int]
    DELETIONS_FIELD_NUMBER: _ClassVar[int]
    PATCH_FIELD_NUMBER: _ClassVar[int]
    OLD_PATH_FIELD_NUMBER: _ClassVar[int]
    path: str
    status: str
    additions: int
    deletions: int
    patch: str
    old_path: str
    def __init__(self, path: _Optional[str] = ..., status: _Optional[str] = ..., additions: _Optional[int] = ..., deletions: _Optional[int] = ..., patch: _Optional[str] = ..., old_path: _Optional[str] = ...) -> None: ...

class Diff(_message.Message):
    __slots__ = ("files",)
    FILES_FIELD_NUMBER: _ClassVar[int]
    files: _containers.RepeatedCompositeFieldContainer[DiffFile]
    def __init__(self, files: _Optional[_Iterable[_Union[DiffFile, _Mapping]]] = ...) -> None: ...

class Comment(_message.Message):
    __slots__ = ("id", "path", "line", "body", "author", "created_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    PATH_FIELD_NUMBER: _ClassVar[int]
    LINE_FIELD_NUMBER: _ClassVar[int]
    BODY_FIELD_NUMBER: _ClassVar[int]
    AUTHOR_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    path: str
    line: int
    body: str
    author: str
    created_at: str
    def __init__(self, id: _Optional[str] = ..., path: _Optional[str] = ..., line: _Optional[int] = ..., body: _Optional[str] = ..., author: _Optional[str] = ..., created_at: _Optional[str] = ...) -> None: ...

class Review(_message.Message):
    __slots__ = ("id", "state", "body", "author", "submitted_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    BODY_FIELD_NUMBER: _ClassVar[int]
    AUTHOR_FIELD_NUMBER: _ClassVar[int]
    SUBMITTED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    state: str
    body: str
    author: str
    submitted_at: str
    def __init__(self, id: _Optional[str] = ..., state: _Optional[str] = ..., body: _Optional[str] = ..., author: _Optional[str] = ..., submitted_at: _Optional[str] = ...) -> None: ...

class Check(_message.Message):
    __slots__ = ("name", "status", "conclusion")
    NAME_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    CONCLUSION_FIELD_NUMBER: _ClassVar[int]
    name: str
    status: str
    conclusion: str
    def __init__(self, name: _Optional[str] = ..., status: _Optional[str] = ..., conclusion: _Optional[str] = ...) -> None: ...

class Proposal(_message.Message):
    __slots__ = ("id", "number", "title", "body", "state", "source_branch", "target_branch", "author", "mergeable", "approvals", "html_url")
    ID_FIELD_NUMBER: _ClassVar[int]
    NUMBER_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    BODY_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    SOURCE_BRANCH_FIELD_NUMBER: _ClassVar[int]
    TARGET_BRANCH_FIELD_NUMBER: _ClassVar[int]
    AUTHOR_FIELD_NUMBER: _ClassVar[int]
    MERGEABLE_FIELD_NUMBER: _ClassVar[int]
    APPROVALS_FIELD_NUMBER: _ClassVar[int]
    HTML_URL_FIELD_NUMBER: _ClassVar[int]
    id: str
    number: int
    title: str
    body: str
    state: str
    source_branch: str
    target_branch: str
    author: str
    mergeable: bool
    approvals: int
    html_url: str
    def __init__(self, id: _Optional[str] = ..., number: _Optional[int] = ..., title: _Optional[str] = ..., body: _Optional[str] = ..., state: _Optional[str] = ..., source_branch: _Optional[str] = ..., target_branch: _Optional[str] = ..., author: _Optional[str] = ..., mergeable: _Optional[bool] = ..., approvals: _Optional[int] = ..., html_url: _Optional[str] = ...) -> None: ...

class WorkflowRun(_message.Message):
    __slots__ = ("id", "name", "workflow_id", "display_title", "run_number", "event", "status", "head_branch", "head_sha", "url", "created_at", "run_started_at", "updated_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    WORKFLOW_ID_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_TITLE_FIELD_NUMBER: _ClassVar[int]
    RUN_NUMBER_FIELD_NUMBER: _ClassVar[int]
    EVENT_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    HEAD_BRANCH_FIELD_NUMBER: _ClassVar[int]
    HEAD_SHA_FIELD_NUMBER: _ClassVar[int]
    URL_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    RUN_STARTED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: int
    name: str
    workflow_id: str
    display_title: str
    run_number: int
    event: str
    status: str
    head_branch: str
    head_sha: str
    url: str
    created_at: str
    run_started_at: str
    updated_at: str
    def __init__(self, id: _Optional[int] = ..., name: _Optional[str] = ..., workflow_id: _Optional[str] = ..., display_title: _Optional[str] = ..., run_number: _Optional[int] = ..., event: _Optional[str] = ..., status: _Optional[str] = ..., head_branch: _Optional[str] = ..., head_sha: _Optional[str] = ..., url: _Optional[str] = ..., created_at: _Optional[str] = ..., run_started_at: _Optional[str] = ..., updated_at: _Optional[str] = ...) -> None: ...

class MergeResult(_message.Message):
    __slots__ = ("merged", "sha", "message")
    MERGED_FIELD_NUMBER: _ClassVar[int]
    SHA_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    merged: bool
    sha: str
    message: str
    def __init__(self, merged: _Optional[bool] = ..., sha: _Optional[str] = ..., message: _Optional[str] = ...) -> None: ...

class Repos(_message.Message):
    __slots__ = ("repos",)
    REPOS_FIELD_NUMBER: _ClassVar[int]
    repos: _containers.RepeatedCompositeFieldContainer[Repo]
    def __init__(self, repos: _Optional[_Iterable[_Union[Repo, _Mapping]]] = ...) -> None: ...

class ContentEntries(_message.Message):
    __slots__ = ("entries",)
    ENTRIES_FIELD_NUMBER: _ClassVar[int]
    entries: _containers.RepeatedCompositeFieldContainer[ContentEntry]
    def __init__(self, entries: _Optional[_Iterable[_Union[ContentEntry, _Mapping]]] = ...) -> None: ...

class Commits(_message.Message):
    __slots__ = ("commits",)
    COMMITS_FIELD_NUMBER: _ClassVar[int]
    commits: _containers.RepeatedCompositeFieldContainer[Commit]
    def __init__(self, commits: _Optional[_Iterable[_Union[Commit, _Mapping]]] = ...) -> None: ...

class Branches(_message.Message):
    __slots__ = ("branches",)
    BRANCHES_FIELD_NUMBER: _ClassVar[int]
    branches: _containers.RepeatedCompositeFieldContainer[Branch]
    def __init__(self, branches: _Optional[_Iterable[_Union[Branch, _Mapping]]] = ...) -> None: ...

class Proposals(_message.Message):
    __slots__ = ("proposals",)
    PROPOSALS_FIELD_NUMBER: _ClassVar[int]
    proposals: _containers.RepeatedCompositeFieldContainer[Proposal]
    def __init__(self, proposals: _Optional[_Iterable[_Union[Proposal, _Mapping]]] = ...) -> None: ...

class Comments(_message.Message):
    __slots__ = ("comments",)
    COMMENTS_FIELD_NUMBER: _ClassVar[int]
    comments: _containers.RepeatedCompositeFieldContainer[Comment]
    def __init__(self, comments: _Optional[_Iterable[_Union[Comment, _Mapping]]] = ...) -> None: ...

class Reviews(_message.Message):
    __slots__ = ("reviews",)
    REVIEWS_FIELD_NUMBER: _ClassVar[int]
    reviews: _containers.RepeatedCompositeFieldContainer[Review]
    def __init__(self, reviews: _Optional[_Iterable[_Union[Review, _Mapping]]] = ...) -> None: ...

class Checks(_message.Message):
    __slots__ = ("checks",)
    CHECKS_FIELD_NUMBER: _ClassVar[int]
    checks: _containers.RepeatedCompositeFieldContainer[Check]
    def __init__(self, checks: _Optional[_Iterable[_Union[Check, _Mapping]]] = ...) -> None: ...

class WorkflowRuns(_message.Message):
    __slots__ = ("workflow_runs",)
    WORKFLOW_RUNS_FIELD_NUMBER: _ClassVar[int]
    workflow_runs: _containers.RepeatedCompositeFieldContainer[WorkflowRun]
    def __init__(self, workflow_runs: _Optional[_Iterable[_Union[WorkflowRun, _Mapping]]] = ...) -> None: ...

class EnsureUserRequest(_message.Message):
    __slots__ = ("context", "external_id", "email", "username")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    EXTERNAL_ID_FIELD_NUMBER: _ClassVar[int]
    EMAIL_FIELD_NUMBER: _ClassVar[int]
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    external_id: str
    email: str
    username: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., external_id: _Optional[str] = ..., email: _Optional[str] = ..., username: _Optional[str] = ...) -> None: ...

class EnsureUserResponse(_message.Message):
    __slots__ = ("user_id", "error")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    error: _common_pb2.CallError
    def __init__(self, user_id: _Optional[str] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class EnsureRepoRequest(_message.Message):
    __slots__ = ("context", "owner", "name", "private", "auto_init")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    OWNER_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    PRIVATE_FIELD_NUMBER: _ClassVar[int]
    AUTO_INIT_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    owner: str
    name: str
    private: bool
    auto_init: bool
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., owner: _Optional[str] = ..., name: _Optional[str] = ..., private: _Optional[bool] = ..., auto_init: _Optional[bool] = ...) -> None: ...

class EnsureRepoResponse(_message.Message):
    __slots__ = ("repo", "error")
    REPO_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    repo: Repo
    error: _common_pb2.CallError
    def __init__(self, repo: _Optional[_Union[Repo, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class ListReposRequest(_message.Message):
    __slots__ = ("context",)
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ...) -> None: ...

class ListReposResponse(_message.Message):
    __slots__ = ("repos", "error")
    REPOS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    repos: Repos
    error: _common_pb2.CallError
    def __init__(self, repos: _Optional[_Union[Repos, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class AddCollaboratorRequest(_message.Message):
    __slots__ = ("context", "repo_id", "username", "permission")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    REPO_ID_FIELD_NUMBER: _ClassVar[int]
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    PERMISSION_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    repo_id: str
    username: str
    permission: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., repo_id: _Optional[str] = ..., username: _Optional[str] = ..., permission: _Optional[str] = ...) -> None: ...

class AddCollaboratorResponse(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class ListContentsRequest(_message.Message):
    __slots__ = ("context", "repo_id", "path", "ref")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    REPO_ID_FIELD_NUMBER: _ClassVar[int]
    PATH_FIELD_NUMBER: _ClassVar[int]
    REF_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    repo_id: str
    path: str
    ref: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., repo_id: _Optional[str] = ..., path: _Optional[str] = ..., ref: _Optional[str] = ...) -> None: ...

class ListContentsResponse(_message.Message):
    __slots__ = ("entries", "error")
    ENTRIES_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    entries: ContentEntries
    error: _common_pb2.CallError
    def __init__(self, entries: _Optional[_Union[ContentEntries, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class GetFileRequest(_message.Message):
    __slots__ = ("context", "repo_id", "path", "ref")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    REPO_ID_FIELD_NUMBER: _ClassVar[int]
    PATH_FIELD_NUMBER: _ClassVar[int]
    REF_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    repo_id: str
    path: str
    ref: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., repo_id: _Optional[str] = ..., path: _Optional[str] = ..., ref: _Optional[str] = ...) -> None: ...

class GetFileResponse(_message.Message):
    __slots__ = ("file", "error")
    FILE_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    file: FileContent
    error: _common_pb2.CallError
    def __init__(self, file: _Optional[_Union[FileContent, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class UpsertFileRequest(_message.Message):
    __slots__ = ("context", "repo_id", "path", "text_content", "binary_content", "message", "branch", "author_name", "author_email")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    REPO_ID_FIELD_NUMBER: _ClassVar[int]
    PATH_FIELD_NUMBER: _ClassVar[int]
    TEXT_CONTENT_FIELD_NUMBER: _ClassVar[int]
    BINARY_CONTENT_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    BRANCH_FIELD_NUMBER: _ClassVar[int]
    AUTHOR_NAME_FIELD_NUMBER: _ClassVar[int]
    AUTHOR_EMAIL_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    repo_id: str
    path: str
    text_content: str
    binary_content: bytes
    message: str
    branch: str
    author_name: str
    author_email: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., repo_id: _Optional[str] = ..., path: _Optional[str] = ..., text_content: _Optional[str] = ..., binary_content: _Optional[bytes] = ..., message: _Optional[str] = ..., branch: _Optional[str] = ..., author_name: _Optional[str] = ..., author_email: _Optional[str] = ...) -> None: ...

class UpsertFileResponse(_message.Message):
    __slots__ = ("commit", "error")
    COMMIT_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    commit: Commit
    error: _common_pb2.CallError
    def __init__(self, commit: _Optional[_Union[Commit, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class UpsertFilesRequest(_message.Message):
    __slots__ = ("context", "repo_id", "files", "message", "branch", "author_name", "author_email")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    REPO_ID_FIELD_NUMBER: _ClassVar[int]
    FILES_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    BRANCH_FIELD_NUMBER: _ClassVar[int]
    AUTHOR_NAME_FIELD_NUMBER: _ClassVar[int]
    AUTHOR_EMAIL_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    repo_id: str
    files: _containers.RepeatedCompositeFieldContainer[FileWrite]
    message: str
    branch: str
    author_name: str
    author_email: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., repo_id: _Optional[str] = ..., files: _Optional[_Iterable[_Union[FileWrite, _Mapping]]] = ..., message: _Optional[str] = ..., branch: _Optional[str] = ..., author_name: _Optional[str] = ..., author_email: _Optional[str] = ...) -> None: ...

class UpsertFilesResponse(_message.Message):
    __slots__ = ("commit", "error")
    COMMIT_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    commit: Commit
    error: _common_pb2.CallError
    def __init__(self, commit: _Optional[_Union[Commit, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class ListCommitsRequest(_message.Message):
    __slots__ = ("context", "repo_id", "ref", "limit")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    REPO_ID_FIELD_NUMBER: _ClassVar[int]
    REF_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    repo_id: str
    ref: str
    limit: int
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., repo_id: _Optional[str] = ..., ref: _Optional[str] = ..., limit: _Optional[int] = ...) -> None: ...

class ListCommitsResponse(_message.Message):
    __slots__ = ("commits", "error")
    COMMITS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    commits: Commits
    error: _common_pb2.CallError
    def __init__(self, commits: _Optional[_Union[Commits, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class ListBranchesRequest(_message.Message):
    __slots__ = ("context", "repo_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    REPO_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    repo_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., repo_id: _Optional[str] = ...) -> None: ...

class ListBranchesResponse(_message.Message):
    __slots__ = ("branches", "error")
    BRANCHES_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    branches: Branches
    error: _common_pb2.CallError
    def __init__(self, branches: _Optional[_Union[Branches, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class CreateBranchRequest(_message.Message):
    __slots__ = ("context", "repo_id", "name", "from_ref")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    REPO_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    FROM_REF_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    repo_id: str
    name: str
    from_ref: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., repo_id: _Optional[str] = ..., name: _Optional[str] = ..., from_ref: _Optional[str] = ...) -> None: ...

class CreateBranchResponse(_message.Message):
    __slots__ = ("branch", "error")
    BRANCH_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    branch: Branch
    error: _common_pb2.CallError
    def __init__(self, branch: _Optional[_Union[Branch, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class DeleteBranchRequest(_message.Message):
    __slots__ = ("context", "repo_id", "name")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    REPO_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    repo_id: str
    name: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., repo_id: _Optional[str] = ..., name: _Optional[str] = ...) -> None: ...

class DeleteBranchResponse(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class GetDiffRequest(_message.Message):
    __slots__ = ("context", "repo_id", "base", "head")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    REPO_ID_FIELD_NUMBER: _ClassVar[int]
    BASE_FIELD_NUMBER: _ClassVar[int]
    HEAD_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    repo_id: str
    base: str
    head: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., repo_id: _Optional[str] = ..., base: _Optional[str] = ..., head: _Optional[str] = ...) -> None: ...

class GetDiffResponse(_message.Message):
    __slots__ = ("diff", "error")
    DIFF_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    diff: Diff
    error: _common_pb2.CallError
    def __init__(self, diff: _Optional[_Union[Diff, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class CreateProposalRequest(_message.Message):
    __slots__ = ("context", "repo_id", "title", "body", "source_branch", "target_branch", "reviewers")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    REPO_ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    BODY_FIELD_NUMBER: _ClassVar[int]
    SOURCE_BRANCH_FIELD_NUMBER: _ClassVar[int]
    TARGET_BRANCH_FIELD_NUMBER: _ClassVar[int]
    REVIEWERS_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    repo_id: str
    title: str
    body: str
    source_branch: str
    target_branch: str
    reviewers: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., repo_id: _Optional[str] = ..., title: _Optional[str] = ..., body: _Optional[str] = ..., source_branch: _Optional[str] = ..., target_branch: _Optional[str] = ..., reviewers: _Optional[_Iterable[str]] = ...) -> None: ...

class CreateProposalResponse(_message.Message):
    __slots__ = ("proposal", "error")
    PROPOSAL_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    proposal: Proposal
    error: _common_pb2.CallError
    def __init__(self, proposal: _Optional[_Union[Proposal, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class ListProposalsRequest(_message.Message):
    __slots__ = ("context", "repo_id", "state")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    REPO_ID_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    repo_id: str
    state: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., repo_id: _Optional[str] = ..., state: _Optional[str] = ...) -> None: ...

class ListProposalsResponse(_message.Message):
    __slots__ = ("proposals", "error")
    PROPOSALS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    proposals: Proposals
    error: _common_pb2.CallError
    def __init__(self, proposals: _Optional[_Union[Proposals, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class GetProposalRequest(_message.Message):
    __slots__ = ("context", "repo_id", "number")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    REPO_ID_FIELD_NUMBER: _ClassVar[int]
    NUMBER_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    repo_id: str
    number: int
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., repo_id: _Optional[str] = ..., number: _Optional[int] = ...) -> None: ...

class GetProposalResponse(_message.Message):
    __slots__ = ("proposal", "error")
    PROPOSAL_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    proposal: Proposal
    error: _common_pb2.CallError
    def __init__(self, proposal: _Optional[_Union[Proposal, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class GetProposalDiffRequest(_message.Message):
    __slots__ = ("context", "repo_id", "number")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    REPO_ID_FIELD_NUMBER: _ClassVar[int]
    NUMBER_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    repo_id: str
    number: int
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., repo_id: _Optional[str] = ..., number: _Optional[int] = ...) -> None: ...

class GetProposalDiffResponse(_message.Message):
    __slots__ = ("diff", "error")
    DIFF_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    diff: Diff
    error: _common_pb2.CallError
    def __init__(self, diff: _Optional[_Union[Diff, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class ListProposalCommitsRequest(_message.Message):
    __slots__ = ("context", "repo_id", "number")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    REPO_ID_FIELD_NUMBER: _ClassVar[int]
    NUMBER_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    repo_id: str
    number: int
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., repo_id: _Optional[str] = ..., number: _Optional[int] = ...) -> None: ...

class ListProposalCommitsResponse(_message.Message):
    __slots__ = ("commits", "error")
    COMMITS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    commits: Commits
    error: _common_pb2.CallError
    def __init__(self, commits: _Optional[_Union[Commits, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class ListCommentsRequest(_message.Message):
    __slots__ = ("context", "repo_id", "number")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    REPO_ID_FIELD_NUMBER: _ClassVar[int]
    NUMBER_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    repo_id: str
    number: int
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., repo_id: _Optional[str] = ..., number: _Optional[int] = ...) -> None: ...

class ListCommentsResponse(_message.Message):
    __slots__ = ("comments", "error")
    COMMENTS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    comments: Comments
    error: _common_pb2.CallError
    def __init__(self, comments: _Optional[_Union[Comments, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class ListReviewsRequest(_message.Message):
    __slots__ = ("context", "repo_id", "number")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    REPO_ID_FIELD_NUMBER: _ClassVar[int]
    NUMBER_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    repo_id: str
    number: int
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., repo_id: _Optional[str] = ..., number: _Optional[int] = ...) -> None: ...

class ListReviewsResponse(_message.Message):
    __slots__ = ("reviews", "error")
    REVIEWS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    reviews: Reviews
    error: _common_pb2.CallError
    def __init__(self, reviews: _Optional[_Union[Reviews, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class AddCommentRequest(_message.Message):
    __slots__ = ("context", "repo_id", "number", "body", "path", "line")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    REPO_ID_FIELD_NUMBER: _ClassVar[int]
    NUMBER_FIELD_NUMBER: _ClassVar[int]
    BODY_FIELD_NUMBER: _ClassVar[int]
    PATH_FIELD_NUMBER: _ClassVar[int]
    LINE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    repo_id: str
    number: int
    body: str
    path: str
    line: int
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., repo_id: _Optional[str] = ..., number: _Optional[int] = ..., body: _Optional[str] = ..., path: _Optional[str] = ..., line: _Optional[int] = ...) -> None: ...

class AddCommentResponse(_message.Message):
    __slots__ = ("comment", "error")
    COMMENT_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    comment: Comment
    error: _common_pb2.CallError
    def __init__(self, comment: _Optional[_Union[Comment, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class SubmitReviewRequest(_message.Message):
    __slots__ = ("context", "repo_id", "number", "event", "body")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    REPO_ID_FIELD_NUMBER: _ClassVar[int]
    NUMBER_FIELD_NUMBER: _ClassVar[int]
    EVENT_FIELD_NUMBER: _ClassVar[int]
    BODY_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    repo_id: str
    number: int
    event: str
    body: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., repo_id: _Optional[str] = ..., number: _Optional[int] = ..., event: _Optional[str] = ..., body: _Optional[str] = ...) -> None: ...

class SubmitReviewResponse(_message.Message):
    __slots__ = ("review", "error")
    REVIEW_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    review: Review
    error: _common_pb2.CallError
    def __init__(self, review: _Optional[_Union[Review, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class ListChecksRequest(_message.Message):
    __slots__ = ("context", "repo_id", "number")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    REPO_ID_FIELD_NUMBER: _ClassVar[int]
    NUMBER_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    repo_id: str
    number: int
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., repo_id: _Optional[str] = ..., number: _Optional[int] = ...) -> None: ...

class ListChecksResponse(_message.Message):
    __slots__ = ("checks", "error")
    CHECKS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    checks: Checks
    error: _common_pb2.CallError
    def __init__(self, checks: _Optional[_Union[Checks, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class SetBranchProtectionRequest(_message.Message):
    __slots__ = ("context", "repo_id", "branch", "required_approvals", "required_checks")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    REPO_ID_FIELD_NUMBER: _ClassVar[int]
    BRANCH_FIELD_NUMBER: _ClassVar[int]
    REQUIRED_APPROVALS_FIELD_NUMBER: _ClassVar[int]
    REQUIRED_CHECKS_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    repo_id: str
    branch: str
    required_approvals: int
    required_checks: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., repo_id: _Optional[str] = ..., branch: _Optional[str] = ..., required_approvals: _Optional[int] = ..., required_checks: _Optional[_Iterable[str]] = ...) -> None: ...

class SetBranchProtectionResponse(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class MergeRequest(_message.Message):
    __slots__ = ("context", "repo_id", "number", "method")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    REPO_ID_FIELD_NUMBER: _ClassVar[int]
    NUMBER_FIELD_NUMBER: _ClassVar[int]
    METHOD_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    repo_id: str
    number: int
    method: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., repo_id: _Optional[str] = ..., number: _Optional[int] = ..., method: _Optional[str] = ...) -> None: ...

class MergeResponse(_message.Message):
    __slots__ = ("merge_result", "error")
    MERGE_RESULT_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    merge_result: MergeResult
    error: _common_pb2.CallError
    def __init__(self, merge_result: _Optional[_Union[MergeResult, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class ListWorkflowRunsRequest(_message.Message):
    __slots__ = ("context", "repo_id", "limit")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    REPO_ID_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    repo_id: str
    limit: int
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., repo_id: _Optional[str] = ..., limit: _Optional[int] = ...) -> None: ...

class ListWorkflowRunsResponse(_message.Message):
    __slots__ = ("workflow_runs", "error")
    WORKFLOW_RUNS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    workflow_runs: WorkflowRuns
    error: _common_pb2.CallError
    def __init__(self, workflow_runs: _Optional[_Union[WorkflowRuns, _Mapping]] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class MintGitTokenRequest(_message.Message):
    __slots__ = ("context", "user_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    user_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., user_id: _Optional[str] = ...) -> None: ...

class MintGitTokenResponse(_message.Message):
    __slots__ = ("token", "error")
    TOKEN_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    token: str
    error: _common_pb2.CallError
    def __init__(self, token: _Optional[str] = ..., error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...
