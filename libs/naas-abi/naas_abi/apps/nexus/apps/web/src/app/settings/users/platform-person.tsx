'use client';

import { useCallback, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { RefreshCw } from 'lucide-react';
import { pageFocus, platformAccessPath } from '@/components/access/access-paths';
import { PLATFORM_ACCESS_SCOPE } from '@/components/access/access-scope';
import { PersonPage } from '@/components/access/people/person-page';
import { OrgSettingsPageHeader } from '@/app/organizations/[orgId]/settings/components/org-settings-page-header';
import '@/app/organizations/[orgId]/settings/components/org-settings-components.css';
import { PLATFORM_USERS_PATH } from './users-model';

const groupHref = (id: string) => platformAccessPath('groups', id);

/**
 * Platform › Users › a person (`/settings/users/<IAM id>`): what they hold at every level and
 * their groups, attached, detached and changed where IAM lets the caller, and View as. The Users
 * list opens it from a row; a policy's holders and a group's members link to it.
 */
export default function PlatformPersonPage() {
  const router = useRouter();
  const personId = pageFocus(usePathname(), PLATFORM_USERS_PATH);
  const [nonce, setNonce] = useState(0);
  const navigate = useCallback((href: string) => router.push(href), [router]);
  if (!personId) return null;
  return (
    <div className="access-settings-page">
      <OrgSettingsPageHeader
        title="User"
        subtitle="Their roles and policies at every level, and their groups, as IAM lets you see them"
        actions={
          <button
            type="button"
            className="org-settings-users-secondary-button"
            data-action="refresh"
            onClick={() => setNonce((n) => n + 1)}
            title="Refresh"
            aria-label="Refresh"
          >
            <RefreshCw size={16} />
          </button>
        }
      />
      <PersonPage
        scope={PLATFORM_ACCESS_SCOPE}
        personId={personId}
        nonce={nonce}
        navigate={navigate}
        groupHref={groupHref}
        onBack={() => router.push(PLATFORM_USERS_PATH)}
        backLabel="Users"
      />
    </div>
  );
}
