/**
 * Nexus tables in Platform Settings: the Nexus tables page at `/settings/tables`,
 * one table at `/settings/tables/<name>`, one row at `/settings/tables/<name>/<row id>`.
 *
 * Which tables there are, their labels and sections come from the API
 * (`GET /api/admin/tables`, the registry in core/platform_tables.py): the web app
 * keeps no copy of the list.
 *
 * No icons or React here: src/middleware.ts imports this file.
 */

/** One table, as `GET /api/admin/tables` returns it (registry order, by section). */
export interface PlatformTableSummary {
  name: string;
  label: string;
  section: string;
  description: string;
  /** Null when the table is missing from this database. */
  rows: number | null;
  columns: number | null;
}

export const PLATFORM_TABLES_PATH = '/settings/tables';

/** `/settings/tables/<name>`. */
export function platformTablePath(name: string): string {
  return `${PLATFORM_TABLES_PATH}/${encodeURIComponent(name)}`;
}

/** Joins primary key values into one row id; keep in sync with ROW_ID_SEPARATOR. */
export const ROW_ID_SEPARATOR = '~';

/** The id a row page uses: its primary key value(s), joined with `~`. Null without a key. */
export function platformRowId(
  row: Record<string, unknown>,
  primaryKey: readonly string[]
): string | null {
  if (primaryKey.length === 0) return null;
  return primaryKey.map((column) => String(row[column])).join(ROW_ID_SEPARATOR);
}

/** `/settings/tables/<name>/<row id>`. */
export function platformRowPath(table: string, rowId: string): string {
  return `${platformTablePath(table)}/${encodeURIComponent(rowId)}`;
}

/**
 * Old workspace settings links (`/settings/<slug>`, from before settings moved
 * under /workspace/[id]) that the middleware still redirects to the workspace.
 * `getWorkspacePath(null, ...)` also yields them while no workspace is current.
 * Every page under app/workspace/[workspaceId]/settings/ is one (a test checks it).
 */
export const LEGACY_WORKSPACE_SETTINGS_SLUGS: readonly string[] = [
  'general',
  'members',
  'servers',
  'services',
  'secrets',
  'export',
  'agents',
  'ontologies',
  'graphs',
  'search',
  'maps',
  'skills',
  'apps',
  'models',
  'drives',
  'infrastructure',
  'workflows',
];

/**
 * The table an old table page slug (`/settings/<slug>`, before the Nexus tables page)
 * showed: the slug itself, or `<name>` for `<name>_table`, the slug a table named like
 * a legacy workspace settings path had.
 */
export function tableFromLegacySlug(slug: string): string {
  const base = slug.endsWith('_table') ? slug.slice(0, -'_table'.length) : null;
  return base && LEGACY_WORKSPACE_SETTINGS_SLUGS.includes(base) ? base : slug;
}
