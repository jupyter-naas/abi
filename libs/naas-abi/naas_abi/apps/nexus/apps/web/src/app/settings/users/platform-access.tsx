'use client';

import { useEffect, useState } from 'react';
import { ShieldCheck } from 'lucide-react';
import { PLATFORM_ACCESS_LABEL } from '@/components/access/builtins';
import { LEVEL_LABELS } from '@/lib/people';
import { OrgSettingsSectionCard } from '@/app/organizations/[orgId]/settings/components/org-settings-section-card';
import { listUsers, userAccess, type Fetcher } from './users-api';
import type { UserAccess } from './users-model';

type Loaded = { state: 'loading' } | { state: 'error'; error: string } | { state: 'ready'; access: UserAccess };

/**
 * Platform › Users › a person: "Platform access (automatic)", what their groups give them
 * (organizations, workspaces, level, capability groups, platform admin). Nothing to edit here:
 * an organization's Users page changes it. `personId` is their IAM id or their account id.
 */
export function PlatformAccess({ personId, nonce = 0, fetcher }: { personId: string; nonce?: number; fetcher?: Fetcher }) {
  const [loaded, setLoaded] = useState<Loaded>({ state: 'loading' });

  useEffect(() => {
    let live = true;
    setLoaded({ state: 'loading' });
    void (async () => {
      const users = await listUsers(fetcher);
      if (!live) return;
      if (!users.ok) return setLoaded({ state: 'error', error: users.error });
      const user = users.data.find((u) => u.principal_id === personId || u.id === personId);
      if (!user) return setLoaded({ state: 'error', error: 'They have no account yet.' });
      const answer = await userAccess(user.id, fetcher);
      if (!live) return;
      setLoaded(answer.ok ? { state: 'ready', access: answer.data } : { state: 'error', error: answer.error });
    })();
    return () => {
      live = false;
    };
  }, [personId, nonce, fetcher]);

  return (
    <OrgSettingsSectionCard padded>
      <div className="org-settings-card-heading" data-section="platform-access">
        <ShieldCheck size={20} />
        <h3 className="org-settings-card-heading-title">{PLATFORM_ACCESS_LABEL}</h3>
      </div>
      {loaded.state === 'loading' && <p className="org-settings-field-hint">Loading…</p>}
      {loaded.state === 'error' && (
        <p className="org-settings-field-hint" role="alert">
          {loaded.error}
        </p>
      )}
      {loaded.state === 'ready' && <AccessSummary access={loaded.access} />}
    </OrgSettingsSectionCard>
  );
}

function AccessSummary({ access }: { access: UserAccess }) {
  const names = (items: { name: string; admin?: boolean }[]) =>
    items.length ? items.map((i) => (i.admin ? `${i.name} (admin)` : i.name)).join(', ') : 'None';
  const rows: [string, string, string][] = [
    ['platform-admin', 'Platform admin', access.platform_admin ? 'Yes' : 'No'],
    ['level', 'Level', access.level ? LEVEL_LABELS[access.level] : 'None'],
    ['organizations', 'Organizations', names(access.organizations.map((o) => ({ name: o.name, admin: o.org_admin })))],
    ['workspaces', 'Workspaces', names(access.workspaces)],
    ['capabilities', 'Capabilities', names(access.capabilities)],
  ];
  return (
    <dl className="platform-access-summary">
      {rows.map(([field, label, value]) => (
        <div key={field} data-field={field}>
          <dt className="org-settings-field-label">{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}
