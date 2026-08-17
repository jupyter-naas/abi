/**
 * Notion-style database model for the Apps section.
 *
 * Apps discovered from installed modules and tenant-level external apps are
 * normalised into a single `AppRecord` row, so every view (gallery, table,
 * list, board) reads one shape and every property is filterable, sortable and
 * groupable regardless of where the app came from. Splitting by module is a
 * grouping choice made inside the page — never a fixed layout.
 */

import type { OpenAppModule } from '@/stores/workspace';

// ---------------------------------------------------------------------------
// Raw API shapes
// ---------------------------------------------------------------------------

export interface AppInfo {
  module_path: string;
  module_name?: string;
  app_name: string;
  app_id: string;
  category: string;
  name: string;
  description: string;
  url?: string | null;
  avatar_url?: string | null;
  icon_emoji?: string | null;
  demo_login?: string | null;
  demo_password?: string | null;
  /** Manifest `agent_path` — file the app's agent lives in. */
  agent_path?: string | null;
  /** Manifest `agent_class` — the agent's Python class name. */
  agent_class?: string | null;
  /** Resolved agent registry key ("<python.module>/<ClassName>"), the join key
   *  against the workspace's agent rows. Null when the agent is not loaded. */
  agent_class_name?: string | null;
  version?: string | null;
  author?: string | null;
  license?: string | null;
  keywords?: string[];
  tier?: string | null;
  maintainer?: string | null;
  installed: boolean;
  enabled: boolean;
}

export interface AppsResponse {
  apps: AppInfo[];
}

export interface TenantApp {
  name: string;
  url: string;
  description?: string | null;
  icon_emoji?: string | null;
}

// ---------------------------------------------------------------------------
// Normalised row
// ---------------------------------------------------------------------------

export type AppSource = 'module' | 'external';

export interface AppRecord {
  /** Stable row id — the app_id for module apps, the URL for external ones. */
  id: string;
  source: AppSource;
  name: string;
  description: string;
  url: string;
  category: string;
  module: string;
  modulePath: string;
  tier: string;
  maintainer: string;
  author: string;
  version: string;
  license: string;
  keywords: string[];
  avatarUrl: string | null;
  iconEmoji: string | null;
  demoLogin: string | null;
  demoPassword: string | null;
  /** Agent the chat pane opens on while this app is showing (manifest). */
  agentPath: string | null;
  agentClass: string | null;
  agentClassName: string | null;
  /** Original payload, kept for the metadata panel. Null for external apps. */
  app: AppInfo | null;
}

/** Last meaningful segment of a dotted module path, used when the API omits module_name. */
function moduleNameFromPath(modulePath: string): string {
  const parts = modulePath.split('.').filter(Boolean);
  return parts[parts.length - 1] ?? '';
}

export function toRecord(app: AppInfo): AppRecord {
  return {
    id: app.app_id,
    source: 'module',
    name: app.name,
    description: app.description ?? '',
    url: app.url ?? '',
    category: app.category ?? '',
    module: app.module_name || moduleNameFromPath(app.module_path),
    modulePath: app.module_path,
    tier: app.tier ?? '',
    maintainer: app.maintainer ?? '',
    author: app.author ?? '',
    version: app.version ?? '',
    license: app.license ?? '',
    keywords: app.keywords ?? [],
    avatarUrl: app.avatar_url ?? null,
    iconEmoji: app.icon_emoji ?? null,
    demoLogin: app.demo_login ?? null,
    demoPassword: app.demo_password ?? null,
    agentPath: app.agent_path ?? null,
    agentClass: app.agent_class ?? null,
    agentClassName: app.agent_class_name ?? null,
    app,
  };
}

export function toTenantRecord(app: TenantApp): AppRecord {
  return {
    id: app.url,
    source: 'external',
    name: app.name,
    description: app.description ?? '',
    url: app.url,
    category: 'external',
    module: '',
    modulePath: '',
    tier: '',
    maintainer: '',
    author: '',
    version: '',
    license: '',
    keywords: [],
    avatarUrl: null,
    iconEmoji: app.icon_emoji ?? null,
    demoLogin: null,
    demoPassword: null,
    agentPath: null,
    agentClass: null,
    agentClassName: null,
    app: null,
  };
}

