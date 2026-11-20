'use client';

import { useCallback, useMemo, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { RefreshCw } from 'lucide-react';
import { AccessPage, type AccessHrefs } from '@/components/access/access-page';
import { AccessHeaderSlot } from '@/components/access/access-list';
import { pageFocus, platformAccessPath, platformPersonPath } from '@/components/access/access-paths';
import { PLATFORM_ACCESS_SCOPE } from '@/components/access/access-scope';
import { accessSection, type AccessSection } from '@/components/access/access-sections';
import { usePlatformSettingsAccess } from '@/hooks/use-platform-settings-access';
import { OrgSettingsPageHeader } from '@/app/organizations/[orgId]/settings/components/org-settings-page-header';
import '@/app/organizations/[orgId]/settings/components/org-settings-components.css';
import { holds, USERS_ITEM } from '../lib/nav';

const SCOPES = [PLATFORM_ACCESS_SCOPE];

/** What each page of Access is for, under its title. */
export const ACCESS_SUBTITLES: Record<AccessSection, string> = {
  policies: 'Where rights come from: every policy, the built-in roles among them, and who holds each at which level',
  groups: 'Groups of people, what each holds at every level, and the identity provider claims that fill them',
  'service-accounts': 'The accounts modules and scripts act as, their policies and their keys',
  approvals: 'What each module asks to do, approved or narrowed before it runs',
  simulator: 'Ask IAM whether someone may do something, and which statement decides',
  audit: 'Every change made to access: who made it, on what, and when',
};

/**
 * A page of Platform › Access: the shared Access UI at platform scope. A policy's or a group's
 * page is its address (`/settings/access/policies/<id>`), and a name opens the person's page
 * under Users for whoever may open Users. Refresh reloads it, for a change made from the CLI or
 * another tab.
 */
export function PlatformAccess({ section }: { section: AccessSection }) {
  const router = useRouter();
  const pathname = usePathname();
  const { actions } = usePlatformSettingsAccess();
  const [nonce, setNonce] = useState(0);
  // The page's own action (Create …) goes after Refresh, as on Platform › Users.
  const [headerSlot, setHeaderSlot] = useState<HTMLElement | null>(null);
  const [badge, setBadge] = useState<string | null>(null);
  const navigate = useCallback((href: string) => router.push(href), [router]);
  const opensPeople = holds(USERS_ITEM.needs, actions);
  const hrefs = useMemo<AccessHrefs>(
    () => ({ page: platformAccessPath, person: opensPeople ? platformPersonPath : null }),
    [opensPeople],
  );
  return (
    <div className="access-settings-page">
      <OrgSettingsPageHeader
        title={accessSection(section).label}
        badge={badge ?? undefined}
        subtitle={ACCESS_SUBTITLES[section]}
        actions={
          <>
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
            <AccessHeaderSlot onSlot={setHeaderSlot} />
          </>
        }
      />
      <AccessPage
        headerSlot={headerSlot}
        onBadge={setBadge}
        section={section}
        scopes={SCOPES}
        focus={pageFocus(pathname, platformAccessPath(section))}
        hrefs={hrefs}
        navigate={navigate}
        nonce={nonce}
      />
    </div>
  );
}
