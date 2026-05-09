import { resolveBucket, type BucketResolvable } from '@/lib/bfo';
import type { OntologyOverviewGraphNode } from './types';

/**
 * Thin wrapper over the shared `lib/bfo` module so this page and `vis-network`
 * can never disagree on bucketing again.
 *
 * Always returns one of the canonical BFO bucket names (or 'Unknown' when
 * nothing resolves) — never `null`.
 */
export function resolveNodeBucket(
  node: OntologyOverviewGraphNode,
  nodesById?: Map<string, OntologyOverviewGraphNode>,
): string {
  return resolveBucket(node as BucketResolvable, nodesById);
}
