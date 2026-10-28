'use client';

import './dataset.css';

import { Database, KeyRound, Layers, Table2 } from 'lucide-react';
import { formatCount } from '../data-model';
import type { ResourceDetail, ResourceEntry } from '../data-types';
import { Badge, CopyButton } from '../data-ui';
import { DataGrid } from '../viewers/data-grid';
import type { ServiceView } from './types';

// Mirrors the dataset port's identifiers: a table, or namespace/table at the top level.
const TABLE_NAME = /^([A-Za-z][A-Za-z0-9_]*\/)?[A-Za-z][A-Za-z0-9_]*$/;
const SCHEMA_OPEN_UP_TO = 16;

interface TableView {
  columns: { name: string; type?: string }[];
  rows: unknown[][];
  total?: number | null;
  primary_key?: string[];
  partitions?: { column: string; transform: string }[];
}

function tableView(detail: ResourceDetail): TableView | null {
  const view = detail.view as (TableView & { type: string }) | null | undefined;
  return view && view.type === 'table' ? view : null;
}

function number(entry: ResourceEntry, key: string): number | null {
  const raw = entry.attributes[key];
  return raw === undefined ? null : Number(raw);
}

/** ``"a, b, +3 more"`` back into names and a remainder. */
export function splitNames(summary: string | undefined): { names: string[]; more: string | null } {
  if (!summary) return { names: [], more: null };
  const parts = summary.split(', ');
  const last = parts[parts.length - 1];
  if (last.startsWith('+')) return { names: parts.slice(0, -1), more: last };
  return { names: parts, more: null };
}

/** An error for CSV the adapter would refuse, or null. Comment lines (#) are skipped. */
export function csvProblem(text: string): string | null {
  const lines = text.split(/\r?\n/).filter((line) => !line.startsWith('#'));
  const header = lines.find((line) => line.trim() !== '');
  if (!header) return 'Start with a header row naming the columns, e.g. id,name.';
  const columns = header.split(',').map((c) => c.trim().replace(/^"|"$/g, ''));
  if (columns.some((c) => c === '')) return 'The header row has an empty column name.';
  const seen = new Set<string>();
  for (const column of columns) {
    if (seen.has(column)) return `The column "${column}" appears twice in the header.`;
    seen.add(column);
  }
  return null;
}

function NamespaceCard({ entry }: { entry: ResourceEntry }) {
  const { names, more } = splitNames(entry.attributes.summary);
  return (
    <div className="data-dataset-chips">
      {names.map((name) => (
        <span key={name} className="data-dataset-chip">
          <Table2 size={11} aria-hidden="true" />
          {name}
        </span>
      ))}
      {more && <span className="data-dataset-chip data-dataset-chip-more">{more}</span>}
    </div>
  );
}

export function TablePreview({ detail }: { detail: ResourceDetail }) {
  const view = tableView(detail);
  if (!view) return null;
  const [namespace, table] = detail.entry.id.split('/');
  const keys = new Set(view.primary_key ?? []);
  const partitions = new Map((view.partitions ?? []).map((p) => [p.column, p.transform]));
  const total = view.total ?? view.rows.length;
  const sql = `SELECT * FROM "${table}" LIMIT 100`;
  return (
    <div className="data-dataset-preview">
      <dl className="data-dataset-stats">
        <div>
          <dt>Rows</dt>
          <dd>{formatCount(total)}</dd>
        </div>
        <div>
          <dt>Columns</dt>
          <dd>{view.columns.length}</dd>
        </div>
        <div>
          <dt>Key</dt>
          <dd className="data-dataset-stat-text">{view.primary_key?.length ? view.primary_key.join(', ') : '—'}</dd>
        </div>
      </dl>
      <details className="data-dataset-schema" open={view.columns.length <= SCHEMA_OPEN_UP_TO}>
        <summary>
          Schema <span className="data-muted">· {view.columns.length} columns</span>
        </summary>
        <ul className="data-dataset-columns">
          {view.columns.map((c) => (
            <li key={c.name} className="data-dataset-column">
              <span className="data-dataset-column-name">{c.name}</span>
              {c.type && <span className={`data-dataset-type data-dataset-type-${c.type}`}>{c.type}</span>}
              {keys.has(c.name) && (
                <span className="data-dataset-marker" title="Primary key (advisory, used to match upserts)">
                  <KeyRound size={11} aria-hidden="true" /> key
                </span>
              )}
              {partitions.has(c.name) && (
                <span className="data-dataset-marker" title="Partition column">
                  <Layers size={11} aria-hidden="true" />
                  {partitions.get(c.name) === 'identity' ? 'partition' : `by ${partitions.get(c.name)}`}
                </span>
              )}
            </li>
          ))}
        </ul>
      </details>
      {total === 0 ? (
        <p className="data-muted">No rows yet. Edit the table to paste CSV, or upload a file.</p>
      ) : (
        <DataGrid columns={view.columns} rows={view.rows} total={view.total} />
      )}
      <div className="data-dataset-query">
        <span className="data-muted">
          Query in <code className="data-mono">{namespace}</code>
        </span>
        <code className="data-mono">{sql}</code>
        <CopyButton value={sql} label="Copy the SQL" />
      </div>
    </div>
  );
}

