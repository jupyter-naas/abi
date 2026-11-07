'use client';

import './document.css';

import { Braces, ChevronRight, FileJson, FolderTree, History, Package, PenLine } from 'lucide-react';
import { formatCount } from '../data-model';
import type { ResourceDetail, ResourceEntry } from '../data-types';
import { Badge, Notice, RelativeTime } from '../data-ui';
import { JsonTree } from '../viewers/json-tree';
import {
  DOCUMENT_TEMPLATE,
  checkpointKind,
  checkpointTitle,
  collectionPurpose,
  collectionSpec,
  deriveColumnKeys,
  describeSpec,
  documentFields,
  documentLevel,
  namespaceKind,
  namespaceLabel,
  threadLabel,
  validateDocument,
  validateDocumentId,
  type FieldValue,
} from './document-model';
import type { Column, Level, ServiceView } from './types';

function count(value: string | undefined): number | null {
  const n = Number(value);
  return value !== undefined && value !== '' && Number.isFinite(n) ? n : null;
}

/** A count from an attribute, or a dash when the API did not report it. */
/** The fields a collection declares (types, indexes, uniqueness) on one line. */
function DeclaredFields({ entry }: { entry: ResourceEntry }) {
  const spec = collectionSpec(entry);
  if (!spec || (!spec.fields.length && !spec.unique_together.length)) {
    return <span className="data-muted">none declared</span>;
  }
  return (
    <span className="data-mono data-document-fields" title={describeSpec(spec).join('\n')}>
      {spec.fields.map((f) => f.name).join(', ') || `${spec.unique_together.length} unique groups`}
    </span>
  );
}

function Count({ value }: { value: string | undefined }) {
  const n = count(value);
  return <span className="data-num">{n === null ? '—' : formatCount(n)}</span>;
}

function FieldCell({ value }: { value: FieldValue | undefined }) {
  if (value === undefined || value === null || value === '') return <span className="data-document-null">—</span>;
  if (typeof value === 'boolean') return <Badge tone={value ? 'success' : 'neutral'}>{String(value)}</Badge>;
  if (typeof value === 'number') return <span className="data-num">{formatCount(value)}</span>;
  return (
    <span className="data-document-cell" title={value}>
      {value}
    </span>
  );
}

/** The first few values of a document as key/value chips, the telling ones first. */
function FieldChips({ entry }: { entry: ResourceEntry }) {
  const fields = documentFields(entry);
  const keys = Object.keys(fields);
  if (!keys.length) return entry.attributes.summary ? <>{entry.attributes.summary}</> : null;
  const preferred = ['title', 'name', 'label', 'status', 'state', 'type', 'kind'];
  const ordered = [
    ...preferred.filter((k) => k in fields),
    ...keys.filter((k) => !preferred.includes(k) && fields[k] !== null && fields[k] !== ''),
  ].slice(0, 3);
  return (
    <span className="data-document-chips">
      {ordered.map((key) => (
        <span key={key} className="data-document-chip">
          <span className="data-document-chip-key">{key}</span>
          <span className="data-document-chip-value">{String(fields[key])}</span>
        </span>
      ))}
      {keys.length > ordered.length && <span className="data-document-chip-more">+{keys.length - ordered.length}</span>}
    </span>
  );
}

function NamespaceCard({ entry }: { entry: ResourceEntry }) {
  const { lead, context } = namespaceLabel(entry.name);
  return (
    <span className="data-document-ns">
      <span className="data-document-ns-lead">{lead}</span>
      {context && <span className="data-document-ns-context">{context}</span>}
    </span>
  );
}

const versionColumn: Column = {
  id: 'version',
  label: 'Version',
  width: '76px',
  align: 'end',
  render: (e) => (e.attributes.version ? <Badge mono>v{e.attributes.version}</Badge> : null),
};

const updatedColumn: Column = {
  id: 'updated',
  label: 'Updated',
  width: '112px',
  render: (e) => <RelativeTime iso={e.modified} />,
};

/** Columns for the keys most documents of the page share (a table-editor feel). */
export function derivedColumns(entries: ResourceEntry[]): Column[] {
  return deriveColumnKeys(entries).map((key) => ({
    id: `field:${key}`,
    label: key,
    width: 'minmax(96px, 0.45fr)',
    render: (e) => <FieldCell value={documentFields(e)[key]} />,
  }));
}

