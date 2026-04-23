export type FeatureKey = 'chat' | 'files' | 'agents' | 'knowledge' | 'settings';

export type WorkspaceFeatureFlags = Partial<Record<FeatureKey, boolean>>;

export const FEATURE_KEYS: FeatureKey[] = ['chat', 'files', 'agents', 'knowledge', 'settings'];

const DEFAULT_ROLE_BASELINE: Record<string, FeatureKey[]> = {
  owner: [...FEATURE_KEYS],
  admin: [...FEATURE_KEYS],
  member: ['chat', 'files'],
  viewer: ['chat', 'files'],
};

const FEATURE_FALLBACK_ROUTE: Record<FeatureKey, string> = {
  chat: '/chat',
  files: '/files',
  agents: '/lab',
  knowledge: '/search',
  settings: '/settings',
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

export function getFeatureForWorkspacePath(pathname: string): FeatureKey | null {
  const parts = pathname.split('/').filter(Boolean);
  const workspaceIndex = parts.indexOf('workspace');
  if (workspaceIndex < 0 || parts.length <= workspaceIndex + 2) {
    return null;
  }

  const firstSegment = parts[workspaceIndex + 2];
  if (firstSegment === 'chat') {
    return 'chat';
  }
  if (firstSegment === 'files') {
    return 'files';
  }
  if (firstSegment === 'search' || firstSegment === 'ontology' || firstSegment === 'graph') {
    return 'knowledge';
  }
  if (
    firstSegment === 'lab' ||
    firstSegment === 'apps' ||
    (firstSegment === 'settings' && parts[workspaceIndex + 3] === 'agents')
  ) {
    return 'agents';
  }
  if (firstSegment === 'settings' || firstSegment === 'organization' || firstSegment === 'help') {
    return 'settings';
  }

  return null;
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
  const priority: FeatureKey[] = ['chat', 'files', 'knowledge', 'agents', 'settings'];

  for (const feature of priority) {
    if (resolved[feature]) {
      return `/workspace/${params.workspaceId}${FEATURE_FALLBACK_ROUTE[feature]}`;
    }
  }

  return `/workspace/${params.workspaceId}/chat`;
}
