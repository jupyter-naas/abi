'use client';

import '@/components/access/access-base.css';
import '@/components/access/access.css';
import { useEffect, useMemo, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { pageFocus } from '@/components/access/access-paths';
import { principalLabel } from '@/components/access/attachments/attachments-model';
import { ViewAsControl } from '@/components/access/people/view-as-control';
import { MemberRoleSection } from '@/components/people/member-role-section';
import { SettingsBackButton, SettingsPageHeader } from '@/components/settings/settings-ui';
import { UsersReloadButton } from '@/components/settings/users-table/users-table-actions';
import '@/app/organizations/[orgId]/settings/users/users.css';
import { createIamAdminApi } from '@/lib/iam-admin/api';
import { PLATFORM_USERS_PATH } from './users-model';
import { PlatformOrganizations } from './platform-organizations';

/**
 * Platform › Users › a person (`/settings/users/<IAM id>`), as a workspace's and an
 * organization's: the organizations they belong to (each opening their page there), their
 * groups and policies on the platform, added and removed here (`MemberRoleSection`), and View
 * as. The Users list opens it from a row; a policy's holders and a group's members link to it.
 */
export default function PlatformPersonPage() {
  const router = useRouter();
  const personId = pageFocus(usePathname(), PLATFORM_USERS_PATH);
  const [nonce, setNonce] = useState(0);
  const iam = useMemo(() => createIamAdminApi(), []);
  const [person, setPerson] = useState<{ name: string; email: string | null } | null>(null);

  useEffect(() => {
    let live = true;
    setPerson(null);
    if (!personId) return;
    iam.getPrincipal(personId).then(
      (found) => live && setPerson({ name: principalLabel(found, personId), email: found.email ?? null }),
      () => undefined
    );
    return () => {
      live = false;
    };
  }, [iam, personId, nonce]);

  if (!personId) return null;
  const named = person ? [person.name, person.email].filter((v, i, all) => v && all.indexOf(v) === i).join(' · ') : '';
  return (
    <div className="space-y-6">
      <SettingsPageHeader
        leading={<SettingsBackButton label="Users" onClick={() => router.push(PLATFORM_USERS_PATH)} />}
        title="User"
        description={named || 'Their organizations, groups and policies on the platform'}
        actions={
          <>
            {person && <ViewAsControl personId={personId} name={person.name} workspaceId={null} />}
            <UsersReloadButton onReload={() => setNonce((n) => n + 1)} />
          </>
        }
      />
      <PlatformOrganizations personId={personId} nonce={nonce} />
      <MemberRoleSection scope={{ kind: 'platform' }} userId={personId} nonce={nonce} />
    </div>
  );
}