/** LangGraph saver collections: one row per step (or write), newest first, grouped by thread. */
function checkpointLevel(kind: 'checkpoint' | 'write'): Level {
  if (kind === 'write') {
    return {
      noun: { one: 'write', many: 'writes' },
      columns: [
        {
          id: 'task',
          label: 'Task',
          width: 'minmax(120px, 0.6fr)',
          render: (e) => <span className="data-document-cell data-mono">{e.attributes.task || '—'}</span>,
        },
        updatedColumn,
      ],
      groupBy: threadLabel,
      notice: <Notice tone="info">What each step produced before LangGraph saved the next checkpoint, grouped by thread.</Notice>,
      emptyTitle: 'No pending writes',
      emptyText: 'Agents using the document checkpointer record them here while a step runs.',
    };
  }
  return {
    noun: { one: 'checkpoint', many: 'checkpoints' },
    columns: [
      {
        id: 'messages',
        label: 'Messages',
        width: '92px',
        align: 'end',
        render: (e) => <Count value={e.attributes.messages} />,
      },
      {
        id: 'saved',
        label: 'Saved',
        width: '112px',
        render: (e) => <RelativeTime iso={e.attributes.checkpoint_at ?? e.modified} />,
      },
    ],
    groupBy: threadLabel,
    notice: (
      <Notice tone="info">
        Each row is a conversation&apos;s state after one step of its agent, newest first and grouped by thread. Open one
        to read the conversation as the agent saw it.
      </Notice>
    ),
    emptyTitle: 'No checkpoints yet',
    emptyText: 'Agents using the document checkpointer save one here after every step.',
  };
}

function level(depth: number, parent: string, entries?: ResourceEntry[]): Level {
  const checkpoints = depth === 2 ? checkpointKind(parent) : null;
  if (checkpoints) return checkpointLevel(checkpoints);
  if (depth === 0) {
    return {
      noun: { one: 'namespace', many: 'namespaces' },
      layout: 'cards',
      card: (e) => <NamespaceCard entry={e} />,
      columns: [
        {
          id: 'collections',
          label: 'Collections',
          width: '1fr',
          render: (e) => <Count value={e.attributes.collections} />,
        },
        { id: 'kind', label: 'Origin', width: '1fr', render: (e) => namespaceKind(e.name) },
      ],
      emptyTitle: 'No document namespaces yet',
      emptyText: 'Modules get a namespace the first time they create a collection.',
    };
  }
  if (depth === 1) {
    return {
      noun: { one: 'collection', many: 'collections' },
      columns: [
        {
          id: 'documents',
          label: 'Documents',
          width: '104px',
          align: 'end',
          render: (e) => <Count value={e.attributes.documents} />,
        },
        {
          id: 'fields',
          label: 'Declared fields',
          width: 'minmax(160px, 1fr)',
          render: (e) => <DeclaredFields entry={e} />,
        },
      ],
      emptyTitle: 'No collections in this namespace',
      emptyText: 'Collections are created by the module that owns them, with the fields and indexes it declares.',
    };
  }
  return {
    noun: { one: 'document', many: 'documents' },
    columns: [...(entries ? derivedColumns(entries) : []), versionColumn, updatedColumn],
    emptyTitle: 'This collection is empty',
    emptyText: 'Create a document to add one by hand, or let the owning module write here.',
  };
}

function DocumentPreview({ detail }: { detail: ResourceDetail }) {
  const view = detail.view;
  if (!view || view.type !== 'json') return null;
  const [namespace, collection] = detail.entry.id.split('/').map((s) => decodeURIComponent(s));
  const keys = view.value && typeof view.value === 'object' ? Object.keys(view.value as object).length : 0;
  return (
    <div className="data-document-preview">
      <div className="data-document-path" aria-label="Location">
        <Package size={13} aria-hidden="true" />
        <span>{namespace}</span>
        <ChevronRight size={12} aria-hidden="true" />
        <FolderTree size={13} aria-hidden="true" />
        <span>{collection}</span>
        {collectionPurpose(collection) && <Badge tone="info">{collectionPurpose(collection)}</Badge>}
      </div>
      <dl className="data-document-meta">
        <div>
          <dt>Version</dt>
          <dd>v{detail.entry.attributes.version ?? '—'}</dd>
        </div>
        <div>
          <dt>Fields</dt>
          <dd>{formatCount(keys)}</dd>
        </div>
        <div>
          <dt>Created</dt>
          <dd>
            <RelativeTime iso={detail.entry.attributes.created_at} />
          </dd>
        </div>
        <div>
          <dt>Updated</dt>
          <dd>
            <RelativeTime iso={detail.entry.modified} />
          </dd>
        </div>
      </dl>
      <JsonTree value={(view as { value: unknown }).value} depth={2} />
    </div>
  );
}

