import { z } from 'zod';

/**
 * NOTE on `.default()` and types:
 * Zod 3's nested `.default()` interacts poorly with `z.infer` when arrays are
 * involved (the inferred type keeps the field optional). We therefore keep the
 * raw schemas with `.optional()` and apply defaults at the call site, which
 * is also what the rest of the app expects.
 */

export const ApiNodeSchema = z.object({
  id: z.string(),
  workspace_id: z.string().optional(),
  type: z.string(),
  label: z.string(),
  properties: z.record(z.unknown()).optional(),
});
export type ApiNode = z.infer<typeof ApiNodeSchema>;

export const ApiEdgeSchema = z.object({
  id: z.string(),
  workspace_id: z.string().optional(),
  source_id: z.string(),
  target_id: z.string(),
  source_label: z.string().optional(),
  target_label: z.string().optional(),
  type: z.string(),
  properties: z.record(z.unknown()).optional(),
});
export type ApiEdge = z.infer<typeof ApiEdgeSchema>;

export const NetworkResponseSchema = z.object({
  nodes: z.array(ApiNodeSchema).optional(),
  edges: z.array(ApiEdgeSchema).optional(),
});
export type NetworkResponse = z.infer<typeof NetworkResponseSchema>;

export const OverviewSchema = z.object({
  kpis: z
    .object({
      total_instances: z.number().optional(),
      total_relationships: z.number().optional(),
      average_degree: z.number().optional(),
      density: z.number().optional(),
    })
    .optional(),
  instances_by_class: z
    .array(z.object({ type: z.string(), count: z.number() }))
    .optional(),
});
export type Overview = z.infer<typeof OverviewSchema>;

const GraphListEntrySchema = z.object({
  id: z.string(),
  label: z.string().optional(),
});

/** Backend may return a flat list, `{ graphs: [...] }`, or a list of `{ graphs: [...] }` chunks. */
export const GraphListResponseSchema = z.union([
  z.array(GraphListEntrySchema),
  z.object({ graphs: z.array(GraphListEntrySchema) }),
  z.array(z.object({ graphs: z.array(GraphListEntrySchema) })),
]);

export const GraphViewInfoSchema = z.object({
  workspace_id: z.string().optional(),
  id: z.string(),
  label: z.string(),
  graph_names: z.array(z.string()).optional(),
  graph_filters: z.array(z.string()).optional(),
  scope: z.enum(['workspace', 'user']),
  user_id: z.string().nullable().optional(),
  created_at: z.string().optional(),
});
export type GraphViewInfo = z.infer<typeof GraphViewInfoSchema>;

export const GraphViewListResponseSchema = z.array(GraphViewInfoSchema);

export const FilterOptionSchema = z.object({
  uri: z.string(),
  label: z.string(),
});
export type FilterOption = z.infer<typeof FilterOptionSchema>;

export const FilterOptionsResponseSchema = z.object({
  subjects: z.array(FilterOptionSchema).optional(),
  predicates: z.array(FilterOptionSchema).optional(),
  objects: z.array(FilterOptionSchema).optional(),
});
export type FilterOptionsResponse = z.infer<typeof FilterOptionsResponseSchema>;

export const TriplePreviewRowSchema = z.object({
  subject: z.string(),
  predicate: z.string(),
  object: z.string(),
});
export type TriplePreviewRow = z.infer<typeof TriplePreviewRowSchema>;

export const TriplePreviewResponseSchema = z.object({
  count: z.number().optional(),
  individual_count: z.number().optional(),
  object_properties_count: z.number().optional(),
  data_properties_count: z.number().optional(),
  rows: z.array(TriplePreviewRowSchema).optional(),
});
export type TriplePreviewResponse = z.infer<typeof TriplePreviewResponseSchema>;

const OntologyClassSchema = z.object({
  id: z.string().optional(),
  iri: z.string().optional(),
  name: z.string().optional(),
  label: z.string().optional(),
  description: z.string().optional(),
  definition: z.string().optional(),
});

export const OntologyClassesResponseSchema = z.union([
  z.array(OntologyClassSchema),
  z.object({ items: z.array(OntologyClassSchema).optional() }),
]);

/** Body returned by `POST /api/graph/create` and `POST /api/view/`. */
export const CreatedEntitySchema = z
  .object({
    id: z.string().optional(),
    view_id: z.string().optional(),
    uri: z.string().optional(),
    view_uri: z.string().optional(),
  })
  .passthrough();

/** Best-effort id extraction from creation responses. */
export function extractCreatedId(payload: unknown): string | null {
  const parsed = CreatedEntitySchema.safeParse(payload);
  if (!parsed.success) return null;
  const { id, view_id, uri, view_uri } = parsed.data;
  if (typeof id === 'string' && id) return id;
  if (typeof view_id === 'string' && view_id) return view_id;
  if (typeof uri === 'string' && uri) return uri.split('/').pop() ?? null;
  if (typeof view_uri === 'string' && view_uri) return view_uri.split('/').pop() ?? null;
  return null;
}
