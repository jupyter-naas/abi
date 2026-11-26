/**
 * Settings › Ontologies and Settings › Graphs (`/api/workspaces/{id}/resource-access/{kind}`): what
 * each row may do under the draft being edited, and the table's columns (search, sort, filter,
 * export, as Settings › Users). Pure: the view is `resource-access.tsx`.
 */
import type { SettingsColumn } from '@/components/settings/users-table/settings-table';

export type ResourceKind = 'ontologies' | 'graphs';
export type ResourcePolicy = {
  enabled?: string[];
  read?: string[];
  write?: string[];
  read_all?: boolean;
  include_owned?: boolean;
  allow_create?: boolean;
};
export type ResourceEntry = {
  id: string;
  name: string;
  description: string;
  available: boolean;
  owned?: boolean;
  read_only?: boolean;
};

export type ResourceAccess = 'enabled' | 'disabled' | 'edit' | 'read' | 'none';

/** A catalog entry and what the draft gives it. */
export type ResourceRow = ResourceEntry & {
  access: ResourceAccess;
  /** Ontologies: enabled. */
  enabled: boolean;
  /** Graphs: included as a graph created in this workspace. */
  ownedIncluded: boolean;
  readable: boolean;
  editable: boolean;
};

/** Each catalog entry under the current (unsaved) draft. */
export function resourceRows(kind: ResourceKind, catalog: readonly ResourceEntry[], draft: ResourcePolicy): ResourceRow[] {
  return catalog.map((item) => {
    const enabled = !!draft.enabled?.includes(item.id);
    const ownedIncluded = !!draft.include_owned && !!item.owned;
    const editable = !item.read_only && (ownedIncluded || !!draft.write?.includes(item.id));
    const readable = !!draft.read_all || ownedIncluded || !!draft.read?.includes(item.id) || !!draft.write?.includes(item.id);
    const access: ResourceAccess =
      kind === 'ontologies'
        ? enabled
          ? 'enabled'
          : 'disabled'
        : editable
          ? 'edit'
          : draft.read_all || ownedIncluded || draft.read?.includes(item.id)
            ? 'read'
            : 'none';
    return { ...item, access, enabled, ownedIncluded, readable, editable };
  });
}

export const ACCESS_LABELS: Record<ResourceAccess, string> = {
  enabled: 'Enabled',
  disabled: 'Disabled',
  edit: 'Read & edit',
  read: 'Read only',
  none: 'No access',
};

export type ResourceColumnId = 'name' | 'enabled' | 'read' | 'edit' | 'availability';
const CHECK_COLUMN = 'w-24';

export const ONTOLOGY_COLUMNS: SettingsColumn<ResourceColumnId>[] = [
  { id: 'name', label: 'Ontology' },
  { id: 'enabled', label: 'Enabled', className: CHECK_COLUMN },
  { id: 'availability', label: 'Availability', className: 'w-36' },
];
export const GRAPH_COLUMNS: SettingsColumn<ResourceColumnId>[] = [
  { id: 'name', label: 'Named graph' },
  { id: 'read', label: 'Read', className: CHECK_COLUMN },
  { id: 'edit', label: 'Edit', className: CHECK_COLUMN },
  { id: 'availability', label: 'Availability', className: 'w-36' },
];

export const resourceColumns = (kind: ResourceKind) => (kind === 'ontologies' ? ONTOLOGY_COLUMNS : GRAPH_COLUMNS);

const yesNo = (value: boolean) => (value ? 'Yes' : 'No');
const availabilityLabel = (row: ResourceRow) => (row.available ? 'Available' : 'Unavailable');

/** What a column filter sees of a row: what the draft gives it. */
export function resourceCellValues(row: ResourceRow, column: ResourceColumnId): string[] {
  if (column === 'name') return [row.name];
  if (column === 'enabled') return [ACCESS_LABELS[row.enabled ? 'enabled' : 'disabled']];
  if (column === 'read') return [yesNo(row.readable)];
  if (column === 'edit') return [yesNo(row.editable)];
  return [availabilityLabel(row)];
}

/** What the search bar reads of a row: its name, description, access and availability. */
export function resourceSearchTexts(row: ResourceRow): string[] {
  return [row.name, row.description, ACCESS_LABELS[row.access], availabilityLabel(row)];
}

export function resourceExportHeaders(kind: ResourceKind): string[] {
  return kind === 'ontologies'
    ? ['Ontology', 'Id', 'Description', 'Enabled', 'Availability']
    : ['Named graph', 'Id', 'Description', 'Read', 'Edit', 'Availability'];
}

export function resourceExportRow(kind: ResourceKind, row: ResourceRow): string[] {
  const access = kind === 'ontologies' ? [yesNo(row.enabled)] : [yesNo(row.readable), yesNo(row.editable)];
  return [row.name, row.id, row.description, ...access, availabilityLabel(row)];
}
