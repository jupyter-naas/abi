# Docs site: a User guide and a Developer guide

- **Status:** Accepted
- **Date:** 2026-10-18

## Context

The docs site (`docs/site`, Docusaurus) grew by topic: Get Started,
Capabilities, Architecture, Reference, Updates and Upgrade. People who build and
run projects on ABI and people who work on ABI itself read the same
navigation, and pages for one audience sit between pages for the other.

Old URLs are linked from outside the site: announcements, issues, other
projects' docs, search results. Some repository file paths are linked too:
`BREAKING CHANGE:` commit footers, the CHANGELOGs' upgrade notes and the PyPI
READMEs point at GitHub URLs such as
`https://github.com/jupyter-naas/abi/blob/main/docs/site/docs/upgrade/migrate-to-3.md`.
A GitHub URL cannot redirect.

## Decision

- **Two sections, two sidebars.** `docs/site/docs/user-guide/` holds get
  started, build, deploy, the CLI reference and the release notes;
  `docs/site/docs/developer-guide/` holds architecture, contributing, toolchain,
  releasing and backporting, and the generated library reference. The navbar has
  one entry per section (`sidebars.js`). Every hand-written page is in exactly
  one of them.
- **The upgrade pages keep their file paths.** `upgrade/migrate-to-3.md`,
  `upgrade/breaking-changes-3.md` and `upgrade/v2-support.md` stay under
  `docs/site/docs/upgrade/`. Their place in the User guide comes from the
  sidebar and from a `slug` (`/user-guide/upgrade/...`).
- **Every old route redirects.** `docs/site/redirects.js` maps each route of the
  pre-split site (`legacy-routes.txt`, taken from a build made before the move)
  to its new route, and feeds `@docusaurus/plugin-client-redirects`.
  `npm run check:redirects`, run by `docs.yml` after the build, fails when a
  legacy route has neither a page nor a redirect that lands on a page.
- **Client-side redirects, not Cloudflare Pages `_redirects`.** A `_redirects`
  file would give a server-side 301, but docs.naas.ai is not served by the
  `abi-docs` Pages project, and that project does not serve this site's pages
  yet, so the file cannot be shown to apply. Client-side redirects work wherever
  the build is hosted. A move to a host known to read `_redirects` can generate
  that file from `redirects.js` instead.
- **Broken links fail the build** (`onBrokenLinks: "throw"`).
- **The library reference** moved to
  `docs/site/docs/developer-guide/reference/libraries/`.
  `scripts/abi_docs_sync.sh` copies the generated pages there; `abi docs sync`
  keeps generating under `docs/reference/`.

## Consequences

- URLs change; the old ones keep working through a page that redirects in the
  browser. Search engines see a meta refresh, not a 301, until a host that
  serves `_redirects` takes over.
- New pages go in one of the two folders, and the sidebar picks them up. A page
  that has to keep its repository path needs an entry in `sidebars.js` and a
  `slug`.
- `legacy-routes.txt` is frozen: it records the old site, and is not updated
  when pages are added.
