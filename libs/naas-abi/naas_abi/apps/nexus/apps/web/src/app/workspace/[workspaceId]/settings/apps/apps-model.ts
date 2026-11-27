/**
 * Settings › Apps: the columns of its table (search, sort, filter, export, as Settings › Users).
 * Pure: the view is `page.tsx`.
 */
import type { AppItem } from '@/stores/apps';
import { enabledLabel, moduleItemKey, type ModuleItem } from '@/components/settings/module-items-model';

export type AppColumnId = 'app' | 'category' | 'source' | 'enabled';
export const APP_COLUMNS: { id: AppColumnId; label: string }[] = [
  { id: 'app', label: 'App' },
  { id: 'category', label: 'Category' },
  { id: 'source', label: 'Source' },
  { id: 'enabled', label: 'Enabled' },
];

/**
 * A row of the apps table: an app the caller may open (`listed`), or a module's app they may not
 * (disabled, or not usable by them), with what the catalog says of it; its module item (`item`,
 * the Enabled checkbox).
 */
export type AppRow = AppItem & { key?: string; item?: ModuleItem | null; listed?: boolean };

/** The module item an app id names (`<module>:<app>`, `remote/<module>:<app>`), or null. */
export function appScope(appId: string): { module: string; name: string } | null {
  const rest = appId.startsWith('remote/') ? appId.slice('remote/'.length) : appId;
  const cut = rest.lastIndexOf(':');
  if (cut <= 0 || cut === rest.length - 1) return null;
  return { module: rest.slice(0, cut), name: rest.slice(cut + 1) };
}

/** Where an app comes from, as its row shows it: its maintainer, else its module. */
export function appSource(app: AppItem): string {
  return app.maintainer || app.module_name || app.module_path;
}

/** The apps a person may open here: installed, with a URL. */
export function installedApps(apps: AppItem[]): AppItem[] {
  return apps.filter((app) => app.installed && app.url);
}

/**
 * The rows of the table: the apps the caller may open, then every module app (`items`) none of
 * them is.
 */
export function appRows(apps: AppItem[], items: readonly ModuleItem[] = []): AppRow[] {
  const matched = new Set<ModuleItem>();
  const listed: AppRow[] = installedApps(apps).map((app) => {
    const scope = appScope(app.app_id);
    const item =
      (scope &&
        items.find((i) => i.kind === 'apps' && i.module === scope.module && i.name === scope.name && !matched.has(i))) ||
      null;
    if (item) matched.add(item);
    return { ...app, key: app.app_id, item, listed: true };
  });
  const unlisted: AppRow[] = items
    .filter((item) => item.kind === 'apps' && !matched.has(item))
    .map((item) => ({
      key: moduleItemKey(item),
      app_id: moduleItemKey(item),
      app_name: item.name,
      module_path: item.module,
      module_name: item.module,
      name: item.label,
      description: '',
      category: '',
      url: null,
      installed: false,
      item,
      listed: false,
    }));
  return [...listed, ...unlisted];
}

/** What a column filter sees of a row (no category for an app the caller may not open). */
export function appCellValues(app: AppRow, column: AppColumnId): string[] {
  if (column === 'app') return [app.name];
  if (column === 'category') return app.category ? [app.category] : [];
  if (column === 'enabled') return [enabledLabel(app.item ?? null)];
  return [appSource(app)];
}

/** What the search bar reads of a row: its name, description, category and source. */
export function appSearchTexts(app: AppItem): string[] {
  return [app.name, app.description ?? '', app.category, appSource(app)];
}

export const APP_EXPORT_HEADERS = ['App', 'Description', 'Category', 'Source', 'URL', 'Enabled'];

/** A row of the CSV / Excel export. */
export function appExportRow(app: AppRow): string[] {
  return [app.name, app.description ?? '', app.category, appSource(app), app.url ?? '', enabledLabel(app.item ?? null)];
}
