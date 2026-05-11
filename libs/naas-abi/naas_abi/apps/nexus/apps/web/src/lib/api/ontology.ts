import { apiFetch, apiFetchRaw, buildQuery, type RequestOptions } from './client';
import {
  OverviewGraphResponseSchema,
  OverviewStatsResponseSchema,
  OntologyTermsResponseSchema,
  HierarchyResponseSchema,
  type OverviewGraphNode,
  type OverviewGraphEdge,
} from '@/lib/schemas/ontology';

export interface OverviewGraphResult {
  nodes: OverviewGraphNode[];
  edges: OverviewGraphEdge[];
}

export interface OverviewStats {
  name: string;
  path: string;
  total_items: number;
  classes: number;
  relationships: number;
  data_properties: number;
  named_individuals: number;
}

export interface OntologyTerm {
  id: string;
  name: string;
}

/* ---------------- queries ---------------- */

export async function fetchOverviewGraph(
  ontologyPath: string | null,
  options: RequestOptions = {},
): Promise<OverviewGraphResult> {
  const data = await apiFetch(
    `/api/ontology/overview/graph${buildQuery({ ontology_path: ontologyPath ?? undefined })}`,
    OverviewGraphResponseSchema,
    options,
  );
  return { nodes: data.nodes ?? [], edges: data.edges ?? [] };
}

export async function fetchOverviewStats(
  ontologyPath: string | null,
  options: RequestOptions = {},
): Promise<OverviewStats> {
  const path = ontologyPath
    ? `/api/ontology/overview/stats${buildQuery({ ontology_path: ontologyPath })}`
    : `/api/ontology/overview/stats/all`;
  const data = await apiFetch(path, OverviewStatsResponseSchema, options);
  const toNum = (v: unknown) => {
    const n = Number(v);
    return Number.isFinite(n) ? n : 0;
  };
  const classes = toNum(data.classes);
  const relationships = toNum(data.object_properties);
  const dataProperties = toNum(data.data_properties);
  const namedIndividuals = toNum(data.named_individuals);
  const totalItems =
    toNum(data.total_items) ||
    classes + relationships + dataProperties + namedIndividuals;
  const fallbackName = ontologyPath
    ? ontologyPath.split('/').pop() || ontologyPath
    : 'All ontologies';
  return {
    name: typeof data.name === 'string' && data.name ? data.name : fallbackName,
    path: typeof data.path === 'string' && data.path ? data.path : ontologyPath ?? '*',
    total_items: totalItems,
    classes,
    relationships,
    data_properties: dataProperties,
    named_individuals: namedIndividuals,
  };
}

export async function fetchSubclassOptions(
  ontologyPath: string | null,
  options: RequestOptions = {},
): Promise<OntologyTerm[]> {
  const data = await apiFetch(
    `/api/ontology/classes${buildQuery({ ontology_path: ontologyPath ?? undefined })}`,
    OntologyTermsResponseSchema,
    options,
  );
  const items = Array.isArray(data) ? data : data.items ?? [];
  return items
    .map<OntologyTerm | null>((item) => {
      const id = item.id ?? item.iri ?? '';
      const name = (item.name && item.name.trim()) || (item.label && item.label.trim()) || id;
      return id ? { id, name } : null;
    })
    .filter((item): item is OntologyTerm => item !== null);
}

export async function fetchSubpropertyOptions(
  ontologyPath: string | null,
  options: RequestOptions = {},
): Promise<OntologyTerm[]> {
  const data = await apiFetch(
    `/api/ontology/relationships${buildQuery({ ontology_path: ontologyPath ?? undefined })}`,
    OntologyTermsResponseSchema,
    options,
  );
  const items = Array.isArray(data) ? data : data.items ?? [];
  return items
    .map<OntologyTerm | null>((item) => {
      const id = item.id ?? item.iri ?? '';
      const name = (item.name && item.name.trim()) || (item.label && item.label.trim()) || id;
      return id ? { id, name } : null;
    })
    .filter((item): item is OntologyTerm => item !== null);
}

export async function fetchHierarchy(args: {
  ontologyPath: string;
  classIris: string[];
  options?: RequestOptions;
}): Promise<{ nodes: OverviewGraphNode[]; edges: OverviewGraphEdge[] }> {
  const data = await apiFetch(
    `/api/ontology/overview/hierarchy${buildQuery({
      ontology_path: args.ontologyPath,
      class_iris: args.classIris,
    })}`,
    HierarchyResponseSchema,
    args.options,
  );
  return { nodes: data.nodes ?? [], edges: data.edges ?? [] };
}

/* ---------------- mutations / file download ---------------- */

/**
 * Triggers a TTL download in the browser. Resolves once the browser has
 * accepted the click; rejects on HTTP failure.
 */
export async function exportOntology(ontologyPath: string): Promise<void> {
  const response = await apiFetchRaw(
    `/api/ontology/export${buildQuery({ ontology_path: ontologyPath })}`,
  );
  const contentDisposition = response.headers.get('content-disposition') || '';
  const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/i);
  const filename = filenameMatch?.[1] || ontologyPath.split('/').pop() || 'ontology.ttl';

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  try {
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
  } finally {
    URL.revokeObjectURL(url);
  }
}

/* ---------------- query keys ---------------- */

export const ontologyKeys = {
  all: () => ['ontology'] as const,
  overviewGraph: (ontologyPath: string | null) =>
    ['ontology', 'overview-graph', ontologyPath] as const,
  overviewStats: (ontologyPath: string | null) =>
    ['ontology', 'overview-stats', ontologyPath] as const,
  classes: (ontologyPath: string | null) => ['ontology', 'classes', ontologyPath] as const,
  relationships: (ontologyPath: string | null) =>
    ['ontology', 'relationships', ontologyPath] as const,
  hierarchy: (ontologyPath: string, classIris: string[]) =>
    ['ontology', 'hierarchy', ontologyPath, [...classIris].sort()] as const,
};
