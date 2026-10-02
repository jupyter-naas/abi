# Nexus settings design system

Status: Proposed

Date: 2026-10-01

## Context

The Nexus settings area (workspace settings under `/workspace/[id]/settings` and organization settings under `/organizations/[id]/settings`) grew page by page. Workspace pages used inline Tailwind with no shared components, organization pages used per-page CSS files, and the Graphs/Ontologies page used a third approach. The result was 14 different primary-button class strings, several input styles, four hand-built slider toggles, page titles from `text-lg` to `text-2xl`, hard-coded blue/red/green/yellow colours next to the theme tokens, and browser `confirm()`/`alert()` dialogs next to the styled `useConfirm()`.

Page switches also felt slow. In `next dev` each settings route compiled on first visit (1–10 s), and some pages blocked on sequential or forced refetches.

## Decision

- Settings pages are built from shared primitives in `components/ui/`: `Button` (`buttonVariants`: primary, secondary, ghost, destructive, destructive-ghost, link; sizes sm/md/icon), `Input`/`Textarea`/`Select` (`fieldClass`), `Checkbox` (plus `radioClass`), and `Badge`.
- Page structure comes from `components/settings/settings-ui.tsx`: `SettingsPageHeader`, `SettingsSection`, `SettingsField`, `SettingsSearch`, `SettingsNotice`, `SettingsEmpty`, `SettingsLoading` and the `settingsTable` class set.
- Settings surfaces have **no border radius**. Primitives use `rounded-none`; settings CSS files set `border-radius: 0` instead of reading `--org-border-radius`.
- Enable/disable controls are **checkboxes**, not sliders.
- Every settings table follows one layout, top to bottom: `SettingsTableToolbar`: the table metadata on the left (counts from `countLabel`, e.g. "3 of 12 agents · 9 enabled"), then the search bar with the table's own `SettingsFilterSelect` filters on the same row, then the table. The table is its own scroll box (max 65vh) with a sticky header row.
- The page title carries a badge with the number of enabled items (`SettingsPageHeader`/`OrgSettingsPageHeader` `badge`).
- The action that adds an element lives only in the top-right corner of the page header; empty states point to it instead of repeating it.
- Colours come from theme tokens only: `primary` for success/selected, `destructive` for errors and deletes, `muted` for neutral, amber for warnings.
- Destructive actions confirm with `useConfirm()`; errors are shown inline with `SettingsNotice`. No `window.confirm` or `window.alert`.
- Organization pages keep their semantic CSS for layout, but their shared button/input classes match the primitives (36px controls, same colours) and they use the shared `Checkbox`.
- API data read by settings pages is cached for **24 hours** in the engine's `CacheService` (hot/cold tiers; local FS fallback) by `SettingsCacheMiddleware` (`app/services/settings_cache/`). It is opt-in: the web app's `authFetch` adds `X-Nexus-Cache: 1` to GET requests sent from settings pages only. Entries are keyed per user (token `sub`), path and query. A successful write to a settings route bumps a global generation (everyone sees changes on the next read); `POST /api/settings-cache/refresh` bumps the caller's generation. An ABI restart bumps the global generation at startup (after config seeds, and again once the background model-catalog sync finishes), so it clears the whole cache; rebuilding or restarting the web app does not. Responses carry `X-Nexus-Cache: HIT|MISS`.
- Every settings page has a **Reload** button (left of the page actions): it calls the refresh endpoint, clears the stores' short client-side caches, refetches the shared workspace/organization lists and remounts the page so all its API calls run again.
- Navigation: each settings tree has a `loading.tsx` so a click renders feedback at once. In development only, `useDevRouteWarmup` requests the sibling settings routes one at a time once the page is idle, so `next dev` compiles them before they are opened. The Infrastructure route is excluded because it pulls in three.js.

## Consequences

- Data that changes without going through a settings API write (agents synced by a module at startup, config-file changes, catalog updates) can be up to 24 hours old on settings pages until someone presses Reload.
- The settings cache stores API answers, including the masked secrets list, in the configured cache backend.

- A new settings page needs no styling decisions: header, sections, fields, tables and notices come from the shared components.
- The organization border-radius branding setting no longer affects the settings area. It still applies to the rest of the app and to the login page.
- The dev warm-up issues background requests to the local dev server after opening settings. It does nothing in production builds, where routes are precompiled.
- A route that fails to compile in `next dev` makes every route return 500 until the server restarts, so warm-up must never include routes that may fail to build in a given environment.