/** Translate a row → the shared module shape consumed by the sidebar panel. */
export function recordToOpenModule(record: AppRecord): OpenAppModule {
  return {
    module_path: record.modulePath,
    module_name: record.module,
    name: record.name,
    description: record.description,
    logo_url: record.avatarUrl,
    icon_emoji: record.iconEmoji,
    category: record.category,
    app_url: record.url,
    app_id: record.id,
    demo_login: record.demoLogin,
    demo_password: record.demoPassword,
    agent_path: record.agentPath,
    agent_class: record.agentClass,
    agent_class_name: record.agentClassName,
    maintainer: record.maintainer,
    tier: record.tier,
    version: record.version,
    author: record.author,
    license: record.license,
    keywords: record.keywords,
  };
}

// ---------------------------------------------------------------------------
// Properties
// ---------------------------------------------------------------------------

export type PropertyKey =
  | 'name'
  | 'description'
  | 'category'
  | 'module'
  | 'source'
  | 'tier'
  | 'maintainer'
  | 'author'
  | 'version'
  | 'license'
  | 'keywords'
  | 'url';

/** `title` is the row name — always visible, never hideable. */
export type PropertyType = 'title' | 'text' | 'select' | 'multi' | 'url';

export interface PropertyDef {
  key: PropertyKey;
  label: string;
  type: PropertyType;
  /** Raw values of the property on a row; empty array when unset. */
  values: (record: AppRecord) => string[];
}

const one = (value: string): string[] => (value ? [value] : []);

export const PROPERTIES: PropertyDef[] = [
  { key: 'name', label: 'Name', type: 'title', values: (r) => one(r.name) },
  { key: 'description', label: 'Description', type: 'text', values: (r) => one(r.description) },
  { key: 'category', label: 'Category', type: 'select', values: (r) => one(r.category) },
  { key: 'module', label: 'Module', type: 'select', values: (r) => one(r.module) },
  { key: 'source', label: 'Source', type: 'select', values: (r) => one(r.source === 'module' ? 'Module app' : 'External') },
  { key: 'tier', label: 'Tier', type: 'select', values: (r) => one(r.tier) },
  { key: 'maintainer', label: 'Maintainer', type: 'select', values: (r) => one(r.maintainer) },
  { key: 'author', label: 'Author', type: 'select', values: (r) => one(r.author) },
  { key: 'version', label: 'Version', type: 'text', values: (r) => one(r.version) },
  { key: 'license', label: 'License', type: 'select', values: (r) => one(r.license) },
  { key: 'keywords', label: 'Keywords', type: 'multi', values: (r) => r.keywords.filter(Boolean) },
  { key: 'url', label: 'URL', type: 'url', values: (r) => one(r.url) },
];

export const PROPERTY_BY_KEY: Record<PropertyKey, PropertyDef> = PROPERTIES.reduce(
  (acc, def) => ({ ...acc, [def.key]: def }),
  {} as Record<PropertyKey, PropertyDef>,
);

/** Properties the user can show/hide, filter and group by (everything but the title). */
export const OPTIONAL_PROPERTIES = PROPERTIES.filter((p) => p.type !== 'title');

/** Properties with a bounded set of values — the ones worth grouping by. */
export const GROUPABLE_PROPERTIES = PROPERTIES.filter((p) => p.type === 'select' || p.type === 'multi');

export function propertyValues(record: AppRecord, key: PropertyKey): string[] {
  return PROPERTY_BY_KEY[key].values(record);
}

/** Single display string for a property ("—" is left to the renderer). */
export function propertyText(record: AppRecord, key: PropertyKey): string {
  return propertyValues(record, key).join(', ');
}

/** Distinct values seen for a property across rows, sorted alphabetically. */
export function facetValues(records: AppRecord[], key: PropertyKey): string[] {
  const seen = new Set<string>();
  for (const record of records) {
    for (const value of propertyValues(record, key)) seen.add(value);
  }
  return Array.from(seen).sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' }));
}

// ---------------------------------------------------------------------------
// Views
// ---------------------------------------------------------------------------

export type ViewType = 'gallery' | 'table' | 'list' | 'board';

export type FilterOperator =
  | 'is'
  | 'is_not'
  | 'contains'
  | 'not_contains'
  | 'is_empty'
  | 'is_not_empty';

export interface Filter {
  id: string;
  property: PropertyKey;
  operator: FilterOperator;
  value: string;
}

export interface SortRule {
  property: PropertyKey;
  direction: 'asc' | 'desc';
}

export interface ViewConfig {
  id: string;
  name: string;
  type: ViewType;
  /** Ordered list of properties shown besides the title. */
  visible: PropertyKey[];
  filters: Filter[];
  sort: SortRule | null;
  groupBy: PropertyKey | null;
}

