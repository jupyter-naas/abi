'use client';

import { useFeature } from '@/hooks/use-feature';
import { opensRolesAndPermissions } from '@/components/access/access-sections';
import { workspaceContainer } from '@/components/access/access-scope';
import {
  workspaceOrganization,
  workspaceSettingsAccess,
  type WorkspaceSettingsAccess,
} from '@/components/shell/settings-nav';
import { useIamAccess } from '@/lib/iam-admin/use-access';
import { useWorkspaceStore } from '@/stores/workspace';

/**
 * Whether the current workspace's settings open for the caller (`workspaceSettingsAccess`):
 * their role there, else what IAM shows them of Roles & permissions at the workspace (read
 * only when the role does not decide).
 */
export function useWorkspaceSettingsAccess(): WorkspaceSettingsAccess {
  const settingsByRole = useFeature('settings.workspace');
  const workspace = useWorkspaceStore((s) => s.workspaces.find((w) => w.id === s.currentWorkspaceId));
  const skip = !workspace || settingsByRole;
  const { access, loading } = useIamAccess(
    workspace ? workspaceContainer(workspaceOrganization(workspace), workspace.id) : undefined,
    undefined,
    { skip }
  );
  return workspaceSettingsAccess({
    settingsByRole,
    holdsIam: !!workspace && opensRolesAndPermissions(access),
    accessSettled: !!workspace && !loading,
  });
}

/** Whether the dock and the mobile sheet offer the workspace's settings. */
export function useOpensWorkspaceSettings(): boolean {
  const access = useWorkspaceSettingsAccess();
  return access === 'all' || access === 'iam';
}
