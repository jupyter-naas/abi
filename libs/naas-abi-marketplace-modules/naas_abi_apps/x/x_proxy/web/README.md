# X Recent Tweets - web

Next.js App Router UI for the X catalog app. Same layout conventions as Nexus
(`src/app`, `src/components`, `src/lib`) and WSR marketplace apps.

## Scripts

```bash
pnpm install
pnpm dev      # http://localhost:3045/__x_proxy_app_root__/ (no data behind it)
pnpm build    # static export → out/
pnpm typecheck
```

`next.config.js` uses `output: 'export'` and the placeholder
`basePath: '/__x_proxy_app_root__'`. The X module publishes the export into
object storage and serves it with `../app.py`, which replaces the placeholder
with the request's `root_path` (`/app-remote/<grant>/applications.x/x_proxy`,
per session) in every HTML, script, style and payload. Build URLs from
`APP_BASE` (`src/lib/base.ts`), never from a literal path.

Snapshot JSON and the dataset endpoints are fetched from `${APP_BASE}/…`
(`src/lib/loadSnapshots.ts`, `userSearch.ts`, `tweetSearch.ts`).

The page runs sandboxed in an opaque origin: `localStorage`, `sessionStorage`
and `document.cookie` throw. Use `src/lib/storage.ts` (guarded, with an
in-memory fallback), never the storage objects directly.
