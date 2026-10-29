/**
 * Client of the IAM admin API. Each function is one route; a refusal is an
 * `IamAdminError` carrying IAM's words (and, for a policy that does not
 * validate, every error it listed).
 */
import { authFetch } from '@/stores/auth';
import type {
  AccessView,
  AttachablePolicy,
  AttachmentCreate,
  AttachmentView,
  AuditEntry,
  CatalogsView,
  CreatedKey,
  GrantableView,
  GroupView,
  KeyCreate,
  KeyView,
  ManifestApprove,
  ManifestReject,
  ManifestStatus,
  ManifestView,
  Page,
  PolicyCreate,
  PolicySource,
  PolicyUpdate,
  PolicyValidation,
  PolicyView,
  PrincipalKind,
  PrincipalView,
  PublishersView,
  ResourcePage,
  ResourceQuery,
  ServiceAccountView,
  Simulation,
  SimulationRequest,
} from './types';

export const IAM_ADMIN_API = '/api/iam/admin';

export type Fetcher = (url: string, options?: RequestInit) => Promise<Response>;

export class IamAdminError extends Error {
  readonly status: number;
  /** IAM's validation errors, one per failure, when a policy was refused. */
  readonly errors: string[];

  constructor(message: string, status: number, errors: string[] = []) {
    super(message);
    this.name = 'IamAdminError';
    this.status = status;
    this.errors = errors;
  }
}

/** The words for a refusal: IAM's own `detail`, else a sentence for the status. */
async function failure(response: Response, fallback: string): Promise<IamAdminError> {
  let detail = '';
  let errors: string[] = [];
  try {
    const body = await response.json();
    const raw = body?.detail;
    if (typeof raw === 'string') detail = raw;
    else if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
      if (Array.isArray(raw.errors)) errors = raw.errors.map(String);
      if (typeof raw.message === 'string') detail = raw.message;
      else if (typeof raw.reason === 'string') detail = raw.reason;
    } else if (Array.isArray(raw) && raw[0]?.msg) detail = String(raw[0].msg);
  } catch {
    // no JSON body
  }
  if (!detail && errors.length) detail = errors.join('; ');
  if (!detail) {
    if (response.status === 403) detail = 'You do not have permission to do this.';
    else if (response.status === 404) detail = 'Not found.';
    else if (response.status === 503) detail = 'IAM is not available on this server.';
    else detail = fallback;
  }
  return new IamAdminError(detail, response.status, errors);
}

const JSON_HEADERS = { 'Content-Type': 'application/json' };

function path(...parts: string[]): string {
  return [IAM_ADMIN_API, ...parts.map(encodeURIComponent)].join('/');
}

function query(params: Record<string, string | number | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== '') search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : '';
}

async function read<T>(fetcher: Fetcher, url: string, fallback: string): Promise<T> {
  const response = await fetcher(url);
  if (!response.ok) throw await failure(response, fallback);
  return (await response.json()) as T;
}

