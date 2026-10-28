/**
 * The IAM admin API (`/api/iam/admin/*`, services/iam_admin in the Nexus API).
 *
 * Every route is a call to the engine's IAM made for the signed-in user, so IAM's
 * own `iam:*` actions decide what each page may read and change: a 403 means the
 * user lacks the action, a 404 that they cannot see the resource. The routes take
 * a session only.
 */

export type Level = 'list' | 'read' | 'write' | 'admin';
export type Effect = 'Allow' | 'Deny';

// -- catalogs (autocomplete of the policy editor) -------------------------------------

export type CatalogAction = {
  name: string;
  /** `<service>:<Action>`, what a policy names. */
  qualified: string;
  level: Level;
  resource_types: string[];
  creates: boolean;
  description: string;
};

export type CatalogResourceType = {
  name: string;
  /** How the id of a resource is written: one opaque value, a `/` path, or `-`. */
  id: 'opaque' | 'path' | 'singleton';
  /** `placed`: named in an org and workspace; `platform`: `abi:-:-:...`. */
  placement: 'placed' | 'platform';
  container: boolean;
  personal: boolean;
  description: string;
};

export type Catalog = {
  service: string;
  version: number;
  actions: CatalogAction[];
  resource_types: CatalogResourceType[];
};

export type CatalogsView = {
  catalogs: Catalog[];
  /** The `${...}` variables a stored policy may use in its resources. */
  variables: string[];
};

/** One agent, app, workflow or pipeline of a module: a module scope (`GET /api/modules/scopes`). */
export type ModuleScopeItem = {
  name: string;
  display_name: string;
  description: string;
  icon: string | null;
  /** The pattern a policy names: `${scope}:module:<type>/<module>/<name>`. */
  resource: string;
  actions: string[];
};

export type ModuleScopesEntry = {
  module: string;
  agents: ModuleScopeItem[];
  apps: ModuleScopeItem[];
  workflows: ModuleScopeItem[];
  pipelines: ModuleScopeItem[];
  /** The catalog the module declares (its own service), if any. */
  declared: {
    service: string;
    version: number;
    resource_types: { name: string; description: string; resource: string }[];
    actions: { action: string; level: string; resource_types: string[]; description: string }[];
  } | null;
};

export type ModuleScopesView = { modules: ModuleScopesEntry[] };

// -- sets: the module scopes and features usable in an organization or a workspace ------

/**
 * What an organization or a workspace may use. `null`: nothing recorded, so everything (for a
 * workspace, whatever its organization has); `[]`: nothing. Module items are `<module>` (the
 * whole module), `<type>/<module>/<name>` (`agent`, `app`, `workflow`, `pipeline`; `*` for every
 * item of that type) or `<service>:<Action>` (an action the module declares). Features are
 * Nexus feature keys (`chat`, `files`, ...).
 */
export type SetParts = { modules: string[] | null; features: string[] | null };

export type WorkspaceSetView = {
  id: string;
  name: string;
  /** What is recorded. */
  set: SetParts;
  /** What it has: the recorded set within its organization's. */
  effective: SetParts;
  /** Whether the caller may change it (`PUT`). */
  editable: boolean;
};

export type OrganizationSetView = WorkspaceSetView & { workspaces: WorkspaceSetView[] };

/** `GET /api/iam/admin/sets[?organization_id=]`: the rows (modules, features) and the columns. */
export type SetsView = {
  modules: ModuleScopesEntry[];
  /** The deployment's enabled features, in order. */
  features: string[];
  organizations: OrganizationSetView[];
};

// -- policies -------------------------------------------------------------------------

export type PolicyStatement = {
  sid?: string | null;
  effect: Effect;
  actions: string[];
  resources: string[];
};

export type PolicyDocument = {
  version: string;
  statements: PolicyStatement[];
};

export type PolicyView = {
  id: string;
  name: string;
  description: string;
  /** Built-in and module policies: IAM writes them, they are read-only here. */
  managed: boolean;
  revision: number;
  /** Who owns it: `abi:-:-` (the platform), `abi:<org>:-` or `abi:<org>:<ws>`. */
  owner_scope?: string;
  /** The policy it is a sub-policy of: it never grants more than that one, read live. */
  parent_id?: string | null;
  /** Read one by one (`GET /policies/{id}`): its parent, named when the caller can see it. */
  parent?: PolicyRef | null;
  /** Read one by one: the sub-policies below it the caller may list. */
  sub_policies?: PolicyRef[];
  document: PolicyDocument;
  created_at: string | null;
  updated_at: string | null;
};

