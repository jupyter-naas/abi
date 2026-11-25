'use client';

import { useCallback, useMemo, useState } from 'react';
import { useParams, usePathname, useRouter } from 'next/navigation';
import { RefreshCw } from 'lucide-react';
import { AccessPage, type AccessHrefs } from '@/components/access/access-page';
import { AccessHeaderSlot } from '@/components/access/access-list';
import {
  pageFocus,
  workspaceAccessPath,
  workspacePersonPath,
  type ContainerAccessPage,
} from '@/components/access/access-paths';
import { workspaceAccessScope } from '@/components/access/access-scope';
import { accessSection } from '@/components/access/access-sections';
import '@/components/access/access-base.css';
import '@/components/access/access.css';
import { ViewAsControl } from '@/components/access/people/view-as-control';
import { PersonBack, PersonInfoSection } from '@/components/access/people/person-info';
import { SettingsReloadButton } from '@/components/settings/settings-reload';
import { MemberRoleSection, type PersonRef } from '@/components/people/member-role-section';
import { SettingsPageHeader } from '@/components/settings/settings-ui';
import { useSettingsReloadGeneration } from '@/components/settings/settings-reload';
import { Button } from '@/components/ui/button';
import { workspaceOrganization } from '@/components/shell/settings-nav';
import { useWorkspaceStore } from '@/stores/workspace';
import { authFetch, useAuthStore } from '@/stores/auth';

const SUBTITLES: Record<ContainerAccessPage, string> = {
  policies: 'Where rights come from in this workspace: each policy, and who holds it here',
  groups: 'Groups of people of this workspace, and what each holds',
};

/** The workspace the address names (by its id or its slug; IAM names it by its id) and its
 *  scope, null while the workspaces are read. */
function useWorkspaceScope() {
  const workspaceId = useParams()?.workspaceId as string;
  const workspace = useWorkspaceStore((s) => s.workspaces.find((w) => w.id === workspaceId || w.slug === workspaceId));
  const org = workspaceOrganization(workspace);
  const id = workspace?.id;
  const name = workspace?.name || 'This workspace';
  const scope = useMemo(() => (id ? workspaceAccessScope(org, id, name) : null), [org, id, name]);
  return { workspaceId, scope };
}

function RefreshButton({ onClick }: { onClick: () => void }) {
  return (
    <Button variant="secondary" size="sm" data-action="refresh" onClick={onClick} title="Refresh" aria-label="Refresh">
      <RefreshCw className="h-4 w-4" />
    </Button>
  );
}

/**
 * Workspace settings › Access › Policies or Groups: the shared Access UI at this workspace's
 * scope. The menu shows a page to whoever IAM lets open it here (Members stays everyone's
 * door); a policy's or a group's page is its address, and a name opens the person's page
 * under Members.
 */
export function WorkspaceAccess({ section }: { section: ContainerAccessPage }) {
  const router = useRouter();
  const pathname = usePathname();
  const { workspaceId, scope } = useWorkspaceScope();
  const [nonce, setNonce] = useState(0);
  // The page's own action (Create …) goes after Refresh, as on Platform › Users.
  const [headerSlot, setHeaderSlot] = useState<HTMLElement | null>(null);
  const [badge, setBadge] = useState<string | null>(null);
  const navigate = useCallback((href: string) => router.push(href), [router]);
  // A policy's or a group's page is the page alone: no header of the list (its back link leads to it).
  const focus = pageFocus(pathname, workspaceAccessPath(workspaceId, section));
  // What the view shows (a row opens its page before the address follows), else the address.
  const [instance, setInstance] = useState<boolean | null>(null);
  const alone = instance ?? !!focus;
  const hrefs = useMemo<AccessHrefs>(
    () => ({
      page: (page, id) => workspaceAccessPath(workspaceId, page === 'groups' ? 'groups' : 'policies', id),
      person: (id) => workspacePersonPath(workspaceId, id),
    }),
    [workspaceId],
  );
  return (
    <div className="access-settings-page">
      {!alone && (
      <SettingsPageHeader
        title={accessSection(section).label}
        badge={badge ?? undefined}
        description={SUBTITLES[section]}
        actions={
          <>
            <RefreshButton onClick={() => setNonce((n) => n + 1)} />
            <AccessHeaderSlot onSlot={setHeaderSlot} />
          </>
        }
      />
      )}
      {scope ? (
        <AccessPage
          headerSlot={headerSlot}
          onBadge={setBadge}
          onInstance={setInstance}
          section={section}
          scopes={[scope]}
          focus={focus}
          hrefs={hrefs}
          navigate={navigate}
          nonce={nonce}
        />
      ) : (
        <p className="text-sm text-muted-foreground">Loading…</p>
      )}
    </div>
  );
}

/**
 * Workspace settings › Users › a person (`users/<IAM id>`): their groups and policies bearing on
 * this workspace, added and removed here (`MemberRoleSection`), and View as. A policy's holders
 * and a group's members link here. The header's Reload (Users is a cached settings page) reads
 * them again in place.
 */
export function WorkspacePerson() {
  const router = useRouter();
  const { workspaceId, scope } = useWorkspaceScope();
  const personId = pageFocus(usePathname(), `/workspace/${workspaceId}/settings/users`);
  const nonce = useSettingsReloadGeneration();
  const [person, setPerson] = useState<PersonRef | null>(null);
  const workspace = useWorkspaceStore((s) => s.workspaces.find((w) => w.id === workspaceId || w.slug === workspaceId));
  const platformAdmin = useAuthStore((s) => !!s.user?.is_superadmin);
  // Who may take someone out of the workspace, as its Users list says (its admins, the
  // platform's); the API decides again.
  const managesMembers =
    workspace?.currentUserRole === 'owner' || workspace?.currentUserRole === 'admin' || platformAdmin;
  const usersPath = `/workspace/${workspaceId}/settings/users`;
  const leave =
    managesMembers && person
      ? async () => {
          const response = await authFetch(
            `/api/workspaces/${encodeURIComponent(workspaceId)}/members/${encodeURIComponent(person.userId)}`,
            { method: 'DELETE' },
          );
          if (!response.ok) {
            const detail = await response.json().then((b) => (typeof b?.detail === 'string' ? b.detail : ''), () => '');
            throw new Error(detail || 'Could not remove them from the workspace.');
          }
          router.push(usersPath);
        }
      : undefined;
  if (!personId) return null;
  // The page alone: back to Users, then who it is about (Info) and what they hold.
  return (
    <div className="access-instance-page">
      <PersonBack onClick={() => router.push(usersPath)} />
      <PersonInfoSection
        id={personId}
        name={person?.name ?? null}
        email={person?.email ?? null}
        actions={
          <>
            <SettingsReloadButton />
            {person && <ViewAsControl personId={personId} name={person.name} workspaceId={scope?.workspaceId ?? null} />}
          </>
        }
      />
      <MemberRoleSection
        scope={{ kind: 'workspace', id: workspaceId }}
        principalId={personId}
        nonce={nonce}
        onPerson={setPerson}
        onLeave={leave}
      />
    </div>
  );
}
