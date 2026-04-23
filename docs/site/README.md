# Naas Docs Site

Docusaurus-powered documentation site.

## From this directory (`docs/site`)

```bash
npm install          # once, or when package.json changes
npm run start        # dev server with live reload (default http://localhost:3000)
```

Use a fixed port (matches repo `Makefile`):

```bash
npm run start -- --port 3003
```

Production build:

```bash
npm run build        # output in ./build
npm run serve        # optional: preview the production build locally
```

## From the repository root (optional)

The root `Makefile` wraps the same commands:

```bash
make docs        # npm install + start on http://localhost:3003
make docs-build  # production build
make docs-clean  # clear Docusaurus cache and ./build
```

There is **no** `Makefile` inside `docs/site`: use `npm` here, or `make docs*` from the repo root.