export const documentView: ServiceView = {
  name: 'document',
  label: 'Documents',
  description: 'JSON documents modules store per namespace and collection.',
  icon: Braces,
  group: 'Storage',
  noun: { one: 'document', many: 'documents' },
  entryIcon: (e) => {
    const at = documentLevel(e.id);
    if (at === 'document' && checkpointKind(e.id)) return checkpointKind(e.id) === 'write' ? PenLine : History;
    return at === 'namespace' ? Package : at === 'collection' ? FolderTree : FileJson;
  },
  nounFor: (e) => {
    const at = documentLevel(e.id);
    if (at === 'namespace') return { one: 'namespace', many: 'namespaces' };
    if (at === 'collection') return { one: 'collection', many: 'collections' };
    if (checkpointKind(e.id) === 'checkpoint') return { one: 'checkpoint', many: 'checkpoints' };
    if (checkpointKind(e.id) === 'write') return { one: 'write', many: 'writes' };
    return { one: 'document', many: 'documents' };
  },
  level,
  canCreate: (depth, parent) => {
    if (depth !== 2) return 'Open a collection to create documents in it.';
    return checkpointKind(parent) ? 'Agents write checkpoints; create them by running the agent.' : true;
  },
  title: (e) => (documentLevel(e.id) === 'document' && checkpointKind(e.id) ? checkpointTitle(e) : null),
  summary: (e) => {
    if (documentLevel(e.id) !== 'document') return e.attributes.summary;
    const kind = checkpointKind(e.id);
    if (kind === 'checkpoint') {
      const n = Number(e.attributes.messages ?? 0);
      const count = `${formatCount(n)} ${n === 1 ? 'message' : 'messages'}`;
      return e.attributes.last ? `${count} · ${e.attributes.last}` : count;
    }
    if (kind === 'write') return e.attributes.summary;
    return <FieldChips entry={e} />;
  },
  badges: (e) => {
    if (documentLevel(e.id) === 'namespace') return <Badge>{namespaceKind(e.name)}</Badge>;
    const purpose = documentLevel(e.id) === 'collection' ? collectionPurpose(e.name) : null;
    return purpose ? <Badge tone="info">{purpose}</Badge> : null;
  },
  facts: (detail) =>
    detail.view?.type === 'checkpoint'
      ? [
          { label: 'Thread', value: threadLabel(detail.entry).replace(/^Thread /, '') },
          { label: 'Saved', value: <RelativeTime iso={detail.entry.attributes.checkpoint_at ?? detail.entry.modified} /> },
        ]
      : [
          { label: 'Version', value: `v${detail.entry.attributes.version ?? '—'}` },
          { label: 'Fields', value: detail.entry.attributes.keys ?? '—' },
          { label: 'Updated', value: <RelativeTime iso={detail.entry.modified} /> },
        ],
  // Too large for a structured view: the generic preview shows the text.
  preview: (detail) => (detail.view?.type === 'json' ? <DocumentPreview detail={detail} /> : null),
  createLabel: 'New document',
  editor: {
    language: () => 'json',
    template: () => DOCUMENT_TEMPLATE,
    validate: validateDocument,
    namePlaceholder: 'document-id',
    validateName: validateDocumentId,
  },
  deleteWarning: (e) => {
    if (documentLevel(e.id) === 'collection') {
      const n = count(e.attributes.documents);
      const what = n === null ? 'every document in it' : `its ${formatCount(n)} ${n === 1 ? 'document' : 'documents'}`;
      return `Drops the ${e.name} collection with ${what}. The module that owns it may recreate it empty on its next write, or fail if it expects the data there.`;
    }
    return `Removes ${e.name}. The owning module gets "not found" the next time it reads it; for a run record or a checkpoint, that history is gone.`;
  },
};
