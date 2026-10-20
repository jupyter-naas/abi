'use client';

import { useEffect, useState } from 'react';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';

export type WorkspaceGraph = { uri: string; label: string };

/** Graphs the workspace may read (for SPARQL layer scoping). */
export function useWorkspaceGraphs(workspaceId: string | null): WorkspaceGraph[] | null {
  const [graphs, setGraphs] = useState<WorkspaceGraph[] | null>(null);

  useEffect(() => {
    if (!workspaceId) {
      setGraphs([]);
      return;
    }
    let cancelled = false;
    authFetch(`${getApiUrl()}/api/graph/list?workspace_id=${encodeURIComponent(workspaceId)}`)
      .then((r) => (r.ok ? r.json() : []))
      .then((packs: { graphs: { uri: string; label: string }[] }[]) => {
        if (cancelled) return;
        const seen = new Map<string, WorkspaceGraph>();
        for (const pack of packs) {
          for (const g of pack.graphs) {
            if (!seen.has(g.uri)) seen.set(g.uri, { uri: g.uri, label: g.label || g.uri });
          }
        }
        setGraphs([...seen.values()].sort((a, b) => a.label.localeCompare(b.label)));
      })
      .catch(() => {
        if (!cancelled) setGraphs([]);
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  return graphs;
}
