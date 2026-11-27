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
import { PLATFORM_USERS_PATH, type UserAccess } from './users-model';
import { PlatformOrganizations } from './platform-organizations';

/**
 * Platform › Users › a person (`/settings/users/<IAM id>`), as a workspace's and an
 * organization's: the organizations they belong to (each opening their page there), their
 * groups and policies on the platform, added and removed here (`MemberRoleSection`), and View
 * as. The Users list opens it from a row; a policy's holders and a group's members link to it.
 * Named from their IAM principal, else from their account (a principal made before they signed
 * in carries no name or email): never by their id while either is known.
 */
export default function PlatformPersonPage() {
  const router = useRouter();
  const personId = pageFocus(usePathname(), PLATFORM_USERS_PATH);
  const iam = useMemo(() => createIamAdminApi(), []);
  const [principal, setPrincipal] = useState<{ name: string | null; email: string | null } | null>(null);
  // Their account, as Organizations reads it, kept with whom it is about: undefined while it is
  // read, null when there is none.
  const [answered, setAnswered] = useState<{ personId: string; account: UserAccess | null } | null>(null);

  useEffect(() => {
    let live = true;
    setPrincipal(null);
    if (!personId) return;
    iam.getPrincipal(personId).then(
      (found) => {
        if (!live) return;
        const label = principalLabel(found, personId);
        // Its label falls back on the id: no name of its own then.
        setPrincipal({ name: label === personId ? null : label, email: found.email ?? null });
      },
      () => live && setPrincipal({ name: null, email: null })
    );
    return () => {
      live = false;
    };
  }, [iam, personId]);

  if (!personId) return null;
  const account = answered?.personId === personId ? answered.account : undefined;
  // Named once both are read (else their id would show before their account's name).
  const read = principal !== null && account !== undefined;
  const name = principal?.name || account?.name || (read ? personId : null);
  const email = principal?.email || account?.email || null;
  const person = read && name ? { name, email } : null;
  // The page alone: back to Users, then who it is about (Info) and what they hold.
  return (
    <div className="access-instance-page">
      <PersonBack onClick={() => router.push(PLATFORM_USERS_PATH)} />
      <PersonInfoSection
        id={personId}
        name={person?.name ?? null}
        email={person?.email ?? null}
        image={account?.avatar ?? null}
        actions={
          <>
            {person && <ViewAsControl personId={personId} name={person.name} workspaceId={null} />}
          </>
        }
      />
      <PlatformOrganizations personId={personId} onAccess={(found) => setAnswered({ personId, account: found })} />
      <MemberRoleSection scope={{ kind: 'platform' }} userId={personId} />
    </div>
  );
}
