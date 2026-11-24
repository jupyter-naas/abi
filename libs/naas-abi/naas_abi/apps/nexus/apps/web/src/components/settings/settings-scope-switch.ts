/**
 * Where the Organization and Workspace switchers atop the Settings column lead: the same
 * section of the level picked (a row's own page, such as a person's, is left behind, as it
 * belongs to the level left). No React here.
 */

const WORKSPACE_SETTINGS = /^(?:\/org\/[^/]+)?\/workspace\/([^/]+)\/settings(?:\/([^/?#]+))?/;
const ORGANIZATION_SETTINGS = /^\/organizations\/([^/]+)\/settings(?:\/([^/?#]+))?/;

/** The workspace of a workspace Settings page, or null. */
export function settingsWorkspaceId(pathname: string): string | null {
  return WORKSPACE_SETTINGS.exec(pathname)?.[1] ?? null;
}

/** The organization of an organization Settings page, or null. */
export function settingsOrganizationId(pathname: string): string | null {
  return ORGANIZATION_SETTINGS.exec(pathname)?.[1] ?? null;
}

/** The same Settings section in workspace ``workspaceId`` (its Settings when none is open). */
export function workspaceSettingsSwitchPath(pathname: string, workspaceId: string): string {
  const section = WORKSPACE_SETTINGS.exec(pathname)?.[2];
  return `/workspace/${encodeURIComponent(workspaceId)}/settings${section ? `/${section}` : ''}`;
}

/** The same Settings section in organization ``orgId`` (its Settings when none is open). */
export function organizationSettingsSwitchPath(pathname: string, orgId: string): string {
  const section = ORGANIZATION_SETTINGS.exec(pathname)?.[2];
  return `/organizations/${encodeURIComponent(orgId)}/settings${section ? `/${section}` : ''}`;
}

type Listed = { id: string; name: string; organizationId?: string; organizationName?: string };

/** The organizations the caller's workspaces belong to, by name, each with its workspaces. */
export function organizationsOfWorkspaces<W extends Listed>(
  workspaces: W[]
): { id: string; name: string; workspaces: W[] }[] {
  const found = new Map<string, { id: string; name: string; workspaces: W[] }>();
  for (const w of workspaces) {
    if (!w.organizationId) continue;
    const org = found.get(w.organizationId) ?? { id: w.organizationId, name: w.organizationName || w.organizationId, workspaces: [] };
    org.workspaces.push(w);
    found.set(w.organizationId, org);
  }
  const byName = (a: { name: string }, b: { name: string }) => a.name.localeCompare(b.name);
  return [...found.values()].map((o) => ({ ...o, workspaces: [...o.workspaces].sort(byName) })).sort(byName);
}
