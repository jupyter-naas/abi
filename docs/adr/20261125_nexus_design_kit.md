# Nexus design kit: one set of components for every surface

- **Status:** Accepted
- **Date:** 2026-11-25

## Context

#1512 audited the four settings scopes and asked to validate one kit. It closed
without one landing: `components/ui` held six primitives (Button, Badge, Input,
Checkbox, dialogs, KpiCard), `components/settings/settings-ui.tsx` held the
generic pieces under settings names (notice, empty, loading, field, section,
search), and the rest of Nexus built its own.

The audit for #1513 (`storage/datastore/audit/nexus/`) measured the features:

- 1,161 hand-built `<button>` in 311 files, against 33 files on `ui/Button`;
- 63 files with their own `<table>`, 48 with their own search field (11 of
  them listed one by one in `globals.css` to remove a focus ring);
- three toast implementations, four dialog shells, five hand-rolled menu
  dropdowns beside nine Radix menu bars;
- Documents, Sheets and Slides each carry a copy of the same sidebar tree,
  gallery, project menu, status bar and menu bar.

The styling rule was left open ("semantic CSS as `AGENTS.md` asks, or Tailwind
as `components/ui` and `settings-ui` use").

## Decision

1. **The kit is `components/ui`, and only that folder.** Generic names, no
   scope prefix: `Button`, `Badge`, `Input`/`Select`/`Textarea`, `Checkbox`,
   `Field`, `SearchBox`, `Notice`, `EmptyState`, `Spinner`/`Loading`, `Card`,
   `PageHeader`, `KpiCard`, `Toolbar`, `Tabs`, `Menu`/`MenuBar`, `TreeRow`,
   split pane (`ColumnResizeHandle`), `Dialog` (sm, md, lg, xl, full),
   `ConfirmDialog`/`useConfirm` (with type-to-confirm), `usePrompt`, `toast`.
2. **Inside the kit, Tailwind + `cva` on the theme tokens.** That is what the
   existing primitives and 45 settings files already use; tokens still come
   from `globals.css` (the Tailwind colours are its HSL variables), and the
   org radius rule in `globals.css` still applies to them. Features **compose**
   kit components and lay them out (semantic CSS or utilities, per the route
   convention); they do not restyle them. A variant a feature needs is added
   to the kit, once.
3. **`settings-ui` keeps only what settings add:** `SettingsPageHeader`
   (PageHeader + Reload), the table toolbar and filters, `settingsTable`,
   `countLabel`, the back button.
4. **One toast stack** (`<Toaster />` in the root layout, `toast()` anywhere),
   **one dialog** (focus trap, Escape, ⌘↵), **one menu style** (Radix
   DropdownMenu; `menuClasses` for custom triggers).
5. **The Theme page** (Platform Settings › Administration › Theme,
   `/settings/theme`) shows every kit module in its states with the
   platform's tokens. `theme-model.test.ts` fails when a file in
   `components/ui` is not listed on the page.
6. **Migration is one feature per PR**, each deleting its local copies, in
   the order of the audit's plan (largest duplicate first).

## Consequences

- A fix to a component reaches every page that uses it; the Theme page is
  where a token or branding change is checked at a glance.
- The kit is the only place where an element's look is decided: a reviewer
  rejects a feature-local toast, badge, notice, empty state, dialog, table or
  search box.
- Feature-specific elements stay in their feature (canvas and graph toolbars,
  editors, the workbook grid, the map controls); the audit lists them.
- The semantic-CSS convention in `nexus/AGENTS.md` still governs page layout;
  it no longer asks for per-scope copies of shared components.
