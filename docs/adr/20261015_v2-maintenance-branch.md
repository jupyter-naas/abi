# A v2 branch carries 2.x fixes, and only main moves :latest

## Status
Accepted.

## Date
2026-10-15

## Context
ABI 3.0 (`naas-abi-core`, `naas-abi`, `naas-abi-cli`) changes the default
runtime and breaks 2.x projects in ways that take time to absorb. Customers on
2.x need fixes while they move, for a limited time.

The release pipeline only knew one line:

- semantic-release ran on `main` (releases) and `dev` (prereleases), with tags
  `<pkg>-v{version}`.
- `build_abi_container.yml` and `build_nexus_web_container.yml` ran on every
  published GitHub release and pushed `:latest`.
- `deploy_api.yml` ran whenever "Build ABI Container" completed, and deployed
  `:latest`.

A second release line would therefore have moved `:latest` back to 2.x and
redeployed the API. Two GitHub behaviours constrain the fix:

- A `release` event runs the workflow file of the tagged commit, so the
  container workflows of each line decide what that line's releases push.
- A `workflow_run` workflow always runs from the default branch's file, so
  `deploy_api.yml` on `main` decides for every line.

semantic-release does not set `target_commitish` when it creates a GitHub
release, so GitHub reports the default branch there whatever the release came
from. A workflow cannot use it to tell which branch a release was cut from.

## Decision
- `v2` is cut from `main` at the last 2.x commit (`61fd8f789`). It takes bug
  and security fixes only, until **2027-01-31**.
- `v2` releases 2.x patch versions of `naas-abi-core`, `naas-abi` and
  `naas-abi-cli` (`[tool.semantic_release.branches.v2]`, `match = "^v2$"`, not
  a prerelease). `naas-abi-marketplace` is released from `main` only, and 2.x
  projects use those releases.
- On `v2`, `release.yml` refuses to release any version outside 2.x, so a
  `BREAKING CHANGE:` footer cannot publish 3.0.0 from 2.x code.
- `v2`'s container workflows push `:v2` and the exact version, never
  `:latest`. They are named "Build ABI Container (v2)" and "Build Nexus Web
  Container (v2)", so `deploy_api.yml`, which listens for "Build ABI
  Container", never starts for them.
- On `main`, `:latest` and the API deploy are for releases cut from `main`.
  The container workflows and `deploy_api.yml` ask the GitHub compare API
  whether `main` contains the release commit (`identical` or `ahead`). Releases
  from `v2` or `dev` carry a commit that `main` does not contain, so they get
  their version tags only.
- A fix that applies to both lines lands on `main` first, then is
  cherry-picked (`-x`) onto `v2`. Features are never backported.

## Consequences
- 2.x users pin `naas-abi-core<3`, `naas-abi<3`, `naas-abi-cli<3`, and use
  `:v2` images. The Nexus web tag of an `abi deploy local` stack defaults to
  `latest`, so a 2.x stack must set `NEXUS_WEB_TAG=v2` in `.env`.
- Each line has its own copies of the workflows. A change to release or
  container workflows may need to be made on both.
- While `main` still releases 2.x (before 3.0 is merged), `main` and `v2`
  compute versions from the same tags, and would collide. Until then, 2.x
  fixes land on `main` only and `main` is merged into `v2`.
- `dev` prereleases no longer move `:latest` or deploy the API. They are
  released and tagged as before.
- A release from `v2` is the newest GitHub release when it is published, so
  GitHub may show it as "Latest" on the releases page. Nothing in the
  pipeline reads that label.
- After 2027-01-31, `v2` gets no fixes and no releases. The branch can be
  archived then.

Users: [Staying on 2.x: v2 support](../site/docs/upgrade/v2-support.md).
Maintainers: [Backporting a fix to v2](../site/docs/capabilities/developer-toolchain/backporting-to-v2.md).
