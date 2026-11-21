/**
 * Model sets (S3, #1586, `iam/model_sets.py`): which models a person chats with directly. Each
 * set is a platform policy on `abi:model_registry:model/<canonical id>`, kept in step with the
 * configuration at each start:
 * - "Models · member": the members' default set, `nexus_config.models.member_set`;
 * - "Models · all": every model (admins, and the capability group "Models · all");
 * - "Models · embeddings": the embedding models, for search (every Member and Viewer).
 * An agent's own model is always allowed, whatever the set.
 *
 * Read from the policies themselves (`GET /api/iam/admin/policies`): no endpoint of its own, and
 * read-only, since the configuration is where a set changes. Pure.
 */
import type { PolicyView } from '@/lib/iam-admin/types';

export type ModelSetKey = 'member' | 'all' | 'embeddings';

export const MODEL_SETS: { key: ModelSetKey; name: string; title: string; heldBy: string }[] = [
  {
    key: 'member',
    name: 'Models · member',
    title: 'Members’ default set',
    heldBy: 'Members (the level group), in the workspaces they belong to',
  },
  {
    key: 'all',
    name: 'Models · all',
    title: 'Every model',
    heldBy: 'Workspace and organization admins, and the capability group Models · all',
  },
  {
    key: 'embeddings',
    name: 'Models · embeddings',
    title: 'Embedding models',
    heldBy: 'Every Member and Viewer, for search',
  },
];

const MODEL_PREFIX = 'abi:model_registry:model/';

function decoded(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

/** The models a set names: their canonical ids, or `all` for `model/*`. An empty set (a name no
 *  id matches) is no model. */
export function modelsOf(policy: Pick<PolicyView, 'document'>): string[] | 'all' {
  const ids = new Set<string>();
  for (const statement of policy.document.statements) {
    // "Embed" on every model is how search embeds: what names the embedding models is "Resolve".
    if (statement.effect !== 'Allow' || statement.actions.every((a) => a === 'model_registry:Embed')) continue;
    for (const resource of statement.resources) {
      if (!resource.startsWith(MODEL_PREFIX)) continue;
      const id = decoded(resource.slice(MODEL_PREFIX.length));
      if (id === '*') return 'all';
      // "Models · member" with no id names a model no id can be (a NUL): nothing.
      if (id && !id.includes('\u0000')) ids.add(id);
    }
  }
  return [...ids].sort((a, b) => a.localeCompare(b));
}

export type ModelSetView = (typeof MODEL_SETS)[number] & { policy: PolicyView | null; models: string[] | 'all' };

/** Each set, with its policy (the platform's, by name) and the models it names; a set not made
 *  yet has no policy and no model. */
export function modelSets(policies: PolicyView[]): ModelSetView[] {
  return MODEL_SETS.map((set) => {
    const policy = policies.find((p) => p.name === set.name && (p.owner_scope ?? 'abi:') === 'abi:') ?? null;
    return { ...set, policy, models: policy ? modelsOf(policy) : [] };
  });
}
