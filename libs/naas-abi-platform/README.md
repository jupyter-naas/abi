# naas-abi-platform

A thin, dependency-light client for the ABI **platform data services**, meant to
run *inside a coding workspace*. It talks to the Nexus platform API so code (and
agents, by generating these commands) can move data directly between the
workspace and the platform — the bytes stream workspace ⇄ storage and never pass
through an LLM's context.

Only `click` + `httpx` are required (no engine dependencies), so it installs fast
in a workspace.

## Configuration

Two env vars (exported by the workspace at provision time):

- `ABI_API_BASE` — e.g. `http://abi:9879`
- `ABI_TOKEN` — the per-user bearer token

## Usage

```bash
abi-platform storage ls [PREFIX]
abi-platform storage cp ./big.bin remote:datasets/big.bin   # upload
abi-platform storage cp remote:datasets/big.bin ./big.bin   # download
```

Exactly one side of `cp` is a remote path, written as `remote:<key>`. All keys
are scoped to your own namespace server-side.