async function send<T>(
  fetcher: Fetcher,
  url: string,
  method: 'POST' | 'PUT' | 'DELETE',
  body: unknown,
  fallback: string,
): Promise<T> {
  const response = await fetcher(url, {
    method,
    ...(body === undefined ? {} : { headers: JSON_HEADERS, body: JSON.stringify(body) }),
  });
  if (!response.ok) throw await failure(response, fallback);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** Every call of the admin API, bound to one fetcher (tests pass a fake). */
export function createIamAdminApi(fetcher: Fetcher = authFetch) {
  return {
    /** What the caller may do on the platform, or on the attachments of `scope`
     *  (an organization's or a workspace's container) when one is given. */
    access: (scope?: string) =>
      read<AccessView>(fetcher, path('access') + query({ scope }), 'Could not read your access.'),
    /** The actions the caller may grant at `scope` (within `parent`, for a sub-policy of it). */
    catalogs: (scope?: string, parent?: string | null) =>
      read<CatalogsView>(fetcher, path('catalogs') + query({ scope, parent }), 'Could not load the action catalogs.'),
    /** What the caller may grant at `scope` (`abi:` for the platform), within `parent`. */
    grantable: (scope: string, parent?: string | null) =>
      read<GrantableView>(fetcher, path('grantable') + query({ scope, parent }), 'Could not read what you may grant.'),
    /** The same by publisher and resource type: the policy builder's groups. */
    publishers: (scope: string, parent?: string | null) =>
      read<PublishersView>(
        fetcher,
        path('publishers') + query({ scope, parent }),
        'Could not read what you may grant.',
      ),
    /** The existing resources of a type the caller may list at the scope, a page at a time. */
    resources: (input: ResourceQuery) =>
      read<ResourcePage>(
        fetcher,
        path('resources') +
          query({
            scope: input.scope,
            service: input.service,
            type: input.type,
            q: input.q,
            cursor: input.cursor,
            module: input.module,
            limit: input.limit,
          }),
        'Could not list the resources.',
      ),

    // policies
    /** Every policy the caller may list; with `scope`, that level's own and those above it the
     *  caller may attach there. */
    listPolicies: (after?: string, scope?: string) =>
      read<Page<PolicyView>>(fetcher, path('policies') + query({ after, scope }), 'Could not load the policies.'),
    getPolicy: (id: string) => read<PolicyView>(fetcher, path('policies', id), 'Could not load the policy.'),
    /** With `scope` (an org or a workspace), checked as a policy that level owns. */
    validatePolicy: (source: PolicySource, scope?: string) =>
      send<PolicyValidation>(
        fetcher,
        path('policies', 'validate') + query({ scope }),
        'POST',
        source,
        'Could not validate the policy.',
      ),
    createPolicy: (input: PolicyCreate) =>
      send<PolicyView>(fetcher, path('policies'), 'POST', input, 'Could not create the policy.'),
    updatePolicy: (id: string, input: PolicyUpdate) =>
      send<PolicyView>(fetcher, path('policies', id), 'PUT', input, 'Could not save the policy.'),
    deletePolicy: (id: string) =>
      send<void>(fetcher, path('policies', id), 'DELETE', undefined, 'Could not delete the policy.'),

    // attachments (any scope the caller may list: the platform's or an org's)
    listAttachments: (filter: { principal_id?: string; policy_id?: string; scope?: string } = {}) =>
      read<{ items: AttachmentView[] }>(
        fetcher,
        path('attachments') + query(filter),
        'Could not load the attachments.',
      ),
    attachable: (scope: string, principalId?: string) =>
      read<{ items: AttachablePolicy[] }>(
        fetcher,
        path('attachable-policies') + query({ scope, principal_id: principalId }),
        'Could not load the policies you may attach.',
      ),
    attach: (input: AttachmentCreate) =>
      send<AttachmentView>(fetcher, path('attachments'), 'POST', input, 'Could not attach the policy.'),
    detach: (input: AttachmentCreate) =>
      send<void>(
        fetcher,
        path('attachments') + query({ policy_id: input.policy_id, principal_id: input.principal_id, scope: input.scope }),
        'DELETE',
        undefined,
        'Could not detach the policy.',
      ),

    // principals
    listPrincipals: (kind?: PrincipalKind, after?: string) =>
      read<Page<PrincipalView>>(
        fetcher,
        path('principals') + query({ kind, after }),
        'Could not load the principals.',
      ),
    getPrincipal: (id: string) =>
      read<PrincipalView>(fetcher, path('principals', id), 'Could not load the principal.'),
    suspend: (id: string) =>
      send<PrincipalView>(fetcher, path('principals', id, 'suspend'), 'POST', undefined, 'Could not suspend.'),
    resume: (id: string) =>
      send<PrincipalView>(fetcher, path('principals', id, 'resume'), 'POST', undefined, 'Could not resume.'),

    // groups
    /** Every group the caller may list; with `scope`, that level's own (and, at a workspace,
     *  its org's the caller attaches to there). */
    listGroups: (scope?: string) =>
      read<{ items: PrincipalView[] }>(fetcher, path('groups') + query({ scope }), 'Could not load the groups.'),
    getGroup: (id: string) => read<GroupView>(fetcher, path('groups', id), 'Could not load the group.'),
    /** `scope`: the owner (an organization's or a workspace's container); none: the platform. */
    createGroup: (input: { name: string; org?: string | null; scope?: string | null }) =>
      send<PrincipalView>(fetcher, path('groups'), 'POST', input, 'Could not create the group.'),
    deleteGroup: (id: string) =>
      send<void>(fetcher, path('groups', id), 'DELETE', undefined, 'Could not delete the group.'),
    addMember: (groupId: string, memberId: string) =>
      send<GroupView>(fetcher, path('groups', groupId, 'members', memberId), 'PUT', undefined, 'Could not add the member.'),
    removeMember: (groupId: string, memberId: string) =>
      send<GroupView>(
        fetcher,
        path('groups', groupId, 'members', memberId),
        'DELETE',
        undefined,
        'Could not remove the member.',
      ),
    mapIdpGroup: (groupId: string, mapping: { provider: string; claim_value: string }) =>
      send<GroupView>(fetcher, path('groups', groupId, 'idp-mappings'), 'PUT', mapping, 'Could not map the IdP group.'),
    unmapIdpGroup: (groupId: string, mapping: { provider: string; claim_value: string }) =>
      send<GroupView>(
        fetcher,
        path('groups', groupId, 'idp-mappings') + query(mapping),
        'DELETE',
        undefined,
        'Could not remove the mapping.',
      ),

    // service accounts and their keys
    listServiceAccounts: () =>
      read<{ items: ServiceAccountView[] }>(
        fetcher,
        path('service-accounts'),
        'Could not load the service accounts.',
      ),
    createServiceAccount: (name: string) =>
      send<ServiceAccountView>(
        fetcher,
        path('service-accounts'),
        'POST',
        { name },
        'Could not create the service account.',
      ),
    deleteServiceAccount: (id: string) =>
      send<void>(
        fetcher,
        path('service-accounts', id),
        'DELETE',
        undefined,
        'Could not delete the service account.',
      ),
    listKeys: (accountId: string) =>
      read<{ items: KeyView[] }>(fetcher, path('service-accounts', accountId, 'keys'), 'Could not load the keys.'),
    createKey: (accountId: string, input: KeyCreate = {}) =>
      send<CreatedKey>(fetcher, path('service-accounts', accountId, 'keys'), 'POST', input, 'Could not create the key.'),
    revokeKey: (accountId: string, keyId: string) =>
      send<KeyView>(
        fetcher,
        path('service-accounts', accountId, 'keys', keyId),
        'DELETE',
        undefined,
        'Could not revoke the key.',
      ),
    rotateKey: (accountId: string, keyId: string) =>
      send<CreatedKey>(
        fetcher,
        path('service-accounts', accountId, 'keys', keyId, 'rotate'),
        'POST',
        undefined,
        'Could not rotate the key.',
      ),

    // module permission approvals
    listManifests: (status?: ManifestStatus) =>
      read<{ items: ManifestView[] }>(
        fetcher,
        path('manifests') + query({ status }),
        'Could not load the permission manifests.',
      ),
    approveManifest: (principalId: string, sha256: string, input: ManifestApprove = {}) =>
      send<ManifestView>(
        fetcher,
        path('manifests', principalId, sha256, 'approve'),
        'POST',
        input,
        'Could not approve the manifest.',
      ),
    rejectManifest: (principalId: string, sha256: string, input: ManifestReject) =>
      send<ManifestView>(
        fetcher,
        path('manifests', principalId, sha256, 'reject'),
        'POST',
        input,
        'Could not reject the manifest.',
      ),

    // the simulator and the audit
    simulate: (input: SimulationRequest) =>
      send<Simulation>(fetcher, path('simulate'), 'POST', input, 'Could not run the simulation.'),
    audit: (filter: { operation?: string; resource_id?: string; limit?: number } = {}) =>
      read<{ items: AuditEntry[] }>(fetcher, path('audit') + query(filter), 'Could not load the audit log.'),
  };
}

export type IamAdminApi = ReturnType<typeof createIamAdminApi>;
