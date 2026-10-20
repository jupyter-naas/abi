---
sidebar_position: 1
title: "Releasing"
---

# Releasing

Each package of the monorepo is released on its own by
[python-semantic-release](https://python-semantic-release.readthedocs.io), from
[Conventional Commits](https://www.conventionalcommits.org). A release is a push to `main`
(stable) or `dev` (prerelease); `.github/workflows/release.yml` does the rest. To get a fix
into 2.x, see [Backporting a fix to v2](/developer-guide/releasing/backporting-to-v2).

---

## What a commit does

The commit type decides the version of each package whose folder it touches:

| Commit | Bump |
|---|---|
| `fix:` | patch |
| `feat:` | minor |
| a `BREAKING CHANGE:` footer | major |
| `docs:`, `chore:`, `test:`, ... | none |

Tags look like `<package>-v{version}` (`naas-abi-core-v3.0.0`). Each package keeps its own
`[tool.semantic_release]` section in its `pyproject.toml`: the tag format, the commit message, the
version file and the build.

## The order of a release

The workflow releases the packages **in dependency order**, because each one needs the previous
ones on PyPI:

1. `naas-abi-proto`
2. `naas-abi-sdk`
3. `naas-abi-core`: its `nats` and `otel` extras need proto and the SDK
4. `naas-abi-marketplace`
5. `naas-abi`: needs `naas-abi-core[nats]`
6. `naas-abi-cli`

First it versions and tags every package that has something to release, then uploads each
release's assets to GitHub, then publishes each to PyPI.

## Merge commits only

A release is computed from the commits that reach `main`, and a `BREAKING CHANGE:` footer is
only seen if the commit that carries it is there. A **squash or a rebase merge rewrites the
commits and drops the footer**, so a major bump is silently lost. A release PR, or a PR that
carries a breaking commit, is merged with **Create a merge commit**.

## Trusted publishers

PyPI uploads use [trusted publishing](https://docs.pypi.org/trusted-publishers/): the `release`
job runs in the GitHub environment `pypi` with `id-token: write`, and
`pypa/gh-action-pypi-publish` exchanges that token for a short-lived upload credential. There is no
PyPI token in the repository. A package's first publish needs a **pending trusted publisher**
registered for it on PyPI (owner `jupyter-naas`, repository `abi`, workflow `release.yml`); do that
before the first merge that releases a new package.

Leave the **environment name blank**, as the publishers of the existing packages are. PyPI mints the
upload token from the most specific matching publisher: a publisher with the environment `pypi` on
some projects and a blank one on the others makes the token valid only for the first group, and the
other uploads fail with `OIDC scoped token is not valid for project`. PyPI also takes only one pending
publisher with the same settings at a time, so register the new packages one release at a time.

If a release is tagged and published on GitHub but an upload failed, re-running the workflow uploads
nothing: the version is already tagged. Run **Actions > Release > Run workflow** from `main` with the
tag (`publish-existing` job): it uploads the files of that GitHub release, one package at a time, in
dependency order (proto, SDK, core, marketplace, naas-abi, CLI). Versions already on PyPI are skipped.

## Containers and the API deploy

Publishing a GitHub release starts two workflows, `build_abi_container.yml` and
`build_nexus_web_container.yml`, which push the images to `ghcr.io` tagged with the release version. A
release cut from `main` also moves `:latest`. Only `main` does that; the v2 branch's images are
tagged `v2` and with their exact version.

`deploy_api.yml` (the workflow named "ABI API") deployed `:latest` to a Naas space after each such
release. It is **disabled** since 2026-10-20: its last successful run was in January 2026 and
nothing used it. Enable it in the Actions tab to bring the deploy back; it needs a working space
first, since it waits for the API to answer.

## Check a release without cutting it

```bash
cd libs/naas-abi-core
uvx --from "python-semantic-release==10.5.2" semantic-release --noop version --print
```

`--noop` prints the next version and changes nothing. Run it in each package folder, in the order
above.

## Related

- [Backporting a fix to v2](/developer-guide/releasing/backporting-to-v2)
- [Staying on 2.x: v2 support](/user-guide/upgrade/v2-support)
- [Testing](/developer-guide/contributing/testing): what CI checks before a merge
