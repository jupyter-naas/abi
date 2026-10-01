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
- Colours come from theme tokens only: `primary` for success/selected, `destructive` for errors and deletes, `muted` for neutral, amber for warnings.
- Destructive actions confirm with `useConfirm()`; errors are shown inline with `SettingsNotice`. No `window.confirm` or `window.alert`.
- Organization pages keep their semantic CSS for layout, but their shared button/input classes match the primitives (36px controls, same colours) and they use the shared `Checkbox`.
- Navigation: each settings tree has a `loading.tsx` so a click renders feedback at once. In development only, `useDevRouteWarmup` requests the sibling settings routes one at a time once the page is idle, so `next dev` compiles them before they are opened. The Infrastructure route is excluded because it pulls in three.js.

## Consequences

- A new settings page needs no styling decisions: header, sections, fields, tables and notices come from the shared components.
- The organization border-radius branding setting no longer affects the settings area. It still applies to the rest of the app and to the login page.
- The dev warm-up issues background requests to the local dev server after opening settings. It does nothing in production builds, where routes are precompiled.
- A route that fails to compile in `next dev` makes every route return 500 until the server restarts, so warm-up must never include routes that may fail to build in a given environment.
