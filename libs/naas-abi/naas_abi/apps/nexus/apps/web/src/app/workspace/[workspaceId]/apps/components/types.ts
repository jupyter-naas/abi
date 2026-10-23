/**
 * Notion-style database model for the Apps section.
 *
 * Apps discovered from installed modules and tenant-level external apps are
 * normalised into a single `AppRecord` row, so every view (gallery, table,
 * list, board) reads one shape and every property is filterable, sortable and
 * groupable regardless of where the app came from. Splitting by module is a
 * grouping choice made inside the page — never a fixed layout.
 *
 * Filtering, search, sorting and grouping come from the shared database model
 * (`components/database-view`); this file only describes the app properties.
 */

import type { OpenAppModule } from '@/stores/workspace';
import {
  createSchema,
  type Filter as DatabaseFilter,
  type PropertyDef as DatabasePropertyDef,
  type RecordGroup as DatabaseRecordGroup,
  type SortRule as DatabaseSortRule,
  type ViewConfig as DatabaseViewConfig,
} from '@/components/database-view/model';

export {
  FILTER_OPERATOR_LABELS,
  operatorNeedsValue,
  operatorsFor,
  type FilterOperator,
  type PropertyType,
} from '@/components/database-view/model';

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
  version?: string | null;
  author?: string | null;
  license?: string | null;
  keywords?: string[];
  tier?: string | null;
  maintainer?: string | null;
  agent?: string | null;
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
    demo_login: record.demoLogin,
    demo_password: record.demoPassword,
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

export type PropertyDef = DatabasePropertyDef<AppRecord, PropertyKey>;

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

export const APPS_SCHEMA = createSchema<AppRecord, PropertyKey>(PROPERTIES);

export const PROPERTY_BY_KEY = APPS_SCHEMA.propertyByKey;
export const OPTIONAL_PROPERTIES = APPS_SCHEMA.optionalProperties;
export const GROUPABLE_PROPERTIES = APPS_SCHEMA.groupableProperties;

export const {
  propertyValues,
  propertyText,
  facetValues,
  applyFilters,
  applySearch,
  applySort,
  groupRecords,
} = APPS_SCHEMA;

// ---------------------------------------------------------------------------
// Views
// ---------------------------------------------------------------------------

export type ViewType = 'gallery' | 'table' | 'list' | 'board';

export type Filter = DatabaseFilter<PropertyKey>;
export type SortRule = DatabaseSortRule<PropertyKey>;
export type ViewConfig = DatabaseViewConfig<PropertyKey, ViewType>;
export type RecordGroup = DatabaseRecordGroup<AppRecord>;

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
