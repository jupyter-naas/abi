'use client';

import './access-base.css';
import './access.css';

import { useEffect, useMemo, useState } from 'react';
import { createIamAdminApi, type IamAdminApi } from '@/lib/iam-admin/api';
import type { InviteProviders } from '@/lib/invitations';
import { useIamAccess } from '@/lib/iam-admin/use-access';
import { createAccessDirectory, type AccessDirectory } from './access-directory';
import type { AccessNavigation } from './access-props';
import type { AccessScope } from './access-scope';
import { parseAccessSection, visibleSections, type AccessSection } from './access-sections';
import { ApprovalsView } from './approvals/approvals';
import { AuditView } from './audit/audit';
import { GroupsView } from './groups/groups';
import { PeopleView, type PersonFocus } from './people/people';
import type { BuiltInRole, RoleTarget } from './roles/role-change';
import { PoliciesView } from './policies/policies';
import { ServiceAccountsView } from './service-accounts/service-accounts';
import { SimulatorView } from './simulator/simulator';

export type RolesAndPermissionsProps = {
  /** The scopes this page manages, the first shown first: the platform; an organization and
   *  its workspaces; one workspace. */
  scopes: AccessScope[];
  /** Bumped by the page's refresh button. */
  nonce?: number;
  /** Tests pass fakes; the pages use the real API and member routes. */
  api?: IamAdminApi;
  directory?: AccessDirectory;
  loadProviders?: () => Promise<InviteProviders>;
  /** Changes a member's role (tests pass a fake); the membership routes by default. */
  changeRole?: (target: RoleTarget, userId: string, role: BuiltInRole) => Promise<void>;
};

/**
 * Roles & permissions: the same components at every level, the scope as a parameter. IAM
 * says what the caller may do at the scope (`GET /api/iam/admin/access?scope=`) and that
 * alone decides the sections and buttons: People & roles, Groups, Policies, and what the
 * platform administers (service accounts, module approvals, the simulator, the audit). A caller who may do nothing there sees no section.
 * The page's address may name a section and a policy to open (`?section=policies&policy=<id>`:
 * a link from another level's Policies, ``policy-owners.ownerHref``), a person's page
 * (`?section=people&person=<id>`) or a group's (`?section=groups&group=<id>`). A person's and a
 * group's page show what IAM lets the caller list at every level, whatever the page's own; the
 * sections link to them, and the address follows, so a page can be shared.
 */
