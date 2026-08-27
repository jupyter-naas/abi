'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { authFetch } from './auth';
import { useWorkspaceStore } from './workspace';

export interface DatasetColumn {
  name: string;
  type: string;
}

export interface DatasetPartition {
  column: string;
  transform: string;
}

export interface DatasetInfo {
  name: string;
  namespace: string;
  columns: DatasetColumn[];
  partitions: DatasetPartition[];
  snapshot_id: string;
  location: string;
}

export interface DatasetQueryResult {
  columns: string[];
  rows: Record<string, unknown>[];
  truncated: boolean;
  limit: number;
}

interface DatasetsState {
  datasets: DatasetInfo[];
  loading: boolean;
  error: string | null;
  expandedNamespaces: string[];
  fetchDatasets: (workspaceId?: string | null) => Promise<void>;
  toggleNamespace: (namespace: string) => void;
  describe: (namespace: string, name: string, workspaceId?: string | null) => Promise<DatasetInfo>;
  preview: (
    namespace: string,
    name: string,
    workspaceId?: string | null,
    limit?: number,
  ) => Promise<DatasetQueryResult>;
  query: (
    namespace: string,
    sql: string,
    workspaceId?: string | null,
    limit?: number,
  ) => Promise<DatasetQueryResult>;
}

function currentWorkspaceId(): string | null {
  return useWorkspaceStore.getState().currentWorkspaceId;
}

function requireWorkspaceId(workspaceId?: string | null): string {
  const id = workspaceId ?? currentWorkspaceId();
  if (!id) {
    throw new Error('workspace_id is required');
  }
  return id;
}

async function readError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === 'string') return body.detail;
  } catch {
    // ignore
  }
  return response.statusText || 'Request failed';
}

export const useDatasetsStore = create<DatasetsState>()(
  persist(
    (set, get) => ({
      datasets: [],
      loading: false,
      error: null,
      expandedNamespaces: [],

      fetchDatasets: async (workspaceId) => {
        const id = requireWorkspaceId(workspaceId);
        set({ loading: true, error: null });
        try {
          const response = await authFetch(
            `/api/datasets/?workspace_id=${encodeURIComponent(id)}`,
          );
          if (!response.ok) {
            throw new Error(await readError(response));
          }
          const payload = (await response.json()) as { datasets: DatasetInfo[] };
          const datasets = payload.datasets ?? [];
          const namespaces = [...new Set(datasets.map((item) => item.namespace))];
          const expanded = get().expandedNamespaces;
          set({
            datasets,
            loading: false,
            expandedNamespaces: expanded.length > 0 ? expanded : namespaces,
          });
        } catch (error) {
          set({
            loading: false,
            error: error instanceof Error ? error.message : 'Failed to load datasets',
          });
        }
      },

      toggleNamespace: (namespace) =>
        set({
          expandedNamespaces: get().expandedNamespaces.includes(namespace)
            ? get().expandedNamespaces.filter((item) => item !== namespace)
            : [...get().expandedNamespaces, namespace],
        }),

      describe: async (namespace, name, workspaceId) => {
        const id = requireWorkspaceId(workspaceId);
        const response = await authFetch(
          `/api/datasets/${encodeURIComponent(namespace)}/${encodeURIComponent(name)}?workspace_id=${encodeURIComponent(id)}`,
        );
        if (!response.ok) {
          throw new Error(await readError(response));
        }
        return (await response.json()) as DatasetInfo;
      },

      preview: async (namespace, name, workspaceId, limit = 100) => {
        const id = requireWorkspaceId(workspaceId);
        const params = new URLSearchParams({
          workspace_id: id,
          limit: String(limit),
        });
        const response = await authFetch(
          `/api/datasets/${encodeURIComponent(namespace)}/${encodeURIComponent(name)}/preview?${params}`,
        );
        if (!response.ok) {
          throw new Error(await readError(response));
        }
        return (await response.json()) as DatasetQueryResult;
      },

      query: async (namespace, sql, workspaceId, limit) => {
        const id = requireWorkspaceId(workspaceId);
        const response = await authFetch(
          `/api/datasets/${encodeURIComponent(namespace)}/query`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              workspace_id: id,
              sql,
              limit: limit ?? 1000,
            }),
          },
        );
        if (!response.ok) {
          throw new Error(await readError(response));
        }
        return (await response.json()) as DatasetQueryResult;
      },
    }),
    { name: 'nexus-datasets', partialize: (state) => ({ expandedNamespaces: state.expandedNamespaces }) },
  ),
);
