'use client';

import './access-base.css';
import './access.css';

import { useMemo, useState } from 'react';
import { createIamAdminApi, type IamAdminApi } from '@/lib/iam-admin/api';
import type { InviteProviders } from '@/lib/invitations';
import { useIamAccess } from '@/lib/iam-admin/use-access';
import { createAccessDirectory, type AccessDirectory } from './access-directory';
import type { AccessScope } from './access-scope';
import { parseAccessSection, visibleSections, type AccessSection } from './access-sections';
import { ApprovalsView } from './approvals/approvals';
import { AuditView } from './audit/audit';
import { GroupsView } from './groups/groups';
import { PeopleView } from './people/people';
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
};

/**
 * Roles & permissions: the same components at every level, the scope as a parameter. IAM
 * says what the caller may do at the scope (`GET /api/iam/admin/access?scope=`) and that
 * alone decides the sections and buttons: People & roles, Groups, Policies, and what the
 * platform administers (service accounts, module approvals, the simulator, the audit). A caller who may do nothing there sees no section.
 */
export function RolesAndPermissions({ scopes, nonce = 0, api, directory, loadProviders }: RolesAndPermissionsProps) {
  const client = useMemo(() => api ?? createIamAdminApi(), [api]);
  const people = useMemo(() => directory ?? createAccessDirectory(), [directory]);
  const [index, setIndex] = useState(0);
  const [section, setSection] = useState<string | null>(null);
  const picked = scopes[Math.min(index, scopes.length - 1)];
  const pickedKey = JSON.stringify(picked ?? null);
  // The sections reload on a change of scope, not on a new array of the same scopes.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const scope = useMemo(() => picked, [pickedKey]);
  // Refresh asks IAM again too: a grant or a revoke made elsewhere changes the sections.
  const { access, loading, error, can } = useIamAccess(scope?.value ?? undefined, client, { reload: nonce });

  if (!scope) return null;

  const picker = scopes.length > 1 && (
    <label className="access-scope-picker">
      <span>Manage</span>
      <select className="access-input" aria-label="Scope" value={index} onChange={(e) => setIndex(Number(e.target.value))}>
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
    const props = { api: client, can, scope, directory: people, nonce };
    const views: Record<AccessSection, React.ReactNode> = {
      people: <PeopleView {...props} />,
      groups: <GroupsView {...props} loadProviders={loadProviders} />,
      policies: <PoliciesView {...props} />,
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
              onClick={() => setSection(s.id)}
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
