'use client';

/**
 * Platform settings › Access › Features, Services and Modules: an organization's own page (on its
 * "<O> access", `org:<id>`), the organization picked atop it (`?org=`, the first one the caller
 * opens by default). The platform has no offer of its own above the organizations: these pages
 * are the way to every organization's from Platform settings.
 */
import { Suspense, type ReactNode } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { SettingsEmpty, SettingsLoading } from '@/components/settings/settings-ui';
import { useOpenableOrganizations } from '@/hooks/use-openable-organizations';
import { orgTarget } from '@/lib/access-model/target';
import '@/app/organizations/[orgId]/settings/components/org-settings-components.css';
// The choices and notes of a row (Workspace › General's CSS) and the table of Users.
import '@/app/workspace/[workspaceId]/settings/general/general.css';
import '@/app/organizations/[orgId]/settings/users/users.css';

export type OrganizationPage = (props: {
  target: string;
  initialPolicy: string | null;
  onPolicyChange: (policyId: string | null) => void;
}) => ReactNode;

function Picked({ render }: { render: OrganizationPage }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const { status, orgs } = useOpenableOrganizations();
  if (status !== 'ready') return <SettingsLoading label="Loading organizations…" />;
  if (orgs.length === 0) return <SettingsEmpty title="No organization to open." />;
  const asked = params.get('org');
  const orgId = orgs.some((o) => o.id === asked) ? (asked as string) : orgs[0].id;
  const policy = params.get('policy');
  const go = (org: string, nextPolicy: string | null) => {
    const query = new URLSearchParams({ org });
    if (nextPolicy) query.set('policy', nextPolicy);
    router.replace(`${pathname}?${query.toString()}`);
  };
  return (
    <div className="space-y-4">
      <label className="flex max-w-sm flex-col gap-2" data-organization-picker="">
        <span className="org-settings-field-label">Organization</span>
        <select
          className="org-settings-input"
          value={orgId}
          onChange={(event) => go(event.target.value, null)}
          aria-label="Organization"
        >
          {orgs.map((o) => (
            <option key={o.id} value={o.id}>
              {o.name}
            </option>
          ))}
        </select>
      </label>
      <div key={orgId}>
        {render({
          target: orgTarget(orgId),
          initialPolicy: policy,
          onPolicyChange: (next) => go(orgId, next),
        })}
      </div>
    </div>
  );
}

export function OrganizationOffer({ render }: { render: OrganizationPage }) {
  return (
    <Suspense fallback={<SettingsLoading label="Loading…" />}>
      <Picked render={render} />
    </Suspense>
  );
}
