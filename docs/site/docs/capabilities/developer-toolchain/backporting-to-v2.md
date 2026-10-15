---
sidebar_position: 9
---

# Backporting a fix to v2

`v2` is the 2.x maintenance branch. It takes bug fixes and security fixes until
2027-01-31, and releases 2.x patch versions of `naas-abi-core`, `naas-abi` and
`naas-abi-cli`. What users get from it is in
[Staying on 2.x: v2 support](/upgrade/v2-support).

**Features are never backported.** That includes refactors, dependency
upgrades that are not security fixes, and fixes that need a 3.0 feature. If
a fix needs one, write a 2.x fix of its own, or leave it out of 2.x.

## Land the fix on main first

A fix that applies to both lines goes into `main` first, through the usual PR
with its tests. `main` is the line every later version comes from: a fix that
lands only on `v2` comes back as a regression in 3.x.

A fix for code that only exists in 2.x (removed or rewritten in 3.0) skips
`main` and goes straight to a PR into `v2`.

## Cherry-pick onto v2

Once the fix is merged into `main`, take its commits onto a branch from `v2`.
Use `-x`, so each commit records the `main` commit it came from:

```bash
git fetch origin
git switch -c fix/v2-<topic> origin/v2
git cherry-pick -x <commit-on-main>     # one per commit of the fix, oldest first
```

If the fix was squash-merged into `main`, pick the squash commit. If it came
in through a merge commit, pick the commits it brought in, or pick the merge
with `git cherry-pick -x -m 1 <merge-commit>`.

When the code differs between the lines, resolve the conflicts so the change
does the same thing on 2.x, then run the tests of the packages you touched:

```bash
uv run pytest libs/naas-abi-core     # and libs/naas-abi, libs/naas-abi-cli
make check
```

Open a PR into `v2`, not `main`:

```bash
git push -u origin fix/v2-<topic>
gh pr create --base v2 --title "fix(<scope>): <what it fixes>"
```

The commits that reach `v2` must be `fix:` commits (Conventional Commits),
because the commit type decides the release. A cherry-picked `fix:` commit
keeps its type. If the original used another type, say so in the PR and
reword it to `fix:` when merging. Link the original PR in the description.

## How the 2.x release runs

Merging into `v2` starts `release.yml` on `v2`. It runs semantic-release for
`naas-abi-core`, `naas-abi` and `naas-abi-cli` with their
`[tool.semantic_release.branches.v2]` configuration (`match = "^v2$"`, not a
prerelease). For each package with a `fix:` commit under its folder, it:

1. computes the next patch version from that package's latest 2.x tag, for
   example `naas-abi-core-v2.43.0` to `2.43.1`;
2. commits the version bump to `v2`, tags it (`naas-abi-core-v2.43.1`) and
   creates the GitHub release;
3. publishes the package to PyPI.

`naas-abi-marketplace` is not released from `v2`: its step is skipped there,
and `main` keeps releasing it.

Each GitHub release then runs the container workflows from the tagged `v2`
commit, which are named "Build ABI Container (v2)" and "Build Nexus Web
Container (v2)". They push the images with the tag `:v2` and with their exact
version, never `:latest`. `deploy_api.yml` only starts for a workflow named
"Build ABI Container", and only deploys a release whose commit is on `main`, so
a 2.x release never deploys the API.

A `feat:` commit on `v2` would release a 2.x minor version. Don't merge one.
A `BREAKING CHANGE:` footer would compute 3.0.0. Before releasing anything,
`release.yml` checks that each package's next version is 2.x and stops if it is
not, so nothing is released from `v2` until the commit is reverted.

## Before 3.0 is merged into main

Until 3.0 is merged into `main`, `main` still releases 2.x, from the same tags
as `v2`. If both released, they would compute the same next version: after
`v2` tags `naas-abi-core-v2.43.1`, the next fix on `main` also computes 2.43.1,
and semantic-release skips it as already released. Until then, land 2.x fixes
on `main` only, and merge `main` into `v2` to keep it level.
