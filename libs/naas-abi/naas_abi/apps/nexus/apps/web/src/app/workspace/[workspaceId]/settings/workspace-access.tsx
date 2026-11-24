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
import { MemberRoleSection, type PersonRef } from '@/components/people/member-role-section';
import { SettingsBackButton, SettingsPageHeader } from '@/components/settings/settings-ui';
import { useSettingsReloadGeneration } from '@/components/settings/settings-reload';
import { Button } from '@/components/ui/button';
import { workspaceOrganization } from '@/components/shell/settings-nav';
import { useWorkspaceStore } from '@/stores/workspace';

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
  const hrefs = useMemo<AccessHrefs>(
    () => ({
      page: (page, id) => workspaceAccessPath(workspaceId, page === 'groups' ? 'groups' : 'policies', id),
      person: (id) => workspacePersonPath(workspaceId, id),
    }),
    [workspaceId],
  );
  return (
    <div className="access-settings-page">
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
      {scope ? (
        <AccessPage
          headerSlot={headerSlot}
          onBadge={setBadge}
          section={section}
          scopes={[scope]}
          focus={pageFocus(pathname, workspaceAccessPath(workspaceId, section))}
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
  if (!personId) return null;
  const named = person ? [person.name, person.email].filter((v, i, all) => v && all.indexOf(v) === i).join(' · ') : '';
  return (
    <div className="space-y-6">
      <SettingsPageHeader
        leading={<SettingsBackButton label="Users" onClick={() => router.push(`/workspace/${workspaceId}/settings/users`)} />}
        title="Member"
        description={named || 'Their groups and policies in this workspace'}
        actions={
          person ? <ViewAsControl personId={personId} name={person.name} workspaceId={scope?.workspaceId ?? null} /> : undefined
        }
      />
      <MemberRoleSection
        scope={{ kind: 'workspace', id: workspaceId }}
        principalId={personId}
        nonce={nonce}
        onPerson={setPerson}
      />
    </div>
  );
}
