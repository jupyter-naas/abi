'use client';

/**
 * Platform settings › Access › Features, Services and Modules: an organization's own page (on its
 * "<O> access", `org:<id>`), the organization picked before its Policy dropdown, in the same row
 * and style (`?org=`, the first one the caller opens by default). The platform has no offer of its own above the organizations: these pages
 * are the way to every organization's from Platform settings.
 */
import { Suspense, type ReactNode } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { EmptyState } from '@/components/ui/empty-state';
import { Loading } from '@/components/ui/spinner';
import { useOpenableOrganizations } from '@/hooks/use-openable-organizations';
import { orgTarget } from '@/lib/access-model/target';
import { PICKER_LABEL_CLASS, PICKER_SELECT_CLASS } from '@/components/settings/policy-picker';
import '@/app/organizations/[orgId]/settings/components/org-settings-components.css';
// The choices and notes of a row (Workspace › General's CSS) and the table of Users.
import '@/app/workspace/[workspaceId]/settings/general/general.css';
import '@/app/organizations/[orgId]/settings/users/users.css';

export type OrganizationPage = (props: {
  target: string;
  initialPolicy: string | null;
  onPolicyChange: (policyId: string | null) => void;
  /** The Organization picker, for the page to put before its Policy dropdown, in its row. */
  pickerPrefix: ReactNode;
}) => ReactNode;

function Picked({ render }: { render: OrganizationPage }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const { status, orgs } = useOpenableOrganizations();
  if (status !== 'ready') return <Loading label="Loading organizations…" />;
  if (orgs.length === 0) return <EmptyState framed title="No organization to open." />;
  const asked = params.get('org');
  const orgId = orgs.some((o) => o.id === asked) ? (asked as string) : orgs[0].id;
  const policy = params.get('policy');
  const go = (org: string, nextPolicy: string | null) => {
    const query = new URLSearchParams({ org });
    if (nextPolicy) query.set('policy', nextPolicy);
    router.replace(`${pathname}?${query.toString()}`);
  };
  const picker = (
    <label className={PICKER_LABEL_CLASS} data-organization-picker="">
      <span className="text-muted-foreground">Organization</span>
      <select
        className={PICKER_SELECT_CLASS}
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
  );
  return (
    <div key={orgId}>
      {render({
        target: orgTarget(orgId),
        initialPolicy: policy,
        onPolicyChange: (next) => go(orgId, next),
        pickerPrefix: picker,
      })}
    </div>
  );
}

export function OrganizationOffer({ render }: { render: OrganizationPage }) {
  return (
    <Suspense fallback={<Loading label="Loading…" />}>
      <Picked render={render} />
    </Suspense>
  );
}
