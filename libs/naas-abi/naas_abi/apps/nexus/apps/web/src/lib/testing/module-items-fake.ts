/**
 * A fake of what `useModuleItems` reads and writes (the offer, IAM's publishers and resources),
 * for the page tests of Agents, Apps and Workflows. A test mocks `createOfferApi` and
 * `createIamAdminApi` to return `moduleItemsFake.offer` and `.iam`, then `set`s the catalog.
 */
import type { OfferApi, OfferChange, OfferItem, OfferKind, OfferState } from '@/lib/access-model/workspace-offer';
import type { IamAdminApi } from '@/lib/iam-admin/api';
import type { ResourceQuery } from '@/lib/iam-admin/types';

const SCOPE = 'abi:nexus:organization/acme/nexus:workspace/ws-1';

export type FakeCatalog = {
  /** What the policy offers. */
  offered?: Partial<Record<OfferKind, OfferItem[]>>;
  /** Each module's items by type (`agent`, `app`, `workflow`, `pipeline`). */
  modules?: Record<string, Partial<Record<string, { name: string; label?: string }[]>>>;
  editable?: boolean;
};

export function createModuleItemsFake() {
  let catalog: FakeCatalog = {};
  let offered: Record<OfferKind, OfferItem[]> = { agents: [], apps: [], workflows: [], pipelines: [] };
  const saves: { changes: OfferChange[]; policyId: string | null }[] = [];
  const reads: (string | null)[] = [];

  const state = (): OfferState => ({
    workspace_id: 'ws-1',
    scope: SCOPE,
    access_policy: { id: 'pol_access', name: 'Alpha access', owner_scope: SCOPE },
    editable: catalog.editable ?? true,
    whole_module: '*',
    offered: { ...offered },
  });

  const offer = {
    read: async (_workspaceId: string, policyId?: string | null) => {
      reads.push(policyId ?? null);
      return state();
    },
    save: async (_workspaceId: string, changes: OfferChange[], policyId?: string | null) => {
      saves.push({ changes, policyId: policyId ?? null });
      for (const change of changes) {
        const kept = offered[change.kind].filter((i) => !(i.module === change.module && i.name === change.name));
        offered = { ...offered, [change.kind]: change.offered ? [...kept, { module: change.module, name: change.name }] : kept };
      }
      return state();
    },
  } as unknown as OfferApi;

  const iam = {
    publishers: async (scope: string) => ({
      scope,
      publishers: Object.entries(catalog.modules ?? {}).map(([id, types]) => ({
        id,
        kind: 'module',
        types: Object.keys(types).map((type) => ({ service: 'module', type, module: id })),
      })),
    }),
    resources: async (query: ResourceQuery) => ({
      scope: query.scope,
      service: query.service,
      type: query.type,
      items: (catalog.modules?.[query.module ?? '']?.[query.type] ?? []).map((item) => ({
        name: `${query.scope}/module:${query.type}/${query.module}/${item.name}`,
        id: `${query.module}/${item.name}`,
        label: item.label ?? item.name,
        description: '',
      })),
      next_cursor: null,
      listed: true,
    }),
  } as unknown as IamAdminApi;

  return {
    offer,
    iam,
    saves,
    reads,
    set(next: FakeCatalog) {
      catalog = next;
      offered = { agents: [], apps: [], workflows: [], pipelines: [], ...next.offered };
      saves.length = 0;
      reads.length = 0;
    },
  };
}

export const moduleItemsFake = createModuleItemsFake();
