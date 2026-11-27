'use client';

import '@/components/access/access-base.css';
import '@/components/access/access.css';
import { useEffect, useMemo, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { pageFocus } from '@/components/access/access-paths';
import { principalLabel } from '@/components/access/attachments/attachments-model';
import { ViewAsControl } from '@/components/access/people/view-as-control';
import { MemberRoleSection } from '@/components/people/member-role-section';
import { PersonBack, PersonInfoSection } from '@/components/access/people/person-info';
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
  }, [iam, personId]);

  if (!personId) return null;
  // The page alone: back to Users, then who it is about (Info) and what they hold.
  return (
    <div className="access-instance-page">
      <PersonBack onClick={() => router.push(PLATFORM_USERS_PATH)} />
      <PersonInfoSection
        id={personId}
        name={person?.name ?? null}
        email={person?.email ?? null}
        actions={
          <>
            {person && <ViewAsControl personId={personId} name={person.name} workspaceId={null} />}
          </>
        }
      />
      <PlatformOrganizations personId={personId} />
      <MemberRoleSection scope={{ kind: 'platform' }} userId={personId} />
    </div>
  );
}
