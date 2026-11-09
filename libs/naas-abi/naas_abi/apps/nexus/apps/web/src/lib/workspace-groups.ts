import { viewFlagActive } from '@/lib/view-flag';
import { authFetch } from '@/stores/auth';

/**
 * The groups the organization's workspaces already use (the Group picker of Settings › General),
 * sorted. In a view the organization's other workspaces are outside it (``view_as/AGENTS.md``):
 * nothing is asked, and the picker shows the workspace's own group.
 */
export async function existingWorkspaceGroups(
  orgId: string | undefined | null,
  ownGroup: string,
  fetcher: (url: string) => Promise<Response> = authFetch,
): Promise<string[]> {
  if (viewFlagActive()) return ownGroup.trim() ? [ownGroup.trim()] : [];
  if (!orgId) return [];
  try {
    const response = await fetcher(`/api/organizations/${orgId}/workspaces`);
    if (!response.ok) return [];
    const rows: { workspace_group?: string | null }[] = await response.json();
    const groups = new Set(rows.map((row) => row.workspace_group?.trim()).filter(Boolean) as string[]);
    return [...groups].sort((a, b) => a.localeCompare(b));
  } catch {
    return [];
  }
}
