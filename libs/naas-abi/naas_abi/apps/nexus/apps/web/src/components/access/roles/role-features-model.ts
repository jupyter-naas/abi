/**
 * The built-in roles' feature defaults of an organization (`GET|PUT
 * /api/organizations/{org}/roles/features`): which Nexus features each role gets, within the
 * deployment's `enabled_features`. The owner's column is the deployment's, never edited here.
 */
import { authFetch } from '@/stores/auth';
import type { BuiltInRole } from './role-change';

export type RoleFeatures = {
  enabled_features: string[];
  known_features: string[];
  role_baseline: Record<string, string[]>;
  roles: BuiltInRole[];
  persistence?: string;
};

export type Baseline = Record<BuiltInRole, string[]>;

/** Least to most privileged, as the matrix shows them. */
export const MATRIX_ORDER: BuiltInRole[] = ['viewer', 'member', 'admin', 'owner'];

export const READ_ONLY_ROLE: BuiltInRole = 'owner';

export function baselineOf(view: RoleFeatures): Baseline {
  const baseline = { owner: [], admin: [], member: [], viewer: [] } as Baseline;
  for (const role of view.roles) baseline[role] = [...(view.role_baseline[role] ?? [])];
  return baseline;
}

/** The features the matrix lists: those the deployment enables, else every known one. */
export function featuresOf(view: RoleFeatures): string[] {
  return view.enabled_features.length ? view.enabled_features : view.known_features;
}

export function toggled(baseline: Baseline, role: BuiltInRole, feature: string, order: string[]): Baseline {
  if (role === READ_ONLY_ROLE) return baseline;
  const held = new Set(baseline[role]);
  if (held.has(feature)) held.delete(feature);
  else held.add(feature);
  return { ...baseline, [role]: order.filter((key) => held.has(key)) };
}

export function changed(a: Baseline, b: Baseline): boolean {
  return MATRIX_ORDER.some(
    (role) => role !== READ_ONLY_ROLE && [...a[role]].sort().join(',') !== [...b[role]].sort().join(','),
  );
}

type Fetcher = (url: string, options?: RequestInit) => Promise<Response>;

async function failure(response: Response, fallback: string): Promise<Error> {
  const body = await response.json().catch(() => ({}));
  return new Error(typeof body?.detail === 'string' ? body.detail : fallback);
}

export function createRoleFeaturesApi(fetcher: Fetcher = authFetch) {
  const path = (org: string) => `/api/organizations/${encodeURIComponent(org)}/roles/features`;
  return {
    read: async (org: string): Promise<RoleFeatures> => {
      const response = await fetcher(path(org));
      if (!response.ok) throw await failure(response, 'Could not load the roles’ features.');
      return (await response.json()) as RoleFeatures;
    },
    save: async (org: string, baseline: Baseline, roles: BuiltInRole[]): Promise<RoleFeatures> => {
      const response = await fetcher(path(org), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role_baseline: Object.fromEntries(roles.map((role) => [role, baseline[role]])) }),
      });
      if (!response.ok) throw await failure(response, 'Could not save the roles’ features.');
      return (await response.json()) as RoleFeatures;
    },
  };
}

export type RoleFeaturesApi = ReturnType<typeof createRoleFeaturesApi>;
