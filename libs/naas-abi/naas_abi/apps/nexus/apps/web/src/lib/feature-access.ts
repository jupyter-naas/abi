export type FeatureKey =
  | 'maps'
  | 'chat'
  | 'files'
  | 'agents'
  | 'skills'
  | 'apps'
  | 'marketplace'
  | 'search'
  | 'ontology'
  | 'graph'
  | 'datasets'
  | 'code'
  | 'slides'
  | 'settings'
  | 'settings.workspace'
  | 'settings.organization';

export type WorkspaceFeatureFlags = Partial<Record<FeatureKey, boolean>>;

export const FEATURE_KEYS: FeatureKey[] = [
  'maps',
  'chat',
  'files',
  'agents',
  'skills',
  'apps',
  'marketplace',
  'search',
  'ontology',
  'graph',
  'datasets',
  'code',
  'slides',
  'settings',
  'settings.workspace',
  'settings.organization',
];

// Features that are OFF by default for every role and only turn on when a
// deployment enables them in nexus_config.feature_flags. Kept out of the
// owner/admin "everything" baseline so the default state is disabled.
const OPT_IN_FEATURES: FeatureKey[] = ['code'];

const DEFAULT_ROLE_BASELINE: Record<string, FeatureKey[]> = {
  owner: FEATURE_KEYS.filter((f) => !OPT_IN_FEATURES.includes(f)),
  admin: FEATURE_KEYS.filter((f) => !OPT_IN_FEATURES.includes(f)),
  member: ['maps', 'chat', 'files', 'datasets', 'skills', 'slides'],
  viewer: ['maps', 'chat', 'files', 'datasets', 'skills', 'slides'],
};

const FEATURE_FALLBACK_ROUTE: Record<FeatureKey, string> = {
  maps: '/maps/presence',
  chat: '/chat',
  files: '/files',
  agents: '/lab',
  skills: '/chat',
  apps: '/apps',
  marketplace: '/marketplace',
  search: '/search',
  ontology: '/ontology',
  graph: '/graph',
  datasets: '/datasets',
  code: '/code',
  slides: '/slides',
  settings: '/settings',
  'settings.workspace': '/settings',
  'settings.organization': '/organization',
};

export function mergeFeatureFlags(role?: string, workspaceFlags?: WorkspaceFeatureFlags): Record<FeatureKey, boolean> {
  const baseline = new Set(DEFAULT_ROLE_BASELINE[role || ''] || []);
  const resolved = Object.fromEntries(
    FEATURE_KEYS.map((feature) => [feature, baseline.has(feature)])
  ) as Record<FeatureKey, boolean>;

  if (!workspaceFlags) {
    return resolved;
  }

  for (const feature of FEATURE_KEYS) {
    if (typeof workspaceFlags[feature] === 'boolean') {
      resolved[feature] = Boolean(workspaceFlags[feature]);
    }
  }
  return resolved;
}

export function isFeatureEnabled(params: {
  feature: FeatureKey;
  role?: string;
  workspaceFlags?: WorkspaceFeatureFlags;
}): boolean {
  if (!FEATURE_KEYS.includes(params.feature)) {
    return false;
  }
  const resolved = mergeFeatureFlags(params.role, params.workspaceFlags);
  return resolved[params.feature] === true;
}

