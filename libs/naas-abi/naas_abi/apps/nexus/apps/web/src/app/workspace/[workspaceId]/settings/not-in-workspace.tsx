'use client';

import Link from 'next/link';
import { Blocks } from 'lucide-react';
import { SettingsEmpty } from '@/components/settings/settings-ui';
import { orgModulesPath } from '@/app/organizations/[orgId]/settings/lib/nav';
import type { WorkspaceResources } from '@/lib/workspace-resources';

/**
 * A settings page of something outside the workspace's set: there is nothing to manage
 * here. Adding it is the organization's (Modules & features), linked for who may.
 */
export function NotInWorkspace({
  label,
  resources,
  workspaceId,
}: {
  label: string;
  resources: WorkspaceResources;
  workspaceId: string;
}) {
  const modulesHref =
    resources.can_edit_set && resources.organization_id
      ? orgModulesPath(resources.organization_id, workspaceId)
      : null;
  return (
    <SettingsEmpty
      icon={<Blocks size={40} className="opacity-40" />}
      title={`${label} is not in this workspace`}
      description={
        modulesHref ? (
          <>
            Add it to the workspace on the organization&rsquo;s{' '}
            <Link href={modulesHref} className="underline">
              Modules &amp; features
            </Link>
            .
          </>
        ) : (
          'Organization owners and admins choose what this workspace has.'
        )
      }
    />
  );
}
