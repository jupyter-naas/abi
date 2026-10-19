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
  document: PolicyDocument;
  created_at: string | null;
  updated_at: string | null;
};

export type Page<T> = { items: T[]; next_after: string | null };

/** The document as the user wrote it: an object (visual editor) or text (YAML or JSON). */
export type PolicySource = { document: PolicyDocument } | { text: string };

export type PolicyCreate = PolicySource & { name: string; description?: string };
export type PolicyUpdate = Partial<PolicySource> & {
  expected_revision: number;
  name?: string;
  description?: string;
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
export type AttachablePolicy = { id: string; name: string; description: string; managed: boolean };

// -- module permission approvals --------------------------------------------------------

export type ManifestStatus = 'pending' | 'approved' | 'rejected' | 'superseded';

export type ManifestView = {
  principal_id: string;
  account_name: string | null;
  sha256: string;
  module_id: string;
  project: string;
  status: ManifestStatus;
  /** What the module asked for (variables unsubstituted). */
  document: PolicyDocument;
  submitted_at: string | null;
  decided_at: string | null;
  decided_by: string | null;
  reason: string;
};

/** Approve as submitted (no `document`) or narrowed: Allow statements may lose
 *  actions and resources, never gain any; Deny statements stay as submitted. */
export type ManifestApprove = { document?: PolicyDocument };
export type ManifestReject = { reason: string };

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
  /** `allow`, `explicit_deny`, `implicit_deny`, `suspended` or `sealed`. */
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
 *  `iam:RejectManifest`, `iam:Explain` and `nexus:ReadSystem` (the audit). Without a scope they
 *  are decided on the platform; with `?scope=abi:<org>:<workspace>` the attachment actions are
 *  decided at that scope (an org admin may attach at their org and not on the platform). */
export type AccessView = { actions: Record<string, boolean> };
