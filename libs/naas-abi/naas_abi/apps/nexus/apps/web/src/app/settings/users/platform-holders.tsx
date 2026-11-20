'use client';

import '@/components/access/access-base.css';
import '@/components/access/access.css';

import { useMemo } from 'react';
import { createIamAdminApi } from '@/lib/iam-admin/api';
import { EMPTY_DIRECTORY } from '@/components/access/access-directory';
import type { AccessNavigation } from '@/components/access/access-props';
import { platformAccessPath, platformPersonPath } from '@/components/access/access-paths';
import { PLATFORM_ACCESS_SCOPE } from '@/components/access/access-scope';
import { PeopleView } from '@/components/access/people/people';
import { OrgSettingsPageHeader } from '@/app/organizations/[orgId]/settings/components/org-settings-page-header';

/**
 * Platform › Users for whoever may list who holds what (`iam:ListAttachments`) and not the
 * accounts (`nexus:ListUsers`): the people who hold something at the platform, found by IAM's
 * search too where they may list principals; each opens their page.
 */
export function PlatformHolders({ can, navigate }: { can: (action: string) => boolean; navigate: (href: string) => void }) {
  const api = useMemo(() => createIamAdminApi(), []);
  const showsGroups = can('iam:ListGroups');
  const open = useMemo<AccessNavigation>(
    () => ({
      person: (id) => navigate(platformPersonPath(id)),
      group: showsGroups ? (id) => navigate(platformAccessPath('groups', id)) : undefined,
    }),
    [navigate, showsGroups],
  );
  return (
    <div className="access-settings-page">
      <OrgSettingsPageHeader title="Users" subtitle="The people who hold a role or a policy on the platform" />
      <div className="access-tab">
        <PeopleView api={api} can={can} scope={PLATFORM_ACCESS_SCOPE} directory={EMPTY_DIRECTORY} open={open} />
      </div>
    </div>
  );
}
