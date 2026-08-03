# X Recent Tweets — web

Next.js App Router UI for the X catalog app. Same layout conventions as Nexus
(`src/app`, `src/components`, `src/lib`) and WSR marketplace apps.

## Scripts

```bash
pnpm install
pnpm dev      # http://localhost:3045/app-html/x/apps/x/
pnpm build    # static export → out/
pnpm typecheck
```

`next.config.js` uses `output: 'export'` and
`basePath: '/app-html/x/apps/x'` so the build can be published into object
storage and served by `../routes.py` next to the JSON snapshots.

Snapshot JSON is loaded at runtime from the same `/app-html/x/apps/x/` origin
(see `src/lib/loadSnapshots.ts`).
