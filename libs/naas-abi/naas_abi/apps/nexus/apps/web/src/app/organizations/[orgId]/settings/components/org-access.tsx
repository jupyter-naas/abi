'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, usePathname, useRouter, useSearchParams } from 'next/navigation';
import { RefreshCw } from 'lucide-react';
import { AccessPage, type AccessHrefs } from '@/components/access/access-page';
import { AccessHeaderSlot } from '@/components/access/access-list';
import {
  organizationAccessPath,
  organizationPersonPath,
  pageFocus,
  type ContainerAccessPage,
} from '@/components/access/access-paths';
import { organizationAccessScope, workspaceAccessScope } from '@/components/access/access-scope';
import { accessSection } from '@/components/access/access-sections';
import { OrgSettingsPageHeader } from './org-settings-page-header';
import './org-settings-components.css';

type OrgWorkspace = { id: string; name: string };

const SUBTITLES: Record<ContainerAccessPage, string> = {
  policies: 'The policies of the organization and its workspaces, and who holds each',
  groups: 'Groups of people here and in its workspaces, and what each holds',
};

/**
 * Organization settings › Access › Policies or Groups: the shared Access UI at the
 * organization's scope, each of its workspaces one pick away (the pick in the address,
 * `?in=<workspace id>`). A policy's or a group's page is its address; a name opens the
 * person's page under Members. IAM decides what the caller sees at each scope.
 */
export function OrgAccess({ section }: { section: ContainerAccessPage }) {
  const orgId = useParams().orgId as string;
  const router = useRouter();
  const pathname = usePathname();
  const [workspaces, setWorkspaces] = useState<OrgWorkspace[]>([]);
  const [nonce, setNonce] = useState(0);
  // The page's own action (Create …) goes after Refresh, as on Platform › Users.
  const [headerSlot, setHeaderSlot] = useState<HTMLElement | null>(null);
  const [badge, setBadge] = useState<string | null>(null);
  // The workspace the address picks (`?in=<workspace id>`).
  const inWorkspace = useSearchParams()?.get('in') ?? null;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { authFetch } = await import('@/stores/auth');
        const response = await authFetch(`/api/organizations/${orgId}/workspaces`);
        if (response.ok && !cancelled) setWorkspaces((await response.json()) as OrgWorkspace[]);
      } catch (e) {
        console.error('Failed to fetch org workspaces:', e);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [orgId]);

  const scopes = useMemo(
    () => [
      organizationAccessScope(orgId, 'This organization'),
      ...workspaces.map((w) => workspaceAccessScope(orgId, w.id, `Workspace: ${w.name}`)),
    ],
    [orgId, workspaces],
  );
  const picked = Math.max(0, scopes.findIndex((s) => !!inWorkspace && s.workspaceId === inWorkspace));
  const query = picked > 0 && inWorkspace ? `?in=${encodeURIComponent(inWorkspace)}` : '';
  const navigate = useCallback((href: string) => router.push(href), [router]);
  // A policy's or a group's page is the page alone: no header of the list (its back link leads to it).
  const focus = pageFocus(pathname, organizationAccessPath(orgId, section));
  // What the view shows (a row opens its page before the address follows), else the address.
  const [instance, setInstance] = useState<boolean | null>(null);
  const alone = instance ?? !!focus;
  const hrefs = useMemo<AccessHrefs>(
    () => ({
      page: (page, id) => `${organizationAccessPath(orgId, page === 'groups' ? 'groups' : 'policies', id)}${query}`,
      person: (id) => organizationPersonPath(orgId, id),
    }),
    [orgId, query],
  );

  return (
    <div className="access-settings-page">
      {!alone && (
      <OrgSettingsPageHeader
        title={accessSection(section).label}
        badge={badge ?? undefined}
        subtitle={SUBTITLES[section]}
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
      )}
      <AccessPage
        headerSlot={headerSlot}
        onBadge={setBadge}
        onInstance={setInstance}
        section={section}
        scopes={scopes}
        picked={picked}
        // The page open was judged at the scope left: another scope opens its list.
        onPick={(index) => {
          const workspace = scopes[index]?.workspaceId;
          navigate(`${organizationAccessPath(orgId, section)}${workspace ? `?in=${encodeURIComponent(workspace)}` : ''}`);
        }}
        focus={focus}
        hrefs={hrefs}
        navigate={navigate}
        nonce={nonce}
      />
    </div>
  );
}
