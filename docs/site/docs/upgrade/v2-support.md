---
sidebar_position: 3
title: "Staying on 2.x: v2 support"
slug: /user-guide/upgrade/v2-support
---

# Staying on 2.x: v2 support

ABI 3.0 is the current line. Projects that cannot move yet can stay on 2.x for
a limited time: the `v2` branch of
[jupyter-naas/abi](https://github.com/jupyter-naas/abi/tree/v2) carries 2.x
after 3.0 is released.

- **Fixes only.** `v2` takes bug fixes and security fixes. It gets no new
  features and no backports of 3.0 features.
- **End of life: 2027-01-31.** After that date, `v2` gets no fixes and no
  releases. Plan the move to 3.0 before then:
  [Migrate from 2.x to 3.0](./migrate-to-3).

## What v2 releases

| | Released from `v2` | Starting after |
|---|---|---|
| `naas-abi-core` | 2.x patch versions on PyPI | 2.44.0 |
| `naas-abi` | 2.x patch versions on PyPI | 2.89.0 |
| `naas-abi-cli` | 2.x patch versions on PyPI | 2.28.0 |
| `naas-abi-marketplace` | Not released from `v2` | |
| `ghcr.io/jupyter-naas/nexus-web` | `:v2`, and the exact version (`:2.89.1`) | |
| `ghcr.io/jupyter-naas/abi/abi` | `:v2`, and the release tag (`:naas-abi-core-v2.44.1`) | |

Images from `v2` are never tagged `:latest`: `:latest` follows 3.0.

**The marketplace** keeps its own version line, released from `main` only.
2.x projects use the same `naas-abi-marketplace` releases as 3.0 projects. On
2026-10-15, the marketplace from the 3.0 release branch was installed with
`naas-abi-core` 2.43.0, `naas-abi` 2.87.0 and `naas-abi-cli` 2.28.0. Every
marketplace module that imports with 3.0 also imported with 2.x. If a later
marketplace release stops working with your 2.x project, pin the last version
that works, for example `naas-abi-marketplace==3.60.0`.

## Stay on 2.x

### Python packages

Cap the three ABI packages below 3 in your project's `pyproject.toml`, so that
`uv lock --upgrade` and `uv add` keep you on 2.x:

```bash
uv add 'naas-abi-core<3' 'naas-abi<3' 'naas-abi-cli<3'
```

Keep the extras you already list, for example `'naas-abi-core[all]<3'`. You
still get every 2.x patch release.

### Projects that use the `.abi` submodule

Projects made by `abi new project` may resolve ABI from a `.abi` git submodule
(their `pyproject.toml` has a `[tool.uv.sources]` block pointing at
`.abi/libs/...`). The submodule follows `main`, which is 3.0. Point it at
`v2`:

```bash
git submodule set-branch --branch v2 .abi
git submodule update --remote .abi
git add .gitmodules .abi
git commit -m "chore: follow ABI v2"
uv sync
```

The submodule's copy of the marketplace stops at the `v2` cut. To get later
marketplace releases, remove the `naas-abi-marketplace` line from
`[tool.uv.sources]` and run `uv sync`, so it comes from PyPI.

### Container images

A stack made by `abi deploy local` runs the Nexus web image with the tag set in
`.env`, `latest` by default. After 3.0 is released, `latest` is the 3.0 web
app, which does not match a 2.x API. Set the tag in `.env`:

```bash
NEXUS_WEB_TAG=v2
```

Then run `docker compose up -d`. `:v2` points at the last 2.x build (2.89.0) and
moves with each 2.x release from `v2`; to stay on a fixed build, use the exact
version instead, `NEXUS_WEB_TAG=2.89.0`.

If you pull the ABI image (`ghcr.io/jupyter-naas/abi/abi`), use `:v2` instead
of `:latest` too.

## Ask for a fix

Open an issue on [GitHub](https://github.com/jupyter-naas/abi/issues/new) and
say that it affects 2.x. Include:

- the versions you run: `uv pip show naas-abi-core naas-abi naas-abi-cli naas-abi-marketplace`;
- what you did, what you expected, and what happened, with the error or log;
- whether 3.0 has the same problem, if you can check.

Report security issues privately to [support@naas.ai](mailto:support@naas.ai),
not in a public issue.

A fix that also applies to 3.0 lands on `main` first, then on `v2`. A fix for
2.x only lands on `v2` directly. Either way, it is released as the next 2.x patch
version. How maintainers do this is in
[Backporting a fix to v2](/developer-guide/releasing/backporting-to-v2).
