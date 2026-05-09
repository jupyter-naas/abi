import { z } from 'zod';

/**
 * Ontology API schemas. Mirrors the conventions in `schemas/graph.ts`:
 * - `.optional()` instead of `.default()` to keep z.infer types stable.
 * - Defaults applied at call sites in `lib/api/ontology.ts`.
 */

const OverviewGraphNodeSchema = z.object({
  id: z.string(),
  label: z.string(),
  type: z.string(),
  properties: z.record(z.unknown()).optional(),
});
export type OverviewGraphNode = z.infer<typeof OverviewGraphNodeSchema>;

const OverviewGraphEdgeSchema = z.object({
  id: z.string(),
  source: z.string(),
  target: z.string(),
  type: z.string(),
  label: z.string().optional(),
  properties: z.record(z.unknown()).optional(),
});
export type OverviewGraphEdge = z.infer<typeof OverviewGraphEdgeSchema>;

export const OverviewGraphResponseSchema = z.object({
  nodes: z.array(OverviewGraphNodeSchema).optional(),
  edges: z.array(OverviewGraphEdgeSchema).optional(),
});
export type OverviewGraphResponse = z.infer<typeof OverviewGraphResponseSchema>;

export const OverviewStatsResponseSchema = z.object({
  name: z.string().optional(),
  path: z.string().optional(),
  classes: z.union([z.number(), z.string()]).optional(),
  object_properties: z.union([z.number(), z.string()]).optional(),
  data_properties: z.union([z.number(), z.string()]).optional(),
  named_individuals: z.union([z.number(), z.string()]).optional(),
  total_items: z.union([z.number(), z.string()]).optional(),
});
export type OverviewStatsResponse = z.infer<typeof OverviewStatsResponseSchema>;

const OntologyTermSchema = z.object({
  id: z.string().optional(),
  iri: z.string().optional(),
  name: z.string().optional(),
  label: z.string().optional(),
});

export const OntologyTermsResponseSchema = z.union([
  z.array(OntologyTermSchema),
  z.object({ items: z.array(OntologyTermSchema).optional() }),
]);

export const HierarchyResponseSchema = z.object({
  nodes: z.array(OverviewGraphNodeSchema).optional(),
  edges: z.array(OverviewGraphEdgeSchema).optional(),
});
export type HierarchyResponse = z.infer<typeof HierarchyResponseSchema>;
