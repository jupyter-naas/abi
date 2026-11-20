/**
 * The names of the access model (ADR `20261120_access_levels_and_groups`, epic #1583) as the
 * web reads them. Two axes: **where** someone works is a workspace group ("<W> workspace", a
 * membership group of W holding "<W> access", the workspace's offer); **what** they may do there
 * is a level, written once as a generic policy held by a level group.
 *
 * The group and policy names are S2's (#1585, `services/iam/levels.py`, `container_defaults.py`)
 * and S3's (#1586): kept here alone, so a change of name there is a change of this file. Pure:
 * no React, no fetch.
 */

/** A level a person holds everywhere they work (Workspace Admin is a Member with "<W> admins"). */
export type Level = 'viewer' | 'member' | 'admin';

/** The generic level policies: one each, written once and owned by the platform (S2). Viewer and
 *  Member access are held by "Viewers" and "Members" at `${my workspaces}`; Workspace admin access
 *  by each "<W> admins" there. */
export const LEVEL_POLICIES: { level: Level; name: string; group: string; summary: string }[] = [
  {
    level: 'viewer',
    name: 'Viewer access',
    group: 'Viewers',
    summary:
      'Read only, in the workspaces they belong to. Features: apps and datasets. No model.',
  },
  {
    level: 'member',
    name: 'Member access',
    group: 'Members',
    summary:
      'Work in the workspaces they belong to: read and write. Features: apps, chat, files, datasets, graph, maps, ontology and search. The workspace’s agents and apps, and the deployment’s member model set.',
  },
  {
    level: 'admin',
    name: 'Workspace admin access',
    group: '<W> admins',
    summary:
      'Administer a workspace: its settings, people, workflows and maps. Every feature, the workspace’s workflows, pipelines and maps, and every model.',
  },
];

/** The level a policy is, by its name; null for any other policy. */
export function levelPolicyOf(policy: { name: string }): (typeof LEVEL_POLICIES)[number] | null {
  return LEVEL_POLICIES.find((p) => p.name === policy.name) ?? null;
}

/** What a level's policy grants, in plain words. */
export function levelSummary(level: Level): string {
  return LEVEL_POLICIES.find((p) => p.level === level)?.summary ?? '';
}

/** The level groups, platform-owned and marked `level_group` (S2). */
export const LEVEL_GROUP_NAMES: readonly string[] = ['Viewers', 'Members'];
/** The platform's "Workspace admins": whoever is in a "<W> admins" or "<O> admins", holding
 *  every model (its members follow those groups). */
export const ALL_WORKSPACE_ADMINS = 'Workspace admins';
/** The platform's "Platform admins": `builtin.platform_admin` (`is_superadmin`). */
export const PLATFORM_ADMINS = 'Platform admins';

/** "<W> workspace": the membership group of W, holding W's offer ("<W> access"). */
export const workspaceGroupName = (workspace: string) => `${workspace} workspace`;
/** "<W> admins": holds "Workspace admin access" at W. */
export const workspaceAdminsGroupName = (workspace: string) => `${workspace} admins`;
/** "<O> admins": holds "<O> access" below the organization, and admin at it. */
export const orgAdminsGroupName = (org: string) => `${org} admins`;
/** "<O> people": the organization's people with no workspace (Viewer access at the org). */
export const orgPeopleGroupName = (org: string) => `${org} people`;

/** A capability group adds one thing to a level, made on demand (S3, `iam/capabilities.py`). */
export type Capability = 'workflow_runners' | 'models_all';

export const CAPABILITY_GROUPS: { capability: Capability; name: string; summary: string; level: 'organization' | 'platform' }[] = [
  {
    capability: 'workflow_runners',
    name: 'Workflow runners',
    summary: 'Lets its Members run the workflows and pipelines their workspaces offer.',
    level: 'organization',
  },
  {
    capability: 'models_all',
    name: 'Models · all',
    summary: 'Lets its Members chat with every model, beyond the member model set.',
    level: 'platform',
  },
];

/** What a group is in the model: a level, an admins group, a workspace's membership group,
 *  an organization's people, a capability group, or one made for a per-person exception. */
export type GroupKind =
  | 'platform-admins'
  | 'level'
  | 'org-admins'
  | 'workspace-admins'
  | 'workspace'
  | 'people'
  | 'capability'
  | 'custom';

export const GROUP_KIND_LABELS: Record<GroupKind, string> = {
  'platform-admins': 'Platform admins',
  level: 'Level',
  'org-admins': 'Org admins',
  'workspace-admins': 'Workspace admins',
  workspace: 'Workspace',
  people: 'Org people',
  capability: 'Capability',
  custom: 'Custom',
};

const ORDER: GroupKind[] = ['platform-admins', 'level', 'org-admins', 'workspace-admins', 'workspace', 'people', 'capability', 'custom'];

export function groupRank(kind: GroupKind): number {
  return ORDER.indexOf(kind);
}

type GroupLike = {
  name: string | null;
  owner_scope?: string | null;
  membership_of?: string | null;
  level_group?: boolean | null;
};

const WORKSPACE_STEP = /\/nexus:workspace\/[^/]+$/;
const ORG_ONLY = /^abi:nexus:organization\/[^/]+$/;

/** A group's kind: its markers first (core #1584), else its name at its owner. */
export function groupKind(group: GroupLike): GroupKind {
  const name = group.name ?? '';
  const owner = group.owner_scope ?? 'abi:';
  if (group.level_group) return 'level';
  if (group.membership_of) return WORKSPACE_STEP.test(group.membership_of) ? 'workspace' : 'people';
  if (CAPABILITY_GROUPS.some((c) => c.name === name)) return 'capability';
  if (owner === 'abi:' && LEVEL_GROUP_NAMES.includes(name)) return 'level';
  if (owner === 'abi:' && name === PLATFORM_ADMINS) return 'platform-admins';
  if (owner === 'abi:' && name === ALL_WORKSPACE_ADMINS) return 'workspace-admins';
  if (WORKSPACE_STEP.test(owner)) {
    if (name.endsWith(' workspace')) return 'workspace';
    if (name.endsWith(' admins')) return 'workspace-admins';
  }
  if (ORG_ONLY.test(owner)) {
    if (name.endsWith(' admins')) return 'org-admins';
    if (name.endsWith(' people')) return 'people';
  }
  return 'custom';
}
