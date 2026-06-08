'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  ChevronDown,
  ChevronRight,
  Info,
  Loader2,
  Pencil,
  Trash2,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';

export interface DiscoveryInstance {
  uri: string;
  label: string;
  class_uri: string;
  class_label: string;
}

interface InstanceDetail {
  uri: string;
  label: string;
  class_uri: string;
  class_label: string;
  data_properties: Array<{
    predicate_uri: string;
    predicate_label: string;
    value: string;
  }>;
  relations: Array<{
    role: 'domain' | 'range';
    predicate_uri: string;
    predicate_label: string;
    other_uri: string;
    other_label: string;
  }>;
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

export function InstanceInspector({
  instance,
  graphUri,
  workspaceId,
  onClose,
}: {
  instance: DiscoveryInstance;
  graphUri: string;
  workspaceId: string;
  onClose: () => void;
}) {
  const router = useRouter();
  const [detail, setDetail] = useState<InstanceDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [relationsCollapsed, setRelationsCollapsed] = useState(false);
  const [roleFilter, setRoleFilter] = useState<'domain' | 'range'>('domain');

  useEffect(() => {
    if (!graphUri || !instance.uri) return;
    setDetail(null);
    setLoading(true);
    void authFetch(`${getApiUrl()}/api/graph/discovery/instance-detail`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        workspace_id: workspaceId,
        graph_uri: graphUri,
        instance_uri: instance.uri,
      }),
    })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((data) => setDetail(data as InstanceDetail))
      .catch(() => setDetail(null))
      .finally(() => setLoading(false));
  }, [instance.uri, graphUri, workspaceId]);

  const filteredRelations = useMemo(
    () => (detail?.relations ?? []).filter((r) => r.role === roleFilter),
    [detail, roleFilter]
  );

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <header className="flex items-center justify-between border-b bg-muted/40 px-4 py-2">
        <div className="flex items-center gap-2">
          <Info size={14} className="text-muted-foreground" />
          <h3 className="text-sm font-semibold">Inspector</h3>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-muted-foreground hover:text-foreground"
          title="Close inspector"
        >
          <X size={14} />
        </button>
      </header>

      <div className="flex-1 space-y-4 overflow-auto px-4 py-3 text-xs">
        <div>
          <div className="mb-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            URI
          </div>
          <span className="break-all font-mono text-[11px]">{instance.uri}</span>
        </div>

        <div>
          <div className="mb-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            Label
          </div>
          <span>{instance.label || '—'}</span>
        </div>

        <div>
          <div className="mb-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            Class
          </div>
          <div>{instance.class_label || compactUri(instance.class_uri)}</div>
          <div className="break-all font-mono text-[11px] text-muted-foreground">
            {instance.class_uri}
          </div>
        </div>

        <div>
          <div className="mb-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            Data properties
          </div>
          {loading ? (
            <div className="flex items-center gap-1.5 text-muted-foreground">
              <Loader2 size={12} className="animate-spin" />
              Loading…
            </div>
          ) : detail && detail.data_properties.length > 0 ? (
            <div className="space-y-2">
              {detail.data_properties.map((dp, i) => (
                <div key={`${dp.predicate_uri}-${i}`}>
                  <div className="text-muted-foreground">{dp.predicate_label}</div>
                  <div className="break-all">{dp.value}</div>
                </div>
              ))}
            </div>
          ) : detail ? (
            <div className="text-muted-foreground">No data properties.</div>
          ) : null}
        </div>

        <div className="border-t pt-3">
          <button
            type="button"
            onClick={() => setRelationsCollapsed((v) => !v)}
            className="flex w-full items-center gap-1.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground hover:text-foreground"
          >
            {relationsCollapsed ? <ChevronRight size={12} /> : <ChevronDown size={12} />}
            Relations
            {detail && (
              <span className="ml-auto font-normal normal-case tracking-normal">
                {detail.relations.length}
              </span>
            )}
          </button>

          {!relationsCollapsed && (
            <div className="mt-2 space-y-3">
              <div className="flex gap-1">
                {(['domain', 'range'] as const).map((role) => (
                  <button
                    key={role}
                    type="button"
                    onClick={() => setRoleFilter(role)}
                    className={cn(
                      'rounded px-2 py-0.5 text-[11px] capitalize',
                      roleFilter === role
                        ? 'bg-workspace-accent text-white'
                        : 'bg-muted text-muted-foreground hover:bg-muted/70'
                    )}
                  >
                    {role}
                  </button>
                ))}
              </div>

              {loading ? (
                <div className="flex items-center gap-1.5 text-muted-foreground">
                  <Loader2 size={12} className="animate-spin" />
                  Loading…
                </div>
              ) : filteredRelations.length === 0 ? (
                <div className="text-muted-foreground">No {roleFilter} relations.</div>
              ) : (
                <div className="space-y-3">
                  {filteredRelations.map((r, i) => (
                    <div key={`${r.predicate_uri}-${r.other_uri}-${i}`} className="space-y-0.5">
                      <div className="text-muted-foreground">{r.predicate_label}</div>
                      <div>{r.other_label}</div>
                      <div className="break-all font-mono text-[11px] text-muted-foreground">
                        {r.other_uri}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <footer className="flex shrink-0 items-center gap-2 border-t bg-muted/20 px-4 py-2">
        <button
          type="button"
          onClick={() => {
            onClose();
            router.push(
              `/workspace/${workspaceId}/graph/individuals?selected=${encodeURIComponent(instance.uri)}`
            );
          }}
          className="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs transition-colors hover:bg-muted"
        >
          <Pencil size={12} />
          Edit
        </button>
        <button
          type="button"
          onClick={() => {
            onClose();
            router.push(
              `/workspace/${workspaceId}/graph/individuals?selected=${encodeURIComponent(instance.uri)}`
            );
          }}
          className="flex items-center gap-1.5 rounded-md border border-red-300 px-3 py-1.5 text-xs text-red-500 transition-colors hover:bg-red-50 dark:hover:bg-red-900/20"
        >
          <Trash2 size={12} />
          Remove
        </button>
      </footer>
    </div>
  );
}
