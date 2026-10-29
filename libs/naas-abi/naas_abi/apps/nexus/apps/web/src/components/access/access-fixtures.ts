/** Fixtures for the Roles & permissions tests. */
import type { IamAdminApi } from '@/lib/iam-admin/api';
import type {
  AttachmentView,
  CatalogsView,
  PolicyView,
  PrincipalView,
  PublishedType,
  PublishersView,
  ResourcePage,
} from '@/lib/iam-admin/types';
import type { AccessDirectory, ScopeMember } from './access-directory';
import { organizationAccessScope, workspaceAccessScope } from './access-scope';

/** The containers of the organization acme and of its workspace ws-1, as IAM names them. */
export const ORG = 'abi:nexus:organization/acme';
export const WS = `${ORG}/nexus:workspace/ws-1`;

export const orgScope = organizationAccessScope('acme');
export const wsScope = workspaceAccessScope('acme', 'ws-1', 'Workspace ws-1');

export function member(over: Partial<ScopeMember> = {}): ScopeMember {
  return { userId: 'usr_bob', name: 'Bob', email: 'bob@example.com', role: 'member', inherited: false, ...over };
}

/** A directory that answers ``members`` at every scope. */
export function fakeDirectory(members: ScopeMember[] = []): AccessDirectory {
  return { members: () => Promise.resolve(members) };
}

type ActionRow = [action: string, resources: string[]];

/** A type a publisher offers, with the actions the caller may grant and on what. */
export function publishedType(service: string, type: string, actions: ActionRow[], over: Partial<PublishedType> = {}): PublishedType {
  return {
    service,
    type,
    description: '',
    id: 'opaque',
    placement: 'placed',
    container: false,
    listed: true,
    module: null,
    actions: actions.map(([action, resources]) => ({
      action,
      name: action.split(':')[1] ?? action,
      level: 'read',
      description: '',
      resources,
      excluded: [],
    })),
    ...over,
  };
}

/** What a workspace admin of ws-1 may grant there, by publisher: the engine's graphs,
 *  naas_abi's organizations, workspaces and features, and the agents of two modules. */
export const adminPublishers: PublishersView = {
  scope: WS,
  publishers: [
    {
      id: 'engine',
      kind: 'engine',
      types: [
        publishedType(
          'triple_store',
          'graph',
          [
            ['triple_store:ListGraphs', ['${scope}/triple_store:graph/*']],
            ['triple_store:Query', ['${scope}/triple_store:graph/*']],
          ],
          { description: 'A named graph.' },
        ),
      ],
    },
    {
      id: 'naas_abi',
      kind: 'naas_abi',
      types: [
        publishedType('nexus', 'organization', [['nexus:GetOrganization', ['${scope}']]], { container: true, placement: 'platform' }),
        publishedType('nexus', 'workspace', [['nexus:GetWorkspace', ['${scope}']]], { container: true, placement: 'platform' }),
        publishedType('nexus', 'feature', [['nexus:UseFeature', ['${scope}/nexus:feature/chat', '${scope}/nexus:feature/files']]]),
      ],
    },
    {
      id: 'acme.market',
      kind: 'module',
      types: [publishedType('module', 'agent', [['module:UseAgent', ['${scope}/module:agent/acme.market/*']]], { module: 'acme.market' })],
    },
    {
      id: 'acme.people',
      kind: 'module',
      types: [publishedType('module', 'agent', [['module:UseAgent', ['${scope}/module:agent/acme.people/*']]], { module: 'acme.people' })],
    },
  ],
};

/** A listing page of ``items`` (`[id, label]`), named in ``container``. */
export function resourcePage(service: string, type: string, items: [string, string][], over: Partial<ResourcePage> = {}): ResourcePage {
  return {
    scope: WS,
    service,
    type,
    items: items.map(([id, label]) => ({ name: `${WS}/${service}:${type}/${id}`, id, label, description: '' })),
    next_cursor: null,
    listed: true,
    ...over,
  };
}

export const catalogsView: CatalogsView = {
  variables: ['scope', 'principal.id', 'user.id'],
  catalogs: [
    {
      service: 'triple_store',
      version: 1,
      resource_types: [
        { name: 'graph', id: 'opaque', placement: 'placed', container: false, id_prefix: false, personal: false, description: 'A named graph.' },
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
        { name: 'policy', id: 'opaque', placement: 'platform', container: false, id_prefix: false, personal: false, description: 'A policy.' },
        { name: 'key', id: 'path', placement: 'platform', container: false, id_prefix: false, personal: true, description: 'A key.' },
      ],
      actions: [
        { name: 'GetPolicy', qualified: 'iam:GetPolicy', level: 'read', resource_types: ['policy'], creates: false, description: 'Read a policy.' },
        { name: 'ListKeys', qualified: 'iam:ListKeys', level: 'list', resource_types: ['key'], creates: false, description: 'List keys.' },
      ],
    },
    {
      service: 'nexus',
      version: 1,
      resource_types: [
        { name: 'organization', id: 'opaque', placement: 'platform', container: true, id_prefix: false, personal: false, description: 'An organization.' },
        { name: 'workspace', id: 'opaque', placement: 'platform', container: true, id_prefix: false, personal: false, description: 'A workspace.' },
      ],
      actions: [
        { name: 'CreateWorkspace', qualified: 'nexus:CreateWorkspace', level: 'write', resource_types: ['workspace'], creates: true, description: 'Create a workspace.' },
      ],
    },
  ],
};

/** ``catalogsView`` as publishers: what someone who may grant all of it at the scope is offered
 *  (each action on `${scope}/<service>:<type>/*`; naas_abi publishes `nexus`, the engine the rest). */
export function publishersOf(view: CatalogsView, scope: string = WS): PublishersView {
  return {
    scope,
    publishers: (['engine', 'naas_abi'] as const).map((id) => ({
      id,
      kind: id,
      types: view.catalogs
        .filter((c) => (c.service === 'nexus') === (id === 'naas_abi'))
        .flatMap((catalog) =>
          catalog.resource_types.map((type) => ({
            service: catalog.service,
            type: type.name,
            description: type.description,
            id: type.id,
            placement: type.placement,
            container: type.container,
            listed: false,
            module: null,
            actions: catalog.actions
              .filter((a) => a.resource_types.includes(type.name))
              .map((a) => ({
                action: a.qualified,
                name: a.name,
                level: a.level,
                description: a.description,
                resources: [`\${scope}/${catalog.service}:${type.name}/*`],
                excluded: [],
              })),
          })),
        )
        .filter((t) => t.actions.length > 0),
    })),
  };
}

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
        resources: [`${WS}/triple_store:graph/*`],
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
    scope: ORG,
    created_at: '2026-10-03T10:00:00Z',
    ...over,
  };
}

/** An API whose every call is a vitest mock the test can override; unused calls fail loudly. */
export function fakeApi(over: Partial<Record<keyof IamAdminApi, unknown>> = {}): IamAdminApi {
  return new Proxy(over, {
    get: (target, name: string) =>
      (target as Record<string, unknown>)[name] ??
      // Not a promise: an async helper may return it.
      (name === 'then' ? undefined : () => Promise.reject(new Error(`unexpected call: ${name}`))),
  }) as unknown as IamAdminApi;
}
