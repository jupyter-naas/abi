/**
 * What Access › Features, Services and Modules edit: a workspace (its id: "<W> access"), an
 * organization (`org:<id>`: "<O> access", the ceiling of every workspace in it), or the platform
 * (`platform`: "Platform access", what it offers every organization; Features only). The same pages
 * and API clients serve both; the API answers at `/api/workspaces/<id>` or
 * `/api/organizations/<id>`.
 */
const ORG = 'org:';

export const orgTarget = (orgId: string) => `${ORG}${orgId}`;

export const isOrgTarget = (target: string) => target.startsWith(ORG);

/** The platform (`platform`: "Platform access", what it offers every organization). */
export const PLATFORM_TARGET = 'platform';

export const isPlatformTarget = (target: string) => target === PLATFORM_TARGET;

export function targetApiPath(target: string): string {
  if (isPlatformTarget(target)) return '/api/platform';
  return isOrgTarget(target)
    ? `/api/organizations/${encodeURIComponent(target.slice(ORG.length))}`
    : `/api/workspaces/${encodeURIComponent(target)}`;
}
