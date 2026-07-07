# CHANGELOG

<!-- version list -->

## v2.9.0 (2026-07-07)

### Bug Fixes

- **coder**: Activate dormant users + strip internal app-proxy port
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **coder**: Native-arch workspace agent + gate readiness on app health
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **coder**: Raise admin token max lifetime so the Nexus admin token doesn't expire weekly
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **coder**: Sanitize Coder username + map invalid/missing workspace id to not-found
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **coder-adapter**: Unique per-mint token name so get_access is repeatable
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **coder-template**: Clear /tmp/template before push so it can't ship stale content
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **coder-template**: Ensure $HOME/project exists for code-server
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **coding-env**: Disable built-in Chat; drop unworkable state.vscdb layout seed
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **coding-env**: Hide deleting workspaces from the list
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **coding-env**: Move VS Code's built-in Chat off the right bar so Continue shows
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **coding-env**: Pin Continue to 1.3.40 so injected agents show
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **coding-env**: Reliable workspace delete (keep shared image; recover stuck)
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **coding-env**: Show Continue chat on the right by default in new workspaces
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **deploy**: Dagster also waits on coding-init
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **engine**: Wire coding_environment + source_control into engine.services
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **nexus/code**: Complete the empty-repo push instructions (commit + auth)
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **nexus/code**: Grant push access when generating a token (fixes 'repo not found')
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **openai-shim**: Carry chat id in the reply instead of hashing the first message
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **openai-shim**: Stable per-conversation thread id so chat has memory
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **platform**: Gate root (unscoped) datastore access to superadmins
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **source-control**: Populate PR diff patches from the raw .diff endpoint
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **source-control,nexus**: Address adversarial-review findings
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

### Chores

- **coder-prototype**: Don't ship a default admin password
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **stack**: Disable headscale (unused, crash-looping)
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

### Features

- In-app coding workspaces (Nexus IDE) — Phases 1–4
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **agent-core**: Only expose workspace tools when a workspace is bound
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **agents**: Add PlatformServicesAgent with access to platform data services
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **code-review**: Actions tab — CI workflow runs in the repo view
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **code-review**: GitHub-style file tree + full-width diffs in PR Files tab
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **code-review**: GitHub-style per-project pull-request UI
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **coder-template**: Continue + branch-per-workspace in the workspace template (Phase 2)
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **coding-env**: Auto-clone the monorepo on a chosen branch
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **coding-env**: Auto-wire the workspace exec sidecar at provision time
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **coding-env**: Clear clone credentials via a Clone dropdown
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **coding-env**: Clone box copies a ready-to-paste git clone command
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **coding-env**: Commits view, latest-commit bar, line numbers, slimmer tab headers
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **coding-env**: Continue lists every registered agent, built at provision time
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **coding-env**: In-workspace dev-server preview + Continue as the only AI chat
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **coding-env**: List a user's coding workspaces in Nexus
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **coding-env**: Make workspace tools generic + confirm tool-only turns
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **coding-env**: Option B agent->workspace bridge (write_file slice)
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **coding-env**: Phase 2 — run_terminal tool + auto-show Continue
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **coding-env**: PR review UI — file diffs + publish reviews
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **coding-env**: Scope the workspaces list per repo
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **coding-env**: Stream provisioning + startup logs while a workspace prepares
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **coding-env**: Suggest a random workspace name instead of always 'dev'
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **coding-env**: Wire in-IDE agents — inject token + API base for Continue
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **coding-environment**: Add coding environment core service + in-app IDE RFC
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **coding-environment**: Per-user environments API + Coder deployment (Phase 1)
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **core/source-control**: Add source_control hexagonal service (Phase 3)
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **deploy**: Add `abi deploy local --coding` for the coding-workspaces stack
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **deploy**: Auto-mint coding tokens via a coding-init one-shot
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **new**: Default embedding model to text-embedding-3-large (chatgpt module)
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **new**: Default the model registry to Opus 4.8 via OpenRouter
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **new**: Enable password login by default (no SMTP needed on first run)
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **new**: Enable the 'code' feature flag for workspace admins with --with-coding
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **new**: Thread --with-coding through `abi new project`
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **nexus**: Gate the coding workspaces behind a 'code' feature flag (off by default)
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **nexus/code**: GitHub-style repository UI (index, repo page, file browser)
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **nexus/code**: Multi-repository support + left-panel navigation
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **nexus/code**: Push panel — self-signed TLS skip + copyable tokenized remote
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **nexus/code**: Repo onboarding — empty repo + push instructions + team default
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **nexus/code**: Restore the shared top bar (API status, etc.) in Code
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **nexus/code**: Unify IDE + Review into one Code sub-app with branch management
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **nexus/code-review**: In-app review API + Forgejo deployment (Phase 3)
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **nexus/ide**: Coding workspace IDE page + sidebar nav (Phase 1 frontend)
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **nexus/openai-gateway**: OpenAI-compatible shim over abi agents (Phase 2)
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **nexus/review**: In-app code review UI page + nav (Phase 3 frontend)
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **nexus/verticals**: Vertical framework scaffold (Phase 4)
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **openai-shim**: Stream tool calls + results to the client
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **platform**: Add --root (whole-datastore) mode to storage API + CLI
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **platform**: Add the thin abi-platform workspace CLI
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **platform**: Serve + install the abi-platform CLI in workspaces
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **platform**: Streaming object-storage upload (put_object_stream)
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **platform**: Workspace-facing object-storage read API
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))

