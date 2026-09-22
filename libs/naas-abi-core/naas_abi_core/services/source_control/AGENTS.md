# Source control service

## Purpose
Backend-independent repository, file, branch, and review operations.

## Files and port
`SourceControlPorts.py` defines DTOs, exceptions and `ISourceControlAdapter`.
`SourceControlService.py` delegates operations and publishes review events.

## Adapters and factory
`adapters/secondary/` contains Forgejo, LocalGit and InMemory implementations.
`SourceControlFactory.py` configures the adapter.

## Conditional writes
`compare_and_swap_file` requires the SHA-256 `content_revision` of the UTF-8
content read by the caller. A mismatch raises `RevisionConflictError`; callers
must preserve local edits and reload explicitly. Never retry with a fresh token.
Forgejo uses its conditional blob SHA update; LocalGit uses a private index and
atomic update-ref with the expected branch head. Unsupported adapters fail closed.

## Tests
Run pytest on `services/source_control/tests/` and colocated adapter tests.

## Adding an adapter
Implement the port and its contract tests. Do not emulate conditional writes with
an unlocked read followed by an unconditional write.