/** A policy named by its id; its name and owner are null when they cannot be read. */
export type PolicyRef = {
  id: string;
  name: string | null;
  owner_scope: string | null;
  managed: boolean | null;
};

export type Page<T> = { items: T[]; next_after: string | null };

/** The document as the user wrote it: an object (visual editor) or text (YAML or JSON). */
export type PolicySource = { document: PolicyDocument } | { text: string };

/** `scope`: the owner, `abi:<org>:-` or `abi:<org>:<ws>`; none: the platform. */
export type PolicyCreate = PolicySource & {
  name: string;
  description?: string;
  scope?: string | null;
  /** A sub-policy of this one. */
  parent?: string;
};
export type PolicyUpdate = Partial<PolicySource> & {
  expected_revision: number;
  name?: string;
  description?: string;
  /** Absent keeps the parent; null removes it; an id sets it. */
  parent?: string | null;
};

/** What IAM says of a document, without saving it. `errors` lists every failure. */
export type PolicyValidation = {
  valid: boolean;
  errors: string[];
  /** The document as IAM reads it (normalized), when it is valid. */
  document: PolicyDocument | null;
};

// -- principals, groups, service accounts ----------------------------------------------

export type PrincipalKind = 'user' | 'group' | 'service_account';
export type PrincipalStatus = 'active' | 'suspended' | 'deleted';

export type PrincipalView = {
  id: string;
  kind: PrincipalKind;
  status: PrincipalStatus;
  /** Service accounts: their unique name. Groups: their display name. */
  name: string | null;
  email: string | null;
  display_name: string | null;
  provider: string | null;
  org: string | null;
  owner_id: string | null;
  /** Groups: who owns them, `abi:-:-` (the platform), `abi:<org>:-` or `abi:<org>:<ws>`. */
  owner_scope?: string;
  created_at: string | null;
};

export type IdpMapping = { provider: string; claim_value: string };

export type GroupView = PrincipalView & {
  members: PrincipalView[];
  idp_mappings: IdpMapping[];
};

export type KeyStatus = 'active' | 'revoked' | 'expired';

/** A key as IAM keeps it: never its secret. */
export type KeyView = {
  id: string;
  principal_id: string;
  kind: 'service' | 'personal' | 'grant';
  description: string;
  /** `abi_sk_<id>`: enough to tell keys apart. */
  prefix: string;
  created_at: string | null;
  expires_at: string | null;
  last_used_at: string | null;
  revoked_at: string | null;
  status: KeyStatus;
};

/** A new key. `value` is the key itself: shown once, never stored or returned again. */
export type CreatedKey = { key: KeyView; value: string };

export type ServiceAccountView = PrincipalView & {
  /** `module` for `module/<project>/<id>` accounts, `builtin` for engine, api, idp. */
  account_kind: 'module' | 'builtin' | 'custom';
  active_keys: number;
};

export type KeyCreate = { description?: string; expires_in_days?: number | null };

// -- attachments ----------------------------------------------------------------------

export type AttachmentView = {
  id: string;
  policy_id: string;
  policy_name: string | null;
  principal_id: string;
  principal: PrincipalView | null;
  /** `abi:<org>:<workspace>` (`-` for the org itself), or null: everywhere. */
  scope: string | null;
  created_at: string | null;
};

export type AttachmentCreate = {
  policy_id: string;
  principal_id: string;
  scope?: string | null;
};

/** A policy the caller may attach at a scope (IAM's rules: only a policy whose
 *  every Allow starts with `${scope}:` goes at a scope). */
export type AttachablePolicy = {
  id: string;
  name: string;
  description: string;
  managed: boolean;
  owner_scope?: string;
};

// -- module permission approvals --------------------------------------------------------

export type ManifestStatus = 'pending' | 'approved' | 'rejected' | 'superseded';

/** A module's own catalog, as its manifest declares it. */
export type DeclaredCatalog = {
  service: string;
  version: number;
  resource_types: { name: string; id?: string; description?: string }[];
  actions: { name: string; level: string; resource_types: string[]; description?: string }[];
};

