'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, usePathname, useRouter } from 'next/navigation';
import { AlertCircle, RefreshCw, Trash2 } from 'lucide-react';
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
import { PersonBack } from '@/components/access/people/person-info';
import { InstanceHeader } from '@/components/access/instance-header';
import { getApiUrl } from '@/lib/config';
import { MemberRoleSection, type PersonRef } from '@/components/people/member-role-section';
import { SettingsPageHeader } from '@/components/settings/settings-ui';
import { Notice } from '@/components/ui/notice';
import { Card } from '@/components/ui/card';
import { useConfirm } from '@/components/ui/dialogs';
// The header's Remove button, as on an organization's person page.
import '@/app/organizations/[orgId]/settings/users/users.css';
import { useSettingsReloadGeneration } from '@/components/settings/settings-reload';
import { Button } from '@/components/ui/button';
import { workspaceOrganization } from '@/components/shell/settings-nav';
import { useWorkspaceStore } from '@/stores/workspace';
import { authFetch, useAuthStore } from '@/stores/auth';

const SUBTITLES: Record<ContainerAccessPage, string> = {
  policies: 'The policies of this workspace, and who holds each',
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

/** A member's account and their profile in the workspace's organization
 *  (`GET …/members/{user}/profile`), read-only here: its organization's admins change it. */
type MemberProfile = {
  user_id: string;
  name: string | null;
  email: string | null;
  avatar: string | null;
  organization_id: string | null;
  organization_profile: Record<'organization' | 'job_title' | 'service_line' | 'country' | 'interest' | 'bio' | 'avatar', string | null> | null;
};

const PROFILE_ROWS: { key: 'organization' | 'job_title' | 'service_line' | 'country' | 'interest'; label: string }[] = [
  { key: 'organization', label: 'Organization' },
  { key: 'job_title', label: 'Job title' },
  { key: 'service_line', label: 'Service line' },
  { key: 'country', label: 'Country' },
  { key: 'interest', label: 'Interest' },
];

const pictureUrl = (avatar?: string | null) => (avatar ? (avatar.startsWith('/') ? `${getApiUrl()}${avatar}` : avatar) : null);

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
  const [removing, setRemoving] = useState(false);
  const [removeError, setRemoveError] = useState('');
  const { confirm, dialog: confirmDialog } = useConfirm();
  const selfId = useAuthStore((s) => s.user?.id);
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
  const isSelf = !!person && person.userId === selfId;
  // Their account and their profile in the organization, read-only (the org's admins change it).
  const [profile, setProfile] = useState<MemberProfile | null>(null);
  const memberUserId = person?.userId;
  useEffect(() => {
    setProfile(null);
    if (!memberUserId) return;
    let cancelled = false;
    void authFetch(
      `/api/workspaces/${encodeURIComponent(workspaceId)}/members/${encodeURIComponent(memberUserId)}/profile`,
    )
      .then(async (response) => {
        if (response.ok && !cancelled) setProfile((await response.json()) as MemberProfile);
      })
      .catch(() => {
        // No profile: the header and the section show the account's name and email.
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId, memberUserId, nonce]);
  // Remove from workspace, at the top right as Remove from organization: asked first.
  const removeFromWorkspace = async () => {
    if (!leave || !person) return;
    const ok = await confirm({
      title: `Remove ${person.name || person.email || 'them'} from this workspace?`,
      description:
        'They leave it: its groups, their level and the policies attached to them here. Their account and their other workspaces stay.',
      confirmLabel: 'Remove from workspace',
    });
    if (!ok) return;
    setRemoveError('');
    setRemoving(true);
    try {
      await leave();
    } catch (e) {
      setRemoveError(e instanceof Error ? e.message : 'Could not remove them from the workspace.');
      setRemoving(false);
    }
  };
  const readOnly = (key: string, label: string, value: string) => (
    <div className="account-profile-field" key={key}>
      <label className="account-profile-field-label" htmlFor={`person-${key}`}>
        {label}
      </label>
      <input
        id={`person-${key}`}
        type="text"
        value={value}
        readOnly
        aria-readonly="true"
        className="account-profile-field-input account-profile-field-input-readonly"
      />
    </div>
  );
  if (!personId) return null;
  // The page alone: back to Users, then who it is about, and what they hold.
  return (
    <div className="access-instance-page">
      <PersonBack onClick={() => router.push(usersPath)} />
      <InstanceHeader
        name={profile?.name || person?.name || 'Loading…'}
        id={personId}
        meta={profile?.email || person?.email ? <span>{profile?.email || person?.email}</span> : undefined}
        // Their picture in the organization, else their account's, else their initial.
        avatar={(() => {
          const shownName = profile?.name || person?.name || '';
          const picture = pictureUrl(profile?.organization_profile?.avatar) ?? pictureUrl(profile?.avatar);
          return (
            <div className="account-profile-avatar-wrapper" data-member-avatar="">
              {picture ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={picture} alt={shownName} className="account-profile-avatar-image" />
              ) : (
                <div className="account-profile-avatar-placeholder">{(shownName || '?').charAt(0).toUpperCase()}</div>
              )}
            </div>
          );
        })()}
        actions={
          <>
            {person && <ViewAsControl personId={personId} name={person.name} workspaceId={scope?.workspaceId ?? null} />}
            <button
              type="button"
              onClick={() => void removeFromWorkspace()}
              disabled={!leave || isSelf || removing}
              className="org-member-detail-remove-button"
              title={
                isSelf
                  ? 'You cannot remove yourself'
                  : !managesMembers
                    ? 'Only the workspace’s admins remove someone from it'
                    : undefined
              }
              data-action="remove-from-workspace"
            >
              <Trash2 size={16} />
              {removing ? 'Removing...' : 'Remove from workspace'}
            </button>
          </>
        }
      />
      {removeError && (
        <Notice tone="error" icon={<AlertCircle size={14} />}>
          {removeError}
        </Notice>
      )}
      {/* Who they are, read-only: their account, then their profile in the organization (as its
          person page shows it, where its admins change it). */}
      <Card bodyClassName="space-y-6 p-4">
        <div className="account-profile-form-grid" data-person-info={personId} data-section="profile">
          {readOnly('name', 'Name', profile?.name || person?.name || '')}
          {readOnly('email', 'Email', profile?.email || person?.email || '')}
          {profile?.organization_profile &&
            PROFILE_ROWS.map(({ key, label }) => readOnly(key, label, profile.organization_profile?.[key] ?? ''))}
        </div>
        {profile?.organization_profile && (
          <div className="account-profile-field">
            <label className="account-profile-field-label" htmlFor="person-bio">
              Bio
            </label>
            <textarea
              id="person-bio"
              value={profile.organization_profile.bio ?? ''}
              rows={4}
              readOnly
              aria-readonly="true"
              className="account-profile-field-textarea account-profile-field-input-readonly"
            />
          </div>
        )}
      </Card>
      {/* Removing them is the header's button: the section lists what they hold. */}
      <MemberRoleSection
        scope={{ kind: 'workspace', id: workspaceId }}
        principalId={personId}
        nonce={nonce}
        onPerson={setPerson}
      />
      {confirmDialog}
    </div>
  );
}
