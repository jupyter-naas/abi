---
sidebar_position: 0
title: "Developer guide"
---

# Developer guide

For people who work on ABI itself: how it is built, how to change it, and how it is released.
To build on ABI, use the [User guide](/user-guide/get-started/install).

| Section | What |
|---|---|
| [Architecture](/developer-guide/architecture) | The stack, the knowledge graph, the agent system, NATS, remote modules and apps, security, observability |
| [Contribute to ABI](/developer-guide/contributing/overview) | Set up the repository, run it on NATS, the `AGENTS.md` map and conventions |
| [Testing](/developer-guide/contributing/testing) | Unit, NATS, PostgreSQL, testcontainers, Nexus web and CLI smoke tests, and which CI job runs what |
| [Toolchain](/developer-guide/toolchain) | The Makefile, dependencies, running scripts |
| [Releasing and backporting](/developer-guide/releasing) | How releases are cut, and how a fix reaches the v2 branch |
| [Architecture decision records](/developer-guide/adr) | Every ADR, by topic |
| [SDK and proto internals](/developer-guide/sdk-and-proto) | Where the SDK and proto packages are documented |
| [Library reference](/developer-guide/reference) | Generated reference pages of every package |
