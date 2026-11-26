/**
 * What Access › Features, Services and Modules edit: a workspace (its id: "<W> access") or an
 * organization (`org:<id>`: "<O> access", the ceiling of every workspace in it). The same pages
 * and API clients serve both; the API answers at `/api/workspaces/<id>` or
 * `/api/organizations/<id>`.
 */
const ORG = 'org:';

export const orgTarget = (orgId: string) => `${ORG}${orgId}`;

export const isOrgTarget = (target: string) => target.startsWith(ORG);

export function targetApiPath(target: string): string {
  return isOrgTarget(target)
    ? `/api/organizations/${encodeURIComponent(target.slice(ORG.length))}`
    : `/api/workspaces/${encodeURIComponent(target)}`;
}