- **source-control**: Repo browsing API (contents, file, commits, metadata)
  ([#1039](https://github.com/jupyter-naas/abi/pull/1039),
  [`ed38d06`](https://github.com/jupyter-naas/abi/commit/ed38d063dcffb1eb4ccc5c64a65e3cebfb33c09c))


## v2.8.0 (2026-07-07)

### Features

- **cli**: Add periodic Fuseki TDB2 compaction sidecar to local stack
  ([#1058](https://github.com/jupyter-naas/abi/pull/1058),
  [`b14a5fe`](https://github.com/jupyter-naas/abi/commit/b14a5fe7e97e7ec6f9e4db5c11ca03bdc08b0084))


## v2.7.0 (2026-07-02)

### Features

- **cli**: Add 'abi stack snapshot' for stack snapshot/rollback/migrate
  ([#1052](https://github.com/jupyter-naas/abi/pull/1052),
  [`c9aa7ee`](https://github.com/jupyter-naas/abi/commit/c9aa7ee6a6d63ab1715569b65c7007d5d118dd8e))


## v2.6.1 (2026-07-01)

### Bug Fixes

- Do not enforce chatgpt module on abi new module
  ([`9f6f3ff`](https://github.com/jupyter-naas/abi/commit/9f6f3ff3bc4bb4cd4b19b588fda9223466b91289))


## v2.6.0 (2026-06-30)

### Features

- **x**: Add scheduled files-reprocessing sensors for search_recent_tweets_files
  ([`aea27f6`](https://github.com/jupyter-naas/abi/commit/aea27f6b482011b1bb5f9bb487bfd9b8b3415729))


## v2.5.1 (2026-06-29)

### Bug Fixes

- **email**: Simplify attachment inline and cid handling
  ([`17bc48d`](https://github.com/jupyter-naas/abi/commit/17bc48dd744de843b35ee57facf43241c2b55f64))


## v2.5.0 (2026-06-28)


## v2.4.1 (2026-06-25)

### Bug Fixes

- **dev**: Use os.path.relpath for symlink target in _ensure_nexus_web_sources
  ([`342c92e`](https://github.com/jupyter-naas/abi/commit/342c92ee82430d27263cc8e922330920c596ba17))


## v2.4.0 (2026-06-23)

### Features

- **x**: Update recent tweets workflow and tests
  ([`58434a2`](https://github.com/jupyter-naas/abi/commit/58434a2c88368d2832b3ddc3150652d2e4b06fe9))


## v2.3.1 (2026-06-17)


## v2.3.0 (2026-06-16)

### Features

- **app-html**: Add support for serving bundled Nexus app HTML via /app-html/ proxy
  ([`047090a`](https://github.com/jupyter-naas/abi/commit/047090a0f0ac065aa692df99d1aa8eb864e13a19))


## v2.2.0 (2026-06-11)

### Chores

- Update lockfiles
  ([`ddbb3cb`](https://github.com/jupyter-naas/abi/commit/ddbb3cb169c80e5f0092833a1db4ee2c4483845f))

### Features

- **naas-abi-cli**: Add `new app` command and app scaffolding templates
  ([`cd2bbb0`](https://github.com/jupyter-naas/abi/commit/cd2bbb09b5ff1ce4a1ed554c4b5f0ed3fffb7b1b))

- **naas-abi-cli**: Modernise agent template scaffold
  ([`0cc6df5`](https://github.com/jupyter-naas/abi/commit/0cc6df5ff195c983e0dd46594ff996315bb64782))


## v2.1.1 (2026-06-08)

### Bug Fixes

- **uv.lock**: Update naas-abi package version to 2.21.0
  ([`877a861`](https://github.com/jupyter-naas/abi/commit/877a861c829ccf8b82e04d072c9e061df8a37da1))


## v2.1.0 (2026-06-05)

### Features

- **graph**: Improve graph discovery adapter and export formatting
  ([`97448a7`](https://github.com/jupyter-naas/abi/commit/97448a7c3d9239a1e4148ca4aac23a9079a82df4))

- **graph-discovery**: Update graph discovery page and bump versions
  ([`3f653c8`](https://github.com/jupyter-naas/abi/commit/3f653c898a015a7d6c7a5966147a3b5871057e62))


## v2.0.0 (2026-06-04)

### Bug Fixes

- **test**: Refine _assert_routed_to function in XAgent_test.py
  ([#1004](https://github.com/jupyter-naas/abi/pull/1004),
  [`bf8e9b7`](https://github.com/jupyter-naas/abi/commit/bf8e9b71d5834c24f9d2658bd5c29e80399a273b))

- **x**: Cd to project root from generate_tweet_dump.sh before delegating
  ([#1004](https://github.com/jupyter-naas/abi/pull/1004),
  [`bf8e9b7`](https://github.com/jupyter-naas/abi/commit/bf8e9b71d5834c24f9d2658bd5c29e80399a273b))

- **x**: Update X application module and pipelines
  ([#1004](https://github.com/jupyter-naas/abi/pull/1004),
  [`bf8e9b7`](https://github.com/jupyter-naas/abi/commit/bf8e9b71d5834c24f9d2658bd5c29e80399a273b))

### Chores

- Update lockfile ([#1004](https://github.com/jupyter-naas/abi/pull/1004),
  [`bf8e9b7`](https://github.com/jupyter-naas/abi/commit/bf8e9b71d5834c24f9d2658bd5c29e80399a273b))

### Features

- **object_storage**: Add streaming get_object_stream to the port
  ([#1004](https://github.com/jupyter-naas/abi/pull/1004),
  [`bf8e9b7`](https://github.com/jupyter-naas/abi/commit/bf8e9b71d5834c24f9d2658bd5c29e80399a273b))

- **twitter**: Add ontology and action classes for X (Twitter) entities
  ([#1004](https://github.com/jupyter-naas/abi/pull/1004),
  [`bf8e9b7`](https://github.com/jupyter-naas/abi/commit/bf8e9b71d5834c24f9d2658bd5c29e80399a273b))

- **twitter-module**: Add read-only X (Twitter) v2 API integration with LangChain agent
  ([#1004](https://github.com/jupyter-naas/abi/pull/1004),
  [`bf8e9b7`](https://github.com/jupyter-naas/abi/commit/bf8e9b71d5834c24f9d2658bd5c29e80399a273b))

- **twitter-module**: Add X (Twitter) API integration module, agent, and tests
  ([#1004](https://github.com/jupyter-naas/abi/pull/1004),
  [`bf8e9b7`](https://github.com/jupyter-naas/abi/commit/bf8e9b71d5834c24f9d2658bd5c29e80399a273b))

- **utils**: Enhance ontology discovery and import resolution
  ([#1004](https://github.com/jupyter-naas/abi/pull/1004),
  [`bf8e9b7`](https://github.com/jupyter-naas/abi/commit/bf8e9b71d5834c24f9d2658bd5c29e80399a273b))

- **x**: Add initial X orchestration and workflow implementations
  ([#1004](https://github.com/jupyter-naas/abi/pull/1004),
  [`bf8e9b7`](https://github.com/jupyter-naas/abi/commit/bf8e9b71d5834c24f9d2658bd5c29e80399a273b))

- **x**: Add per-filter Dagster ingestion + ingested-tweets agent tools
  ([#1004](https://github.com/jupyter-naas/abi/pull/1004),
  [`bf8e9b7`](https://github.com/jupyter-naas/abi/commit/bf8e9b71d5834c24f9d2658bd5c29e80399a273b))

- **x**: Add SPARQL query capabilities and tests for X agent
  ([#1004](https://github.com/jupyter-naas/abi/pull/1004),
  [`bf8e9b7`](https://github.com/jupyter-naas/abi/commit/bf8e9b71d5834c24f9d2658bd5c29e80399a273b))

- **x**: Add XSearchRecentTweetsPipeline and tests
  ([#1004](https://github.com/jupyter-naas/abi/pull/1004),
  [`bf8e9b7`](https://github.com/jupyter-naas/abi/commit/bf8e9b71d5834c24f9d2658bd5c29e80399a273b))

- **x**: Bash wrapper around generate_tweet_dump
  ([#1004](https://github.com/jupyter-naas/abi/pull/1004),
  [`bf8e9b7`](https://github.com/jupyter-naas/abi/commit/bf8e9b71d5834c24f9d2658bd5c29e80399a273b))

- **x**: CLI to generate a tweet dump file from the search endpoint
  ([#1004](https://github.com/jupyter-naas/abi/pull/1004),
  [`bf8e9b7`](https://github.com/jupyter-naas/abi/commit/bf8e9b71d5834c24f9d2658bd5c29e80399a273b))

- **x**: Event-driven auto-discovery of tweet dump files
  ([#1004](https://github.com/jupyter-naas/abi/pull/1004),
  [`bf8e9b7`](https://github.com/jupyter-naas/abi/commit/bf8e9b71d5834c24f9d2658bd5c29e80399a273b))

- **x**: Integrate XIntegration.search_recent_tweets and enhance XSearchRecentTweetsPipeline
  ([#1004](https://github.com/jupyter-naas/abi/pull/1004),
  [`bf8e9b7`](https://github.com/jupyter-naas/abi/commit/bf8e9b71d5834c24f9d2658bd5c29e80399a273b))

- **x**: Rename agent to "X", add logo, fix ingested-tweets drill-in
  ([#1004](https://github.com/jupyter-naas/abi/pull/1004),
  [`bf8e9b7`](https://github.com/jupyter-naas/abi/commit/bf8e9b71d5834c24f9d2658bd5c29e80399a273b))

- **x**: Stream large tweet-dump files from object storage into the graph
  ([#1004](https://github.com/jupyter-naas/abi/pull/1004),
  [`bf8e9b7`](https://github.com/jupyter-naas/abi/commit/bf8e9b71d5834c24f9d2658bd5c29e80399a273b))

- **x**: Tool to generate a tweet dump file from a search query
  ([#1004](https://github.com/jupyter-naas/abi/pull/1004),
  [`bf8e9b7`](https://github.com/jupyter-naas/abi/commit/bf8e9b71d5834c24f9d2658bd5c29e80399a273b))

- **x**: Unwrap X v2 search_recent_tweets envelopes during file ingestion
  ([#1004](https://github.com/jupyter-naas/abi/pull/1004),
  [`bf8e9b7`](https://github.com/jupyter-naas/abi/commit/bf8e9b71d5834c24f9d2658bd5c29e80399a273b))

- **x_search_recent_tweets**: Enhance recent tweets search with extended parameters
  ([#1004](https://github.com/jupyter-naas/abi/pull/1004),
  [`bf8e9b7`](https://github.com/jupyter-naas/abi/commit/bf8e9b71d5834c24f9d2658bd5c29e80399a273b))

### Refactoring

- **x**: Leverage `abi run script` in generate_tweet_dump
  ([#1004](https://github.com/jupyter-naas/abi/pull/1004),
  [`bf8e9b7`](https://github.com/jupyter-naas/abi/commit/bf8e9b71d5834c24f9d2658bd5c29e80399a273b))

- **x**: Move generate_tweet_dump CLI under the X module
  ([#1004](https://github.com/jupyter-naas/abi/pull/1004),
  [`bf8e9b7`](https://github.com/jupyter-naas/abi/commit/bf8e9b71d5834c24f9d2658bd5c29e80399a273b))


## v1.43.2 (2026-06-04)

### Bug Fixes

- **api**: Clean up analytics primary adapter code formatting and imports
  ([`e83b4e5`](https://github.com/jupyter-naas/abi/commit/e83b4e52ce91ade2cdb9e813bd041d06ea2995d0))

### Chores

- Update naas-abi and related package versions in uv.lock
  ([`e83b4e5`](https://github.com/jupyter-naas/abi/commit/e83b4e52ce91ade2cdb9e813bd041d06ea2995d0))

### Documentation

- **agents**: Scaffold AGENTS.md across services, marketplace, and generated projects
  ([`ae73bc5`](https://github.com/jupyter-naas/abi/commit/ae73bc57c6299d8d828be6a77990c658176ba07d))


## v1.43.1 (2026-05-28)

### Bug Fixes

- **dev**: Use dynamic nexus url for magic links
  ([`af984c1`](https://github.com/jupyter-naas/abi/commit/af984c1978aa946736555390c6abdb9e956c18bd))


## v1.43.0 (2026-05-28)

### Features

- Add new models and change bedrock default
  ([`2c4082b`](https://github.com/jupyter-naas/abi/commit/2c4082b840cc59bf16f5b27168b70762adfbc4ad))


## v1.42.2 (2026-05-26)

### Bug Fixes

- **core/event**: Satisfy ruff and mypy after benchmark addition
  ([`27aba61`](https://github.com/jupyter-naas/abi/commit/27aba61d114cb64c3f9a9467b785a40b2ca915fc))


## v1.42.1 (2026-05-26)


## v1.42.0 (2026-05-21)

### Features

- **settings**: Add sidebar and layout for workspace settings
  ([`cdeb381`](https://github.com/jupyter-naas/abi/commit/cdeb381289dbf7c2d8499662c29ee49ac3f5365a))

- **system-drive**: Add support for system drive access in workspaces
  ([`0061150`](https://github.com/jupyter-naas/abi/commit/006115008f4ac3aff1898552665f40a8786a4434))


## v1.41.0 (2026-05-19)

### Features

- **nexus**: Split feature flags per sidebar section
  ([`29c1a29`](https://github.com/jupyter-naas/abi/commit/29c1a299ea641ec456081dcc25c00453f26ce6e2))


## v1.40.0 (2026-05-18)

### Features

- **cli**: Add --modules flag to `abi config validate`
  ([`8633114`](https://github.com/jupyter-naas/abi/commit/86331146e210343d6eb33198b6a4d168f28af518))


## v1.39.1 (2026-05-18)

### Bug Fixes

- **cli**: Install libgl1 and libglib2.0-0 in deploy templates
  ([`46307dc`](https://github.com/jupyter-naas/abi/commit/46307dce10979f400241d347677e284885322a0c))


## v1.39.0 (2026-05-18)


## v1.38.0 (2026-05-18)

### Bug Fixes

- **cors**: Share one ApiConfiguration across api + Nexus + Socket.IO
  ([`8d59cca`](https://github.com/jupyter-naas/abi/commit/8d59cca81d1369e4f943a7b91cb448c71007b362))

### Chores

- Bump versions in uv.lock files for naas-abi and naas-abi-core to 1.53.1 and 1.40.0 respectively
  ([`24fb100`](https://github.com/jupyter-naas/abi/commit/24fb100f3659f285e4d1d7aec02eddbfa93073f7))

- **deps**: Refresh naas-abi-cli uv.lock for aiosqlite
  ([`0fc7c91`](https://github.com/jupyter-naas/abi/commit/0fc7c9113e6580f80e6103b5940f2cf97a0d67fb))

### Features

- **dev**: `r` hotkey to restart the stack without leaving `abi dev up`
  ([`f7ff5ba`](https://github.com/jupyter-naas/abi/commit/f7ff5ba170926322008deec5436f046e84de9659))

- **dev**: Bundled oxigraph HTTP server for concurrent triple-store access
  ([`e8a5d3d`](https://github.com/jupyter-naas/abi/commit/e8a5d3dc37c3c39cf571fd2b03e715ae32f264e8))

- **dev**: Dockerless dev mode via `abi dev` + SQLite Nexus
  ([`7f42bff`](https://github.com/jupyter-naas/abi/commit/7f42bffcf8dc2be1455e53c0d763389bdf72142a))

- **dev**: Seed a default admin user in the dockerless config
  ([`f7eeb3b`](https://github.com/jupyter-naas/abi/commit/f7eeb3bdb28f4f29274dee8556e5c5073bb13e6d))

- **vector-store**: SQLite + sqlite-vec adapter for dev
  ([`eb6b571`](https://github.com/jupyter-naas/abi/commit/eb6b5716b6f041b7f97258efb6b1a63e5158985c))


## v1.37.0 (2026-05-18)

### Features

- **workspace/[workspaceId]/graph**: Add export progress log UI
  ([`7e30caf`](https://github.com/jupyter-naas/abi/commit/7e30cafe067c386f56b4aea49911f1b6f86f40e5))


## v1.36.1 (2026-05-16)

### Bug Fixes

- **config**: Replace Jinja2-evaluated secret.X comments with backtick syntax
  ([`68540b9`](https://github.com/jupyter-naas/abi/commit/68540b9c958e5204105f0d316facc27b6bebc25d))


## v1.36.0 (2026-05-15)

### Bug Fixes

- Update naas-abi and naas-abi-marketplace package versions in uv.lock
  ([`500a752`](https://github.com/jupyter-naas/abi/commit/500a7526b012a8d58ac42a1e1a6279de0b4ea7fe))

### Features

- **nexus**: Enhance NexusPlatformPipeline with AIModel and Capabilities support
  ([`49c4a94`](https://github.com/jupyter-naas/abi/commit/49c4a9458f6b052a6593393f3486e4838c11cfe9))


## v1.35.0 (2026-05-15)

### Bug Fixes

- **Agent**: Disable markdown_pretty_display by default
  ([`9bf481c`](https://github.com/jupyter-naas/abi/commit/9bf481c432727a3fba47779190850074ab1f7cb0))

### Features

- **chat**: Add message metadata update and export functionality
  ([`1fc2d25`](https://github.com/jupyter-naas/abi/commit/1fc2d25ee000d6f4fe62bc2a416570a211a906eb))


## v1.34.1 (2026-05-14)

### Bug Fixes

- **suggestions**: Restore rich fields after rebase, swap disabled states, rename App to Apps
  ([`9395da1`](https://github.com/jupyter-naas/abi/commit/9395da1c14f11451e8996c3393604189633f7f9f))


## v1.34.0 (2026-05-14)

### Bug Fixes

- **cli**: Align deploy templates + drop dead .env.example
  ([`58b6b4a`](https://github.com/jupyter-naas/abi/commit/58b6b4ad9c9f861b60ac1eb746f9581a97f2122e))

### Chores

- Remove unused matrix/element services and stale comment refs
  ([`2acbbb0`](https://github.com/jupyter-naas/abi/commit/2acbbb0725a736fa9d01fc23f9f6e1e76daa33da))

### Features

- **cli**: Open Nexus web app on stack start instead of service portal
  ([`9eae875`](https://github.com/jupyter-naas/abi/commit/9eae875c531fb014c8f543b089161cf57221fa13))

- **ux**: Pre-fill login email from NEXUS_USER_ADMIN_EMAIL on local stack start
  ([`92d1fb9`](https://github.com/jupyter-naas/abi/commit/92d1fb90bb4240739a24d777855d67764d315a4d))


## v1.33.0 (2026-05-13)

### Features

- **document**: Add HtmlToVectorPipeline + vision-LLM image captioning
  ([`7f1cb29`](https://github.com/jupyter-naas/abi/commit/7f1cb29894be8fe28efbd138b2e93dfbe7d6d625))


## v1.32.0 (2026-05-13)

### Features

- **nexus-web**: Drive-aware breadcrumb and portalised status popover
  ([`28963e2`](https://github.com/jupyter-naas/abi/commit/28963e2d7df7fdb562b4d608272c74cf5f1d8f65))


## v1.31.0 (2026-05-13)


## v1.30.0 (2026-05-12)


## v1.29.0 (2026-05-11)

### Bug Fixes

- **cli**: Unblock new project on macOS py3.12 and disable matrix/element by default
  ([`394c7fa`](https://github.com/jupyter-naas/abi/commit/394c7fa0964f4d2975606746040d95617dfeb87e))

### Features

- **cli**: Seed local config with filesystem email and default ABI workspace
  ([`e638132`](https://github.com/jupyter-naas/abi/commit/e638132c2fcddb13f341f7b56a48dff06213c44f))


## v1.28.3 (2026-05-08)

### Bug Fixes

- **nexus**: Improve vis-network graph layout by pre-spreading nodes
  ([`fcb887e`](https://github.com/jupyter-naas/abi/commit/fcb887e682cc143310e8c1646d1c8f84d82b823f))


## v1.28.2 (2026-05-07)

### Bug Fixes

- Bump
  ([`c884f71`](https://github.com/jupyter-naas/abi/commit/c884f71e48a45d4a2f7bf284bc8e00e4f15a8226))

### Chores

- Commit uv.lock from libs
  ([`dbb210a`](https://github.com/jupyter-naas/abi/commit/dbb210ac9587035922ffd823d92e724d09e1afc0))

- Uv.lock
  ([`4241536`](https://github.com/jupyter-naas/abi/commit/424153634dcdaa9184d803a4a0d70801f5adcb39))


## v1.28.1 (2026-05-04)

### Bug Fixes

- **deps**: Update versions in uv.lock files
  ([`abeb223`](https://github.com/jupyter-naas/abi/commit/abeb2235da34298ba26602452a8658b1f93a1d20))

### Chores

- Update lockfile version hashes
  ([`3ddb806`](https://github.com/jupyter-naas/abi/commit/3ddb806f6da905f33c448e2112a0bb8944ca4b7c))


## v1.28.0 (2026-05-04)

### Chores

- Comment out ensure_seed_data function in seed.py
  ([`40f17d7`](https://github.com/jupyter-naas/abi/commit/40f17d7e3f8517e66c090ab9b0b45eafba3a3b64))

- **agent**: Improve logging clarity and comment out debug logs
  ([`6a31f86`](https://github.com/jupyter-naas/abi/commit/6a31f86c65ab45a6b0ceb288d0a6392eff673506))

### Features

- Add graph-explorer to the stack
  ([`b8819a9`](https://github.com/jupyter-naas/abi/commit/b8819a9fa65f77557806fcaa4e6c07f856d7be9f))


## v1.27.0 (2026-04-30)

### Features

- **config**: Expose public_api_host to modules via GlobalConfig
  ([`52fbea3`](https://github.com/jupyter-naas/abi/commit/52fbea3c528d0f7aa9834cdf2442b4cd7202b007))


## v1.26.0 (2026-04-28)

### Chores

- **docs**: Rename web → site and add specs/ folder for engineering artifacts
  ([`3192ca4`](https://github.com/jupyter-naas/abi/commit/3192ca483f2890e0e0e6d763d4a400b6c7e8b4ca))

- **release**: Update naas-abi to version 1.24.0 and naas-abi-core to version 1.29.0
  ([`d196d91`](https://github.com/jupyter-naas/abi/commit/d196d91e3faf84d900d70c1603baaec72a44f017))

### Features

- **openrouter**: Enable web search tool when supported
  ([`2f2f808`](https://github.com/jupyter-naas/abi/commit/2f2f808f863fdf718fdce532145908b7eda6c36a))


## v1.25.2 (2026-04-21)


## v1.25.1 (2026-04-21)

### Bug Fixes

- **ci**: Resolve all PR check failures
  ([`5ba33bb`](https://github.com/jupyter-naas/abi/commit/5ba33bbf83483126546daef8815be32f119a45a3))

- **mypy**: Suppress attr-defined on agent_class.New() in chat CLI
  ([`247a959`](https://github.com/jupyter-naas/abi/commit/247a9591e78f77f4ab5224b5189c34bbb88f1eff))

### Chores

- **cli**: Add distributed Fuseki write lock to new project template
  ([`265105e`](https://github.com/jupyter-naas/abi/commit/265105e19f956604c85d34dd8835f946042a6d82))


## v1.25.0 (2026-04-15)

### Features

- Update CLI based on new changes
  ([`ff68d7c`](https://github.com/jupyter-naas/abi/commit/ff68d7cecbeae42519448a500c6bef5e624a37b7))


## v1.24.2 (2026-04-14)

### Bug Fixes

- Bump versions
  ([`9096426`](https://github.com/jupyter-naas/abi/commit/90964266834d48b55770bccd536f26536bde9aec))


## v1.24.1 (2026-04-07)

### Bug Fixes

- Update uv.lock
  ([`14e2af0`](https://github.com/jupyter-naas/abi/commit/14e2af0181a4c3f3fb10143c882a4b36ddd07a2f))

- Update uv.lock
  ([`5064ad7`](https://github.com/jupyter-naas/abi/commit/5064ad70649dc9e116f5b169224bb5879c82e97d))

### Chores

- Update .gitignore, enhance security checks in Makefile, and refine Python version setup in CI
  workflow
  ([`fbb7073`](https://github.com/jupyter-naas/abi/commit/fbb7073adf2ec04d71b013422122ae2321d96346))


## v1.24.0 (2026-03-30)

### Features

- **service-portal**: Enhance index.html.template with improved layout and styling
  ([`14cccf5`](https://github.com/jupyter-naas/abi/commit/14cccf5a4e7333946d4655a83d706e5a73102f27))


## v1.23.1 (2026-03-28)

### Bug Fixes

- Abi cli bootstrap
  ([`a8c5b4a`](https://github.com/jupyter-naas/abi/commit/a8c5b4a7af6722a7634715fb278a72bfcb79bc5a))


## v1.23.0 (2026-03-13)


## v1.22.0 (2026-03-12)

### Features

- Improve service portal
  ([`d207ce4`](https://github.com/jupyter-naas/abi/commit/d207ce459e0bb8a0700b8fed4f566a30261f6a04))


## v1.21.1 (2026-03-10)

### Bug Fixes

- Update the cli to display when it executes sub abi cli
  ([`526eac3`](https://github.com/jupyter-naas/abi/commit/526eac3843cdc92b681ea7debe2c6d9454d057f3))


## v1.21.0 (2026-03-09)

### Features

- Abi cli rerun
  ([`a3a1a2b`](https://github.com/jupyter-naas/abi/commit/a3a1a2b69ed24bce413f514bfab169ebde194369))


## v1.20.0 (2026-03-05)

### Documentation

- Working on documentation
  ([`725631e`](https://github.com/jupyter-naas/abi/commit/725631e61c03183656bd3ac4082a0c444003f353))

### Features

- Working on centralizing CORS usage
  ([`08caa0d`](https://github.com/jupyter-naas/abi/commit/08caa0d2896f03a0c88e25d38ed0f2a076ec73ef))


## v1.19.5 (2026-03-04)


## v1.19.4 (2026-03-04)


## v1.19.3 (2026-03-04)

### Bug Fixes

- Headscale setup
  ([`d3ea48c`](https://github.com/jupyter-naas/abi/commit/d3ea48c6318b3e1fec4b8c03cdb942796e0001f7))


## v1.19.2 (2026-03-04)

### Bug Fixes

- Headscale setup
  ([`dbee594`](https://github.com/jupyter-naas/abi/commit/dbee59421b83c98434b9e2053dc2b345540b9186))


## v1.19.1 (2026-03-03)

### Bug Fixes

- Remove cli rerun
  ([`e590251`](https://github.com/jupyter-naas/abi/commit/e5902510f8e00740508fa1de8610340981351557))


## v1.19.0 (2026-03-03)

### Features

- Add api example in new abi module creation
  ([`735931e`](https://github.com/jupyter-naas/abi/commit/735931ee331b57fec791dbede5949e5d019654b3))


## v1.18.1 (2026-02-25)


## v1.18.0 (2026-02-24)

### Features

- Working on adding headscale to the default deployment
  ([`253c40f`](https://github.com/jupyter-naas/abi/commit/253c40f750e5c9a8930fbebdff69bbb4379e05c8))


## v1.17.3 (2026-02-19)

### Bug Fixes

- Sort modules & agents ascending on abi agent list
  ([`bcf1534`](https://github.com/jupyter-naas/abi/commit/bcf15345d076c257048ca8cf3b90791dae94bd58))


## v1.17.2 (2026-02-18)

### Bug Fixes

- Cors
  ([`b8c5fd5`](https://github.com/jupyter-naas/abi/commit/b8c5fd5a2f65f936d7015267067b72a4c1321b33))

- Working on abi start
  ([`570ddf3`](https://github.com/jupyter-naas/abi/commit/570ddf312799e2cecae09d8aae2bc80d48f20b79))


## v1.17.1 (2026-02-18)

### Bug Fixes

- Overall
  ([`8874852`](https://github.com/jupyter-naas/abi/commit/88748528ad867109f84db8f9f8e71eac5be774b6))


## v1.17.0 (2026-02-18)


## v1.16.0 (2026-02-18)

### Features

- Working on fixing multienv
  ([`ba7d7d0`](https://github.com/jupyter-naas/abi/commit/ba7d7d0396b46ba81e0458a872dabd29b7ac32ae))


## v1.15.7 (2026-02-17)

### Bug Fixes

- Update the local docker compose template
  ([`08f4c1f`](https://github.com/jupyter-naas/abi/commit/08f4c1ff374dcfe66732f9a3d48e57ad367a460c))


## v1.15.6 (2026-02-17)

### Bug Fixes

- Working on fixing nexus workspace access
  ([`d29b007`](https://github.com/jupyter-naas/abi/commit/d29b00775bbe631d978f5d1d0f687fa187282cd0))


## v1.15.5 (2026-02-17)

### Bug Fixes

- Add missing data in naas_abi release
  ([`4aa9316`](https://github.com/jupyter-naas/abi/commit/4aa9316facc963b4ef4f1653f41b594ea7ae5479))


## v1.15.4 (2026-02-17)

### Bug Fixes

- Add migrations to release
  ([`b928c24`](https://github.com/jupyter-naas/abi/commit/b928c24bc1c0034029192b80d1b7cbc06083dd81))


## v1.15.3 (2026-02-17)


## v1.15.2 (2026-02-17)


## v1.15.1 (2026-02-17)

### Bug Fixes

- Generate config.yaml on new project
  ([`cfdc888`](https://github.com/jupyter-naas/abi/commit/cfdc88819326cc52cdf608257c84cb5d03859de1))


## v1.15.0 (2026-02-16)

### Features

- Trigger release
  ([`cf5dfe9`](https://github.com/jupyter-naas/abi/commit/cf5dfe9691af94ff1d791de0bd0d6a53cb877a32))


## v1.14.0 (2026-02-16)

### Features

- Working on abi new project setup and stack management
  ([`2fa9392`](https://github.com/jupyter-naas/abi/commit/2fa939201d32c065cc9284e3e876aac953d66c1b))

- Working on nexus container release to ghcr
  ([`7f6f441`](https://github.com/jupyter-naas/abi/commit/7f6f441f07c409337e4082ea721a7b71080b49a8))

- Working on tui
  ([`01165ef`](https://github.com/jupyter-naas/abi/commit/01165ef2ac49966d0d343d6fe6381b659f32ef93))


## v1.13.4 (2026-02-16)

### Bug Fixes

- **infra**: Rollback unstable weekend runtime wiring
  ([`aac4a33`](https://github.com/jupyter-naas/abi/commit/aac4a33f2309ebff4a5889f72e45d13192955dd4))


## v1.13.3 (2026-02-13)

### Bug Fixes

- **infra**: Resolve CORS/500 errors and optimize Docker startup
  ([`661f2cd`](https://github.com/jupyter-naas/abi/commit/661f2cde9390eb34c914e856644b1355d6b4907f))


## v1.13.2 (2026-02-13)

### Bug Fixes

- Make the generation default to Jena
  ([`470cdce`](https://github.com/jupyter-naas/abi/commit/470cdce3e4e3e970b043c21131ae39a8d4ad1622))


## v1.13.1 (2026-02-12)

### Bug Fixes

- Working on new project setup
  ([`cd2a5cc`](https://github.com/jupyter-naas/abi/commit/cd2a5ccb156fe540759561e6eeb91abdeb1d4924))


## v1.13.0 (2026-02-11)

### Features

- Migrate assets from root to nexus app
  ([`acea3c8`](https://github.com/jupyter-naas/abi/commit/acea3c88affcbeaf636b953ed04cdfb8e450117d))


## v1.12.0 (2026-02-10)


## v1.11.4 (2026-02-10)


## v1.11.3 (2026-02-10)

### Bug Fixes

- Add missing element-config.json
  ([`37c8b76`](https://github.com/jupyter-naas/abi/commit/37c8b76da2d9124e48b5f2548dd7d2bf296af959))


## v1.11.2 (2026-02-10)


## v1.11.1 (2026-02-10)

### Bug Fixes

- Add template .env
  ([`194421b`](https://github.com/jupyter-naas/abi/commit/194421b7828713606e30144f77a2fcd6c3c32b81))

- Add template .env
  ([`b5fbe73`](https://github.com/jupyter-naas/abi/commit/b5fbe731c7bd37bb12348fc0ddbe75b5c5a8aa78))

- Add template .env
  ([`8c9d43d`](https://github.com/jupyter-naas/abi/commit/8c9d43dda47f569b342d44f7d4789b853d6e72d1))


## v1.11.0 (2026-02-09)

### Bug Fixes

- Working on make check
  ([`32b09fa`](https://github.com/jupyter-naas/abi/commit/32b09fa17ff2eecd17208f5b2800f418062676af))

- Working on make check
  ([`64dc00f`](https://github.com/jupyter-naas/abi/commit/64dc00fd8ce415de7d4d977a8d83d834a67a5aa6))

- Working on make check
  ([`2b9972d`](https://github.com/jupyter-naas/abi/commit/2b9972d9602036e6a926ed0a7b469e1dc1b9bb2f))

- Working on make check
  ([`da6c160`](https://github.com/jupyter-naas/abi/commit/da6c160ab55d1ec4c56cdbe3dc3ddef67144d043))

### Features

- Working on deploy local cli
  ([`c3ffe6d`](https://github.com/jupyter-naas/abi/commit/c3ffe6db633f2ce7789de5460d8849f80490b699))

- Working on deploy local cli
  ([`798e02a`](https://github.com/jupyter-naas/abi/commit/798e02ad2576f86344a54068fcd00e8f717c977d))


## v1.10.2 (2026-02-09)

### Bug Fixes

- Agent templating
  ([`e199010`](https://github.com/jupyter-naas/abi/commit/e199010ceea5d4024e6c24337a36a2413eed8659))


## v1.10.1 (2026-02-09)

### Bug Fixes

- Update CLI and rename KVService
  ([`00e62d6`](https://github.com/jupyter-naas/abi/commit/00e62d61c51e36f792cbdc2540e527596df67097))


## v1.10.0 (2026-02-03)

### Features

- Working on Dagster orchestration
  ([`b970d21`](https://github.com/jupyter-naas/abi/commit/b970d21e135ab32c344122be50f292c0b44ff039))


## v1.9.1 (2026-01-26)

### Bug Fixes

- CICD checks
  ([`1cc9a0d`](https://github.com/jupyter-naas/abi/commit/1cc9a0d8aa9e5b89c06269f11b8437d3a60d2c23))


## v1.9.0 (2026-01-25)


## v1.8.1 (2026-01-25)


## v1.8.0 (2026-01-25)


## v1.7.0 (2026-01-25)


## v1.6.1 (2026-01-24)


## v1.6.0 (2026-01-24)


## v1.5.0 (2026-01-24)

### Bug Fixes

- Naas-abi-cli release
  ([`25e669f`](https://github.com/jupyter-naas/abi/commit/25e669f95dc64f689f1d134d89845bad055333b6))

### Features

- Working on improving project initialization
  ([`e7063bb`](https://github.com/jupyter-naas/abi/commit/e7063bb63a7d3b553f159861fb3e1c545e7d8849))


## v1.4.4 (2026-01-15)


## v1.4.3 (2026-01-15)

### Bug Fixes

- Handle payment required for space creation
  ([`265fa48`](https://github.com/jupyter-naas/abi/commit/265fa48e71976465843f4a0676fe7571f06dab8f))


## v1.4.2 (2026-01-08)

### Bug Fixes

- Tipo license
  ([`f639213`](https://github.com/jupyter-naas/abi/commit/f639213b6c680d211c9618737842f01b51a65f8d))

- Tipo license
  ([`0269100`](https://github.com/jupyter-naas/abi/commit/0269100ca7d2d338d1f68be0717be6e981cc8eac))


## v1.4.1 (2026-01-08)

### Bug Fixes

- Add project urls in pyproject.toml
  ([`c155efa`](https://github.com/jupyter-naas/abi/commit/c155efa2a794b44312eb90ae19ab1c0da402d3ef))


## v1.4.0 (2026-01-08)


## v1.3.0 (2026-01-08)

### Features

- Add README.md to cli
  ([`00c4b50`](https://github.com/jupyter-naas/abi/commit/00c4b50f7eeef7170a52fa9a91c025befde13299))


## v1.2.0 (2026-01-07)


## v1.1.0 (2026-01-07)


## v1.0.3 (2026-01-07)

### Bug Fixes

- Add Dockerfile to new project generation
  ([`3cc8ecd`](https://github.com/jupyter-naas/abi/commit/3cc8ecddd80e247b10c7273862f5cfffb33969c5))

- Update config.yaml template on new project generation
  ([`72a174e`](https://github.com/jupyter-naas/abi/commit/72a174efdc779374f4035b3c91ba2aaf035ff6ce))


## v1.0.2 (2025-12-19)


## v1.0.1 (2025-12-19)

### Bug Fixes

- Add missing config in template
  ([`d4df148`](https://github.com/jupyter-naas/abi/commit/d4df148450f356a94ab53b46580db20bbba325b1))


## v1.0.0 (2025-12-19)

- Initial Release
