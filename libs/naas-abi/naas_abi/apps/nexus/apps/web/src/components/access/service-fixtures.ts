/** Fakes for the Access views' tests: an IAM admin API of `vi.fn()` and the rows it serves. */
import { vi } from 'vitest';
import type { IamAdminApi } from '@/lib/iam-admin/api';
import type {
  GroupView,
  KeyView,
  ManifestView,
  PrincipalView,
  ServiceAccountView,
} from '@/lib/iam-admin/types';

export const principal = (over: Partial<PrincipalView> = {}): PrincipalView => ({
  id: 'usr_1',
  kind: 'user',
  status: 'active',
  name: null,
  email: 'ada@example.com',
  display_name: 'Ada',
  provider: 'builtin',
  org: null,
  owner_id: null,
  created_at: '2026-10-01T10:00:00Z',
  ...over,
});

export const account = (over: Partial<ServiceAccountView> = {}): ServiceAccountView => ({
  ...principal({ id: 'sa_1', kind: 'service_account', name: 'ci', email: null, display_name: null, provider: null }),
  account_kind: 'custom',
  active_keys: 1,
  ...over,
});

export const key = (over: Partial<KeyView> = {}): KeyView => ({
  id: 'k1',
  principal_id: 'sa_1',
  kind: 'service',
  description: 'prod',
  prefix: 'abi_sk_k1',
  created_at: '2026-10-01T10:00:00Z',
  expires_at: null,
  last_used_at: null,
  revoked_at: null,
  status: 'active',
  ...over,
});

export const group = (over: Partial<GroupView> = {}): GroupView => ({
  ...principal({ id: 'grp_1', kind: 'group', name: 'Analysts', email: null, display_name: null, provider: null }),
  members: [],
  idp_mappings: [],
  ...over,
});

export const manifest = (over: Partial<ManifestView> = {}): ManifestView => ({
  principal_id: 'sa_mod',
  account_name: 'module/acme/people',
  sha256: 'a'.repeat(64),
  module_id: 'people',
  project: 'acme',
  status: 'pending',
  document: {
    version: '2026-10-13',
    statements: [
      {
        effect: 'Allow',
        actions: ['triple_store:Query', 'triple_store:ListGraphs'],
        resources: ['abi:-:-:triple_store:graph/a', 'abi:-:-:triple_store:graph/b'],
      },
      { effect: 'Deny', actions: ['triple_store:DropGraph'], resources: ['*'] },
    ],
  },
  catalog: null,
  submitted_at: '2026-10-02T10:00:00Z',
  decided_at: null,
  decided_by: null,
  reason: '',
  ...over,
});

/** An API whose every call is a `vi.fn()` that fails loudly unless the test set it up. */
export function fakeApi(over: Record<string, unknown> = {}): IamAdminApi {
  const handler = {
    get: (target: Record<string, unknown>, name: string) =>
      name in target ? target[name] : name === 'then' ? undefined : vi.fn(() => Promise.reject(new Error(`unexpected api.${name}`))),
  };
  return new Proxy({ ...over }, handler) as unknown as IamAdminApi;
}

export const allowAll = () => true;
