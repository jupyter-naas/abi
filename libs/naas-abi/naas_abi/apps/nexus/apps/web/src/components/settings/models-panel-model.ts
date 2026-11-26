/**
 * Settings › Models: the catalog's models as the table lists them, and its columns (search,
 * sort, filter, export, as Settings › Users). Pure: the view is `models-panel.tsx`.
 */

export type Model = {
  canonical_id: string;
  model_id: string;
  provider: string;
  provider_id: string;
  module_path: string;
  configured: boolean;
  name: string | null;
  description: string | null;
  image: string | null;
  context_window: number | null;
};

export type Provider = {
  id: string;
  name: string;
  module_path: string;
  configured: boolean;
  logo_url: string | null;
  config_keys: string[];
  models: Model[];
  description?: string | null;
  tags?: string[];
  slug?: string | null;
  privacy_policy_url?: string | null;
  terms_of_service_url?: string | null;
  status_page_url?: string | null;
  headquarters?: string | null;
  datacenters?: string[] | null;
};

/** A model with the name of its provider, as its row shows it. */
export type ModelRow = Model & { provider_name: string };

export function modelRows(models: Model[], providers: Provider[]): ModelRow[] {
  const names = new Map(providers.map((provider) => [provider.id, provider.name]));
  return models.map((model) => ({ ...model, provider_name: names.get(model.provider_id) ?? model.provider }));
}

// Columns map 1:1 to the backend ModelCatalogEntry properties. `defaultVisible` seeds the
// initial table; the user can add/remove any of them via the Columns menu.
export type ModelColumnId =
  | 'image'
  | 'name'
  | 'model_id'
  | 'canonical_id'
  | 'provider'
  | 'provider_id'
  | 'module_path'
  | 'description'
  | 'context_window'
  | 'status';

export type ModelColumn = {
  id: ModelColumnId;
  label: string;
  defaultVisible: boolean;
  sortable?: boolean;
  className?: string;
};

// Fixed widths keep the logo column from being stretched by long content in sibling columns
// (e.g. a multi-line description), guaranteeing a square logo.
export const MODEL_COLUMNS: ModelColumn[] = [
  { id: 'image', label: 'Image', defaultVisible: true, sortable: false, className: 'w-[52px]' },
  { id: 'name', label: 'Name', defaultVisible: true },
  { id: 'model_id', label: 'Model ID', defaultVisible: true },
  { id: 'canonical_id', label: 'Canonical ID', defaultVisible: false },
  { id: 'provider', label: 'Provider', defaultVisible: true },
  { id: 'provider_id', label: 'Provider ID', defaultVisible: false },
  { id: 'module_path', label: 'Module path', defaultVisible: false },
  { id: 'description', label: 'Description', defaultVisible: true, className: 'max-w-xs' },
  { id: 'context_window', label: 'Context', defaultVisible: true },
  { id: 'status', label: 'Status', defaultVisible: true },
];

export const DEFAULT_VISIBLE_COLUMNS = MODEL_COLUMNS.filter((c) => c.defaultVisible).map((c) => c.id);

/** The columns kept from a stored selection, or the defaults when none is known. */
export function visibleColumnsFrom(stored: unknown): ModelColumnId[] {
  if (!Array.isArray(stored)) return DEFAULT_VISIBLE_COLUMNS;
  const known = stored.filter((id): id is ModelColumnId => MODEL_COLUMNS.some((c) => c.id === id));
  return known.length ? known : DEFAULT_VISIBLE_COLUMNS;
}

export const CONFIGURED = 'Configured';
export const NOT_CONFIGURED = 'Not configured';

export function formatContext(ctx: number | null): string {
  if (!ctx) return '—';
  return ctx >= 1000 ? `${(ctx / 1000).toFixed(0)}K` : `${ctx}`;
}

/** What a column filter sees of a row. */
export function modelCellValues(row: ModelRow, column: ModelColumnId): string[] {
  switch (column) {
    case 'image':
      return [];
    case 'name':
      return [row.name ?? row.canonical_id];
    case 'model_id':
      return [row.model_id];
    case 'canonical_id':
      return [row.canonical_id];
    case 'provider':
      return [row.provider_name];
    case 'provider_id':
      return [row.provider_id];
    case 'module_path':
      return [row.module_path];
    case 'description':
      return [row.description ?? ''];
    case 'context_window':
      return [formatContext(row.context_window)];
    case 'status':
      return [row.configured ? CONFIGURED : NOT_CONFIGURED];
  }
}

/** What a column sorts on: the context window by size, any other column by its text. */
export function modelSortValue(row: ModelRow, column: ModelColumnId): string | number {
  if (column === 'context_window') return row.context_window ?? -1;
  return modelCellValues(row, column).join(', ');
}

/** What the search bar reads of a row: its ids, name and provider. */
export function modelSearchTexts(row: ModelRow): string[] {
  return [row.canonical_id, row.model_id, row.provider_id, row.provider, row.provider_name, row.name ?? ''];
}

export const MODEL_EXPORT_HEADERS = MODEL_COLUMNS.filter((c) => c.id !== 'image').map((c) => c.label);

/** A row of the CSV / Excel export: every column but the image, the context as a number. */
export function modelExportRow(row: ModelRow): string[] {
  return MODEL_COLUMNS.filter((c) => c.id !== 'image').map((c) =>
    c.id === 'context_window' ? (row.context_window ? String(row.context_window) : '') : modelCellValues(row, c.id)[0]
  );
}
