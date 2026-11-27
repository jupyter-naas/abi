/**
 * Settings › Datasets (`GET` / `PUT /api/workspaces/{id}/offer/datasets`, or an organization's):
 * the deployment's dataset namespaces and whether the workspace uses each. Every namespace the
 * deployment shares is used until "<W> access" closes it (`OfferDatasetsDeny`), or "<O> access"
 * above it does for every workspace of the organization. Closing narrows the workspace; reopening
 * lifts a Deny of its bound, which only the platform admin does (IAM says so on save). Pure: the
 * view is `datasets.tsx`.
 */

export type PolicyRef = { id: string; name: string; owner_scope: string };

export type DatasetRow = {
  namespace: string;
  /** How many datasets the deployment holds in it (0: closed, then gone from the deployment). */
  tables: number;
  /** Their names, A to Z: unfolded under the namespace. */
  datasets?: string[];
  available: boolean;
  /** Used here: closed neither by this policy nor by the one above. */
  offered: boolean;
  /** Closed by the organization ("<O> access"): no workspace reopens it. */
  closed_above: boolean;
  editable: boolean;
  reason: string | null;
};

export type DatasetsState = {
  workspace_id: string;
  scope: string;
  access_policy: PolicyRef | null;
  /** The policy read: "<W> access" by default, or another policy of the workspace. */
  policy?: PolicyRef | null;
  ceiling: PolicyRef | null;
  editable: boolean;
  rows: DatasetRow[];
  error: string | null;
};

/** What a save sends: each namespace whose draft is not what it holds (`{namespace: offered}`). */
export function changesFrom(rows: DatasetRow[], drafts: Record<string, boolean>): Record<string, boolean> {
  return Object.fromEntries(
    rows.flatMap((row) => {
      const draft = drafts[row.namespace];
      return draft === undefined || draft === row.offered ? [] : [[row.namespace, draft]];
    })
  );
}

/** What a batch change sends: each editable row of `keys` not yet `on` (`{namespace: on}`). */
export function bulkChanges(rows: DatasetRow[], keys: Iterable<string>, on: boolean): Record<string, boolean> {
  const picked = new Set(keys);
  return Object.fromEntries(
    rows.filter((row) => picked.has(row.namespace) && row.editable && row.offered !== on).map((row) => [row.namespace, on])
  );
}

/** What a row says under its switch: why it cannot change, or that the deployment lost it. */
export function rowNote(row: DatasetRow): string | null {
  if (row.reason) return row.reason;
  if (!row.available) return 'No longer in the deployment: closed here only.';
  return null;
}

/** The columns of the table: each sorts and filters, as Settings › Users. */
export type DatasetColumnId = 'namespace' | 'tables' | 'offered';
export const DATASET_COLUMNS: { id: DatasetColumnId; label: string }[] = [
  { id: 'namespace', label: 'Namespace' },
  { id: 'tables', label: 'Datasets' },
  { id: 'offered', label: 'Offered' },
];

/** What a column filter sees of a row (what it holds, not an unsaved draft). */
export function datasetCellValues(row: DatasetRow, column: DatasetColumnId): string[] {
  if (column === 'namespace') return [row.namespace];
  if (column === 'tables') return [String(row.tables)];
  return [row.offered ? 'Offered' : 'Not offered'];
}

/** What a column sorts on: the number of datasets as a number. */
export function datasetSortValue(row: DatasetRow, column: DatasetColumnId): string | number {
  return column === 'tables' ? row.tables : datasetCellValues(row, column)[0];
}

/** What the search bar reads of a row. */
export function datasetSearchTexts(row: DatasetRow): string[] {
  return [
    row.namespace,
    ...(row.datasets ?? []),
    row.offered ? 'offered' : 'not offered',
    row.closed_above ? 'closed by the organization' : '',
    row.available ? '' : 'gone',
  ];
}

export const DATASET_EXPORT_HEADERS = ['Namespace', 'Datasets', 'Offered', 'Closed by the organization'];

export function datasetExportRow(row: DatasetRow): string[] {
  return [row.namespace, String(row.tables), row.offered ? 'Yes' : 'No', row.closed_above ? 'Yes' : 'No'];
}
