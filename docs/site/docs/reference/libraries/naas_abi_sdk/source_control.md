# SourceControlClient

## What it is
An async client wrapper around `Transport` for calling the `abi.svc.source_control.v1` Source Control service. Each method forwards a protobuf request message to `transport.call(...)` and returns the corresponding protobuf response.

## Public API
### Class: `SourceControlClient`
- `__init__(transport: Transport) -> None`  
  - Stores the provided transport used to make RPC calls.

All methods below are `async` and have the form:
- input: a request message from `naas_abi_proto.source_control.v1.source_control_pb2`
- output: the corresponding response message
- behavior: `return await self._transport.call(<rpc_name>, request, <ResponseType>)`

#### User/Repo
- `ensure_user(request: pb.EnsureUserRequest) -> pb.EnsureUserResponse`  
  Ensure a source-control user exists.
- `ensure_repo(request: pb.EnsureRepoRequest) -> pb.EnsureRepoResponse`  
  Ensure a repository exists.
- `list_repos(request: pb.ListReposRequest) -> pb.ListReposResponse`  
  List repositories.
- `delete_repo(request: pb.DeleteRepoRequest) -> pb.DeleteRepoResponse`  
  Delete a repository.
- `add_collaborator(request: pb.AddCollaboratorRequest) -> pb.AddCollaboratorResponse`  
  Add a collaborator to a repository.

#### Repository contents / files
- `list_contents(request: pb.ListContentsRequest) -> pb.ListContentsResponse`  
  List repository contents.
- `get_file(request: pb.GetFileRequest) -> pb.GetFileResponse`  
  Fetch a file.
- `upsert_file(request: pb.UpsertFileRequest) -> pb.UpsertFileResponse`  
  Create or update a file.
- `upsert_files(request: pb.UpsertFilesRequest) -> pb.UpsertFilesResponse`  
  Create or update multiple files.

#### History / branches / diffs
- `list_commits(request: pb.ListCommitsRequest) -> pb.ListCommitsResponse`  
  List commits.
- `list_branches(request: pb.ListBranchesRequest) -> pb.ListBranchesResponse`  
  List branches.
- `create_branch(request: pb.CreateBranchRequest) -> pb.CreateBranchResponse`  
  Create a branch.
- `delete_branch(request: pb.DeleteBranchRequest) -> pb.DeleteBranchResponse`  
  Delete a branch.
- `get_diff(request: pb.GetDiffRequest) -> pb.GetDiffResponse`  
  Get a diff.

#### Proposals (e.g., PR/MR equivalents)
- `create_proposal(request: pb.CreateProposalRequest) -> pb.CreateProposalResponse`  
  Create a proposal.
- `list_proposals(request: pb.ListProposalsRequest) -> pb.ListProposalsResponse`  
  List proposals.
- `get_proposal(request: pb.GetProposalRequest) -> pb.GetProposalResponse`  
  Get a proposal.
- `get_proposal_diff(request: pb.GetProposalDiffRequest) -> pb.GetProposalDiffResponse`  
  Get proposal diff.
- `list_proposal_commits(request: pb.ListProposalCommitsRequest) -> pb.ListProposalCommitsResponse`  
  List commits in a proposal.

#### Collaboration / reviews / checks
- `list_comments(request: pb.ListCommentsRequest) -> pb.ListCommentsResponse`  
  List comments.
- `list_reviews(request: pb.ListReviewsRequest) -> pb.ListReviewsResponse`  
  List reviews.
- `add_comment(request: pb.AddCommentRequest) -> pb.AddCommentResponse`  
  Add a comment.
- `submit_review(request: pb.SubmitReviewRequest) -> pb.SubmitReviewResponse`  
  Submit a review.
- `list_checks(request: pb.ListChecksRequest) -> pb.ListChecksResponse`  
  List checks.

#### Policy / merge / workflows / tokens
- `set_branch_protection(request: pb.SetBranchProtectionRequest) -> pb.SetBranchProtectionResponse`  
  Configure branch protection.
- `merge(request: pb.MergeRequest) -> pb.MergeResponse`  
  Merge a proposal/branch (service-defined).
- `list_workflow_runs(request: pb.ListWorkflowRunsRequest) -> pb.ListWorkflowRunsResponse`  
  List workflow runs.
- `mint_git_token(request: pb.MintGitTokenRequest) -> pb.MintGitTokenResponse`  
  Mint a git token.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_sdk.transport.Transport` providing an async `call(name, request, response_type)` method.
  - Protobuf messages from `naas_abi_proto.source_control.v1.source_control_pb2` imported as `pb`.
- All operations are asynchronous; requires an asyncio event loop.

## Usage
```python
import asyncio
from naas_abi_sdk.source_control import SourceControlClient
from naas_abi_proto.source_control.v1 import source_control_pb2 as pb

async def main(transport):
    client = SourceControlClient(transport)

    # Example call (populate fields as required by your proto schema)
    resp = await client.list_repos(pb.ListReposRequest())
    print(resp)

# asyncio.run(main(transport))  # provide a configured Transport instance
```

## Caveats
- This module only forwards requests to `Transport.call`; it does not validate request contents or perform retries/error handling.
- Request/response fields and required parameters are defined by the protobuf schema (`source_control_pb2`), not by this client.
