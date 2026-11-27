'use client';

/**
 * Settings › Access › Features: which features a policy of the workspace allows, "<W> access" (its
 * offer) by default, laid out as Settings › Users. The policy edited is kept in the URL (`?policy=`).
 * Files are Settings › Files.
 */
import { Suspense } from 'react';
import { useParams, usePathname, useRouter, useSearchParams } from 'next/navigation';
import { Loading } from '@/components/ui/spinner';
import { FeatureAccess } from './feature-access';
// The choices and notes of a row.
import '../general/general.css';
// The table of Settings › Users: columns that sort and filter.
import '@/app/organizations/[orgId]/settings/users/users.css';

function Features() {
  const workspaceId = useParams().workspaceId as string;
  const router = useRouter();
  const pathname = usePathname();
  const policy = useSearchParams().get('policy');
  return (
    <FeatureAccess
      key={workspaceId}
      workspaceId={workspaceId}
      initialPolicy={policy}
      onPolicyChange={(next) => router.replace(next ? `${pathname}?policy=${encodeURIComponent(next)}` : pathname)}
    />
  );
}

export default function FeaturesSettingsPage() {
  return (
    <Suspense fallback={<Loading label="Loading features…" />}>
      <Features />
    </Suspense>
  );
}
