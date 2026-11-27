'use client';

import { Suspense, useMemo } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { useWorkspaceStore } from '@/stores/workspace';
import { WorkspaceCreateUserForm } from '@/components/people/workspace-create-user';
import { AlertCircle } from 'lucide-react';
import { createUserPrefill, createdMessage, membersAddedHref } from '@/lib/people';
import { Notice } from '@/components/ui/notice';
import { Loading } from '@/components/ui/spinner';

/**
 * Create user (Workspace settings › Users › Create user): their email, full name and Role here
 * (Members and the workspace's own group to start with; groups and policies added or removed).
 * Opened from Add people's Create user, prefilled from `?email=` or `?name=`.
 */
function WorkspaceCreateUser() {
  const params = useParams();
  const router = useRouter();
  const search = useSearchParams();
  const workspaceId = params.workspaceId as string;
  const workspace = useWorkspaceStore((s) => s.workspaces.find((w) => w.id === workspaceId));
  const membersPath = `/workspace/${workspaceId}/settings/users`;
  const prefill = useMemo(() => createUserPrefill(search), [search]);

  if (!workspace) return <Loading label="Loading workspace…" />;
  // The API decides; a known role that may not add anyone is told so before typing.
  if (workspace.currentUserRole && !['owner', 'admin'].includes(workspace.currentUserRole)) {
    return (
      <Notice tone="error" icon={<AlertCircle size={14} />}>
        Only workspace admins can add members.
      </Notice>
    );
  }

  return (
    <WorkspaceCreateUserForm
      workspaceId={workspace.id}
      workspaceName={workspace.name}
      prefill={prefill}
      back={{ href: membersPath, label: 'Users' }}
      onCancel={() => router.push(membersPath)}
      onCreated={(created, warning) => {
        if (warning) {
          router.push(`${membersPath}?notice=${encodeURIComponent(warning)}`);
          return;
        }
        if (created.warning) {
          router.push(`${membersPath}?notice=${encodeURIComponent(createdMessage(created, workspace.name))}`);
          return;
        }
        router.push(membersAddedHref(membersPath, created));
      }}
    />
  );
}

export default function WorkspaceCreateUserPage() {
  return (
    <Suspense fallback={<Loading label="Loading…" />}>
      <WorkspaceCreateUser />
    </Suspense>
  );
}
