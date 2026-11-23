import { defineResource, invalidateResource, pathUnder, readResource, type ReadOptions } from '@/lib/resource-cache';
import { authFetch } from '@/stores/auth';

type OrgParams = { orgId: string };

const changedOrganization = (path: string, { orgId }: OrgParams) =>
  pathUnder(path, `/api/organizations/${orgId}`);

/**
 * One organization (`GET /api/organizations/{id}`): its identity, branding and the
 * caller's role there. Read by the Organization settings layout, its pages and the
 * workspace shell's branding at once: one request, kept a minute. Any change under the
 * organization, a branding edit and every IAM change drop it.
 */
export const ORGANIZATION = defineResource<OrgParams>({
  name: 'organization',
  ttlMs: 60_000,
  key: ({ orgId }) => orgId,
  backendCache: false,
  invalidatedBy: changedOrganization,
});

/** An organization's domains (`GET /api/organizations/{id}/domains`; 403 for a non-admin). */
export const ORGANIZATION_DOMAINS = defineResource<OrgParams>({
  name: 'organization-domains',
  ttlMs: 60_000,
  key: ({ orgId }) => orgId,
  backendCache: false,
  invalidatedBy: changedOrganization,
});

export function readOrganization(orgId: string, options?: ReadOptions): Promise<Response> {
  return readResource(
    ORGANIZATION,
    { orgId },
    () => authFetch(`/api/organizations/${orgId}`, {}, { settingsCache: ORGANIZATION.backendCache }),
    options,
  );
}

export function readOrganizationDomains(orgId: string, options?: ReadOptions): Promise<Response> {
  return readResource(
    ORGANIZATION_DOMAINS,
    { orgId },
    () => authFetch(`/api/organizations/${orgId}/domains`, {}, { settingsCache: ORGANIZATION_DOMAINS.backendCache }),
    options,
  );
}

/** Drop what is kept of one organization (or of all, without an id). */
export function invalidateOrganization(orgId?: string): void {
  const match = ({ orgId: kept }: OrgParams) => orgId === undefined || kept === orgId;
  invalidateResource(ORGANIZATION, match);
  invalidateResource(ORGANIZATION_DOMAINS, match);
}

if (typeof window !== 'undefined') {
  // Branding edits announce themselves; some are saved outside `authFetch`.
  window.addEventListener('org-branding-updated', () => invalidateOrganization());
}