export const datasetView: ServiceView = {
  name: 'dataset',
  label: 'Datasets',
  description: 'Tables in the dataset warehouse, by namespace.',
  icon: Table2,
  group: 'Storage',
  noun: { one: 'table', many: 'tables' },
  nounFor: (entry) => (entry.kind === 'container' ? { one: 'namespace', many: 'namespaces' } : { one: 'table', many: 'tables' }),
  entryIcon: (entry) => (entry.kind === 'container' ? Database : Table2),
  // Tables: the column count and names; namespaces show their tables on the card.
  summary: (entry) => {
    if (entry.kind === 'container') return entry.attributes.summary;
    const columns = number(entry, 'columns');
    if (columns === null) return entry.attributes.summary;
    return (
      <>
        <span className="data-dataset-cols">{columns} cols</span>
        {entry.attributes.summary && <> · {entry.attributes.summary}</>}
      </>
    );
  },
  badges: (entry) =>
    entry.attributes.partitions ? (
      <Badge title="Partitioned by">
        <Layers size={10} aria-hidden="true" />
        {entry.attributes.partitions}
      </Badge>
    ) : null,
  level: (depth) =>
    depth === 0
      ? {
          noun: { one: 'namespace', many: 'namespaces' },
          layout: 'cards',
          card: (entry) => <NamespaceCard entry={entry} />,
          columns: [
            {
              id: 'tables',
              label: 'Tables',
              width: '80px',
              render: (e) => {
                const tables = number(e, 'tables');
                return <span className="data-num">{tables === null ? '—' : formatCount(tables)}</span>;
              },
            },
          ],
          emptyTitle: 'No datasets yet',
          emptyText: 'Modules create tables when they sync data. You can also create one from CSV as namespace/table.',
        }
      : {
          columns: [
            {
              id: 'rows',
              label: 'Rows',
              width: '96px',
              align: 'end',
              render: (e) => {
                const rows = number(e, 'rows');
                return <span className="data-num data-dataset-rows">{rows === null ? '—' : formatCount(rows)}</span>;
              },
            },
            {
              id: 'key',
              label: 'Key',
              width: 'minmax(0, 128px)',
              render: (e) =>
                e.attributes.primary_key ? (
                  <Badge mono title="Primary key">
                    <KeyRound size={10} aria-hidden="true" />
                    {e.attributes.primary_key}
                  </Badge>
                ) : (
                  <span className="data-muted">—</span>
                ),
            },
          ],
          emptyTitle: 'No tables in this namespace',
          emptyText: 'Create one from CSV: the header names the columns.',
        },
  facts: (detail) => {
    const view = tableView(detail);
    const facts: { label: string; value: React.ReactNode }[] = [];
    const rows = view?.total ?? number(detail.entry, 'rows');
    if (rows !== null && rows !== undefined) facts.push({ label: 'Rows', value: formatCount(rows) });
    const columns = view?.columns.length ?? number(detail.entry, 'columns');
    if (columns !== null && columns !== undefined) facts.push({ label: 'Columns', value: columns });
    if (detail.entry.attributes.primary_key) facts.push({ label: 'Key', value: detail.entry.attributes.primary_key });
    if (detail.entry.attributes.partitions) facts.push({ label: 'Partitions', value: detail.entry.attributes.partitions });
    return facts;
  },
  preview: (detail) => (tableView(detail) ? <TablePreview detail={detail} /> : null),
  createLabel: 'New table',
  acceptsDrops: true,
  dropName: (file) => {
    const match = file.name.match(/^([A-Za-z_][A-Za-z0-9_]*)\.csv$/i);
    return match ? match[1] : null;
  },
  dropHint: 'Drop CSV files named after a table, e.g. orders.csv, inside a namespace.',
  inspectorWidth: 640,
  editor: {
    language: () => 'plaintext',
    template: () => 'id,name,created\n1,First row,2026-10-02\n',
    validate: csvProblem,
    namePlaceholder: 'table_name',
    validateName: (name) =>
      TABLE_NAME.test(name.trim())
        ? null
        : 'Letters, digits and "_", starting with a letter (namespace/table at the top level).',
    allowUpload: true,
  },
  deleteWarning: (entry) =>
    `Drops ${entry.name} and all its ${
      number(entry, 'rows') !== null ? `${formatCount(number(entry, 'rows') ?? 0)} ` : ''
    }rows from the warehouse. Jobs and queries reading it fail afterwards.`,
};
