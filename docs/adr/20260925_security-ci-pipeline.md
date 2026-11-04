# Security CI pipeline: baselined gates, DAST and AI review

- **Status:** Proposed (running on the `ci/security-pipeline` branch only)
- **Date:** 2026-09-25

## Context

Security checks before this change were Bandit at medium severity on core packages only, and a Trivy image scan whose exit code was never checked, so it could not fail a build. Nothing scanned dependencies, secrets in git history, the frontend, the GitHub Actions workflows or a running instance. Nothing ran on a schedule.

The 2026-09 API audit found open registration, OTP brute force, anonymous infrastructure ports, rate limiting silently disabled and a default admin password. These are logic and configuration bugs, and static scanners alone would not have caught them.

Two constraints shape the design. The repository is public, so workflow logs and artifacts are world-readable. And the organisation runs a self-hosted runner shared with private customer repositories.

## Decision

1. **One gate for every scanner.** Each tool emits SARIF. The report is uploaded to code scanning (the Security tab) and passed to `scripts/security/sarif_gate.py`. The gate fails only on findings at or above a severity threshold that are not in `.github/security/baselines/<tool>.json`. Existing debt is recorded and visible, and anything new blocks the build. Fingerprints ignore line numbers. A missing or unreadable report fails the gate (fail closed).
2. **Static layer** (`security.yml`): gitleaks over full history and trufflehog (verified live secrets only, never baselined), osv-scanner over every lockfile, CodeQL `security-extended` for Python, JS/TS and Actions, Semgrep community rulesets plus project rules in `.github/security/semgrep/`, Bandit over all packages, Trivy (filesystem and both images, plus SBOM), hadolint, zizmor, actionlint and OpenSSF Scorecard.
3. **Dynamic layer** (`security-dast.yml`): boots a throwaway stack with `abi dev up` on the runner and runs an unauthenticated route sweep, an authenticated OWASP ZAP API scan, Nuclei, and Schemathesis fuzzing. An optional Claude Code pentest runs when a key is configured. Gates run with `--quiet`, and raw reports are never uploaded as artifacts, so findings against a live instance stay in the private Security tab.
4. **AI review** (`security-ai-review.yml`): `anthropics/claude-code-security-review` comments on PR diffs. It is advisory, not blocking.
5. **Everything runs on the self-hosted runner** (`[self-hosted, Linux, X64]`). Every job carries a same-repository guard, so fork pull requests can never execute there.
6. Third-party actions are pinned to commit SHAs, and downloaded scanner binaries to SHA-256 checksums.

## Consequences

- New vulnerabilities in code, dependencies, images or CI configuration fail the build. Old ones stay visible without blocking unrelated work. Baselines should only shrink, and a PR that grows one needs a reviewer to accept the risk explicitly.
- Base-image and dependency CVEs appear daily against unchanged code, so the scheduled run fails when upstream publishes something fixable. That is intended.
- The runner needs Docker (image builds, ZAP, Scorecard) plus `curl`, `jq` and `unzip` or `python3`.
- Enabling `pull_request` triggers on a public repo with a shared self-hosted runner requires "Require approval for all outside collaborators". A dedicated, ephemeral runner for this repository is preferable to one shared with private customer repositories.
- DAST covers the `abi dev` runtime, not the Docker Compose deployment. Checking the exposure of infrastructure ports (Fuseki, Redis, Qdrant, Dagster) needs a compose-based variant.
- The AI jobs need `ANTHROPIC_API_KEY`. The pentest also accepts `CLAUDE_CODE_OAUTH_TOKEN`. Without them they skip, and nothing else depends on them.