export type ManifestView = {
  principal_id: string;
  account_name: string | null;
  sha256: string;
  module_id: string;
  project: string;
  status: ManifestStatus;
  /** What the module asked for (variables unsubstituted). */
  document: PolicyDocument;
  /** The actions the module declares under its own service, approved as submitted. */
  catalog: DeclaredCatalog | null;
  submitted_at: string | null;
  decided_at: string | null;
  decided_by: string | null;
  reason: string;
};

/** Approve as submitted (no `document`) or narrowed: Allow statements may lose
 *  actions and resources, never gain any; Deny statements stay as submitted. */
export type ManifestApprove = { document?: PolicyDocument };
export type ManifestReject = { reason: string };

// -- what the caller may grant ------------------------------------------------------------

/** One action the caller holds at a scope, and on which resources (`${scope}:...`);
 *  `excluded` are Deny patterns that take back part of them. */
export type GrantableAction = { action: string; resources: string[]; excluded: string[] };

/** `GET /api/iam/admin/grantable?scope=`: per catalog (a kernel service, `nexus`, `module` or a
 *  module's own service), what the caller may grant there, within the scope's sets. */
export type GrantableView = {
  scope: string;
  catalogs: { service: string; actions: GrantableAction[] }[];
};

// -- the access simulator ---------------------------------------------------------------

export type SimulationRequest = { principal_id: string; action: string; resource: string };

export type DecidingStatement = {
  side: 'actor' | 'user' | 'token';
  principal_id: string;
  effect: Effect;
  policy_id: string | null;
  policy_name: string | null;
  statement_index: number;
  sid: string | null;
  attachment_id: string | null;
  scope: string | null;
  via_group: string | null;
  /** The statement as written, when the caller may read its policy. */
  statement: PolicyStatement | null;
};

export type Simulation = {
  allowed: boolean;
  /** `allow`, `explicit_deny`, `implicit_deny`, `suspended`, `sealed` or `outside_set`. */
  reason: string;
  action: string;
  resource: string;
  principal: PrincipalView;
  statement: DecidingStatement | null;
};

// -- audit ------------------------------------------------------------------------------

export type AuditPhase = 'requested' | 'succeeded' | 'failed';

export type AuditEntry = {
  at: string;
  actor_id: string;
  actor: string;
  /** `create_policy`, `attach_policy`, `approve_manifest`, `create_key`, ... */
  operation: string;
  resource_id: string;
  /** What changed in words (a policy name, a scope), never a secret. */
  detail: string;
  phase: AuditPhase;
  error: string;
};

// -- what the caller may do ---------------------------------------------------------------

/** The actions the caller may perform, to show only the pages and buttons that will answer:
 *  `iam:ListPolicies`, `iam:CreatePolicy`, `iam:UpdatePolicy`, `iam:DeletePolicy`,
 *  `iam:ListAttachments`, `iam:AttachPolicy`, `iam:DetachPolicy`, `iam:ListGroups`,
 *  `iam:CreateGroup`, `iam:DeleteGroup`, `iam:AddGroupMember`, `iam:RemoveGroupMember`,
 *  `iam:MapIdpGroup`, `iam:UnmapIdpGroup`, `iam:ListPrincipals`, `iam:CreateServiceAccount`,
 *  `iam:DeletePrincipal`, `iam:SuspendPrincipal`, `iam:ResumePrincipal`, `iam:ListKeys`,
 *  `iam:CreateKey`, `iam:RevokeKey`, `iam:ListManifests`, `iam:ApproveManifest`,
 *  `iam:RejectManifest`, `iam:Explain`, `iam:GetSet`, `iam:PutSet`, `nexus:ReadSystem` (the
 *  audit), `nexus:GetRoleFeatures` and `nexus:UpdateRoleFeatures`. Without a scope they are
 *  decided on the platform; with `?scope=abi:<org>:<workspace>` (`-` for the org itself) the
 *  attachment actions at that scope and the policy and group actions on that level's own, so
 *  an org admin may attach at their org and not on the platform. At a scope, what is
 *  administered at platform level only (principals and service accounts, keys, manifests,
 *  the simulator, IdP mappings, the audit) is false; the role feature actions are an
 *  organization's, true only at an org scope for whoever edits its roles' feature defaults. */
export type AccessView = { actions: Record<string, boolean> };
