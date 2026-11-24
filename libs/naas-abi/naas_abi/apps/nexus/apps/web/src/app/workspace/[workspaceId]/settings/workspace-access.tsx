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
import { PersonPage } from '@/components/access/people/person-page';
import { MemberRoleSection } from '@/components/people/member-role-section';
import { SettingsPageHeader } from '@/components/settings/settings-ui';
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
 * Workspace settings › Members › a person (`members/<IAM id>`): what they hold at every level
 * IAM lets the caller list, attached, detached and changed where it lets them, and View as. A
 * policy's holders and a group's members link here.
 */
export function WorkspacePerson() {
  const router = useRouter();
  const { workspaceId, scope } = useWorkspaceScope();
  const personId = pageFocus(usePathname(), `/workspace/${workspaceId}/settings/users`);
  const [nonce, setNonce] = useState(0);
  const navigate = useCallback((href: string) => router.push(href), [router]);
  const groupHref = useCallback((id: string) => workspaceAccessPath(workspaceId, 'groups', id), [workspaceId]);
  if (!personId) return null;
  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title="Member"
        description="Their roles and policies at every level, and their groups, as IAM lets you see them"
        actions={<RefreshButton onClick={() => setNonce((n) => n + 1)} />}
      />
      <MemberRoleSection
        scope={{ kind: 'workspace', id: workspaceId }}
        principalId={personId}
        onChanged={() => setNonce((n) => n + 1)}
      />
      {scope ? (
        <PersonPage
          scope={scope}
          personId={personId}
          nonce={nonce}
          navigate={navigate}
          groupHref={groupHref}
          onBack={() => router.push(`/workspace/${workspaceId}/settings/users`)}
          backLabel="Users"
        />
      ) : (
        <p className="text-sm text-muted-foreground">Loading…</p>
      )}
    </div>
  );
}