export const VIEW_TYPE_LABELS: Record<ViewType, string> = {
  gallery: 'Gallery',
  table: 'Table',
  list: 'List',
  board: 'Board',
};

export const DEFAULT_VISIBLE: Record<ViewType, PropertyKey[]> = {
  gallery: ['description', 'category', 'module'],
  table: ['description', 'category', 'module', 'maintainer'],
  list: ['category', 'module'],
  board: ['description', 'category'],
};

export const FILTER_OPERATOR_LABELS: Record<FilterOperator, string> = {
  is: 'is',
  is_not: 'is not',
  contains: 'contains',
  not_contains: 'does not contain',
  is_empty: 'is empty',
  is_not_empty: 'is not empty',
};

export function operatorsFor(type: PropertyType): FilterOperator[] {
  if (type === 'select') return ['is', 'is_not', 'is_empty', 'is_not_empty'];
  return ['contains', 'not_contains', 'is', 'is_not', 'is_empty', 'is_not_empty'];
}

export function operatorNeedsValue(operator: FilterOperator): boolean {
  return operator !== 'is_empty' && operator !== 'is_not_empty';
}

// ---------------------------------------------------------------------------
// Query pipeline: filter → search → sort → group
// ---------------------------------------------------------------------------

function matchesFilter(record: AppRecord, filter: Filter): boolean {
  const values = propertyValues(record, filter.property);
  const needle = filter.value.trim().toLowerCase();

  switch (filter.operator) {
    case 'is_empty':
      return values.length === 0;
    case 'is_not_empty':
      return values.length > 0;
    case 'is':
      return values.some((v) => v.toLowerCase() === needle);
    case 'is_not':
      return !values.some((v) => v.toLowerCase() === needle);
    case 'contains':
      return values.some((v) => v.toLowerCase().includes(needle));
    case 'not_contains':
      return !values.some((v) => v.toLowerCase().includes(needle));
  }
}

export function applyFilters(records: AppRecord[], filters: Filter[]): AppRecord[] {
  const active = filters.filter((f) => !operatorNeedsValue(f.operator) || f.value.trim() !== '');
  if (active.length === 0) return records;
  return records.filter((record) => active.every((filter) => matchesFilter(record, filter)));
}

export function applySearch(records: AppRecord[], search: string): AppRecord[] {
  const q = search.trim().toLowerCase();
  if (!q) return records;
  return records.filter((record) =>
    PROPERTIES.some((def) => def.values(record).some((v) => v.toLowerCase().includes(q))),
  );
}

export function applySort(records: AppRecord[], sort: SortRule | null): AppRecord[] {
  const rule = sort ?? { property: 'name' as PropertyKey, direction: 'asc' as const };
  const sorted = [...records].sort((a, b) => {
    const left = propertyText(a, rule.property);
    const right = propertyText(b, rule.property);
    // Rows missing the sort property sink to the bottom in either direction.
    if (!left && right) return 1;
    if (left && !right) return -1;
    const cmp = left.localeCompare(right, undefined, { sensitivity: 'base' });
    if (cmp !== 0) return rule.direction === 'asc' ? cmp : -cmp;
    return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' });
  });
  return sorted;
}

export interface RecordGroup {
  key: string;
  label: string;
  records: AppRecord[];
}

/**
 * Split rows by a property. Multi-value properties (keywords) place a row in
 * every matching group, like Notion does. Rows without a value land in a
 * trailing "No <property>" group.
 */
export function groupRecords(records: AppRecord[], groupBy: PropertyKey | null): RecordGroup[] {
  if (!groupBy) return [{ key: '__all__', label: '', records }];

  const groups = new Map<string, AppRecord[]>();
  const empty: AppRecord[] = [];
  for (const record of records) {
    const values = propertyValues(record, groupBy);
    if (values.length === 0) {
      empty.push(record);
      continue;
    }
    for (const value of values) {
      const bucket = groups.get(value);
      if (bucket) bucket.push(record);
      else groups.set(value, [record]);
    }
  }

  const result: RecordGroup[] = Array.from(groups.entries())
    .sort(([a], [b]) => a.localeCompare(b, undefined, { sensitivity: 'base' }))
    .map(([key, groupedRecords]) => ({ key, label: key, records: groupedRecords }));

  if (empty.length > 0) {
    result.push({
      key: '__empty__',
      label: `No ${PROPERTY_BY_KEY[groupBy].label.toLowerCase()}`,
      records: empty,
    });
  }
  return result;
}
