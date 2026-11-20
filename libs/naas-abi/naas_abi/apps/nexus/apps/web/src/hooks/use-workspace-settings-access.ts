'use client';

import { useFeature } from '@/hooks/use-feature';
import { opensAccess } from '@/components/access/access-sections';
import { workspaceContainer } from '@/components/access/access-scope';
import {
  workspaceOrganization,
  workspaceSettingsAccess,
  type WorkspaceSettingsAccess,
} from '@/components/shell/settings-nav';
import { useIamAccess } from '@/lib/iam-admin/use-access';
import type { AccessView } from '@/lib/iam-admin/types';
import { useWorkspaceStore } from '@/stores/workspace';

/**
 * Whether the current workspace's settings open for the caller (`workspaceSettingsAccess`):
 * their role there, else what IAM shows them of the workspace's Access (read only when the
 * role does not decide).
 */
export function useWorkspaceSettingsAccess(): WorkspaceSettingsAccess {
  return useWorkspaceSettingsAccessView().access;
}

/** The same, with IAM's answer at the workspace (`iam`, null when the role decides or while it
 *  is read): which pages of Access an `iam:` holder opens, and where they land. */
export function useWorkspaceSettingsAccessView(): { access: WorkspaceSettingsAccess; iam: AccessView | null } {
  const settingsByRole = useFeature('settings.workspace');
  const workspace = useWorkspaceStore((s) => s.workspaces.find((w) => w.id === s.currentWorkspaceId));
  const skip = !workspace || settingsByRole;
  const { access, loading } = useIamAccess(
    workspace ? workspaceContainer(workspaceOrganization(workspace), workspace.id) : undefined,
    undefined,
    { skip }
  );
  return {
    access: workspaceSettingsAccess({
      settingsByRole,
      holdsIam: !!workspace && opensAccess(access, 'workspace'),
      accessSettled: !!workspace && !loading,
    }),
    iam: skip ? null : access,
  };
}

/** Whether the dock and the mobile sheet offer the workspace's settings. */
export function useOpensWorkspaceSettings(): boolean {
  const access = useWorkspaceSettingsAccess();
  return access === 'all' || access === 'iam';
}
