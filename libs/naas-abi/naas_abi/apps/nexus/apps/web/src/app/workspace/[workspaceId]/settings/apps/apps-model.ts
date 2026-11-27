/**
 * Settings › Apps: the columns of its table (search, sort, filter, export, as Settings › Users).
 * Pure: the view is `page.tsx`.
 */
import type { AppItem } from '@/stores/apps';

export type AppColumnId = 'app' | 'category' | 'source';
export const APP_COLUMNS: { id: AppColumnId; label: string }[] = [
  { id: 'app', label: 'App' },
  { id: 'category', label: 'Category' },
  { id: 'source', label: 'Source' },
];

/** Where an app comes from, as its row shows it: its maintainer, else its module. */
export function appSource(app: AppItem): string {
  return app.maintainer || app.module_name || app.module_path;
}

/** The apps a person may open here: installed, with a URL. */
export function installedApps(apps: AppItem[]): AppItem[] {
  return apps.filter((app) => app.installed && app.url);
}

/** What a column filter sees of a row. */
export function appCellValues(app: AppItem, column: AppColumnId): string[] {
  if (column === 'app') return [app.name];
  if (column === 'category') return [app.category];
  return [appSource(app)];
}

/** What the search bar reads of a row: its name, description, category and source. */
export function appSearchTexts(app: AppItem): string[] {
  return [app.name, app.description ?? '', app.category, appSource(app)];
}

export const APP_EXPORT_HEADERS = ['App', 'Description', 'Category', 'Source', 'URL'];

/** A row of the CSV / Excel export. */
export function appExportRow(app: AppItem): string[] {
  return [app.name, app.description ?? '', app.category, appSource(app), app.url ?? ''];
}
