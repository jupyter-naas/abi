/**
 * `/analytics` was the platform-wide Analytics app (removed, epic #1533). Analytics are
 * read in Organization settings › Analytics and Workspace settings › Analytics now, so
 * the old address leads to the current organization's section, or to a 404.
 *
 * The current organization is the current workspace's (as the sidebar's workspace list
 * groups them); with no current workspace (or one no longer listed), the one
 * organization the user's workspaces belong to, if they belong to exactly one.
 */

interface WorkspaceOfOrganization {
  id: string;
  organizationId?: string | null;
}

export function organizationAnalyticsPath(
  workspaces: readonly WorkspaceOfOrganization[],
  currentWorkspaceId: string | null | undefined,
): string | null {
  const current = currentWorkspaceId
    ? workspaces.find((w) => w.id === currentWorkspaceId)
    : undefined;
  let orgId = current?.organizationId || null;
  if (!orgId && !current) {
    const orgs = new Set(workspaces.map((w) => w.organizationId).filter(Boolean));
    orgId = orgs.size === 1 ? (Array.from(orgs)[0] as string) : null;
  }
  return orgId ? `/organizations/${encodeURIComponent(orgId)}/settings/analytics` : null;
}
