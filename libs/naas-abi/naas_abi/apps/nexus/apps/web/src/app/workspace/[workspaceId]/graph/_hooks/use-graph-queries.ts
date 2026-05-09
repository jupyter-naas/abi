'use client';

import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { useAuthStore } from '@/stores/auth';
import {
  fetchGraphList,
  fetchNetwork,
  fetchOverview,
  fetchViews,
  fetchOntologyClasses,
  fetchFilterOptions,
  fetchTriplePreview,
  createGraph,
  createIndividual,
  createView,
  updateView,
  updateNode,
  deleteNode,
  graphKeys,
  type GraphSelection,
  type ViewFilterDraft,
} from '@/lib/api/graph';

/**
 * `userId` is folded into every query key so a logout/login on the same tab
 * cannot ever serve the previous user's cached data — the bug we'd have hit
 * with the old module-scope Maps keyed only by URL.
 */
function useUserScope() {
  return useAuthStore((s) => s.user?.id ?? 'anon');
}

export function useGraphList(workspaceId: string) {
  const userId = useUserScope();
  return useQuery({
    queryKey: ['graph', workspaceId, 'list', userId] as const,
    queryFn: ({ signal }) => fetchGraphList(workspaceId, { signal }),
    enabled: Boolean(workspaceId),
  });
}

export function useGraphNetwork(sel: GraphSelection, opts?: { enabled?: boolean }) {
  const userId = useUserScope();
  return useQuery({
    queryKey: [...graphKeys.network(sel), userId] as const,
    queryFn: ({ signal }) => fetchNetwork(sel, { signal }),
    enabled: opts?.enabled !== false && Boolean(sel.workspaceId),
  });
}

export function useGraphOverview(sel: GraphSelection, opts?: { enabled?: boolean }) {
  const userId = useUserScope();
  return useQuery({
    queryKey: [...graphKeys.overview(sel), userId] as const,
    queryFn: ({ signal }) => fetchOverview(sel, { signal }),
    enabled: opts?.enabled !== false && Boolean(sel.workspaceId),
  });
}

export function useGraphViews(workspaceId: string) {
  const userId = useUserScope();
  return useQuery({
    queryKey: ['graph', workspaceId, 'views', userId] as const,
    queryFn: ({ signal }) => fetchViews(workspaceId, { signal }),
    enabled: Boolean(workspaceId),
  });
}

export function useOntologyClasses(enabled: boolean) {
  return useQuery({
    queryKey: ['ontology', 'classes'] as const,
    queryFn: ({ signal }) => fetchOntologyClasses({ signal }),
    enabled,
    staleTime: 5 * 60_000,
  });
}

export function useFilterOptions(args: {
  workspaceId: string;
  graphIds: string[];
  rows: ViewFilterDraft[];
  enabled: boolean;
}) {
  const userId = useUserScope();
  return useQuery({
    queryKey: [
      'graph',
      args.workspaceId,
      'filter-options',
      args.graphIds,
      args.rows,
      userId,
    ] as const,
    queryFn: ({ signal }) =>
      Promise.all(args.rows.map((row) => fetchFilterOptions(args.workspaceId, args.graphIds, row, { signal }))),
    enabled: args.enabled,
  });
}

export function useTriplePreview(args: {
  workspaceId: string;
  graphIds: string[];
  filters: ViewFilterDraft[];
  enabled: boolean;
}) {
  const userId = useUserScope();
  const shouldPreview = args.filters.some(
    (item) =>
      item.subject_uri.trim().length > 0 ||
      (item.predicate_uri.trim().length > 0 && item.object_uri.trim().length > 0),
  );
  return useQuery({
    queryKey: [
      'graph',
      args.workspaceId,
      'triple-preview',
      args.graphIds,
      args.filters,
      userId,
    ] as const,
    queryFn: ({ signal }) =>
      fetchTriplePreview({
        workspaceId: args.workspaceId,
        graphIds: args.graphIds,
        filters: args.filters,
        options: { signal },
      }),
    enabled: args.enabled && shouldPreview,
  });
}

/* ---------------- mutations ---------------- */

export function useCreateGraph() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createGraph,
    onSuccess: (_data, variables) => {
      void qc.invalidateQueries({ queryKey: ['graph', variables.workspaceId] });
    },
  });
}

export function useCreateIndividual() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createIndividual,
    onSuccess: (_data, variables) => {
      void qc.invalidateQueries({ queryKey: ['graph', variables.workspaceId] });
    },
  });
}

export function useCreateView(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createView,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['graph', workspaceId, 'views'] });
    },
  });
}

export function useUpdateView(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ viewId, payload }: { viewId: string; payload: Parameters<typeof updateView>[1] }) =>
      updateView(viewId, payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['graph', workspaceId, 'views'] });
    },
  });
}

export function useUpdateNode(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: updateNode,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['graph', workspaceId] });
    },
  });
}

export function useDeleteNode(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteNode,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['graph', workspaceId] });
    },
  });
}