function pathWithoutQuery(pathname: string): string {
  return pathname.split(/[?#]/)[0];
}

export function getFeatureForWorkspacePath(pathname: string): FeatureKey | null {
  const parts = pathWithoutQuery(pathname).split('/').filter(Boolean);
  const workspaceIndex = parts.indexOf('workspace');
  if (workspaceIndex < 0 || parts.length <= workspaceIndex + 2) {
    return null;
  }

  const firstSegment = parts[workspaceIndex + 2];
  if (firstSegment === 'maps') {
    return 'maps';
  }
  if (firstSegment === 'chat') {
    return 'chat';
  }
  if (firstSegment === 'files') {
    return 'files';
  }
  if (firstSegment === 'search') {
    return 'search';
  }
  if (firstSegment === 'ontology') {
    return 'ontology';
  }
  if (firstSegment === 'graph') {
    return 'graph';
  }
  if (firstSegment === 'datasets') {
    return 'datasets';
  }
  if (firstSegment === 'code' || firstSegment === 'ide') {
    return 'code';
  }
  if (firstSegment === 'slides') {
    return 'slides';
  }
  if (firstSegment === 'apps') {
    return 'apps';
  }
  if (firstSegment === 'marketplace') {
    return 'marketplace';
  }
  if (
    firstSegment === 'lab' ||
    (firstSegment === 'settings' && parts[workspaceIndex + 3] === 'agents')
  ) {
    return 'agents';
  }
  if (firstSegment === 'settings' && parts[workspaceIndex + 3] === 'skills') {
    return 'skills';
  }
  if (firstSegment === 'settings') {
    return 'settings.workspace';
  }
  if (firstSegment === 'organization') {
    return 'settings.organization';
  }
  if (firstSegment === 'help') {
    return 'settings';
  }

  return null;
}

/** Surfaces that need the agent catalog (chat, lab, agent settings). Apps does not. */
export function pathNeedsAgentCatalog(pathname: string | null | undefined): boolean {
  const feature = getFeatureForWorkspacePath(pathname || '');
  return feature === 'chat' || feature === 'agents';
}

/** Graph export toasts are only meaningful on graph routes. */
export function pathNeedsGraphExport(pathname: string | null | undefined): boolean {
  return getFeatureForWorkspacePath(pathname || '') === 'graph';
}

export function isWorkspacePathAllowed(params: {
  pathname: string;
  role?: string;
  workspaceFlags?: WorkspaceFeatureFlags;
}): boolean {
  const feature = getFeatureForWorkspacePath(params.pathname);
  if (!feature) {
    return true;
  }
  return isFeatureEnabled({
    feature,
    role: params.role,
    workspaceFlags: params.workspaceFlags,
  });
}

export function getFirstAllowedWorkspacePath(params: {
  workspaceId: string;
  role?: string;
  workspaceFlags?: WorkspaceFeatureFlags;
}): string {
  const resolved = mergeFeatureFlags(params.role, params.workspaceFlags);
  const priority: FeatureKey[] = ['chat', 'maps', 'files', 'datasets', 'search', 'ontology', 'graph', 'agents', 'apps', 'marketplace', 'settings.workspace', 'settings.organization', 'settings'];

  for (const feature of priority) {
    if (resolved[feature]) {
      return `/workspace/${params.workspaceId}${FEATURE_FALLBACK_ROUTE[feature]}`;
    }
  }

  return `/workspace/${params.workspaceId}/chat`;
}

/**
 * Destination when switching workspaces from the current URL.
 *
 * Stays on the same product surface (apps stays apps) and drops resource ids
 * (a chat thread, an opened app) that belong to the previous workspace.
 * If the target workspace does not enable that surface, falls back to its
 * first allowed route.
 */
export function getWorkspaceSwitchPath(params: {
  pathname: string;
  targetWorkspaceId: string;
  role?: string;
  workspaceFlags?: WorkspaceFeatureFlags;
}): string {
  const feature = getFeatureForWorkspacePath(params.pathname);
  if (feature) {
    if (
      isFeatureEnabled({
        feature,
        role: params.role,
        workspaceFlags: params.workspaceFlags,
      })
    ) {
      return `/workspace/${params.targetWorkspaceId}${FEATURE_FALLBACK_ROUTE[feature]}`;
    }
    return getFirstAllowedWorkspacePath({
      workspaceId: params.targetWorkspaceId,
      role: params.role,
      workspaceFlags: params.workspaceFlags,
    });
  }

  const suffix = workspacePathSuffix(params.pathname);
  if (suffix) {
    return `/workspace/${params.targetWorkspaceId}${suffix}`;
  }

  return getFirstAllowedWorkspacePath({
    workspaceId: params.targetWorkspaceId,
    role: params.role,
    workspaceFlags: params.workspaceFlags,
  });
}

function workspacePathSuffix(pathname: string): string | null {
  const parts = pathWithoutQuery(pathname).split('/').filter(Boolean);
  const workspaceIndex = parts.indexOf('workspace');
  if (workspaceIndex < 0 || parts.length <= workspaceIndex + 2) {
    return null;
  }
  return `/${parts.slice(workspaceIndex + 2).join('/')}`;
}
