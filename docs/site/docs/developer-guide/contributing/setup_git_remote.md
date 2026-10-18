---
sidebar_position: 5
---

# Setup Git Remote

Two situations call for a second Git remote, and they use it differently:

- You **forked** the ABI repository to contribute a change. You need the original repository as a remote, to stay up to date with it.
- You have a **project** made with `abi new project`. The framework is not a remote of your repository: it is a submodule, and you update it with `git submodule`.

## Contribute to ABI from a fork

Fork [jupyter-naas/abi](https://github.com/jupyter-naas/abi) on GitHub, clone your fork, and add the original repository as a remote. The conventional name is `upstream`:

```bash
# Clone your fork: Git names it `origin`
git clone git@github.com:<your-user>/abi.git
cd abi

# Add the original repository
git remote add upstream https://github.com/jupyter-naas/abi.git
git remote -v
```

Bring your fork's `main` up to date, then branch from it:

```bash
git fetch upstream
git switch main
git merge --ff-only upstream/main      # or: git rebase upstream/main
git push origin main                   # update your fork

git switch -c fix/my-change
```

Push your branch to **your fork** (`origin`), not to `upstream`, and open a pull request into `main` of `jupyter-naas/abi`:

```bash
git push -u origin fix/my-change
gh pr create --repo jupyter-naas/abi --base main
```

Run `make check` and the tests that cover your change before you push ([The Makefile](/developer-guide/toolchain/makefile), [Test Python scripts](/developer-guide/toolchain/test_python_scripts)). Fixes for 2.x go to the `v2` branch: see [Backporting a fix to v2](/developer-guide/releasing/backporting-to-v2).

## Update the framework of a project

A project made by `abi new project` keeps the ABI repository at `.abi/` as a Git submodule (the default; `--without-abi-submodule` turns it off). A NATS project resolves `naas-abi-proto` and `naas-abi-sdk` from it until they are published on PyPI. The submodule is pinned to one commit. To take the latest framework:

```bash
git submodule update --remote .abi
git add .abi && git commit -m "Bump .abi"
uv sync
```

If you cloned the project without `--recurse-submodules`:

```bash
git submodule update --init --recursive
```

Do not edit files under `.abi/`; to change the framework, contribute to ABI from a fork as above.

## About the default remote

When you clone a repository, Git creates a remote called `origin`: the place you cloned from. With no other arguments, `git push` and `git pull` use the branch you are on and its `origin` counterpart. Other remotes, such as `upstream`, are used only when you name them (`git fetch upstream`).