export function RolesAndPermissions({ scopes, nonce = 0, api, directory, loadProviders, changeRole }: RolesAndPermissionsProps) {
  const client = useMemo(() => api ?? createIamAdminApi(), [api]);
  const people = useMemo(() => directory ?? createAccessDirectory(), [directory]);
  const [index, setIndex] = useState(0);
  const [section, setSection] = useState<string | null>(null);
  const [linkedPolicy, setLinkedPolicy] = useState<string | null>(null);
  const [person, setPerson] = useState<PersonFocus | null>(null);
  const [group, setGroup] = useState<string | null>(null);
  // Read after the first render, so the server's render and the browser's agree.
  useEffect(() => {
    const query = new URLSearchParams(window.location.search);
    const named = query.get('section');
    if (named) setSection(named);
    setLinkedPolicy(query.get('policy'));
    const personId = query.get('person');
    if (personId) setPerson({ id: personId });
    setGroup(query.get('group'));
  }, []);
  const picked = scopes[Math.min(index, scopes.length - 1)];
  const pickedKey = JSON.stringify(picked ?? null);
  // The sections reload on a change of scope, not on a new array of the same scopes.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const scope = useMemo(() => picked, [pickedKey]);
  // Refresh asks IAM again too: a grant or a revoke made elsewhere changes the sections.
  const { access, loading, error, can } = useIamAccess(scope?.value ?? undefined, client, { reload: nonce });

  // A person's or a group's page opens in its section: a name links to it only where the
  // caller is shown that section here (People & roles, Groups).
  const shown = visibleSections(access).map((s) => s.id);
  const showsPeople = shown.includes('people');
  const showsGroups = shown.includes('groups');
  const navigate: AccessNavigation = useMemo(
    () => ({
      person: showsPeople
        ? (id, label) => {
            setPerson({ id, label });
            setGroup(null);
            setLinkedPolicy(null);
            setSection('people');
            writeAddress({ section: 'people', person: id, group: null, policy: null });
          }
        : undefined,
      group: showsGroups
        ? (id) => {
            setGroup(id);
            setPerson(null);
            setLinkedPolicy(null);
            setSection('groups');
            writeAddress({ section: 'groups', group: id, person: null, policy: null });
          }
        : undefined,
    }),
    [showsPeople, showsGroups],
  );
  /** Leave whatever page is open (a person, a group, a linked policy): another section or
   *  another scope shows its own list. */
  const closePages = (changes: Record<string, string | null> = {}) => {
    setPerson(null);
    setGroup(null);
    setLinkedPolicy(null);
    writeAddress({ person: null, group: null, policy: null, ...changes });
  };

  if (!scope) return null;

  const picker = scopes.length > 1 && (
    <label className="access-scope-picker">
      <span>Manage</span>
      <select className="access-input" aria-label="Scope" value={index} onChange={(e) => {
          setIndex(Number(e.target.value));
          // The pages open were judged at the scope left: none stays open at the next one.
          closePages();
        }}>
        {scopes.map((s, i) => (
          <option key={s.value ?? 'platform'} value={i}>
            {s.label}
          </option>
        ))}
      </select>
    </label>
  );

  let body: React.ReactNode;
  const open = parseAccessSection(section, access);
  if (loading) body = <p className="access-empty">Loading…</p>;
  else if (error) {
    body = (
      <p className="access-source-note" role="status">
        <strong>Roles &amp; permissions unavailable.</strong> {error}
      </p>
    );
  } else if (open === null) {
    body = (
      <p className="access-empty" role="status">
        You cannot manage roles or permissions here.
      </p>
    );
  } else {
    const props = { api: client, can, scope, directory: people, nonce, open: navigate };
    const views: Record<AccessSection, React.ReactNode> = {
      people: (
        <PeopleView
          {...props}
          {...(changeRole ? { changeRole } : {})}
          person={person}
          onClosePerson={() => {
            setPerson(null);
            writeAddress({ person: null });
          }}
        />
      ),
      groups: (
        <GroupsView
          {...props}
          loadProviders={loadProviders}
          focus={group}
          onFocus={(id) => {
            setGroup(id);
            writeAddress({ group: id });
          }}
        />
      ),
      policies: <PoliciesView {...props} openPolicy={linkedPolicy} />,
      'service-accounts': <ServiceAccountsView {...props} />,
      approvals: <ApprovalsView {...props} />,
      simulator: <SimulatorView {...props} />,
      audit: <AuditView {...props} />,
    };
    body = (
      <>
        <nav className="access-subnav" aria-label="Roles and permissions sections">
          {visibleSections(access).map((s) => (
            <button
              key={s.id}
              type="button"
              className={s.id === open ? 'access-subtab access-subtab-active' : 'access-subtab'}
              aria-current={s.id === open ? 'page' : undefined}
              data-section={s.id}
              onClick={() => {
                setSection(s.id);
                closePages({ section: s.id });
              }}
            >
              {s.label}
            </button>
          ))}
        </nav>
        <div className="access-body" key={`${scope.value ?? 'platform'}/${open}`}>
          {views[open]}
        </div>
      </>
    );
  }

  return (
    <div className="access-tab" data-scope={scope.value ?? 'platform'}>
      {picker && <div className="access-header">{picker}</div>}
      {body}
    </div>
  );
}

/** The page's address, its query changed in place (null removes a key): what is open can be
 *  shared and survives a reload. */
function writeAddress(changes: Record<string, string | null>) {
  if (typeof window === 'undefined') return;
  const url = new URL(window.location.href);
  for (const [key, value] of Object.entries(changes)) {
    if (value) url.searchParams.set(key, value);
    else url.searchParams.delete(key);
  }
  window.history.replaceState(window.history.state, '', `${url.pathname}${url.search}${url.hash}`);
}
