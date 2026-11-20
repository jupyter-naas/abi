'use client';

import './access-base.css';
import './access.css';

import { useMemo } from 'react';
import { AccessBadgeContext, AccessHeaderSlotContext } from './access-list';
import { createIamAdminApi, type IamAdminApi } from '@/lib/iam-admin/api';
import type { InviteProviders } from '@/lib/invitations';
import { useIamAccess } from '@/lib/iam-admin/use-access';
import { createAccessDirectory, type AccessDirectory } from './access-directory';
import type { AccessNavigation } from './access-props';
import type { AccessScope } from './access-scope';
import { accessSection, opensSection, type AccessSection } from './access-sections';
import { ApprovalsView } from './approvals/approvals';
import { AuditView } from './audit/audit';
import { GroupsView } from './groups/groups';
import { PoliciesView } from './policies/policies';
import { ServiceAccountsView } from './service-accounts/service-accounts';
import { SimulatorView } from './simulator/simulator';

/** Where a level's pages are: an Access page (with what it has open), and a person's page,
 *  null where the caller may open none. */
export type AccessHrefs = {
  page: (section: AccessSection, id?: string | null) => string;
  person: ((personId: string) => string) | null;
};

export type AccessPageProps = {
  section: AccessSection;
  /** The scopes this page manages, the first shown first: the platform; an organization and
   *  its workspaces; one workspace. */
  scopes: AccessScope[];
  /** The one picked (an index into ``scopes``), and told when another is. */
  picked?: number;
  onPick?: (index: number) => void;
  /** What the address has open: a policy's id (or `new`), a group's id. */
  focus?: string | null;
  hrefs: AccessHrefs;
  /** Opens a page of the app (the router's push; tests pass a fake). */
  navigate: (href: string) => void;
  /** Bumped by the page's refresh button. */
  nonce?: number;
  /** Tests pass fakes; the pages use the real API and member routes. */
  api?: IamAdminApi;
  directory?: AccessDirectory;
  loadProviders?: () => Promise<InviteProviders>;
  /** Where the page puts its own action (Create …): a slot in its level's page header. */
  headerSlot?: HTMLElement | null;
  /** Told the count badge of the list shown (null: none), for the page title. */
  onBadge?: (badge: string | null) => void;
};

/**
 * One page of Access (Policies, Groups, Service accounts, Module approvals, Simulator, Audit),
 * the scope as a parameter: the same components at every level. IAM says what the caller may
 * do at the scope (`GET /api/iam/admin/access?scope=`), and that alone decides whether the page
 * shows and its buttons. A policy's or a group's page has its own address (``hrefs.page`` with
 * its id); a name links to a person's page where the level has one the caller opens
 * (``hrefs.person``) and to a group's where its Groups page is shown.
 */
export function AccessPage({
  section,
  scopes,
  picked = 0,
  onPick,
  focus = null,
  hrefs,
  navigate,
  nonce = 0,
  api,
  directory,
  loadProviders,
  headerSlot = null,
  onBadge,
}: AccessPageProps) {
  const client = useMemo(() => api ?? createIamAdminApi(), [api]);
  const people = useMemo(() => directory ?? createAccessDirectory(), [directory]);
  const chosen = scopes[Math.min(picked, scopes.length - 1)];
  const chosenKey = JSON.stringify(chosen ?? null);
  // The page reloads on a change of scope, not on a new array of the same scopes.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const scope = useMemo(() => chosen, [chosenKey]);
  // Refresh asks IAM again too: a grant or a revoke made elsewhere changes the page.
  const { access, loading, error, can } = useIamAccess(scope?.value ?? undefined, client, { reload: nonce });

  const showsGroups = opensSection(access, 'groups');
  const open: AccessNavigation = useMemo(
    () => ({
      person: hrefs.person ? (id) => navigate(hrefs.person!(id)) : undefined,
      group: showsGroups ? (id) => navigate(hrefs.page('groups', id)) : undefined,
    }),
    [hrefs, navigate, showsGroups],
  );

  if (!scope) return null;

  const picker = scopes.length > 1 && (
    <label className="access-scope-picker">
      <span>Manage</span>
      <select
        className="access-input"
        aria-label="Scope"
        value={Math.min(picked, scopes.length - 1)}
        onChange={(e) => onPick?.(Number(e.target.value))}
      >
        {scopes.map((s, i) => (
          <option key={s.value ?? 'platform'} value={i}>
            {s.label}
          </option>
        ))}
      </select>
    </label>
  );

  const label = accessSection(section).label.toLowerCase();
  let body: React.ReactNode;
  if (loading) body = <p className="access-empty">Loading…</p>;
  else if (error) {
    body = (
      <p className="access-source-note" role="status">
        <strong>Access unavailable.</strong> {error}
      </p>
    );
  } else if (!opensSection(access, section)) {
    body = (
      <p className="access-empty" role="status" data-access-refused="">
        You cannot manage {label} here.
      </p>
    );
  } else {
    const props = { api: client, can, scope, directory: people, nonce, open };
    const views: Record<AccessSection, () => React.ReactNode> = {
      policies: () => (
        <PoliciesView {...props} focus={focus} onFocus={(id) => navigate(hrefs.page('policies', id))} />
      ),
      groups: () => (
        <GroupsView
          {...props}
          loadProviders={loadProviders}
          focus={focus}
          onFocus={(id) => navigate(hrefs.page('groups', id))}
        />
      ),
      'service-accounts': () => <ServiceAccountsView {...props} />,
      approvals: () => <ApprovalsView {...props} />,
      simulator: () => <SimulatorView {...props} />,
      audit: () => <AuditView {...props} />,
    };
    body = (
      <div className="access-body" key={`${scope.value ?? 'platform'}/${section}`}>
        {views[section]()}
      </div>
    );
  }

  return (
    <AccessBadgeContext.Provider value={onBadge ?? null}>
    <AccessHeaderSlotContext.Provider value={headerSlot}>
      <div className="access-tab" data-scope={scope.value ?? 'platform'} data-section={section}>
        {picker && <div className="access-header">{picker}</div>}
        {body}
      </div>
    </AccessHeaderSlotContext.Provider>
    </AccessBadgeContext.Provider>
  );
}
