'use client';

import { useEffect, useMemo, useState } from 'react';
import { createIamAdminApi, IamAdminError } from '@/lib/iam-admin/api';
import type { AccessView } from '@/lib/iam-admin/types';
import { ACCESS_SECTIONS, canDo, parseAccessSection, type AccessSection } from './access-sections';
import { ApprovalsView } from './approvals/approvals';
import { AttachmentsView } from './attachments/attachments';
import { AuditView } from './audit/audit';
import { GroupsView } from './groups/groups';
import { PoliciesView } from './policies/policies';
import { ServiceAccountsView } from './service-accounts/service-accounts';
import { SimulatorView } from './simulator/simulator';
import { SourceNote } from '../system-ui';

/** The platform's permissions: policies, who holds them, groups, service accounts, the
 *  approvals modules wait for, the simulator and the audit of every change. IAM decides what
 *  the signed-in user may open; sections they may not use are not shown. */
export function AccessTab({ nonce = 0 }: { nonce?: number }) {
  const api = useMemo(() => createIamAdminApi(), []);
  const [access, setAccess] = useState<AccessView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [section, setSection] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .access()
      .then((view) => !cancelled && (setAccess(view), setError(null)))
      .catch((e: unknown) => !cancelled && setError(e instanceof IamAdminError ? e.message : String(e)));
    return () => {
      cancelled = true;
    };
  }, [api, nonce]);

  if (error) return <SourceNote label="Access" reason={error} />;
  if (!access) return <p className="system-empty">Loading…</p>;

  const open = parseAccessSection(section, access);
  const sections = ACCESS_SECTIONS.filter((s) => canDo(access, s.needs));
  if (open === null) {
    return <p className="system-empty">Your role does not let you manage permissions.</p>;
  }
  const props = { api, can: (action: string) => canDo(access, action), nonce };
  const views: Record<AccessSection, React.ReactNode> = {
    policies: <PoliciesView {...props} />,
    attachments: <AttachmentsView {...props} />,
    groups: <GroupsView {...props} />,
    'service-accounts': <ServiceAccountsView {...props} />,
    approvals: <ApprovalsView {...props} />,
    simulator: <SimulatorView {...props} />,
    audit: <AuditView {...props} />,
  };
  return (
    <div className="access-tab">
      <nav className="access-subnav" aria-label="Access views">
        {sections.map((s) => (
          <button
            key={s.id}
            type="button"
            className={s.id === open ? 'access-subtab access-subtab-active' : 'access-subtab'}
            aria-current={s.id === open ? 'page' : undefined}
            onClick={() => setSection(s.id)}
          >
            {s.label}
          </button>
        ))}
      </nav>
      <div className="access-body">{views[open]}</div>
    </div>
  );
}
