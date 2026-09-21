'use client';
import { useState, useEffect, useRef, type MutableRefObject } from 'react';
import { Loader2, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { authFetch } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';
import { useGraphTableSizing, type GraphTableWidths } from './table/use-graph-table-sizing';
import { ColumnResizeHandle } from './table/column-resize-handle';
const RDFS_LABEL = 'http://www.w3.org/2000/01/rdf-schema#label';
export interface ApiDiscoveryInstance {
  uri: string;
  graph_uri?: string;
  label: string;
  class_uri: string;
  class_label: string;
  properties: Record<string, string>;
  bfo_bucket_uri?: string;
  bfo_bucket_label?: string;
  domain_relations_count?: number;
  range_relations_count?: number;
  properties_count?: number;
}

function compactUri(uri: string): string {
  if (!uri) return '';
  for (const sep of ['#', '/']) {
    if (uri.includes(sep)) {
      const tail = uri.split(sep).pop();
      if (tail) return tail;
    }
  }
  return uri;
}

function instanceLabel(inst: ApiDiscoveryInstance): string {
  return inst.label || inst.properties[RDFS_LABEL] || compactUri(inst.uri);
}

export function IndividualsTable({
  instances,
  graphUri,
  workspaceId,
  onDeleted,
  readOnly = false,
  onOpen,
  graphLabels,
  columnWidthsRef,
}: {
  instances: ApiDiscoveryInstance[];
  graphUri: string;
  workspaceId: string;
  onDeleted: (deletedUris: string[]) => void;
  readOnly?: boolean;
  onOpen?: (instance: ApiDiscoveryInstance) => void;
  graphLabels?: Record<string, string>;
  columnWidthsRef?: MutableRefObject<GraphTableWidths>;
}) {
  const columns = [
    ...(!readOnly ? [{ id: 'selection', label: 'Select', width: 44, minWidth: 44 }] : []),
    ...(graphLabels ? [{ id: 'graph', label: 'Graph', width: 180 }] : []),
    { id: 'uri', label: 'URI', width: 240 },
    { id: 'label', label: 'Label', width: 320 },
    { id: 'class', label: 'Class', width: 220 },
    { id: 'bucket', label: 'Bucket', width: 160 },
    { id: 'outgoing', label: '→', title: 'Outgoing object properties (domain)', width: 80, numeric: true },
    { id: 'incoming', label: '←', title: 'Incoming object properties (range)', width: 80, numeric: true },
    { id: 'properties', label: 'Properties', width: 104, numeric: true },
  ];
  const sizing = useGraphTableSizing(columns, columnWidthsRef);
  const [rowChecked, setRowChecked] = useState<Set<string>>(
    () => new Set(readOnly ? [] : instances.map((i) => i.uri)),
  );
  const [showDialog, setShowDialog] = useState(false);
  const [confirmInput, setConfirmInput] = useState('');
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    setRowChecked(new Set(readOnly ? [] : instances.map((i) => i.uri)));
  }, [instances, readOnly]);

  const allChecked = instances.length > 0 && instances.every((i) => rowChecked.has(i.uri));
  const someChecked = !allChecked && instances.some((i) => rowChecked.has(i.uri));
  const checkedCount = rowChecked.size;

  const headerCheckRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (headerCheckRef.current) headerCheckRef.current.indeterminate = someChecked;
  }, [someChecked]);

  const toggleAll = () => {
    if (allChecked || someChecked) setRowChecked(new Set());
    else setRowChecked(new Set(readOnly ? [] : instances.map((i) => i.uri)));
  };

  const toggleRow = (uri: string) => {
    setRowChecked((prev) => {
      const next = new Set(prev);
      if (next.has(uri)) next.delete(uri);
      else next.add(uri);
      return next;
    });
  };

  const handleBatchDelete = async () => {
    setDeleting(true);
    setShowDialog(false);
    setConfirmInput('');
    const uris = [...rowChecked];
    const deletedUris: string[] = [];
    for (const uri of uris) {
      try {
        const res = await authFetch(`${getApiUrl()}/api/graph/nodes/delete`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            workspace_id: workspaceId,
            graph_uri: graphUri,
            individual_uri: uri,
          }),
        });
        if (res.ok) deletedUris.push(uri);
      } catch {
        // continue with remaining deletions
      }
    }
    setDeleting(false);
    onDeleted(deletedUris);
  };

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
      {showDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-md rounded-lg border bg-background p-6 shadow-2xl">
            <h3 className="text-base font-semibold">
              Remove {checkedCount} individual{checkedCount !== 1 ? 's' : ''}?
            </h3>
            <p className="mt-2 text-sm text-muted-foreground">
              This will permanently remove {checkedCount} individual
              {checkedCount !== 1 ? 's' : ''} and all their triples from the graph. This action
              cannot be undone.
            </p>
            <p className="mt-3 text-sm text-muted-foreground">
              Type <span className="font-semibold text-foreground">{checkedCount}</span> to confirm:
            </p>
            <input
              autoFocus
              value={confirmInput}
              onChange={(e) => setConfirmInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && confirmInput === String(checkedCount))
                  void handleBatchDelete();
                if (e.key === 'Escape') {
                  setShowDialog(false);
                  setConfirmInput('');
                }
              }}
              className="mt-2 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
              placeholder={`Type ${checkedCount} to confirm`}
            />
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setShowDialog(false);
                  setConfirmInput('');
                }}
                className="px-4 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={confirmInput !== String(checkedCount)}
                onClick={() => void handleBatchDelete()}
                className="bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Remove {checkedCount} individual{checkedCount !== 1 ? 's' : ''}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="flex shrink-0 items-center gap-3 border-b px-4 py-2">
        <span className="text-sm font-semibold">
          {instances.length} instance{instances.length !== 1 ? 's' : ''}
          {readOnly ? '' : ' selected'}
        </span>
        {!readOnly && (
          <div className="ml-auto">
            {deleting ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 size={14} className="animate-spin" />
                Removing…
              </div>
            ) : (
              <button
                type="button"
                disabled={checkedCount === 0}
                onClick={() => setShowDialog(true)}
                className="flex items-center gap-1.5 rounded-md border border-red-300 px-3 py-1.5 text-xs text-red-500 transition-colors hover:bg-red-50 disabled:opacity-50 dark:hover:bg-red-900/20"
              >
                <Trash2 size={12} />
                Remove {checkedCount} selected
              </button>
            )}
          </div>
        )}
      </div>

      <div className="graph-table-scroll">
        <table
          ref={sizing.tableRef}
          className="table-fixed border-collapse text-xs"
          style={{ width: sizing.totalWidth }}
        >
          <colgroup>
            {columns.map((col) => (
              <col key={col.id} style={{ width: sizing.colWidths[col.id] ?? col.width }} />
            ))}
          </colgroup>
          <thead>
            <tr>
              {columns.map((col) => (
                <th
                  key={col.id}
                  ref={(el) => { sizing.thRefs.current[col.id] = el; }}
                  scope="col"
                  data-col-id={col.id}
                  className={cn('graph-table-instance-heading', col.numeric && 'is-numeric')}
                  title={col.title}
                >
                  {col.id === 'selection' ? (
                    <input
                      ref={headerCheckRef}
                      type="checkbox"
                      aria-label="Select all instances"
                      checked={allChecked}
                      onChange={toggleAll}
                      className="h-4 w-4 cursor-pointer rounded accent-workspace-accent"
                    />
                  ) : (
                    <>
                      <span>{col.label}</span>
                      <ColumnResizeHandle id={col.id} label={col.title || col.label} sizing={sizing} />
                    </>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {instances.map((inst) => {
              const checked = rowChecked.has(inst.uri);
              return (
                <tr
                  key={`${inst.graph_uri || graphUri}:${inst.uri}`}
                  className={cn(
                    'border-t transition-colors',
                    checked ? 'bg-orange-50/50 dark:bg-orange-900/10' : 'hover:bg-muted/30',
                  )}
                >
                  {!readOnly && (
                    <td className="graph-table-instance-cell">
                      <input
                        type="checkbox"
                        aria-label={`Select ${instanceLabel(inst)}`}
                        checked={checked}
                        onChange={() => toggleRow(inst.uri)}
                        className="h-4 w-4 cursor-pointer rounded accent-workspace-accent"
                      />
                    </td>
                  )}
                  {graphLabels && (
                    <td
                      className="graph-table-instance-cell text-muted-foreground"
                      title={inst.graph_uri}
                    >
                      {graphLabels[inst.graph_uri || graphUri] ||
                        compactUri(inst.graph_uri || graphUri)}
                    </td>
                  )}
                  <td
                    className="graph-table-instance-cell font-mono text-xs text-muted-foreground"
                    title={inst.uri}
                  >
                    {compactUri(inst.uri)}
                  </td>
                  <td
                    className="graph-table-instance-cell font-medium"
                    title={instanceLabel(inst)}
                  >
                    {onOpen ? (
                      <button
                        type="button"
                        className="block max-w-full truncate text-left text-workspace-accent hover:underline"
                        onClick={() => onOpen(inst)}
                      >
                        {instanceLabel(inst)}
                      </button>
                    ) : (
                      instanceLabel(inst)
                    )}
                  </td>
                  <td
                    className="graph-table-instance-cell text-blue-600 dark:text-blue-400"
                    title={inst.class_label || inst.class_uri}
                  >
                    {inst.class_label || compactUri(inst.class_uri)}
                  </td>
                  <td
                    className="graph-table-instance-cell text-muted-foreground"
                    title={inst.bfo_bucket_label ?? ''}
                  >
                    {inst.bfo_bucket_label ?? '—'}
                  </td>
                  <td className="graph-table-instance-cell text-right tabular-nums">
                    {inst.domain_relations_count ?? '—'}
                  </td>
                  <td className="graph-table-instance-cell text-right tabular-nums">
                    {inst.range_relations_count ?? '—'}
                  </td>
                  <td className="graph-table-instance-cell text-right tabular-nums">
                    {inst.properties_count ?? '—'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
