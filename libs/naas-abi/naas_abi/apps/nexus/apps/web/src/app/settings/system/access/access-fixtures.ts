/** Fixtures for the Access views' tests. */
import type { IamAdminApi } from '@/lib/iam-admin/api';
import type {
  AttachmentView,
  CatalogsView,
  PolicyView,
  PrincipalView,
} from '@/lib/iam-admin/types';

export const catalogsView: CatalogsView = {
  variables: ['scope', 'principal.id', 'user.id'],
  catalogs: [
    {
      service: 'triple_store',
      version: 1,
      resource_types: [
        { name: 'graph', id: 'opaque', placement: 'placed', container: false, personal: false, description: 'A named graph.' },
      ],
      actions: [
        { name: 'ListGraphs', qualified: 'triple_store:ListGraphs', level: 'list', resource_types: ['graph'], creates: false, description: 'List graphs.' },
        { name: 'Query', qualified: 'triple_store:Query', level: 'read', resource_types: ['graph'], creates: false, description: 'Run a SPARQL query.' },
        { name: 'Insert', qualified: 'triple_store:Insert', level: 'write', resource_types: ['graph'], creates: false, description: 'Insert triples.' },
        { name: 'DropGraph', qualified: 'triple_store:DropGraph', level: 'admin', resource_types: ['graph'], creates: false, description: 'Drop a graph.' },
      ],
    },
    {
      service: 'iam',
      version: 4,
      resource_types: [
        { name: 'policy', id: 'opaque', placement: 'platform', container: false, personal: false, description: 'A policy.' },
        { name: 'key', id: 'path', placement: 'platform', container: false, personal: true, description: 'A key.' },
      ],
      actions: [
        { name: 'GetPolicy', qualified: 'iam:GetPolicy', level: 'read', resource_types: ['policy'], creates: false, description: 'Read a policy.' },
        { name: 'ListKeys', qualified: 'iam:ListKeys', level: 'list', resource_types: ['key'], creates: false, description: 'List keys.' },
      ],
    },
  ],
};

export const readerPolicy: PolicyView = {
  id: 'pol_1',
  name: 'Graph reader',
  description: 'Reads graphs',
  managed: false,
  revision: 3,
  document: {
    version: '2026-10-13',
    statements: [
      {
        sid: 'Read',
        effect: 'Allow',
        actions: ['triple_store:Query'],
        resources: ['abi:acme:ws-1:triple_store:graph/*'],
      },
    ],
  },
  created_at: '2026-10-01T10:00:00Z',
  updated_at: '2026-10-02T10:00:00Z',
};

export const managedPolicy: PolicyView = {
  ...readerPolicy,
  id: 'builtin.viewer',
  name: 'Viewer',
  managed: true,
  revision: 1,
};

export const ada: PrincipalView = {
  id: 'usr_ada',
  kind: 'user',
  status: 'active',
  name: null,
  email: 'ada@example.com',
  display_name: 'Ada',
  provider: 'builtin',
  org: null,
  owner_id: null,
  created_at: '2026-10-01T10:00:00Z',
};

export const ci: PrincipalView = {
  ...ada,
  id: 'sa_ci',
  kind: 'service_account',
  name: 'ci',
  email: null,
  display_name: null,
};

export function attachment(over: Partial<AttachmentView> = {}): AttachmentView {
  return {
    id: 'att_1',
    policy_id: 'pol_1',
    policy_name: 'Graph reader',
    principal_id: ada.id,
    principal: ada,
    scope: 'abi:acme:-',
    created_at: '2026-10-03T10:00:00Z',
    ...over,
  };
}

/** An API whose every call is a vitest mock the test can override; unused calls fail loudly. */
export function fakeApi(over: Partial<Record<keyof IamAdminApi, unknown>> = {}): IamAdminApi {
  return new Proxy(over, {
    get: (target, name: string) =>
      (target as Record<string, unknown>)[name] ??
      (() => Promise.reject(new Error(`unexpected call: ${name}`))),
  }) as unknown as IamAdminApi;
}
