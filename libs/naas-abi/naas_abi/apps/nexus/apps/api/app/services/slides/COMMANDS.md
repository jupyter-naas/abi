# Slides commands

Nexus Slides stores git-backed HTML (`deck.html`). Named verbs are
the contract. The file format is an implementation detail.

## Architecture

Same model as Documents. HTTP is the public contract. Named verbs
(`rename_deck`, `update_title`, …) are the product surface. The
agent calls those same names. A future `abi slides <verb>` would
wrap the same HTTP routes. That is API first, with CLI-shaped verbs
on top. It is not a CLI that owns the logic.

`POST /api/slides/projects/{slug}/commands` applies an ordered list
of verbs. That is not a shell CLI. There is no `abi slides rename`
today. The `abi` Click CLI is workspace, user, stack, and dev. Do
not invent a Slides Click group until a wrapper is a product need,
and do not put business logic in the agent.

What actually runs:

1. Verb functions live in `slides_commands.py` (HTML).
   `rename_deck` also writes `project.json` `title`.
2. FastAPI `POST /commands` calls those verbs and writes the
   git-backed store (sidecar plus Forgejo).
3. Agent tools use the same names and the same Python mutators. They
   talk to sidecar and git directly. They are not HTTP clients of
   the API.
4. The web UI calls the HTTP API (`PATCH /projects/{slug}` for a
   sidebar-typed display-name change).

This pass only adds `rename_deck` and `update_title` to the command
batch. Insert, delete, duplicate, reorder, and full-deck writes stay
on their dedicated routes and agent tools. Do not rewrite those into
commands in the same change.

Target: one named command per user-facing function, callable from
HTTP and from the agent. A later CLI is a thin wrapper of the API.

## Supported commands

`POST /api/slides/projects/{slug}/commands` applies an ordered list.
The first error aborts the batch.

| Command | What it does | Source |
|---|---|---|
| `update_title` | Change the tab `<title>` and cover H1 only | heading-only retitle |
| `rename_deck` | Sidebar display name plus tab `<title>` and cover H1 | "rename this deck" |

The noun is **deck** (`deck.html`, `read_slides_deck`,
`write_slides_deck`). "Rename this presentation" still maps to
`rename_deck`.

## Rename vs heading

"Rename this deck" or "rename this presentation" is one product
action: `rename_deck`. It updates the project display name the
sidebar tree reads (`project.json` `title`) and the visible deck
title (tab and cover H1). The slug and git folder stay put.
`Untitled presentation` is that display name, not only the slug.

"Change the title" or "change the heading" is heading-only:
`update_title`. It does not rename the sidebar folder.

Agent tools use the same names. Internal helpers can still split
project write vs HTML write; the command the agent and the user see
must not.

Read and project verbs already exist:

| Route / tool | What it does |
|---|---|
| `GET /projects`, `list_slides_projects` | List decks |
| `POST /projects`, `create_slides_project` | Create from a seed |
| `GET /projects/{slug}/deck`, `read_slides_deck` | Read stored HTML (tools return an outline by default) |
| `PUT /projects/{slug}/deck`, `write_slides_deck` | Replace the whole deck |
| `PATCH /projects/{slug}` | Sidebar display name and/or archive. Does not edit cover HTML |
| `POST .../slides/insert` | Add a slide |
| `POST .../slides/delete` | Remove a slide |
| `POST .../slides/duplicate` | Copy a slide |
| `POST .../slides/reorder` | Move slides |
| `GET /projects/{slug}/history` | Git history |

## Explicit non-goals

- A Click `abi slides` group (later wrapper of this API)
- Rewriting insert/delete/duplicate/reorder into the command batch
  in this pass
- Changing Documents
