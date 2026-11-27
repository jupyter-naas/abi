'use client';

/**
 * Organization › Access › Services: the workspace page's own component on "<O> access" (`org:<id>`),
 * the ceiling of every workspace of the organization, or another policy it owns (`?policy=`).
 */
import { Suspense } from 'react';
import { useParams, usePathname, useRouter, useSearchParams } from 'next/navigation';
import { Loading } from '@/components/ui/spinner';
import { orgTarget } from '@/lib/access-model/target';
import { CoreServices } from '@/app/workspace/[workspaceId]/settings/core-services/core-services';
// The choices and notes of a row (Workspace › General's CSS) and the table of Users.
import '@/app/workspace/[workspaceId]/settings/general/general.css';
import '@/app/organizations/[orgId]/settings/users/users.css';

function Page() {
  const orgId = useParams().orgId as string;
  const router = useRouter();
  const pathname = usePathname();
  const policy = useSearchParams().get('policy');
  return (
    <CoreServices
      key={orgId}
      workspaceId={orgTarget(orgId)}
      initialPolicy={policy}
      onPolicyChange={(next) => router.replace(next ? `${pathname}?policy=${encodeURIComponent(next)}` : pathname)}
    />
  );
}

export default function OrgServicesPage() {
  return (
    <Suspense fallback={<Loading label="Loading…" />}>
      <Page />
    </Suspense>
  );
}
