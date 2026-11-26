'use client';

import { Suspense, useMemo } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { useWorkspaceStore } from '@/stores/workspace';
import { CreateUserForm } from '@/components/people/create-user-form';
import { workspaceOrganization } from '@/components/shell/settings-nav';
import { AlertCircle } from 'lucide-react';
import { SettingsLoading, SettingsNotice } from '@/components/settings/settings-ui';
import { createUserPrefill, createdMessage, membersAddedHref } from '@/lib/people';

/**
 * Create user (Workspace settings › Members › New): the form Organization settings › Users ›
 * New uses, with the workspace's organization shown read-only and this workspace joined: their
 * level (in all their workspaces), the workspace admin toggle and capability groups (#1589). A
 * workspace admin makes nobody an org admin. Opened from Add people's "Create user '<text>'",
 * prefilled from `?email=` or `?name=`.
 */
function WorkspaceCreateUser() {
  const params = useParams();
  const router = useRouter();
  const search = useSearchParams();
  const workspaceId = params.workspaceId as string;
  const workspace = useWorkspaceStore((s) => s.workspaces.find((w) => w.id === workspaceId));
  const organizationId = workspaceOrganization(workspace);
  const membersPath = `/workspace/${workspaceId}/settings/users`;
  const prefill = useMemo(() => createUserPrefill(search), [search]);

  if (!workspace) return <SettingsLoading label="Loading workspace…" />;
  // The API decides; a known role that may not add anyone is told so before typing.
  if (workspace.currentUserRole && !['owner', 'admin'].includes(workspace.currentUserRole)) {
    return (
      <SettingsNotice tone="error" icon={<AlertCircle size={14} />}>
        Only workspace admins can add members.
      </SettingsNotice>
    );
  }

  return (
    <CreateUserForm
      organization={{ fixed: { id: organizationId ?? '', name: workspace.organizationName ?? '' } }}
      attachedWorkspace={{ id: workspace.id, name: workspace.name }}
      organizationRoute={false}
      prefill={prefill}
      subtitle="Add someone to this workspace. They are created at once and invited until they first sign in; an email that already has an account is linked to it. They join the organization's directory through this workspace."
      back={{ href: membersPath, label: 'Users' }}
      onCancel={() => router.push(membersPath)}
      onCreated={(created) => {
        // A warning is worth reading here; otherwise Members says who was added.
        if (created.warning) return createdMessage(created, workspace.name);
        router.push(membersAddedHref(membersPath, created));
      }}
    />
  );
}

export default function WorkspaceCreateUserPage() {
  return (
    <Suspense fallback={<SettingsLoading label="Loading…" />}>
      <WorkspaceCreateUser />
    </Suspense>
  );
}
