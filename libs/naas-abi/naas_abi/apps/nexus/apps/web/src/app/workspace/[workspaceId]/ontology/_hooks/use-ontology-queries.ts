'use client';

import { useMutation, useQuery } from '@tanstack/react-query';
import {
  exportOntology,
  fetchHierarchy,
  fetchOverviewGraph,
  fetchOverviewStats,
  fetchSubclassOptions,
  fetchSubpropertyOptions,
  ontologyKeys,
} from '@/lib/api/ontology';

export function useOntologyOverviewGraph(args: {
  ontologyPath: string | null;
  enabled: boolean;
}) {
  return useQuery({
    queryKey: ontologyKeys.overviewGraph(args.ontologyPath),
    queryFn: ({ signal }) => fetchOverviewGraph(args.ontologyPath, { signal }),
    enabled: args.enabled,
    staleTime: 60_000,
  });
}

export function useOntologyOverviewStats(ontologyPath: string | null) {
  return useQuery({
    queryKey: ontologyKeys.overviewStats(ontologyPath),
    queryFn: ({ signal }) => fetchOverviewStats(ontologyPath, { signal }),
    staleTime: 60_000,
  });
}

export function useOntologySubclassOptions(args: {
  ontologyPath: string | null;
  enabled: boolean;
}) {
  return useQuery({
    queryKey: ontologyKeys.classes(args.ontologyPath),
    queryFn: ({ signal }) => fetchSubclassOptions(args.ontologyPath, { signal }),
    enabled: args.enabled,
    staleTime: 5 * 60_000,
  });
}

export function useOntologySubpropertyOptions(args: {
  ontologyPath: string | null;
  enabled: boolean;
}) {
  return useQuery({
    queryKey: ontologyKeys.relationships(args.ontologyPath),
    queryFn: ({ signal }) => fetchSubpropertyOptions(args.ontologyPath, { signal }),
    enabled: args.enabled,
    staleTime: 5 * 60_000,
  });
}

export function useOntologyHierarchy(args: {
  ontologyPath: string | null;
  classIris: string[];
  enabled: boolean;
}) {
  return useQuery({
    queryKey: args.ontologyPath
      ? ontologyKeys.hierarchy(args.ontologyPath, args.classIris)
      : ['ontology', 'hierarchy', null] as const,
    queryFn: ({ signal }) =>
      fetchHierarchy({
        ontologyPath: args.ontologyPath as string,
        classIris: args.classIris,
        options: { signal },
      }),
    enabled: args.enabled && Boolean(args.ontologyPath) && args.classIris.length > 0,
  });
}

export function useExportOntology() {
  return useMutation({
    mutationFn: exportOntology,
  });
}
